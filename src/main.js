// ============================================================================
// MAIN ENTRY POINT
// ============================================================================

function render() {
  // Clear any previously visible shell immediately so login routes do not flash the sidebar.
  const sidebar = document.querySelector('.sm-sidebar')
  if (sidebar) sidebar.style.display = 'none'
  const overlay = document.getElementById('mobileOverlay')
  if (overlay) overlay.classList.remove('active')
  const mobileSidebar = document.getElementById('sidebar')
  if (mobileSidebar) mobileSidebar.classList.remove('open')

  if (!token) return renderLogin()

  // Reset overflow/height overrides applied by renderLogin()
  document.body.style.overflow = ''
  document.body.style.margin = ''
  document.documentElement.style.overflow = ''
  document.documentElement.style.margin = ''
  var _mc = document.querySelector('.main-content')
  if (_mc) { _mc.style.overflow = ''; _mc.style.height = ''; _mc.style.marginLeft = '' }
  if (root) { root.style.overflow = ''; root.style.height = ''; root.style.padding = '' }

  // Show sidebar when logged in
  if (sidebar) sidebar.style.display = 'flex'
  
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

function _sessionUiSignature() {
  return JSON.stringify({
    userId: user && user.id,
    userRole: user && user.role,
    tenantSlug: user && user.tenant_slug,
    currentProduct: currentProduct,
    productSlugs: (availableProducts || []).map(function(p) { return p.slug })
  })
}

function _sidebarRefreshIfChanged(previousSignature) {
  if (previousSignature === _sessionUiSignature()) return
  if (typeof _sidebarBuilt !== 'undefined') {
    _sidebarBuilt = false
    if (typeof _buildSidebar === 'function' &&
        document.querySelector('.sm-sidebar') &&
        document.querySelector('.sm-sidebar').style.display !== 'none') {
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

  var _needsHydrateBeforeDispatch = false

  if (impHandled) {
    _PERF.lap('init', 'session=impersonation')
    // Impersonation session: schedule expiry now and refresh session data after first paint.
    if (token) authScheduleExpiry()
    _needsHydrateBeforeDispatch = availableProducts.length === 0
  } else {
    // Normal session restore from storage (validates token expiry locally)
    var hasSession = authRestoreSession()
    _PERF.lap('init', 'session=' + (hasSession ? 'restored-from-storage' : 'none-redirect-to-login'))
    if (hasSession) {
      if (token) authScheduleExpiry()
      _needsHydrateBeforeDispatch = availableProducts.length === 0
    }
  }

  if (_needsHydrateBeforeDispatch) {
    try { await loadMe() } catch (_e) {}
  }

  if (typeof hideLoader === 'function') hideLoader()
  _PERF.end('init')
  dispatch()

  if (token && !_needsHydrateBeforeDispatch) {
    var _beforeHydrateSig = _sessionUiSignature()
    loadMe()
      .then(function () { _sidebarRefreshIfChanged(_beforeHydrateSig) })
      .catch(function () {})
  }
  // Remind developer how to see the waterfall after full hydration
  setTimeout(function () {
    console.log('%c[PERF] Ready. Call _PERF.report() to see the full timing waterfall.', 'color:#3b82f6;font-style:italic')
  }, 4000)
}

init()
