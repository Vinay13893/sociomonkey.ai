// ============================================================================
// AUTH MANAGER — Central authentication orchestration
// JWT decoding, role-based access control, session management, expiry handling
//
// LOADING ORDER: Must be loaded AFTER app-state.js (needs `token`, `user`,
//                `API_BASE` globals) and BEFORE api.js (api.js calls authSetSession)
// ============================================================================

// Roles that belong to the platform layer (not tenant apps)
var AUTH_PLATFORM_ROLES = new Set(['platform_owner', 'platform_admin', 'product_admin'])

// ── JWT Utilities ─────────────────────────────────────────────────────────────

function authParseJwt(tok) {
  if (!tok) return null
  try {
    var b64 = tok.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(b64))
  } catch (e) { return null }
}

function authTokenExpired(tok) {
  var p = authParseJwt(tok)
  return !p || !p.exp || (Date.now() / 1000 >= p.exp)
}

function authSecondsRemaining(tok) {
  var p = authParseJwt(tok)
  if (!p || !p.exp) return 0
  return Math.max(0, Math.floor(p.exp - Date.now() / 1000))
}

// ── Role Predicates ───────────────────────────────────────────────────────────

// Returns true if the current (or given) user is a platform-layer user
function authIsPlatformUser(u) {
  var target = (typeof u !== 'undefined') ? u : user
  return !!(target && AUTH_PLATFORM_ROLES.has(target.role))
}

// Returns true if the current (or given) user is a tenant user
function authIsTenantUser(u) {
  var target = (typeof u !== 'undefined') ? u : user
  return !!(target && !AUTH_PLATFORM_ROLES.has(target.role))
}

// Returns true if the current user has the exact given role
function authHasRole(role) {
  return !!(user && user.role === role)
}

// ── Access Control ────────────────────────────────────────────────────────────

/**
 * Returns true if the current authenticated user is permitted to access route.
 * route: { layer: 'platform'|'tenant'|'product-hub', slug?, product? }
 *
 * Rules:
 *   - Platform routes: only platform users
 *   - Tenant routes:   platform users can access any tenant (product hub launch)
 *                      tenant users can only access their own tenant slug
 */
function authCanAccess(route) {
  if (!user) return false
  var layer = route.layer

  if (layer === 'platform' || layer === 'product-hub') {
    return authIsPlatformUser()
  }

  if (layer === 'tenant') {
    // Platform owners can drill into any tenant (launched via product hub)
    if (authIsPlatformUser()) return true
    if (authIsTenantUser()) {
      // If the user's tenant_slug is not yet set (legacy data), allow by tenant_id match
      if (!user.tenant_slug) return true
      return user.tenant_slug === route.slug
    }
  }

  return false
}

/**
 * Returns the appropriate login path for an unauthenticated access attempt.
 * Tenant routes redirect to /:slug/:product/login
 * Everything else redirects to /login
 */
function authGetLoginPath(route) {
  if (route && route.layer === 'tenant' && route.slug) {
    return '/' + route.slug + '/login'
  }
  return '/login'
}

// ── Session Management ────────────────────────────────────────────────────────

/**
 * Persist a new session.
 * remember=true  → localStorage  (survives browser close)
 * remember=false → sessionStorage (cleared when tab closes)
 */
function authSetSession(newToken, newUser, remember) {
  token = newToken
  user  = newUser
  if (remember) {
    localStorage.setItem('lms_token', newToken)
    localStorage.setItem('lms_user',  JSON.stringify(newUser))
    sessionStorage.removeItem('lms_token')
    sessionStorage.removeItem('lms_user')
  } else {
    sessionStorage.setItem('lms_token', newToken)
    sessionStorage.setItem('lms_user',  JSON.stringify(newUser))
    localStorage.removeItem('lms_token')
    localStorage.removeItem('lms_user')
  }
  // Broadcast login event to other tabs
  try {
    localStorage.setItem('_auth_sync', JSON.stringify({ type: 'login', ts: Date.now() }))
  } catch (e) {}
}

/**
 * Clear all auth state (memory + storage) and notify other tabs.
 */
function authClearSession() {
  token = null
  user  = null
  localStorage.removeItem('lms_token')
  localStorage.removeItem('lms_user')
  sessionStorage.removeItem('lms_token')
  sessionStorage.removeItem('lms_user')
  try {
    localStorage.setItem('_auth_sync', JSON.stringify({ type: 'logout', ts: Date.now() }))
  } catch (e) {}
}

/**
 * Attempt to restore a session from storage.
 * Returns true if a valid, non-expired token was found.
 * Clears storage and returns false if the stored token is expired.
 */
function authRestoreSession() {
  var tok = localStorage.getItem('lms_token') || sessionStorage.getItem('lms_token')
  if (!tok) return false
  if (authTokenExpired(tok)) {
    authClearSession()
    return false
  }
  token = tok
  try {
    var rawUser = localStorage.getItem('lms_user') || sessionStorage.getItem('lms_user')
    if (rawUser) user = JSON.parse(rawUser)
  } catch (e) {}
  return true
}

// ── Session Expiry Scheduling ─────────────────────────────────────────────────

var _authWarnTimer   = null
var _authLogoutTimer = null

/**
 * Schedule an expiry warning banner 5 min before expiry, and an auto-logout
 * when the token actually expires.  Call this after every login or token refresh.
 */
function authScheduleExpiry() {
  if (_authWarnTimer)   clearTimeout(_authWarnTimer)
  if (_authLogoutTimer) clearTimeout(_authLogoutTimer)
  if (!token) return

  var secs = authSecondsRemaining(token)
  if (secs <= 0) return

  if (secs > 300) {
    _authWarnTimer = setTimeout(authShowExpiryWarning, (secs - 300) * 1000)
  }

  _authLogoutTimer = setTimeout(function () {
    authClearSession()
    var b = document.getElementById('_authExpiryBanner')
    if (b) b.remove()
    if (typeof dispatch === 'function') dispatch()
  }, secs * 1000)
}

function authShowExpiryWarning() {
  if (document.getElementById('_authExpiryBanner')) return
  var b = document.createElement('div')
  b.id = '_authExpiryBanner'
  b.style.cssText = [
    'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:9999',
    'background:#fef3c7', 'border-bottom:2px solid #fde68a',
    'padding:10px 20px', 'display:flex', 'align-items:center', 'gap:12px',
    'font-size:13px', 'color:#92400e', 'box-shadow:0 2px 8px rgba(0,0,0,.12)'
  ].join(';')
  b.innerHTML =
    '<i class="fa-solid fa-clock" style="color:#f59e0b;font-size:16px;flex-shrink:0;"></i>' +
    '<span><strong>Session expiring soon.</strong> Your session will expire in 5 minutes.</span>' +
    '<button id="_authExtendBtn" onclick="authExtendSession()" style="padding:5px 16px;border:1px solid #f59e0b;border-radius:7px;background:#fff;color:#92400e;cursor:pointer;font-size:12px;font-weight:600;margin-left:8px;flex-shrink:0;">Extend Session</button>' +
    '<button onclick="document.getElementById(\'_authExpiryBanner\').remove()" style="margin-left:auto;background:none;border:none;cursor:pointer;font-size:22px;color:#92400e;line-height:1;padding:0 4px;">&times;</button>'
  document.body.appendChild(b)
}

async function authExtendSession() {
  var btn = document.getElementById('_authExtendBtn')
  if (btn) { btn.disabled = true; btn.textContent = 'Extending…' }
  try {
    var resp = await fetch(API_BASE + '/auth/refresh', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
      }
    })
    if (resp.ok) {
      var data = await resp.json()
      if (data.token) {
        var remember = !!localStorage.getItem('lms_token')
        authSetSession(data.token, user, remember)
        authScheduleExpiry()
        var b = document.getElementById('_authExpiryBanner')
        if (b) b.remove()
        return
      }
    }
  } catch (e) {}
  // Refresh failed — update banner (do not force logout yet; let normal expiry handle it)
  var b = document.getElementById('_authExpiryBanner')
  if (b) {
    var span = b.querySelector('span')
    if (span) span.innerHTML = '<strong>Session extension failed.</strong> Please save your work and sign in again.'
    if (btn) { btn.disabled = false; btn.textContent = 'Retry' }
  }
}

// ── Cross-tab Sync ────────────────────────────────────────────────────────────

window.addEventListener('storage', function (e) {
  if (e.key !== '_auth_sync') return
  try {
    var d = JSON.parse(e.newValue)
    if (!d) return
    if (d.type === 'logout') {
      token = null
      user  = null
      if (typeof dispatch === 'function') dispatch()
    } else if (d.type === 'login') {
      // Another tab just logged in with localStorage — pick up the token
      var newTok = localStorage.getItem('lms_token')
      if (newTok && newTok !== token) {
        token = newTok
        try { user = JSON.parse(localStorage.getItem('lms_user')) } catch (ex) {}
        if (typeof dispatch === 'function') dispatch()
      }
    }
  } catch (e) {}
})
