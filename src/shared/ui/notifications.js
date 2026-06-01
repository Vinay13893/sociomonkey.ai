// ============================================================================
// NOTIFICATION BELL
// A lightweight in-app notification bell that polls the backend every 60s.
// Rendered into #notifBellWrapper injected into the sidebar footer.
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
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
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
