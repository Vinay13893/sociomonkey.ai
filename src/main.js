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
  if (typeof showLoader === 'function') showLoader()
  // Restore session from storage (also validates token expiry)
  const hasSession = authRestoreSession()
  if (hasSession) {
    // Validate session with backend and refresh user object
    await loadMe()
    if (token) authScheduleExpiry()
  }
  if (typeof hideLoader === 'function') hideLoader()
  dispatch()
}

init()
