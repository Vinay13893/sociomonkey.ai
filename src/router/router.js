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
  if (activeTab === 'lead_sources') {
    if (currentProduct === 'lms' && typeof renderLmsLeadSources === 'function') return renderLmsLeadSources()
    return renderLeadSources()
  }
  if (activeTab === 'profile') return renderMyProfile()
  return renderDashboard()
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

const ROUTER_PLATFORM_HOSTS = new Set(['app.sociomonkey.com'])
const ROUTER_LMS_HOSTS = new Set(['lms.sociomonkey.com'])

function _routerHostName() {
  return String(window.location.hostname || '').trim().toLowerCase()
}

function _routerHostKind() {
  var host = _routerHostName()
  if (!host) return 'other'
  if (ROUTER_PLATFORM_HOSTS.has(host)) return 'platform'
  if (ROUTER_LMS_HOSTS.has(host)) return 'lms'
  if (host === 'localhost' || host === '127.0.0.1') return 'dev'
  return 'other'
}

function parseRoute() {
  const raw  = window.location.pathname
  const path = raw.replace(/\/+$/, '') || '/'

  function _canonicalLeadSourcesView(view) {
    var rawView = String(view || '').trim().toLowerCase()
    if (rawView === 'validate') return 'validation'
    return rawView
  }

  if (path === '/') return { layer: 'root-entry' }

  // Legacy app-centric entry points are rewritten into the new LMS path model.
  if (path === '/apps/lms' || path === '/apps/lms/apps') {
    history.replaceState({}, '', '/')
    return { layer: 'root-entry' }
  }

  if (path === '/apps/lms/apps/login') {
    history.replaceState({}, '', '/login')
    return { layer: 'platform-login' }
  }

  // Legacy canonical tenant login path: /apps/:product/:slug/login
  const appTenantLoginMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)\/login$/)
  if (appTenantLoginMatch) {
    var _legacyLoginPath = authBuildTenantLoginPath(appTenantLoginMatch[2], appTenantLoginMatch[1])
    history.replaceState({}, '', _legacyLoginPath)
    return {
      layer: 'tenant-login',
      product: 'lms',
      slug: authCanonicalTenantSlug(appTenantLoginMatch[2]),
      tenant_data_slug: authTenantDataSlug(appTenantLoginMatch[2]),
    }
  }

  // Legacy lead detail path: /apps/:product/:slug/:tab/lead/:leadId
  const appLeadMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)\/([^\/]+)\/lead\/(\d+)$/)
  if (appLeadMatch) {
    var _legacyLeadPath = authBuildTenantTabPath(appLeadMatch[2], appLeadMatch[1], appLeadMatch[3]) + '/lead/' + appLeadMatch[4]
    history.replaceState({}, '', _legacyLeadPath)
    return {
      layer: 'tenant',
      product: 'lms',
      slug: authCanonicalTenantSlug(appLeadMatch[2]),
      tenant_data_slug: authTenantDataSlug(appLeadMatch[2]),
      tab: authCanonicalTenantTab(appLeadMatch[3]),
      leadId: parseInt(appLeadMatch[4], 10),
    }
  }

  // Legacy lead-sources sub-view: /apps/:product/:slug/lead-sources/:view
  const appLeadSourcesViewMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)\/lead-sources\/([^\/]+)$/)
  if (appLeadSourcesViewMatch) {
    var _legacyLeadSourcesPath = authBuildTenantTabPath(appLeadSourcesViewMatch[2], appLeadSourcesViewMatch[1], 'lead_sources') + '/' + _canonicalLeadSourcesView(appLeadSourcesViewMatch[3])
    history.replaceState({}, '', _legacyLeadSourcesPath)
    return {
      layer: 'tenant',
      product: 'lms',
      slug: authCanonicalTenantSlug(appLeadSourcesViewMatch[2]),
      tenant_data_slug: authTenantDataSlug(appLeadSourcesViewMatch[2]),
      tab: 'lead_sources',
      leadSourcesView: _canonicalLeadSourcesView(appLeadSourcesViewMatch[3]),
    }
  }

  // Legacy canonical tenant app path: /apps/:product/:slug or /apps/:product/:slug/:tab
  const appTenantMatch = path.match(/^\/apps\/([^\/]+)\/([^\/]+)(?:\/([^\/]+))?$/)
  if (appTenantMatch) {
    var _canonicalSlug = authCanonicalTenantSlug(appTenantMatch[2])
    var _canonicalTab = authCanonicalTenantTab(appTenantMatch[3] || 'dashboard')
    var _canonicalPath = authBuildTenantTabPath(_canonicalSlug, appTenantMatch[1], _canonicalTab)
    history.replaceState({}, '', _canonicalPath)
    return {
      layer: 'tenant',
      product: 'lms',
      slug: _canonicalSlug,
      tenant_data_slug: authTenantDataSlug(appTenantMatch[2]),
      tab: _canonicalTab,
    }
  }

  // Explicit platform paths
  if (PLATFORM_ROUTE_VIEWS[path]) {
    return { layer: 'platform', view: PLATFORM_ROUTE_VIEWS[path] }
  }

  // Product hub: /products/:code
  const productHubMatch = path.match(/^\/products\/([^\/]+)$/)
  if (productHubMatch) {
    platformContext = { productCode: productHubMatch[1] }
    return { layer: 'platform', view: 'product-hub' }
  }

  // Platform login page
  if (path === '/login') return { layer: 'platform-login' }

  // New canonical demo login path
  if (path === '/demo/login') {
    return { layer: 'demo-login', product: 'lms' }
  }

  // Legacy demo login path: /demo/:product/login
  const demoLoginMatch = path.match(/^\/demo\/([^\/]+)\/login$/)
  if (demoLoginMatch) {
    history.replaceState({}, '', '/demo/login')
    return { layer: 'demo-login', product: 'lms' }
  }

  // New canonical demo app path: /demo or /demo/:tab
  const demoAppMatch = path.match(/^\/demo(?:\/([^\/]+))?$/)
  if (demoAppMatch) {
    return {
      layer: 'demo',
      product: 'lms',
      slug: 'demo',
      tenant_data_slug: 'demo',
      tab: authCanonicalTenantTab(demoAppMatch[1] || 'dashboard'),
    }
  }

  // Tenant login page: /:slug/login (canonical)
  const tenantLoginSimpleMatch = path.match(/^\/([^\/]+)\/login$/)
  if (tenantLoginSimpleMatch) {
    const legacySlug = tenantLoginSimpleMatch[1]
    if (legacySlug === 'demo') {
      history.replaceState({}, '', '/demo/login')
      return { layer: 'demo-login', product: 'lms' }
    }
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

  // Tenant lead detail: /:slug/:tab/lead/:leadId
  const tenantLeadMatch = path.match(/^\/([^\/]+)\/([^\/]+)\/lead\/(\d+)$/)
  if (tenantLeadMatch) {
    return {
      layer: 'tenant',
      product: 'lms',
      slug: authCanonicalTenantSlug(tenantLeadMatch[1]),
      tenant_data_slug: authTenantDataSlug(tenantLeadMatch[1]),
      tab: authCanonicalTenantTab(tenantLeadMatch[2]),
      leadId: parseInt(tenantLeadMatch[3], 10),
    }
  }

  // Tenant lead-sources sub-view: /:slug/lead-sources/:view
  const tenantLeadSourcesViewMatch = path.match(/^\/([^\/]+)\/lead-sources\/([^\/]+)$/)
  if (tenantLeadSourcesViewMatch) {
    return {
      layer: 'tenant',
      product: 'lms',
      slug: authCanonicalTenantSlug(tenantLeadSourcesViewMatch[1]),
      tenant_data_slug: authTenantDataSlug(tenantLeadSourcesViewMatch[1]),
      tab: 'lead_sources',
      leadSourcesView: _canonicalLeadSourcesView(tenantLeadSourcesViewMatch[2]),
    }
  }

  // Tenant app path: /:slug or /:slug/:tab
  const tenantAppMatch = path.match(/^\/([^\/]+)(?:\/([^\/]+))?$/)
  if (tenantAppMatch) {
    var slug = tenantAppMatch[1]
    var tab = authCanonicalTenantTab(tenantAppMatch[2] || 'dashboard')
    var platformReserved = {
      login: 1,
      dashboard: 1,
      applications: 1,
      users: 1,
      organizations: 1,
      analytics: 1,
      billing: 1,
      integrations: 1,
      automation: 1,
      settings: 1,
      'audit-logs': 1,
      support: 1,
      products: 1,
      api: 1,
      app: 1,
      apps: 1,
    }
    if (!platformReserved[slug]) {
      var canonicalSlug = authCanonicalTenantSlug(slug)
      var canonicalPath = authBuildTenantTabPath(canonicalSlug, 'lms', tab)
      if (canonicalPath !== path) history.replaceState({}, '', canonicalPath)
      return {
        layer: 'tenant',
        product: 'lms',
        slug: canonicalSlug,
        tenant_data_slug: authTenantDataSlug(slug),
        tab: tab,
      }
    }
  }

  return { layer: 'unknown' }
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
            ? '<button onclick="window.location.href=authBuildTenantAppUrl(user.tenant_slug,\'lms\')" class="button" style="font-size:14px;">Go to My App</button>'
            : '') +
'<button onclick="authClearSession();clearTenantContext();history.replaceState({},' + "''" + ',\'/login\');if(typeof _setPublicLoginMode===\'function\'){_setPublicLoginMode(true)};if(typeof renderLogin===\'function\'){renderLogin({ type: \'platform\' })};dispatch()" class="button" style="font-size:14px;background:#64748b;color:#fff;">Sign Out</button>'
        '</div>' +
      '</div>' +
    '</div>'
}

function _showLoginContextMessage(message) {
  setTimeout(function () {
    var el = document.getElementById('loginError')
    if (el) {
      el.textContent = message || 'Please sign in through the correct portal.'
      el.style.display = 'block'
    }
  }, 0)
}

function renderDomainError(title, message) {
  const platRoot = document.getElementById('platformRoot')
  const tenantLayout = document.getElementById('tenantLayout')
  if (platRoot) platRoot.style.display = 'none'
  if (tenantLayout) tenantLayout.style.display = 'none'
  _setPublicLoginMode(false)
  clearTenantContext()

  var publicRoot = document.getElementById('publicLoginRoot')
  if (!publicRoot) {
    publicRoot = document.createElement('div')
    publicRoot.id = 'publicLoginRoot'
    document.body.appendChild(publicRoot)
  }
  publicRoot.style.display = 'block'
  publicRoot.innerHTML =
    '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f8fafc;padding:24px;">' +
      '<div class="card" style="max-width:520px;width:100%;text-align:center;padding:36px 28px;">' +
        '<div style="font-size:42px;margin-bottom:12px;">&#9888;</div>' +
        '<h2 style="margin:0 0 10px;color:#0f172a;">' + (title || 'Page Not Available') + '</h2>' +
        '<p style="margin:0;color:#475569;font-size:14px;line-height:1.55;">' + (message || 'This URL is not available on this domain.') + '</p>' +
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
  const hostKind = _routerHostKind()
  _PERF.mark('parseRoute')
  const route = parseRoute()
  _PERF.end('parseRoute')

  if (hostKind === 'other') {
    renderDomainError('Invalid Domain', 'Use app.sociomonkey.com for platform access and lms.sociomonkey.com for tenant/demo access.')
    return
  }

  if (route.layer === 'unknown') {
    renderDomainError('Invalid URL', 'This URL is not defined for the Sociomonkey platform.')
    return
  }

  if (route.layer === 'root-entry') {
    if (hostKind === 'platform' || hostKind === 'dev') {
      route.layer = 'platform'
      route.view = 'dashboard'
    } else {
      route.layer = 'lms-entry'
      route.product = 'lms'
    }
  }

  if (hostKind === 'platform' && route.layer !== 'platform' && route.layer !== 'platform-login' && route.layer !== 'product-hub') {
    renderDomainError('Wrong Portal', 'Tenant and demo routes are only available on lms.sociomonkey.com.')
    return
  }

  if (hostKind === 'lms' && route.layer !== 'tenant' && route.layer !== 'tenant-login' && route.layer !== 'demo' && route.layer !== 'demo-login' && route.layer !== 'lms-entry') {
    renderDomainError('Wrong Portal', 'Platform routes are only available on app.sociomonkey.com.')
    return
  }

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
    var reserved = { app:1, login:1, lms:1, products:1, api:1 }
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
      loginRedirectPath = '/'
      history.replaceState({}, '', authBuildTenantLoginPath(hintedTenant, 'lms'))
      _setPublicLoginMode(true)
      renderLogin({ type: 'tenant', slug: hintedTenant, product: 'lms' })
      return
    }
    renderDomainError('Tenant URL Required', 'Open your tenant URL like /ganga-realty/login or /demo/login on lms.sociomonkey.com.')
    return
  }

  // ── Login pages (no auth required) ─────────────────────────────────────────
  if (route.layer === 'platform-login') {
    // Already authenticated → route by user type
    if (token && user) {
      if (authHasLoginContext('platform')) {
        history.replaceState({}, '', '/')
        return _dispatchInner()
      }
      authClearSession()
      clearTenantContext()
      _setPublicLoginMode(true)
      renderLogin({ type: 'platform' })
      _showLoginContextMessage('This account must sign in through the correct portal.')
      return
    }
    _setPublicLoginMode(true)
    clearTenantContext()
    renderLogin({ type: 'platform' })
    return
  }
  if (route.layer === 'demo-login') {
    if (token && user) {
      if (authHasLoginContext('demo')) {
        history.replaceState({}, '', '/demo')
        return _dispatchInner()
      }
      authClearSession()
      clearTenantContext()
      _setPublicLoginMode(true)
      renderLogin({ type: 'demo', product: route.product || 'lms' })
      _showLoginContextMessage('This account must sign in through the correct portal.')
      return
    }
    _setPublicLoginMode(true)
    clearTenantContext()
    renderLogin({ type: 'demo', product: route.product || 'lms' })
    return
  }
  if (route.layer === 'tenant-login') {
    if ((route.product || 'lms') !== 'lms') {
      history.replaceState({}, '', authBuildTenantLoginPath(route.slug, 'lms'))
      route.product = 'lms'
    }
    _rememberTenantSlug(route.slug)
    // Already authenticated → go to tenant LMS
    if (token && user) {
      if (authHasLoginContext('tenant') && authCanonicalTenantSlug(user.tenant_slug) === authCanonicalTenantSlug(route.slug)) {
        const slug = (user && user.tenant_slug) || route.slug
        _rememberTenantSlug(slug)
        history.replaceState({}, '', authBuildTenantAppPath(slug, 'lms'))
        return _dispatchInner()
      }
      authClearSession()
      _setPublicLoginMode(true)
      renderLogin({ type: 'tenant', slug: route.slug, product: route.product })
      _showLoginContextMessage('This account must sign in through the correct portal.')
      return
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
  if (token && user && !authHasLoginContext('platform') && (route.layer === 'platform' || route.layer === 'product-hub')) {
    authClearSession()
    clearTenantContext()
    loginRedirectPath = ''
    history.replaceState({}, '', '/login')
    _setPublicLoginMode(true)
    renderLogin({ type: 'platform' })
    _showLoginContextMessage('This account must sign in through the platform portal.')
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
    } else if (loginRoute.layer === 'demo-login') {
      clearTenantContext()
      renderLogin({ type: 'demo', product: loginRoute.product || 'lms' })
    } else {
      clearTenantContext()
      renderLogin({ type: 'platform' })
    }
    return
  }

  _setPublicLoginMode(false)

  // ── Access control check ────────────────────────────────────────────────────
  if (!authCanAccess(route)) {
    const loginPath = authGetLoginPath(route)
    authClearSession()
    clearTenantContext()
    loginRedirectPath = ''
    history.replaceState({}, '', loginPath)
    _setPublicLoginMode(true)
    const retryRoute = parseRoute()
    if (retryRoute.layer === 'tenant-login') {
      renderLogin({ type: 'tenant', slug: retryRoute.slug, product: retryRoute.product })
    } else if (retryRoute.layer === 'demo-login') {
      renderLogin({ type: 'demo', product: retryRoute.product || 'lms' })
    } else {
      renderLogin({ type: 'platform' })
    }
    _showLoginContextMessage('Your session is not valid for this portal. Please sign in again.')
    return
  }

  // ── Platform routes ─────────────────────────────────────────────────────────
  if (authIsPlatformUser() && authHasLoginContext('platform') && route.layer !== 'tenant' && route.layer !== 'demo') {
    platformView = route.view || 'dashboard'
    clearTenantContext()
    // platformContext already set by parseRoute() for product-hub
    renderPlatformLayout(platformView)
    return
  }

  // ── Tenant routes (including platform owner drilling in via product hub) ────
  if (route.layer === 'tenant' || route.layer === 'demo') {
    if (route.layer === 'tenant' && (route.product || 'lms') !== 'lms') {
      var normalizedPath = ''
      if (route.leadId) {
        var _TENANT_TAB_SLUGS = { action_board: 'action-board', recycle_queue: 'recycle-queue', activitylogs: 'activity-logs' }
        var _leadTabSlug = _TENANT_TAB_SLUGS[route.tab] || route.tab || 'dashboard'
        normalizedPath = authBuildTenantTabPath(route.slug, 'lms', _leadTabSlug) + '/lead/' + route.leadId
      } else if (route.tab === 'lead_sources' && route.leadSourcesView) {
        normalizedPath = authBuildTenantTabPath(route.slug, 'lms', 'lead-sources') + '/' + route.leadSourcesView
      } else {
        normalizedPath = authBuildTenantTabPath(route.slug, 'lms', route.tab || 'dashboard')
      }
      history.replaceState({}, '', normalizedPath)
      route.product = 'lms'
    }
    _rememberTenantSlug(route.slug)
    platformTenantSlug = route.tenant_data_slug || authTenantDataSlug(route.slug)
    currentProduct = route.layer === 'demo' ? (route.product || 'lms') : 'lms'
    localStorage.setItem('current_product', currentProduct)
    activeTab = route.tab || 'dashboard'
    if (activeTab === 'product_home') {
      activeTab = 'dashboard'
      history.replaceState({}, '', authBuildTenantTabPath(route.slug, 'lms', 'dashboard'))
    }
    window._LS_ROUTE_VIEW = route.leadSourcesView || null
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
  window.location.href = authBuildTenantAppUrl(slug, 'lms')
}

// Handle browser back/forward
window.addEventListener('popstate', () => {
  if (user) dispatch()
})

