// ============================================================================
// NOTIFICATION BELL
// A lightweight in-app notification bell that polls the backend every 60s.
// Rendered as a floating FAB in the bottom-right corner of the viewport.
// ============================================================================

var _notifPollTimer  = null
var _notifOpen       = false
var _notifData       = []   // cached unread notifications

// ── Init ─────────────────────────────────────────────────────────────────────
function initNotifBell() {
  const wrapper = document.getElementById('notifBellWrapper')
  if (!wrapper) return

  wrapper.style.display = 'block'
  _renderBell()
  _pollNotifications()

  // Poll every 60 seconds
  if (_notifPollTimer) clearInterval(_notifPollTimer)
  _notifPollTimer = setInterval(_pollNotifications, 60000)

  // Close dropdown when clicking outside
  document.addEventListener('click', function (e) {
    if (_notifOpen && !wrapper.contains(e.target)) {
      _closeNotifDropdown()
    }
  }, true)
}

function destroyNotifBell() {
  if (_notifPollTimer) { clearInterval(_notifPollTimer); _notifPollTimer = null }
  _notifData = []
  _notifOpen = false
  const wrapper = document.getElementById('notifBellWrapper')
  if (wrapper) wrapper.style.display = 'none'
}

// ── Render bell button ────────────────────────────────────────────────────────
function _renderBell() {
  const wrapper = document.getElementById('notifBellWrapper')
  if (!wrapper) return
  const count   = _notifData.length
  const badgeHTML = count > 0
    ? `<span class="notif-badge">${count > 99 ? '99+' : count}</span>`
    : ''
  wrapper.innerHTML = `
    <div class="notif-bell-container">
      <button id="notifBellBtn" class="notif-bell-btn" aria-label="Notifications" title="Notifications">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" stroke="none">
          <path d="M12 2a7 7 0 0 0-7 7c0 4.1-1.8 6.3-2.7 7.3-.3.4-.3.9 0 1.3.3.3.7.4 1.1.4h5.1a2.5 2.5 0 0 0 4.9 0H18.6c.4 0 .8-.1 1.1-.4.3-.4.3-.9 0-1.3C18.8 15.3 17 13.1 17 9a7 7 0 0 0-5-6.7V2z"/>
        </svg>
        ${badgeHTML}
      </button>
      <div id="notifDropdown" class="notif-dropdown" style="display:none;">
        <div class="notif-dropdown-header">
          <span>Notifications</span>
          ${count > 0 ? `<button id="markAllReadBtn" class="notif-mark-read-btn">Mark all read</button>` : ''}
        </div>
        <div id="notifList" class="notif-list">
          ${_renderNotifItems()}
        </div>
      </div>
    </div>
  `
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
  if (_notifData.length === 0) {
    return '<div class="notif-empty">No new notifications</div>'
  }
  return _notifData.map(n => `
    <div class="notif-item notif-item--${n.kind || 'info'}">
      <div class="notif-item-title">${escape(n.title || 'Notification')}</div>
      <div class="notif-item-msg">${escape(n.message || '')}</div>
      <div class="notif-item-time">${_fmtIST(n.created_at)}</div>
    </div>
  `).join('')
}

// ── Toggle / close ────────────────────────────────────────────────────────────
function _toggleNotifDropdown() {
  if (_notifOpen) {
    _closeNotifDropdown()
  } else {
    _openNotifDropdown()
  }
}

function _openNotifDropdown() {
  const dropdown = document.getElementById('notifDropdown')
  if (!dropdown) return
  dropdown.style.display = 'block'
  _notifOpen = true
}

function _closeNotifDropdown() {
  const dropdown = document.getElementById('notifDropdown')
  if (dropdown) dropdown.style.display = 'none'
  _notifOpen = false
}

// ── Poll backend ──────────────────────────────────────────────────────────────
async function _pollNotifications() {
  if (!token) return
  try {
    const res = await fetch(`${API_BASE}/leads/notifications`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) return
    const data = await res.json()
    _notifData = data.notifications || []
    _renderBell()
    // Re-open dropdown if it was open
    if (_notifOpen) {
      _openNotifDropdown()
    }
  } catch (e) {
    // silently fail on network errors
  }
}

// ── Mark all as read ──────────────────────────────────────────────────────────
async function _markAllRead() {
  if (!token) return
  try {
    await fetch(`${API_BASE}/leads/notifications/mark-read`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
    _notifData = []
    _renderBell()
    _closeNotifDropdown()
  } catch (e) {
    // silently fail
  }
}
