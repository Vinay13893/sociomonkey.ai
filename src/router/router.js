// ============================================================================
// ROUTER - LMS tab router + URL-based platform/tenant dispatcher
// ============================================================================

// Maps activeTab → LMS render function (tenant layer, unchanged)
function showContent() {
  _PERF.count('showContent')
  window._ACTIVE_ROUTE = activeTab  // update global route BEFORE any render function runs — this is what kills stale _guard() checks in renders that are no longer the active route
  if (window._PENDING_LEAD_ID) {
    var _pendingId = window._PENDING_LEAD_ID
    window._PENDING_LEAD_ID = null
    window._ACTIVE_ROUTE = 'lead_details'
    if (typeof viewLeadDetails === 'function') { viewLeadDetails(_pendingId); return }
  }
  if (activeTab === 'dashboard') return renderDashboard()
  if (activeTab === 'leads') return renderLeads()
  if (activeTab === 'action_board') { return (loadUsers ? loadUsers() : Promise.resolve()).then(function() { if (window._ACTIVE_ROUTE === 'action_board') renderActionBoard() }) }
  if (activeTab === 'assign_reassign') return renderAssignReassign()
  if (activeTab === 'recycle_queue') return renderAssignReassign('recycle_queue')
  if (activeTab === 'projects') return renderProjects()
  if (activeTab === 'team') return renderTeamManagement()
  if (activeTab === 'pipeline') return renderPipeline()
  if (activeTab === 'excel') return renderExcelUpload()
  if (activeTab === 'reports') return renderReports()
  if (activeTab === 'export') return renderExportLeads()
  if (activeTab === 'platform') return renderPlatformAdmin()
  if (activeTab === 'activitylogs') return renderActivityLogs()
  if (activeTab === 'lead_sources') return renderLeadSources()
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

  // Single-PWA LMS launch entry: /apps/lms
  if (path === '/apps/lms') {
    return { layer: 'lms-entry', product: 'lms' }
  }

  // Defensive normalization for malformed LMS aliases occasionally produced by
  // legacy URL parsing paths.
  if (path === '/apps/lms/apps') {
    history.replaceState({}, '', '/apps/lms')
    return { layer: 'lms-entry', product: 'lms' }
  }
  if (path === '/apps/lms/apps/login') {
    history.replaceState({}, '', '/login')
    return { layer: 'platform-login' }
  }

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
    if (appTenantLoginMatch[1] === 'lms' && appTenantLoginMatch[2] === 'apps') {
      history.replaceState({}, '', '/login')
      return { layer: 'platform-login' }
    }
    return {
      layer: 'tenant-login',
      product: appTenantLoginMatch[1],
      slug: authCanonicalTenantSlug(appTenantLoginMatch[2]),
      tenant_data_slug: authTenantDataSlug(appTenantLoginMatch[2]),
    }
  }

  // Lead detail sub-path: /apps/:product/:slug/:tab/lead/:leadId
  const appLeadMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)\/([^\/]+)\/lead\/(\d+)$/)
  if (appLeadMatch) {
    return {
      layer: 'tenant',
      product: appLeadMatch[1],
      slug: authCanonicalTenantSlug(appLeadMatch[2]),
      tenant_data_slug: authTenantDataSlug(appLeadMatch[2]),
      tab: authCanonicalTenantTab(appLeadMatch[3]),
      leadId: parseInt(appLeadMatch[4], 10),
    }
  }

  // Canonical tenant app path: /apps/:product/:slug or /apps/:product/:slug/:tab
  const appTenantMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)(?:\/([^\/]+))?$/)
  if (appTenantMatch) {
    if (appTenantMatch[1] === 'lms' && appTenantMatch[2] === 'apps') {
      history.replaceState({}, '', '/apps/lms')
      return { layer: 'lms-entry', product: 'lms' }
    }
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

  function _setTenantCookie(slug) {
    try {
      if (!slug) return
      document.cookie = 'lms_last_tenant_slug=' + encodeURIComponent(slug) + '; Path=/; Max-Age=2592000; SameSite=Lax; Secure'
    } catch (_e) {}
  }

  function _isValidTenantSlug(slug) {
    var s = String(slug || '').trim().toLowerCase()
    if (!s) return false
    if (!/^[a-z0-9-]{2,80}$/.test(s)) return false
    var reserved = { apps:1, app:1, login:1, lms:1, crm:1, products:1, api:1 }
    return !reserved[s]
  }

  function _readTenantCookie() {
    try {
      var parts = (document.cookie || '').split(';')
      for (var i = 0; i < parts.length; i++) {
        var kv = parts[i].trim()
        if (kv.indexOf('lms_last_tenant_slug=') === 0) {
          return decodeURIComponent(kv.substring('lms_last_tenant_slug='.length))
        }
      }
    } catch (_e) {}
    return ''
  }

  function _rememberTenantSlug(slug) {
    try {
      var canonical = authCanonicalTenantSlug(slug || '')
      if (!canonical || !_isValidTenantSlug(canonical)) return
      localStorage.setItem('lms_last_tenant_slug', canonical)
      _setTenantCookie(canonical)
    } catch (_e) {}
  }

  function _lastTenantSlug() {
    try {
      var fromStorage = authCanonicalTenantSlug(localStorage.getItem('lms_last_tenant_slug') || '')
      if (fromStorage && _isValidTenantSlug(fromStorage)) return fromStorage
      var fromCookie = authCanonicalTenantSlug(_readTenantCookie() || '')
      if (fromCookie && _isValidTenantSlug(fromCookie)) {
        localStorage.setItem('lms_last_tenant_slug', fromCookie)
        return fromCookie
      }
      // Purge corrupted hints so they can't keep poisoning route resolution.
      localStorage.removeItem('lms_last_tenant_slug')
      document.cookie = 'lms_last_tenant_slug=; Path=/; Max-Age=0; SameSite=Lax; Secure'
    } catch (_e) {}
    return ''
  }

  // ── LMS PWA launch entry ─────────────────────────────────────────────────
  if (route.layer === 'lms-entry') {
    if (token && user && authIsTenantUser()) {
      const tenantSlug = authCanonicalTenantSlug((user && user.tenant_slug) || _lastTenantSlug())
      if (tenantSlug) {
        _rememberTenantSlug(tenantSlug)
        history.replaceState({}, '', authBuildTenantTabPath(tenantSlug, 'lms', 'dashboard'))
        return _dispatchInner()
      }
    }
    if (token && user && authIsPlatformUser()) {
      history.replaceState({}, '', '/')
      return _dispatchInner()
    }
    var hintedTenant = _lastTenantSlug()
    if (hintedTenant) {
      loginRedirectPath = '/apps/lms'
      history.replaceState({}, '', authBuildTenantLoginPath(hintedTenant, 'lms'))
      _setPublicLoginMode(true)
      renderLogin({ type: 'tenant', slug: hintedTenant, product: 'lms' })
      return
    }
    loginRedirectPath = '/apps/lms'
    history.replaceState({}, '', '/login')
    _setPublicLoginMode(true)
    clearTenantContext()
    renderLogin({ type: 'platform' })
    return
  }

  // ── Login pages (no auth required) ─────────────────────────────────────────
  if (route.layer === 'platform-login') {
    // Already authenticated → route by user type
    if (token && user) {
      if (authIsTenantUser() && user.tenant_slug) {
        // Tenant users must not land on the platform dashboard; send them to
        // their own app so the platform-route guard never clears their session.
        history.replaceState({}, '', authBuildTenantAppPath(user.tenant_slug, 'lms'))
      } else {
        history.replaceState({}, '', '/')
      }
      return _dispatchInner()
    }
    _setPublicLoginMode(true)
    clearTenantContext()
    renderLogin({ type: 'platform' })
    return
  }
  if (route.layer === 'tenant-login') {
    _rememberTenantSlug(route.slug)
    // Already authenticated → go to tenant LMS
    if (token && user) {
      const slug = (user && user.tenant_slug) || route.slug
      _rememberTenantSlug(slug)
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
    _rememberTenantSlug(route.slug)
    platformTenantSlug = route.tenant_data_slug || authTenantDataSlug(route.slug)
    // Sync currentProduct from URL so nav items and content match the route
    if (route.product) {
      currentProduct = route.product
      localStorage.setItem('current_product', route.product)
    }
    activeTab = route.tab || 'dashboard'
    if (route.leadId) {
      var _TAB_SLUGS = { action_board: 'action-board', recycle_queue: 'recycle-queue', activitylogs: 'activity-logs' }
      var _tabSlug = _TAB_SLUGS[activeTab] || activeTab
      window._PENDING_LEAD_ID = route.leadId
      window._LEAD_DETAIL_ORIGIN = activeTab
      window._LEAD_ORIGIN_URL = authBuildTenantTabPath(platformTenantSlug, currentProduct, _tabSlug)
    }
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

