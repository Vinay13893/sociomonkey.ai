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
        <svg viewBox="0 0 32 34" width="26" height="26" xmlns="http://www.w3.org/2000/svg">
          <!-- Bell body: red -->
          <path d="M16 3 C10.5 3 6 7.5 6 13 C6 19.5 3 22 2.5 23 L29.5 23 C29 22 26 19.5 26 13 C26 7.5 21.5 3 16 3 Z" fill="#ef4444" stroke="#1e1b4b" stroke-width="1.6" stroke-linejoin="round"/>
          <!-- Shine on bell -->
          <path d="M9.5 9.5 Q10.5 7 13 6" fill="none" stroke="rgba(255,255,255,0.65)" stroke-width="1.6" stroke-linecap="round"/>
          <!-- Bell rim: yellow-orange -->
          <rect x="2" y="22.2" width="28" height="3" rx="1.5" fill="#fbbf24" stroke="#1e1b4b" stroke-width="1.4"/>
          <!-- Clapper: yellow -->
          <circle cx="16" cy="28.5" r="2.2" fill="#fbbf24" stroke="#1e1b4b" stroke-width="1.4"/>
          <!-- Hook at top -->
          <path d="M14.2 3.5 Q16 1.5 17.8 3.5" fill="none" stroke="#1e1b4b" stroke-width="1.5" stroke-linecap="round"/>
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
