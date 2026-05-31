// ============================================================================
// ROUTER - LMS tab router + URL-based platform/tenant dispatcher
// ============================================================================

// Maps activeTab → LMS render function (tenant layer, unchanged)
function showContent() {
  _PERF.count('showContent')
  window._ACTIVE_ROUTE = activeTab  // update global route BEFORE any render function runs — this is what kills stale _guard() checks in renders that are no longer the active route
  if (activeTab === 'dashboard') return renderDashboard()
  if (activeTab === 'leads') return renderLeads()
  if (activeTab === 'action_board') return renderActionBoard()
  if (activeTab === 'recycle_queue') return renderRecycleQueue()
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

function _setPublicLoginMode(enabled) {
  var platRoot = document.getElementById('platformRoot')
  var tenantLayout = document.getElementById('tenantLayout')
  var publicRoot = document.getElementById('publicLoginRoot')
  if (enabled) {
    if (platRoot) platRoot.style.display = 'none'
    if (tenantLayout) tenantLayout.style.display = 'none'
    if (publicRoot) publicRoot.style.display = 'block'
  } else {
    if (publicRoot) publicRoot.style.display = 'none'
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

  // Canonical tenant app login path: /apps/:product/:slug/login
  const appTenantLoginMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)\/login$/)
  if (appTenantLoginMatch) {
    return {
      layer: 'tenant-login',
      product: appTenantLoginMatch[1],
      slug: authCanonicalTenantSlug(appTenantLoginMatch[2]),
      tenant_data_slug: authTenantDataSlug(appTenantLoginMatch[2]),
    }
  }

  // Canonical tenant app path: /apps/:product/:slug or /apps/:product/:slug/:tab
  const appTenantMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)(?:\/([^\/]+))?$/)
  if (appTenantMatch) {
    const canonicalSlug = authCanonicalTenantSlug(appTenantMatch[2])
    const canonicalTab = authCanonicalTenantTab(appTenantMatch[3] || 'dashboard')
    const canonicalPath = authBuildTenantTabPath(canonicalSlug, appTenantMatch[1], canonicalTab)
    if (canonicalPath !== path) {
      history.replaceState({}, '', canonicalPath)
    }
    return {
      layer: 'tenant',
      product: appTenantMatch[1],
      slug: canonicalSlug,
      tenant_data_slug: authTenantDataSlug(appTenantMatch[2]),
      tab: canonicalTab,
    }
  }

  // Tenant login page: /:slug/login (stable) or /:slug/:product/login (legacy)
  const tenantLoginSimpleMatch = path.match(/^\/([^\/]+)\/login$/)
  if (tenantLoginSimpleMatch) {
    const legacySlug = tenantLoginSimpleMatch[1]
    history.replaceState({}, '', authBuildTenantLoginPath(legacySlug, 'lms'))
    return {
      layer: 'tenant-login',
      slug: authCanonicalTenantSlug(legacySlug),
      product: 'lms',
      tenant_data_slug: authTenantDataSlug(legacySlug),
    }
  }

  // Legacy tenant login page: /:slug/:product/login
  const tenantLoginMatch = path.match(/^\/([^\/]+)\/([^\/]+)\/login$/)
  if (tenantLoginMatch) {
    const legacySlug = tenantLoginMatch[1]
    const product = tenantLoginMatch[2]
    history.replaceState({}, '', authBuildTenantLoginPath(legacySlug, product))
    return {
      layer: 'tenant-login',
      slug: authCanonicalTenantSlug(legacySlug),
      product: product,
      tenant_data_slug: authTenantDataSlug(legacySlug),
    }
  }

  // Tenant product paths:  /:slug/:product  (e.g. /ganga/crm  or /ganga/lms)
  const m = path.match(/^\/([^\/]+)\/([^\/]+)(?:\/([^\/]+))?$/)
  if (m && m[1] !== 'products' && m[1] !== 'apps') {
    const slug = m[1]
    let product = m[2]
    const tab = authCanonicalTenantTab(m[3] || 'dashboard')
    // Backward compat: legacy routes map into canonical /apps/:product/:tenant
    if (product === 'crm') {
      history.replaceState({}, '', authBuildTenantTabPath(slug, 'lms', tab))
      product = 'lms'
    } else {
      history.replaceState({}, '', authBuildTenantTabPath(slug, product, tab))
    }
    return {
      layer: 'tenant',
      slug: authCanonicalTenantSlug(slug),
      product: product,
      tenant_data_slug: authTenantDataSlug(slug),
      tab: tab,
    }
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
            ? '<button onclick="history.pushState({},\'\',authBuildTenantAppPath(user.tenant_slug,\'lms\'));dispatch()" class="button" style="font-size:14px;">Go to My App</button>'
            : '') +
'<button onclick="authClearSession();clearTenantContext();history.replaceState({},' + "''" + ',\'/login\');if(typeof _setPublicLoginMode===\'function\'){_setPublicLoginMode(true)};if(typeof renderLogin===\'function\'){renderLogin({ type: \'platform\' })};dispatch()" class="button" style="font-size:14px;background:#64748b;color:#fff;">Sign Out</button>'
        '</div>' +
      '</div>' +
    '</div>'
}

var _dispatchInFlight = false
async function dispatch() {
  // Prevent re-entrant dispatch — e.g. popstate fires while a render is in progress
  if (_dispatchInFlight) {
    _PERF.lap('dispatch', 'skipped-reentrant')
    return
  }
  _dispatchInFlight = true
  _PERF.count('dispatch')
  _PERF.mark('dispatch')
  if (typeof showLoader === 'function') showLoader()
  try {
    await _dispatchInner()
  } catch (err) {
    if (typeof showToast === 'function') showToast((err && err.message) || 'Navigation error', 'error')
  } finally {
    _dispatchInFlight = false
    if (typeof hideLoader === 'function') hideLoader()
    _PERF.end('dispatch')
  }
}

async function _dispatchInner() {
  const platRoot     = document.getElementById('platformRoot')
  const tenantLayout = document.getElementById('tenantLayout')
  _PERF.mark('parseRoute')
  const route = parseRoute()
  _PERF.end('parseRoute')

  // ── Login pages (no auth required) ─────────────────────────────────────────
  if (route.layer === 'platform-login') {
    // Already authenticated → go to platform dashboard
    if (token && user) {
      history.replaceState({}, '', '/')
      return _dispatchInner()
    }
    _setPublicLoginMode(true)
    clearTenantContext()
    renderLogin({ type: 'platform' })
    return
  }
  if (route.layer === 'tenant-login') {
    // Already authenticated → go to tenant LMS
    if (token && user) {
      const slug = (user && user.tenant_slug) || route.slug
      history.replaceState({}, '', authBuildTenantAppPath(slug, route.product || 'lms'))
      return _dispatchInner()
    }
    _setPublicLoginMode(true)
    renderLogin({ type: 'tenant', slug: route.slug, product: route.product })
    loadTenantConfig(route.tenant_data_slug || authTenantDataSlug(route.slug)).then(function () {
      if (!token && window.location.pathname === authBuildTenantLoginPath(route.slug, route.product || 'lms')) {
        renderLogin({ type: 'tenant', slug: route.slug, product: route.product })
      }
    }).catch(function () {})
    return
  }

  // Never auto-enter tenant apps from platform/root routes.
  // Tenant sessions must use explicit tenant URLs or explicit tenant launch flow.
  if (token && user && authIsTenantUser() && (route.layer === 'platform' || route.layer === 'product-hub')) {
    authClearSession()
    clearTenantContext()
    loginRedirectPath = ''
    history.replaceState({}, '', '/login')
    _setPublicLoginMode(true)
    renderLogin({ type: 'platform' })
    return
  }

  // ── Unauthenticated ─────────────────────────────────────────────────────────
  if (!token || !user) {
    loginRedirectPath = window.location.pathname
    const loginPath = authGetLoginPath(route)
    history.replaceState({}, '', loginPath)
    _setPublicLoginMode(true)
    const loginRoute = parseRoute()
    if (loginRoute.layer === 'tenant-login') {
      renderLogin({ type: 'tenant', slug: loginRoute.slug, product: loginRoute.product })
      loadTenantConfig(loginRoute.tenant_data_slug || authTenantDataSlug(loginRoute.slug)).then(function () {
        if (!token && window.location.pathname === authBuildTenantLoginPath(loginRoute.slug, loginRoute.product || 'lms')) {
          renderLogin({ type: 'tenant', slug: loginRoute.slug, product: loginRoute.product })
        }
      }).catch(function () {})
    } else {
      clearTenantContext()
      renderLogin({ type: 'platform' })
    }
    return
  }

  _setPublicLoginMode(false)

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
    platformTenantSlug = route.tenant_data_slug || authTenantDataSlug(route.slug)
    // Sync currentProduct from URL so nav items and content match the route
    if (route.product) {
      currentProduct = route.product
      localStorage.setItem('current_product', route.product)
    }
    activeTab = route.tab || 'dashboard'
    // Don't block render — cached paths (in-memory/sessionStorage) apply branding
    // synchronously; cold-path network fetch applies branding when it resolves.
    loadTenantConfig(platformTenantSlug)
  }
  if (platRoot)     platRoot.style.display     = 'none'
  if (tenantLayout) tenantLayout.style.display = ''
  _PERF.mark('render')
  render()
  _PERF.end('render')
}

// ─── Programmatic navigation ─────────────────────────────────────────────────

// Called from product-launcher when platform owner opens a tenant app
function launchTenantApp(productCode, slug) {
  // Navigate to the canonical tenant URL and run the full dispatch() pipeline.
  // This guarantees loadTenantConfig(), tenant cache reset, and auth checks all
  // run identically to a direct URL navigation or page refresh.
  history.pushState({}, '', authBuildTenantAppPath(slug, productCode))
  dispatch()
}

// Handle browser back/forward
window.addEventListener('popstate', () => {
  if (user) dispatch()
})

