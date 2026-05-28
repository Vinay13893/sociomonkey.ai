// ============================================================================
// ROUTER - LMS tab router + URL-based platform/tenant dispatcher
// ============================================================================

// Maps activeTab → LMS render function (tenant layer, unchanged)
function showContent() {
  if (activeTab === 'dashboard') return renderDashboard()
  if (activeTab === 'leads') return renderLeads()
  if (activeTab === 'projects') return renderProjects()
  if (activeTab === 'team') return renderTeamManagement()
  if (activeTab === 'pipeline') return renderPipeline()
  if (activeTab === 'excel') return renderExcelUpload()
  if (activeTab === 'reports') return renderReports()
  if (activeTab === 'export') return renderExportLeads()
  if (activeTab === 'platform') return renderPlatformAdmin()
  if (activeTab === 'activitylogs') return renderActivityLogs()
  if (activeTab === 'profile') return renderMyProfile()
  if (activeTab === 'product_home') {
    // LMS product home has its own rich landing page
    if (currentProduct === 'lms' && typeof renderLmsHome === 'function') return renderLmsHome()
    return renderProductHome()
  }
}

// Safely invoke showContent() — catches async render errors and shows retry UI
function _safeShowContent() {
  var result
  try { result = showContent() } catch (err) { _showPageError(err); return }
  if (result && typeof result.catch === 'function') {
    result.catch(function (err) { _showPageError(err) })
  }
}

function _showPageError(err) {
  var c = document.getElementById('content')
  if (!c) return
  var msg = (err && err.message) ? err.message : 'Failed to load page.'
  c.innerHTML =
    '<div style="padding:60px 40px;text-align:center;">' +
      '<div style="font-size:40px;margin-bottom:12px;">&#x26A0;</div>' +
      '<h3 style="color:#1e293b;margin-bottom:8px;">Something went wrong</h3>' +
      '<p style="color:#64748b;font-size:14px;margin-bottom:24px;">' + msg + '</p>' +
      '<button class="button" onclick="dispatch()" style="font-size:14px;">Retry</button>' +
    '</div>'
  if (typeof showToast === 'function') showToast(msg, 'error')
}

// ─── URL Route Parser ───────────────────────────────────────────────────────

const PLATFORM_ROUTE_VIEWS = {
  '/':              'dashboard',
  '/dashboard':     'dashboard',
  '/applications':  'applications',
  '/users':         'users',
  '/organizations': 'organizations',
  '/analytics':     'analytics',
  '/billing':       'billing',
  '/integrations':  'integrations',
  '/automation':    'automation',
  '/settings':      'settings',
  '/audit-logs':    'audit-logs',
  '/support':       'support',
}

function parseRoute() {
  const raw  = window.location.pathname
  const path = raw.replace(/\/+$/, '') || '/'

  // Explicit platform paths
  if (PLATFORM_ROUTE_VIEWS[path]) {
    return { layer: 'platform', view: PLATFORM_ROUTE_VIEWS[path] }
  }

  // Product hub:  /products/:code  (e.g. /products/crm)
  const productHubMatch = path.match(/^\/products\/([^\/]+)$/)
  if (productHubMatch) {
    platformContext = { productCode: productHubMatch[1] }
    return { layer: 'platform', view: 'product-hub' }
  }

  // Platform login page
  if (path === '/login') return { layer: 'platform-login' }

  // Tenant login page: /:slug/login (stable) or /:slug/:product/login (legacy)
  const tenantLoginSimpleMatch = path.match(/^\/([^\/]+)\/login$/)
  if (tenantLoginSimpleMatch) {
    return { layer: 'tenant-login', slug: tenantLoginSimpleMatch[1], product: 'lms' }
  }

  // Legacy tenant login page: /:slug/:product/login
  const tenantLoginMatch = path.match(/^\/([^\/]+)\/([^\/]+)\/login$/)
  if (tenantLoginMatch) {
    return { layer: 'tenant-login', slug: tenantLoginMatch[1], product: tenantLoginMatch[2] }
  }

  // Tenant product paths:  /:slug/:product  (e.g. /ganga/crm  or /ganga/lms)
  const m = path.match(/^\/([^\/]+)\/([^\/]+)/)
  if (m && m[1] !== 'products') {
    const slug = m[1]
    let product = m[2]
    // Backward compat: /ganga/crm silently redirects to /ganga/lms
    if (product === 'crm') {
      history.replaceState({}, '', '/' + slug + '/lms')
      product = 'lms'
    }
    return { layer: 'tenant', slug: slug, product: product }
  }

  // Default: platform dashboard
  return { layer: 'platform', view: 'dashboard' }
}

// ─── Top-level dispatcher (called from init + popstate) ─────────────────────

function renderAccessDenied(route) {
  const platRoot     = document.getElementById('platformRoot')
  const tenantLayout = document.getElementById('tenantLayout')
  if (platRoot)     platRoot.style.display     = 'none'
  if (tenantLayout) tenantLayout.style.display = ''

  // For tenant users hitting platform routes, redirect them to their own tenant app
  if (user && authIsTenantUser() && (route.layer === 'platform' || route.layer === 'product-hub')) {
    if (user.tenant_slug) {
      history.replaceState({}, '', '/' + user.tenant_slug + '/lms')
      dispatch()
      return
    }
  }

  const sidebar = document.querySelector('.sidebar')
  if (sidebar) sidebar.style.display = 'none'
  const mainContent = document.querySelector('.main-content')
  if (mainContent) mainContent.style.marginLeft = '0'

  root.innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f1f5f9;">' +
      '<div class="card" style="max-width:420px;width:100%;text-align:center;padding:40px 32px;">' +
        '<div style="font-size:48px;margin-bottom:16px;">&#x1F512;</div>' +
        '<h2 style="color:#1e293b;margin-bottom:8px;">Access Denied</h2>' +
        '<p style="color:#64748b;font-size:14px;margin-bottom:24px;">You don\'t have permission to access this page.</p>' +
        '<div style="display:flex;flex-direction:column;gap:10px;">' +
          (user && user.tenant_slug
            ? '<button onclick="history.pushState({},\'\',' + "'/'+(user.tenant_slug)+'/lms');dispatch()" + '" class="button" style="font-size:14px;">Go to My App</button>'
            : '') +
          '<button onclick="authClearSession();history.replaceState({},' + "'','/login');dispatch()" + '" class="button" style="font-size:14px;background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0;">Sign Out</button>' +
        '</div>' +
      '</div>' +
    '</div>'
}

async function dispatch() {
  if (typeof showLoader === 'function') showLoader()
  try {
    await _dispatchInner()
  } catch (err) {
    if (typeof showToast === 'function') showToast((err && err.message) || 'Navigation error', 'error')
  } finally {
    if (typeof hideLoader === 'function') hideLoader()
  }
}

async function _dispatchInner() {
  const platRoot     = document.getElementById('platformRoot')
  const tenantLayout = document.getElementById('tenantLayout')
  const route = parseRoute()

  // ── Login pages (no auth required) ─────────────────────────────────────────
  if (route.layer === 'platform-login') {
    // Already authenticated → go to platform dashboard
    if (token && user) {
      history.replaceState({}, '', '/')
      return _dispatchInner()
    }
    if (platRoot)     platRoot.style.display     = 'none'
    if (tenantLayout) tenantLayout.style.display = ''
    clearTenantContext()
    renderLogin({ type: 'platform' })
    return
  }
  if (route.layer === 'tenant-login') {
    // Already authenticated → go to tenant LMS
    if (token && user) {
      const slug = (user && user.tenant_slug) || route.slug
      history.replaceState({}, '', '/' + slug + '/lms')
      return _dispatchInner()
    }
    if (platRoot)     platRoot.style.display     = 'none'
    if (tenantLayout) tenantLayout.style.display = ''
    await loadTenantConfig(route.slug)
    renderLogin({ type: 'tenant', slug: route.slug, product: route.product })
    return
  }

  // ── Unauthenticated ─────────────────────────────────────────────────────────
  if (!token || !user) {
    loginRedirectPath = window.location.pathname
    const loginPath = authGetLoginPath(route)
    history.replaceState({}, '', loginPath)
    if (platRoot)     platRoot.style.display     = 'none'
    if (tenantLayout) tenantLayout.style.display = ''
    const loginRoute = parseRoute()
    if (loginRoute.layer === 'tenant-login') {
      await loadTenantConfig(loginRoute.slug)
      renderLogin({ type: 'tenant', slug: loginRoute.slug, product: loginRoute.product })
    } else {
      clearTenantContext()
      renderLogin({ type: 'platform' })
    }
    return
  }

  // ── Access control check ────────────────────────────────────────────────────
  if (!authCanAccess(route)) {
    renderAccessDenied(route)
    return
  }

  // ── Platform routes ─────────────────────────────────────────────────────────
  if (authIsPlatformUser() && route.layer !== 'tenant') {
    platformView = route.view || 'dashboard'
    clearTenantContext()
    // platformContext already set by parseRoute() for product-hub
    renderPlatformLayout(platformView)
    return
  }

  // ── Tenant routes (including platform owner drilling in via product hub) ────
  if (route.layer === 'tenant') {
    platformTenantSlug = route.slug
    // Sync currentProduct from URL so nav items and content match the route
    if (route.product) {
      currentProduct = route.product
      localStorage.setItem('current_product', route.product)
    }
    activeTab = 'dashboard'
    await loadTenantConfig(route.slug)
  }
  if (platRoot)     platRoot.style.display     = 'none'
  if (tenantLayout) tenantLayout.style.display = ''
  render()
}

// ─── Programmatic navigation ─────────────────────────────────────────────────

// Called from product-launcher when platform owner opens a tenant app
function launchTenantApp(productCode, slug) {
  platformTenantSlug = slug
  currentProduct = productCode
  localStorage.setItem('current_product', productCode)
  history.pushState({}, '', `/${slug}/${productCode}`)
  const platRoot     = document.getElementById('platformRoot')
  const tenantLayout = document.getElementById('tenantLayout')
  if (platRoot)     platRoot.style.display     = 'none'
  if (tenantLayout) tenantLayout.style.display = ''
  activeTab = 'dashboard'
  render()
}

// Handle browser back/forward
window.addEventListener('popstate', () => {
  if (user) dispatch()
})

