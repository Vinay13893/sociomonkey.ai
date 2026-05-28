// ============================================================================
// MAIN ENTRY POINT
// ============================================================================

function render() {
  if (!token) return renderLogin()
  
  // Show sidebar when logged in
  const sidebar = document.querySelector('.sidebar')
  if (sidebar) sidebar.style.display = 'flex'
  
  const mainContent = document.querySelector('.main-content')
  if (mainContent && window.innerWidth > 768) mainContent.style.marginLeft = '220px'
  
  initMobileNav()
  renderApp()
}

function initMobileNav() {
  if (mobileNavInitialized) return
  mobileNavInitialized = true
  const hamburger = document.getElementById('hamburgerBtn')
  const overlay = document.getElementById('mobileOverlay')
  const sidebar = document.getElementById('sidebar')
  if (!hamburger || !overlay || !sidebar) return
  hamburger.addEventListener('click', () => {
    sidebar.classList.toggle('open')
    overlay.classList.toggle('active')
  })
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open')
    overlay.classList.remove('active')
  })
}


function closeMobileSidebar() {
  document.getElementById('sidebar')?.classList.remove('open')
  document.getElementById('mobileOverlay')?.classList.remove('active')
}

/**
 * Handle impersonation tokens passed via URL (?imp=TOKEN&user=JSON).
 * Called by platOpenOrgApp and platImpersonateOrg when opening tenant apps.
 * Stores the session in sessionStorage ONLY so the platform owner's
 * localStorage session is unaffected in the originating tab.
 * Returns true if an impersonation session was successfully hydrated.
 */
function _handleImpToken() {
  try {
    var params = new URLSearchParams(window.location.search)
    var impToken = params.get('imp')
    var impUserStr = params.get('user')
    if (!impToken || !impUserStr) return false

    var impUser = JSON.parse(decodeURIComponent(impUserStr))
    if (!impUser || !impUser.id) return false

    // Set in-memory session from impersonation token
    token = impToken
    user  = impUser
    availableProducts = []   // backend will refresh via loadMe()

    // Persist only in sessionStorage — does NOT affect platform owner's localStorage
    sessionStorage.setItem('lms_token',   impToken)
    sessionStorage.setItem('lms_user',    JSON.stringify(impUser))
    sessionStorage.removeItem('lms_products')
    sessionStorage.setItem('_imp_session', '1')   // flag for authClearSession()

    // Remove ?imp=…&user=… from the address bar (clean URL)
    history.replaceState({}, '', window.location.pathname)
    return true
  } catch (e) {
    return false
  }
}

function _sidebarRefresh() {
  if (typeof _sidebarBuilt !== 'undefined') {
    _sidebarBuilt = false
    if (typeof _buildSidebar === 'function' &&
        document.querySelector('.sidebar') &&
        document.querySelector('.sidebar').style.display !== 'none') {
      _buildSidebar()
      _sidebarBuilt = true
      if (typeof _sidebarForProduct !== 'undefined') _sidebarForProduct = currentProduct
      if (typeof _sidebarForSlug !== 'undefined') _sidebarForSlug = platformTenantSlug
    }
  }
}

async function init() {
  _PERF.mark('init')
  // Pre-warm the Railway backend immediately — eliminates cold-start wait.
  // Fires before any user interaction; by the time they authenticate and navigate,
  // the backend is already awake and responsive.
  try { fetch(API_BASE + '/health', { method: 'HEAD' }).catch(function() {}) } catch (_e) {}

  if (typeof showLoader === 'function') showLoader()

  // Check for impersonation token in URL first — bypasses localStorage entirely
  // so the platform owner's main-tab session is not disturbed.
  var impHandled = _handleImpToken()

  if (impHandled) {
    _PERF.lap('init', 'session=impersonation')
    // Impersonation session: schedule expiry + background refresh
    if (token) authScheduleExpiry()
    loadMe().then(_sidebarRefresh).catch(function() {})
  } else {
    // Normal session restore from storage (validates token expiry locally)
    var hasSession = authRestoreSession()
    _PERF.lap('init', 'session=' + (hasSession ? 'restored-from-storage' : 'none-redirect-to-login'))
    if (hasSession) {
      if (token) authScheduleExpiry()
      loadMe().then(_sidebarRefresh).catch(function() {})
    }
  }

  if (typeof hideLoader === 'function') hideLoader()
  _PERF.end('init')
  dispatch()
  // Remind developer how to see the waterfall after full hydration
  setTimeout(function () {
    console.log('%c[PERF] Ready. Call _PERF.report() to see the full timing waterfall.', 'color:#3b82f6;font-style:italic')
  }, 4000)
}

init()
