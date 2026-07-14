// API FUNCTIONS
// ============================================================================

function _apiAuthHeaders() {
  if (!token) return {}
  const headers = { Authorization: `Bearer ${token}` }
  if (currentProduct) {
    headers['X-Product-Slug'] = currentProduct
  }
  // When platform owner is viewing a tenant, tell the backend which tenant's data to return
  if (typeof platformTenantSlug === 'string' && platformTenantSlug) {
    headers['X-Tenant-Slug'] = platformTenantSlug
  }
  return headers
}

function _apiJsonHeaders(extra) {
  return Object.assign({ 'Content-Type': 'application/json' }, extra || {})
}

var _perfReqSeq = 0

function _perfRound(ms) {
  return Math.round(Number(ms || 0) * 100) / 100
}

function _perfTrackedRoute(path, method) {
  var normalizedMethod = String(method || 'GET').toUpperCase()
  if (normalizedMethod === 'POST' && path === '/auth/login') return 'login'
  if (normalizedMethod === 'GET' && (path === '/leads' || path.indexOf('/leads?') === 0)) return 'leads'
  if (normalizedMethod === 'GET' && path.indexOf('/leads/dashboard/stats') === 0) return 'dashboard_stats'
  return ''
}

function _perfLog(routeKey, stage, payload) {
  if (!routeKey) return
  if (!window.DEBUG_PERF) return
  console.log('[PERF]', Object.assign({ route: routeKey, stage: stage }, payload || {}))
}

function _perfStartRequest(routeKey, path, method) {
  if (!routeKey || typeof performance === 'undefined') return null
  var trace = {
    id: 'perf-' + (++_perfReqSeq),
    route: routeKey,
    path: path,
    method: String(method || 'GET').toUpperCase(),
    browserRequestStartPerf: performance.now(),
    browserRequestStartAtMs: Date.now(),
  }
  _perfLog(routeKey, 'browser_request_start', {
    traceId: trace.id,
    method: trace.method,
    path: path,
    browserRequestStartAtMs: trace.browserRequestStartAtMs,
  })
  return trace
}

function _perfMarkSent(trace) {
  if (!trace || typeof performance === 'undefined') return
  trace.apiRequestSentPerf = performance.now()
  trace.apiRequestSentAtMs = Date.now()
  _perfLog(trace.route, 'api_request_sent', {
    traceId: trace.id,
    apiRequestSentAtMs: trace.apiRequestSentAtMs,
  })
}

function _perfReadResponse(trace, res) {
  if (!trace || typeof performance === 'undefined' || !res) return null
  trace.browserResponseReceivedPerf = performance.now()
  trace.browserResponseReceivedAtMs = Date.now()

  var backendMs = Number(res.headers.get('X-Perf-Backend-Duration-Ms') || 0)
  var dbMs = Number(res.headers.get('X-Perf-Db-Duration-Ms') || 0)
  var totalMs = _perfRound(trace.browserResponseReceivedPerf - trace.browserRequestStartPerf)
  var summary = {
    traceId: trace.id,
    requestId: res.headers.get('X-Perf-Request-Id') || '',
    browserResponseReceivedAtMs: trace.browserResponseReceivedAtMs,
    serverRequestReceivedAtMs: Number(res.headers.get('X-Perf-Request-Received-At-Ms') || 0),
    serverResponseSentAtMs: Number(res.headers.get('X-Perf-Response-Sent-At-Ms') || 0),
    totalRequestDurationMs: totalMs,
    backendProcessingDurationMs: _perfRound(backendMs),
    databaseDurationMs: _perfRound(dbMs),
    networkDurationMs: _perfRound(Math.max(0, totalMs - backendMs)),
    dbQueryCount: Number(res.headers.get('X-Perf-Db-Query-Count') || 0),
  }
  trace.summary = summary
  _perfLog(trace.route, 'browser_response_received', summary)
  return summary
}

function _perfMarkRenderComplete(routeKey, trace, extra) {
  if (!routeKey || !trace || typeof performance === 'undefined') return
  _perfLog(routeKey, 'dashboard_render_complete', Object.assign({}, trace.summary || {}, {
    totalToRenderDurationMs: _perfRound(performance.now() - trace.browserRequestStartPerf),
    renderDurationMs: typeof trace.browserResponseReceivedPerf === 'number'
      ? _perfRound(performance.now() - trace.browserResponseReceivedPerf)
      : undefined,
  }, extra || {}))
}

window._perfLog = _perfLog
window._perfStartRequest = _perfStartRequest
window._perfMarkSent = _perfMarkSent
window._perfReadResponse = _perfReadResponse
window._perfMarkRenderComplete = _perfMarkRenderComplete

function _apiIsLocalOfflineHost() {
  var host = String((window.location && window.location.hostname) || '').toLowerCase()
  return host === '127.0.0.1' || host === 'localhost'
}

function _apiOfflineToken(user, loginContext) {
  function b64(obj) {
    return btoa(JSON.stringify(obj)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  }
  var now = Math.floor(Date.now() / 1000)
  return [
    b64({ alg: 'none', typ: 'JWT' }),
    b64({ sub: user.id, role: user.role, tenant_id: user.tenant_id, ctx: loginContext, iat: now, exp: now + 86400 }),
    'offline'
  ].join('.')
}

function _apiOfflineLoginData(email, tenantSlug, loginContext, productSlug) {
  var slug = tenantSlug || 'ganga-realty'
  var userObj = {
    id: 1,
    name: 'Ganga Realty Admin',
    email: email || 'offline@sociomonkey.local',
    phone: '',
    role: 'superadmin',
    tenant_id: 1,
    tenant_name: 'Ganga Realty',
    tenant_slug: slug,
    manager_id: null,
    manager_name: null,
    assigned_manager_id: null,
    assigned_manager_name: null,
    is_active: true,
    created_at: new Date().toISOString(),
    last_login: new Date().toISOString(),
    offline: true,
  }
  var ctx = loginContext || 'tenant'
  return {
    token: _apiOfflineToken(userObj, ctx),
    refresh_token: null,
    user: userObj,
    login_context: ctx,
    products: [
      {
        slug: productSlug || 'lms',
        name: 'Lead Management System (Offline)',
        fullName: 'Lead Management System',
        icon: '📋',
        color: '#1e3a5f',
      },
    ],
    offline: true,
  }
}

async function _apiRequest(path, opts) {
  const options = opts || {}
  const retries = typeof options.retries === 'number' ? options.retries : 1
  const timeoutMs = typeof options.timeoutMs === 'number' ? options.timeoutMs : 12000
  const method = String(options.method || 'GET').toUpperCase()
  const perfRoute = _perfTrackedRoute(path, method)

  let lastErr = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    let timedOut = false
    let perfTrace = null
    const timer = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, timeoutMs)

    try {
      const fetchOptions = Object.assign({}, options, { signal: controller.signal })
      delete fetchOptions.retries
      delete fetchOptions.timeoutMs

      perfTrace = _perfStartRequest(perfRoute, path, method)
      _perfMarkSent(perfTrace)

      const res = await fetch(`${API_BASE}${path}`, fetchOptions)
      clearTimeout(timer)
      _perfReadResponse(perfTrace, res)

      const ct = (res.headers.get('content-type') || '').toLowerCase()
      const payload = ct.indexOf('application/json') !== -1 ? await res.json() : null

      if (res.status === 401) {
        authClearSession()
        if (typeof dispatch === 'function') dispatch()
      }

      if (!res.ok) {
        const err = new Error((payload && (payload.message || payload.error)) || 'Request failed')
        err.status = res.status
        err.payload = payload
        throw err
      }

      return payload
    } catch (err) {
      clearTimeout(timer)
      if (perfRoute) {
        _perfLog(perfRoute, 'request_error', {
          path: path,
          method: method,
          attempt: attempt + 1,
          message: (err && err.message) || 'Request failed',
          errorName: (err && err.name) || '',
        })
      }
      if (timedOut && err && err.name === 'AbortError') {
        const timeoutErr = new Error('Request timed out. Please try again.')
        timeoutErr.name = 'TimeoutError'
        lastErr = timeoutErr
      } else {
        lastErr = err
      }

      // Retry transient network/timeout errors only
      const isAbort = err && err.name === 'AbortError'
      const isNetwork = !err || typeof err.status === 'undefined'
      const canRetry = attempt < retries && (isAbort || isNetwork)
      if (!canRetry) break
    }
  }

  throw lastErr || new Error('Request failed')
}

async function login(email, password, remember, tenantSlug, loginCtx, productSlug) {
  let data
  try {
    const loginContext = authNormalizeLoginContext(loginCtx) || (tenantSlug ? 'tenant' : 'platform')
    const body = {
      email: email,
      password: password,
      remember: !!remember,
      tenant_slug: tenantSlug || '',
      login_context: loginContext,
    }
    if (tenantSlug) body.tenant_slug = tenantSlug
    if (productSlug) body.product_slug = productSlug
    data = await _apiRequest('/auth/login', {
      method: 'POST',
      headers: _apiJsonHeaders(),
      body: JSON.stringify(body),
      retries: 1,
      timeoutMs: 45000,
    })
  } catch (e) {
    if (_apiIsLocalOfflineHost()) {
      var loginContext = authNormalizeLoginContext(loginCtx) || (tenantSlug ? 'tenant' : 'platform')
      data = _apiOfflineLoginData(email, tenantSlug, loginContext, productSlug)
    } else {
    const msg = (e && e.message) || 'Login failed. Please try again.'
    const errEl = document.getElementById('loginError')
    if (errEl) {
      errEl.textContent = msg
      errEl.style.display = 'block'
    }
    if (typeof showToast === 'function') showToast(msg, 'error')
    return
    }
  }

  var sessionContext = data.login_context || loginCtx
  authSetSession(data.token, data.user, !!remember, data.refresh_token || null, sessionContext)
  // iOS Web Push permission is most reliable when requested immediately after
  // a user-initiated login action.
  try {
    if (typeof pushRequestPermission === 'function') {
      pushRequestPermission().catch(function () {})
    }
  } catch (_e) {}
  availableProducts = data.products || []
  if (availableProducts.length > 0) {
    const hasLms = availableProducts.find(p => p.slug === 'lms')
    currentProduct = hasLms ? 'lms' : ((availableProducts[0] && availableProducts[0].slug) || 'lms')
    localStorage.setItem('current_product', currentProduct)
  }
  // Persist products so the sidebar can render instantly on the next page load
  // without waiting for the background loadMe() call to complete.
  try {
    var _ps = localStorage.getItem('lms_token') ? localStorage : sessionStorage
    _ps.setItem('lms_products', JSON.stringify(availableProducts))
  } catch (_e) {}
  await loadMe()
  authScheduleExpiry()
  var requestedPath = loginRedirectPath
  loginRedirectPath = ''
  if (requestedPath && requestedPath !== '/login' && !requestedPath.endsWith('/login')) {
    history.pushState({}, '', requestedPath)
  } else if (sessionContext === 'platform') {
    history.replaceState({}, '', '/')
  } else if (sessionContext === 'tenant' && user && user.tenant_slug) {
    const preferredProduct = availableProducts.find(p => p.slug === 'lms') ? 'lms' : ((availableProducts[0] && availableProducts[0].slug) || 'lms')
    history.replaceState({}, '', authBuildTenantAppPath(user.tenant_slug, preferredProduct))
  } else if (sessionContext === 'demo') {
    history.replaceState({}, '', '/demo')
  }
  dispatch()
}

async function loadMe() {
  let data
  try {
    data = await _apiRequest('/auth/me', {
      headers: _apiAuthHeaders(),
      retries: 0,
      timeoutMs: 30000,
    })
  } catch (e) {
    // _apiRequest already clears session on definitive auth failure (401).
    // Keep session on transient abort/network issues to avoid false logouts.
    var isTransient = !!e && (
      e.name === 'AbortError' ||
      e.name === 'TimeoutError' ||
      typeof e.status === 'undefined'
    )
    if (isTransient) {
      return
    }
    authClearSession()
    if (typeof dispatch === 'function') dispatch(); else render()
    return
  }

  user = data.user
  if (data.login_context) loginContext = authNormalizeLoginContext(data.login_context)
  if (data.products) {
    availableProducts = data.products
  }
  try {
    var _sessionStore = localStorage.getItem('lms_token') ? localStorage : sessionStorage
    _sessionStore.setItem('lms_user', JSON.stringify(user))
    _sessionStore.setItem('lms_products', JSON.stringify(availableProducts || []))
  } catch (_e) {}
  // Ensure activeTab is valid for this user's role
  if (user && user.role === 'platform_owner' && activeTab === 'dashboard') {
    activeTab = 'platform'
  }
}

// ── In-memory data caches (5-minute TTL, invalidated on tenant context switch) ──
var _CACHE_TTL_MS = 5 * 60 * 1000
var _LEADS_CACHE_TTL_MS = 15 * 1000
var _cacheSlug = null
var _projectsCache = null; var _projectsCacheTs = 0
var _leadsCache    = null; var _leadsCacheTs    = 0
var _leadsPageCache = {}
var _leadsInFlight = {}
var _leadsPagination = { page: 1, page_size: 25, total: 0, total_pages: 1, has_next: false, has_prev: false }
var _leadsLastServerTime = ''
var _usersCache    = null; var _usersCacheTs    = 0
var _metaRealtimeSyncTs = 0
var _metaRealtimeSyncPromise = null
var _META_REALTIME_SYNC_COOLDOWN_MS = 15 * 60 * 1000
var _metaCreatedAtBackfillTs = 0
var _META_CREATED_AT_BACKFILL_INTERVAL_MS = 6 * 60 * 60 * 1000

function _cacheValid(ts) { return ts > 0 && (Date.now() - ts) < _CACHE_TTL_MS }
function _leadsCacheValid(ts) { return ts > 0 && (Date.now() - ts) < _LEADS_CACHE_TTL_MS }

function _checkCacheTenant() {
  // Bust all caches when the active tenant context changes (platform owner switching tenants)
  var slug = (typeof platformTenantSlug === 'string' && platformTenantSlug) ? platformTenantSlug : ''
  if (_cacheSlug !== slug) {
    _projectsCacheTs = 0; _leadsCacheTs = 0; _leadsPageCache = {}; _leadsInFlight = {}; _leadsLastServerTime = ''; _usersCacheTs = 0
    _cacheSlug = slug
  }
}

// Call before any mutation that changes lead data (delete, edit, assign, import)
function invalidateLeadsCache() { _leadsCacheTs = 0; _leadsPageCache = {}; _leadsInFlight = {} }
function invalidateProjectsCache() { _projectsCacheTs = 0 }

async function _maybeRealtimeMetaSync() {
  var role = String((user && user.role) || '').toLowerCase()
  if (role !== 'superadmin' && role !== 'platform_owner') return false
  if (_metaRealtimeSyncPromise) return _metaRealtimeSyncPromise

  var now = Date.now()
  var tenantKey = String((user && user.tenant_slug) || platformTenantSlug || (user && user.tenant_id) || 'tenant')
  var storageKey = 'lms_meta_auto_fetch_v1_' + tenantKey
  var storedTs = 0
  try { storedTs = Number(localStorage.getItem(storageKey) || 0) } catch (_e) {}
  var lastTs = Math.max(_metaRealtimeSyncTs, storedTs)
  if ((now - lastTs) < _META_REALTIME_SYNC_COOLDOWN_MS) return false
  _metaRealtimeSyncTs = now
  try { localStorage.setItem(storageKey, String(now)) } catch (_e) {}

  _metaRealtimeSyncPromise = (async function () {
    try {
    if (!_metaCreatedAtBackfillTs || (now - _metaCreatedAtBackfillTs) >= _META_CREATED_AT_BACKFILL_INTERVAL_MS) {
      _metaCreatedAtBackfillTs = now
      _apiRequest('/lead-sources/meta/backfill/lead-created-at?limit=4000', {
        method: 'POST',
        headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
        retries: 0,
        timeoutMs: 30000,
      }).catch(function () {})
    }

    var srcData = await _apiRequest('/lead-sources?include_inactive=true', {
      headers: _apiAuthHeaders(),
      retries: 0,
      timeoutMs: 12000,
    })
    var activeMeta = (srcData.sources || []).filter(function (s) {
      return s && s.source_type === 'meta' && s.is_active
    })
    for (var i = 0; i < activeMeta.length; i++) {
      var s = activeMeta[i]
      var mappingData = await _apiRequest('/lead-sources/' + s.id + '/forms/mappings', {
        headers: _apiAuthHeaders(),
        retries: 0,
        timeoutMs: 12000,
      })
      var mappedFormIds = (mappingData.rows || []).filter(function (row) {
        return row && row.form_id && row.is_active !== false && row.project_id
      }).map(function (row) {
        return String(row.form_id)
      })
      if (!mappedFormIds.length) continue

      await _apiRequest('/lead-sources/' + s.id + '/meta/pull-recent', {
        method: 'POST',
        headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
        body: JSON.stringify({
          per_form_limit: 100,
          page_size: 100,
          max_pages: 1,
          full_history: false,
          form_ids: mappedFormIds,
        }),
        retries: 0,
        timeoutMs: 55000,
      })
    }
      return true
    } catch (_e) {
      _metaRealtimeSyncTs = 0
      try { localStorage.removeItem(storageKey) } catch (_ignored) {}
      return false
    } finally {
      _metaRealtimeSyncPromise = null
    }
  })()
  return _metaRealtimeSyncPromise
}

async function loadProjects() {
  _checkCacheTenant()
  if (_cacheValid(_projectsCacheTs)) { projects = _projectsCache; return }
  try {
    const data = await _apiRequest('/projects', {
      headers: _apiAuthHeaders(),
      retries: 1,
      timeoutMs: 15000,
    })
    projects = data.projects || []
    _projectsCache = projects; _projectsCacheTs = Date.now()
  } catch (_e) {
    projects = _projectsCache || []
  }
}

// _force=true bypasses the cache — use after any mutation that modifies lead data
function _buildDefaultLeadsQuery(options) {
  var opts = options || {}
  var params = new URLSearchParams()
  params.set('page', String(opts.page || leadsPage || 1))
  params.set('page_size', String(opts.page_size || leadsPageSize || 25))
  if (opts.ids && opts.ids.length) params.set('ids', opts.ids.join(','))
  if (opts.updated_since) params.set('updated_since', opts.updated_since)
  return params
}

function _buildLeadsRequestPath(options) {
  var opts = options || {}
  var params = (typeof _buildLeadsListQueryParams === 'function')
    ? _buildLeadsListQueryParams(opts)
    : _buildDefaultLeadsQuery(opts)
  if (!(params instanceof URLSearchParams)) params = _buildDefaultLeadsQuery(opts)
  if (opts.ids && opts.ids.length) {
    params.delete('updated_since')
    params.set('ids', opts.ids.join(','))
    params.set('page', '1')
    params.set('page_size', String(Math.min(Math.max(opts.ids.length, 1), 100)))
  }
  if (opts.updated_since) {
    params.set('updated_since', opts.updated_since)
    params.set('page', '1')
    if (!params.get('page_size')) params.set('page_size', '100')
  }
  var query = params.toString()
  return '/leads' + (query ? '?' + query : '')
}

async function loadLeads(_force) {
  _checkCacheTenant()
  var opts = (typeof _force === 'object' && _force !== null) ? Object.assign({}, _force) : { force: !!_force }
  var force = !!opts.force
  var path = _buildLeadsRequestPath(opts)
  var cacheKey = path
  var cached = _leadsPageCache[cacheKey]
  if (!force && !opts.ids && !opts.updated_since && cached && _leadsCacheValid(cached.ts)) {
    leads = cached.leads || []
    _leadsPagination = cached.pagination || _leadsPagination
    _leadsLastServerTime = cached.server_time || _leadsLastServerTime
    return cached.data
  }
  if (!force && _leadsInFlight[cacheKey]) return _leadsInFlight[cacheKey]
  _leadsInFlight[cacheKey] = (async function () {
    try {
      const data = await _apiRequest(path, {
        headers: _apiAuthHeaders(),
        retries: 1,
        timeoutMs: 15000,
      })
      var responseLeads = data.leads || []
      if (!opts.ids && !opts.updated_since) leads = responseLeads
      _leadsPagination = data.pagination || _leadsPagination
      _leadsLastServerTime = data.server_time || _leadsLastServerTime
      if (!opts.ids && !opts.updated_since) {
        _leadsCache = leads; _leadsCacheTs = Date.now()
      }
      if (!opts.ids && !opts.updated_since) {
        _leadsPageCache[cacheKey] = {
          ts: Date.now(),
          leads: responseLeads,
          pagination: _leadsPagination,
          server_time: _leadsLastServerTime,
          data: data,
        }
      }
      return data
    } catch (_e) {
      if (!opts.ids && !opts.updated_since) leads = _leadsCache || []
      if (typeof showToast === 'function') showToast('Could not load leads. Check your connection.', 'warning')
      return { leads: (opts.ids || opts.updated_since) ? [] : leads, pagination: _leadsPagination, server_time: _leadsLastServerTime }
    } finally {
      delete _leadsInFlight[cacheKey]
    }
  })()
  return _leadsInFlight[cacheKey]
}

async function loadUsers() {
  _checkCacheTenant()
  if (_cacheValid(_usersCacheTs)) { users = _usersCache; return }
  try {
    const data = await _apiRequest('/users', {
      headers: _apiAuthHeaders(),
      retries: 1,
      timeoutMs: 15000,
    })
    users = data.users || []
    _usersCache = users; _usersCacheTs = Date.now()
  } catch (_e) {
    users = _usersCache || []
  }
}

// ============================================================================
