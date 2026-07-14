// ============================================================================
// NOTIFICATION BELL
// Bounded initial load plus delta polling. One visible tab per user/tenant
// becomes the polling leader; follower tabs receive updates through
// BroadcastChannel/localStorage.
// ============================================================================

var _notifPollTimer = null
var _notifLeaseTimer = null
var _notifOpen = false
var _notifData = []
var _notifUnreadCount = 0
var _notifCursor = 0
var _notifInFlight = false
var _notifBackoffMs = 60000
var _notifLastContext = ''
var _notifTabId = 'ntf-' + Date.now() + '-' + Math.random().toString(36).slice(2)
var _notifChannel = null

var _NOTIF_BASE_INTERVAL_MS = 60000
var _NOTIF_MAX_BACKOFF_MS = 300000
var _NOTIF_LEASE_MS = 90000
var _NOTIF_LEASE_RENEW_MS = 20000
var _NOTIF_LIMIT = 20

function initNotifBell() {
  const wrapper = document.getElementById('notifBellWrapper')
  if (!wrapper) return

  wrapper.style.display = 'block'
  _notifResetForContext()
  _renderBell()
  _notifSetupChannel()
  _notifSyncNow(true)
  _notifStartTimers()

  document.addEventListener('click', _notifOutsideClick, true)
  document.addEventListener('visibilitychange', _notifVisibilityChanged)
  window.addEventListener('storage', _notifStorageChanged)
}

function destroyNotifBell() {
  if (_notifPollTimer) { clearInterval(_notifPollTimer); _notifPollTimer = null }
  if (_notifLeaseTimer) { clearInterval(_notifLeaseTimer); _notifLeaseTimer = null }
  document.removeEventListener('click', _notifOutsideClick, true)
  document.removeEventListener('visibilitychange', _notifVisibilityChanged)
  window.removeEventListener('storage', _notifStorageChanged)
  if (_notifChannel) { try { _notifChannel.close() } catch (e) {} }
  _notifChannel = null
  _notifReleaseLeadership()
  _notifData = []
  _notifUnreadCount = 0
  _notifCursor = 0
  _notifOpen = false
  const wrapper = document.getElementById('notifBellWrapper')
  if (wrapper) wrapper.style.display = 'none'
}

function _notifContextKey() {
  var tenant = ''
  if (typeof currentTenant !== 'undefined' && currentTenant) tenant = currentTenant.slug || currentTenant.id || ''
  if (!tenant && typeof authGetTenantSlug === 'function') tenant = authGetTenantSlug() || ''
  var userId = ''
  if (typeof currentUser !== 'undefined' && currentUser) userId = currentUser.id || currentUser.email || ''
  if (!userId && typeof user !== 'undefined' && user) userId = user.id || user.email || ''
  return String(tenant || 'global') + ':' + String(userId || 'anonymous')
}

function _notifLeaseKey() {
  return 'sm:notif:leader:' + _notifContextKey()
}

function _notifResetForContext() {
  var ctx = _notifContextKey()
  if (_notifLastContext === ctx) return
  _notifReleaseLeadership()
  _notifData = []
  _notifUnreadCount = 0
  _notifCursor = 0
  _notifBackoffMs = _NOTIF_BASE_INTERVAL_MS
  _notifLastContext = ctx
}

function _notifSetupChannel() {
  if (_notifChannel || !('BroadcastChannel' in window)) return
  try {
    _notifChannel = new BroadcastChannel('sm-notifications')
    _notifChannel.onmessage = function (event) {
      _notifHandlePeerMessage(event.data || {})
    }
  } catch (e) {
    _notifChannel = null
  }
}

function _notifStartTimers() {
  if (_notifPollTimer) clearInterval(_notifPollTimer)
  if (_notifLeaseTimer) clearInterval(_notifLeaseTimer)
  _notifPollTimer = setInterval(function () { _notifSyncNow(false) }, _NOTIF_BASE_INTERVAL_MS)
  _notifLeaseTimer = setInterval(_notifMaintainLease, _NOTIF_LEASE_RENEW_MS)
  _notifMaintainLease()
}

function _notifCanPoll() {
  if (!token) return false
  if (document.visibilityState && document.visibilityState !== 'visible') return false
  return _notifIsLeader()
}

function _notifIsLeader() {
  var now = Date.now()
  var key = _notifLeaseKey()
  var lease = null
  try { lease = JSON.parse(localStorage.getItem(key) || 'null') } catch (e) {}
  if (!lease || lease.expiresAt < now || lease.tabId === _notifTabId) {
    try {
      localStorage.setItem(key, JSON.stringify({
        tabId: _notifTabId,
        context: _notifContextKey(),
        expiresAt: now + _NOTIF_LEASE_MS
      }))
      return true
    } catch (e) {
      return true
    }
  }
  return false
}

function _notifMaintainLease() {
  _notifResetForContext()
  if (!token || (document.visibilityState && document.visibilityState !== 'visible')) {
    _notifReleaseLeadership()
    return
  }
  _notifIsLeader()
}

function _notifReleaseLeadership() {
  try {
    var key = _notifLeaseKey()
    var lease = JSON.parse(localStorage.getItem(key) || 'null')
    if (lease && lease.tabId === _notifTabId) localStorage.removeItem(key)
  } catch (e) {}
}

function _notifVisibilityChanged() {
  if (document.visibilityState === 'visible') {
    _notifMaintainLease()
    _notifSyncNow(false)
  } else {
    _notifReleaseLeadership()
  }
}

function _notifStorageChanged(event) {
  if (!event || event.key !== _notifLeaseKey()) return
  if (document.visibilityState === 'visible') _notifMaintainLease()
}

function _notifBroadcast(payload) {
  payload = payload || {}
  payload.context = _notifContextKey()
  payload.from = _notifTabId
  if (_notifChannel) {
    try { _notifChannel.postMessage(payload) } catch (e) {}
  }
  try { localStorage.setItem('sm:notif:last:' + payload.context, JSON.stringify(payload)) } catch (e) {}
}

function _notifHandlePeerMessage(payload) {
  if (!payload || payload.from === _notifTabId || payload.context !== _notifContextKey()) return
  if (payload.type === 'sync') {
    _notifApplyServerData(payload.data || {})
  } else if (payload.type === 'mark-read') {
    _notifApplyMarkRead(payload.ids || null)
  }
}

async function _notifSyncNow(initial) {
  _notifResetForContext()
  if (!_notifCanPoll() || _notifInFlight) return
  _notifInFlight = true
  try {
    var qs = initial || !_notifCursor
      ? '?mode=history&unread_only=1&limit=' + _NOTIF_LIMIT
      : '?after_id=' + encodeURIComponent(_notifCursor) + '&limit=' + _NOTIF_LIMIT
    const res = await fetch(API_BASE + '/leads/notifications' + qs, {
      headers: { Authorization: 'Bearer ' + token }
    })
    if (!res.ok) throw new Error('notification poll failed')
    const data = await res.json()
    _notifApplyServerData(data)
    _notifBroadcast({ type: 'sync', data: data })
    _notifBackoffMs = _NOTIF_BASE_INTERVAL_MS
  } catch (e) {
    _notifBackoffMs = Math.min(_NOTIF_MAX_BACKOFF_MS, Math.max(_NOTIF_BASE_INTERVAL_MS, _notifBackoffMs * 2))
    if (_notifPollTimer) {
      clearInterval(_notifPollTimer)
      _notifPollTimer = setInterval(function () { _notifSyncNow(false) }, _notifBackoffMs)
    }
  } finally {
    _notifInFlight = false
  }
}

function _notifApplyServerData(data) {
  var incoming = Array.isArray(data.notifications) ? data.notifications : []
  if ((data.mode || '') === 'history' && !_notifCursor) {
    _notifData = incoming.filter(function (n) { return !n.is_read })
  } else {
    incoming.forEach(function (n) {
      if (n.is_read) {
        _notifData = _notifData.filter(function (row) { return row.id !== n.id })
      } else if (!_notifData.some(function (row) { return row.id === n.id })) {
        _notifData.push(n)
      }
    })
  }
  _notifData.sort(function (a, b) { return Number(b.id || 0) - Number(a.id || 0) })
  _notifData = _notifData.slice(0, _NOTIF_LIMIT)
  _notifUnreadCount = typeof data.unread_count === 'number' ? data.unread_count : _notifData.length
  if (typeof data.cursor === 'number') _notifCursor = Math.max(_notifCursor, data.cursor)
  _renderBell()
  if (_notifOpen) _openNotifDropdown()
}

function _notifApplyMarkRead(ids) {
  if (Array.isArray(ids) && ids.length) {
    var idMap = {}
    ids.forEach(function (id) { idMap[Number(id)] = true })
    _notifData = _notifData.filter(function (n) { return !idMap[Number(n.id)] })
  } else {
    _notifData = []
  }
  _notifUnreadCount = _notifData.length
  _renderBell()
}

function _renderBell() {
  const wrapper = document.getElementById('notifBellWrapper')
  if (!wrapper) return
  const count = _notifUnreadCount || _notifData.length
  const badgeHTML = count > 0
    ? '<span class="notif-badge">' + (count > 99 ? '99+' : count) + '</span>'
    : ''
  wrapper.innerHTML =
    '<div class="notif-bell-container">' +
      '<button id="notifBellBtn" class="notif-bell-btn" aria-label="Notifications" title="Notifications">' +
        '<svg viewBox="0 0 32 34" width="26" height="26" xmlns="http://www.w3.org/2000/svg">' +
          '<path d="M16 3 C10.5 3 6 7.5 6 13 C6 19.5 3 22 2.5 23 L29.5 23 C29 22 26 19.5 26 13 C26 7.5 21.5 3 16 3 Z" fill="#ef4444" stroke="#1e1b4b" stroke-width="1.6" stroke-linejoin="round"/>' +
          '<path d="M9.5 9.5 Q10.5 7 13 6" fill="none" stroke="rgba(255,255,255,0.65)" stroke-width="1.6" stroke-linecap="round"/>' +
          '<rect x="2" y="22.2" width="28" height="3" rx="1.5" fill="#fbbf24" stroke="#1e1b4b" stroke-width="1.4"/>' +
          '<circle cx="16" cy="28.5" r="2.2" fill="#fbbf24" stroke="#1e1b4b" stroke-width="1.4"/>' +
          '<path d="M14.2 3.5 Q16 1.5 17.8 3.5" fill="none" stroke="#1e1b4b" stroke-width="1.5" stroke-linecap="round"/>' +
        '</svg>' +
        badgeHTML +
      '</button>' +
      '<div id="notifDropdown" class="notif-dropdown" style="display:none;">' +
        '<div class="notif-dropdown-header">' +
          '<span>Notifications</span>' +
          (count > 0 ? '<button id="markAllReadBtn" class="notif-mark-read-btn">Mark all read</button>' : '') +
        '</div>' +
        '<div id="notifList" class="notif-list">' + _renderNotifItems() + '</div>' +
      '</div>' +
    '</div>'

  document.getElementById('notifBellBtn').addEventListener('click', function (e) {
    e.stopPropagation()
    _toggleNotifDropdown()
  })
  const markBtn = document.getElementById('markAllReadBtn')
  if (markBtn) markBtn.addEventListener('click', function (e) {
    e.stopPropagation()
    _markAllRead()
  })
}

function _renderNotifItems() {
  if (_notifData.length === 0) return '<div class="notif-empty">No new notifications</div>'
  return _notifData.map(function (n) {
    var href = n.action_url || (n.lead_id ? _notifLeadUrl(n.lead_id) : '')
    var attrs = href ? ' role="button" tabindex="0" data-href="' + _notifEsc(href) + '"' : ''
    return '<div class="notif-item notif-item--' + _notifEsc(n.kind || 'info') + '"' + attrs + '>' +
      '<div class="notif-item-title">' + _notifEsc(n.title || 'Notification') + '</div>' +
      '<div class="notif-item-msg">' + _notifEsc(n.message || '') + '</div>' +
      '<div class="notif-item-time">' + _notifFmtTime(n.created_at) + '</div>' +
    '</div>'
  }).join('')
}

function _toggleNotifDropdown() {
  if (_notifOpen) _closeNotifDropdown()
  else _openNotifDropdown()
}

function _openNotifDropdown() {
  const dropdown = document.getElementById('notifDropdown')
  if (!dropdown) return
  dropdown.style.display = 'block'
  _notifOpen = true
  Array.prototype.forEach.call(dropdown.querySelectorAll('[data-href]'), function (el) {
    el.onclick = function () {
      var href = el.getAttribute('data-href')
      if (href) {
        history.pushState({}, '', href)
        window.dispatchEvent(new PopStateEvent('popstate'))
      }
    }
  })
}

function _closeNotifDropdown() {
  const dropdown = document.getElementById('notifDropdown')
  if (dropdown) dropdown.style.display = 'none'
  _notifOpen = false
}

function _notifOutsideClick(e) {
  const wrapper = document.getElementById('notifBellWrapper')
  if (_notifOpen && wrapper && !wrapper.contains(e.target)) _closeNotifDropdown()
}

async function _pollNotifications() {
  return _notifSyncNow(false)
}

async function _markAllRead() {
  if (!token) return
  try {
    await fetch(API_BASE + '/leads/notifications/mark-read', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
    _notifApplyMarkRead(null)
    _notifBroadcast({ type: 'mark-read', ids: null })
    _closeNotifDropdown()
  } catch (e) {}
}

function _notifLeadUrl(leadId) {
  var tenant = ''
  if (typeof currentTenant !== 'undefined' && currentTenant) tenant = currentTenant.slug || ''
  if (!tenant && typeof authGetTenantSlug === 'function') tenant = authGetTenantSlug() || ''
  return tenant ? '/' + tenant + '/action-board/lead/' + encodeURIComponent(leadId) : ''
}

function _notifFmtTime(value) {
  if (!value) return ''
  var d = new Date(value)
  if (isNaN(d.getTime())) return String(value)
  return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

function _notifEsc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
