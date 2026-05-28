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

async function init() {
  // Pre-warm the Railway backend immediately — eliminates cold-start wait.
  // Fires before any user interaction; by the time they authenticate and navigate,
  // the backend is already awake and responsive.
  try { fetch(API_BASE + '/health', { method: 'HEAD' }).catch(function() {}) } catch (_e) {}

  if (typeof showLoader === 'function') showLoader()
  // Restore session from storage (validates token expiry locally)
  const hasSession = authRestoreSession()
  if (hasSession) {
    // Schedule token expiry immediately — token is already in memory
    if (token) authScheduleExpiry()
    // Render the app RIGHT NOW using locally-cached user + products.
    // Validate session with the backend in the background.
    // If the server returns 401, loadMe() → authClearSession() → dispatch() handles re-login.
    loadMe().then(function() {
      // After server confirms the session, refresh the sidebar with any server-side changes
      // (e.g. role change, new product access) without re-rendering the content area.
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
    }).catch(function() {})
  }
  if (typeof hideLoader === 'function') hideLoader()
  dispatch()
}

init()
