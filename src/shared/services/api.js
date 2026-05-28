// API FUNCTIONS
// ============================================================================

function _apiAuthHeaders() {
  if (!token) return {}
  const headers = { Authorization: `Bearer ${token}` }
  // When platform owner is viewing a tenant, tell the backend which tenant's data to return
  if (typeof platformTenantSlug === 'string' && platformTenantSlug) {
    headers['X-Tenant-Slug'] = platformTenantSlug
  }
  return headers
}

function _apiJsonHeaders(extra) {
  return Object.assign({ 'Content-Type': 'application/json' }, extra || {})
}

async function _apiRequest(path, opts) {
  const options = opts || {}
  const retries = typeof options.retries === 'number' ? options.retries : 1
  const timeoutMs = typeof options.timeoutMs === 'number' ? options.timeoutMs : 12000

  let lastErr = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)

    try {
      const fetchOptions = Object.assign({}, options, { signal: controller.signal })
      delete fetchOptions.retries
      delete fetchOptions.timeoutMs

      const res = await fetch(`${API_BASE}${path}`, fetchOptions)
      clearTimeout(timer)

      const ct = (res.headers.get('content-type') || '').toLowerCase()
      const payload = ct.indexOf('application/json') !== -1 ? await res.json() : null

      if (res.status === 401) {
        authClearSession()
        if (typeof dispatch === 'function') dispatch()
      }

      if (!res.ok) {
        const err = new Error((payload && payload.error) || 'Request failed')
        err.status = res.status
        err.payload = payload
        throw err
      }

      return payload
    } catch (err) {
      clearTimeout(timer)
      lastErr = err

      // Retry transient network/timeout errors only
      const isAbort = err && err.name === 'AbortError'
      const isNetwork = !err || typeof err.status === 'undefined'
      const canRetry = attempt < retries && (isAbort || isNetwork)
      if (!canRetry) break
    }
  }

  throw lastErr || new Error('Request failed')
}

async function login(email, password, remember, tenantSlug) {
  let data
  try {
    const body = { email: email, password: password }
    if (tenantSlug) body.tenant_slug = tenantSlug
    data = await _apiRequest('/auth/login', {
      method: 'POST',
      headers: _apiJsonHeaders(),
      body: JSON.stringify(body),
      retries: 0,
      timeoutMs: 18000,
    })
  } catch (e) {
    const msg = (e && e.message) || 'Login failed. Please try again.'
    const errEl = document.getElementById('loginError')
    if (errEl) {
      errEl.textContent = msg
      errEl.style.display = 'block'
    }
    if (typeof showToast === 'function') showToast(msg, 'error')
    return
  }

  authSetSession(data.token, data.user, !!remember)
  availableProducts = data.products || []
  if (availableProducts.length > 0) {
    const hasLms = availableProducts.find(p => p.slug === 'lms')
    const hasCrm = availableProducts.find(p => p.slug === 'crm')
    currentProduct = hasLms ? 'lms' : (hasCrm ? 'crm' : ((availableProducts[0] && availableProducts[0].slug) || 'lms'))
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
  // Redirect to the originally-requested page if one was stored, else default by role
  if (loginRedirectPath && loginRedirectPath !== '/login' && !loginRedirectPath.endsWith('/login')) {
    history.pushState({}, '', loginRedirectPath)
    loginRedirectPath = ''
  } else if (!loginRedirectPath || loginRedirectPath.endsWith('/login')) {
    if (authIsPlatformUser()) {
      history.replaceState({}, '', '/')
    } else if (user && user.tenant_slug) {
      const preferredProduct = availableProducts.find(p => p.slug === 'lms') ? 'lms' : 'crm'
      history.replaceState({}, '', '/' + user.tenant_slug + '/' + preferredProduct)
    }
  }
  dispatch()
}

async function loadMe() {
  let data
  try {
    data = await _apiRequest('/auth/me', {
      headers: _apiAuthHeaders(),
      retries: 0,
      timeoutMs: 12000,
    })
  } catch (_e) {
    authClearSession()
    if (typeof dispatch === 'function') dispatch(); else render()
    return
  }

  user = data.user
  if (data.products) {
    availableProducts = data.products
  }
  // Ensure activeTab is valid for this user's role
  if (user && user.role === 'platform_owner' && activeTab === 'dashboard') {
    activeTab = 'platform'
  }
}

// ── In-memory data caches (5-minute TTL, invalidated on tenant context switch) ──
var _CACHE_TTL_MS = 5 * 60 * 1000
var _cacheSlug = null
var _projectsCache = null; var _projectsCacheTs = 0
var _leadsCache    = null; var _leadsCacheTs    = 0
var _usersCache    = null; var _usersCacheTs    = 0

function _cacheValid(ts) { return ts > 0 && (Date.now() - ts) < _CACHE_TTL_MS }

function _checkCacheTenant() {
  // Bust all caches when the active tenant context changes (platform owner switching tenants)
  var slug = (typeof platformTenantSlug === 'string' && platformTenantSlug) ? platformTenantSlug : ''
  if (_cacheSlug !== slug) {
    _projectsCacheTs = 0; _leadsCacheTs = 0; _usersCacheTs = 0
    _cacheSlug = slug
  }
}

// Call before any mutation that changes lead data (delete, edit, assign, import)
function invalidateLeadsCache() { _leadsCacheTs = 0 }
function invalidateProjectsCache() { _projectsCacheTs = 0 }

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
async function loadLeads(_force) {
  _checkCacheTenant()
  if (!_force && _cacheValid(_leadsCacheTs)) { leads = _leadsCache; return }
  try {
    const data = await _apiRequest('/leads', {
      headers: _apiAuthHeaders(),
      retries: 1,
      timeoutMs: 15000,
    })
    leads = data.leads || []
    _leadsCache = leads; _leadsCacheTs = Date.now()
  } catch (_e) {
    leads = _leadsCache || []
    if (typeof showToast === 'function') showToast('Could not load leads. Check your connection.', 'warning')
  }
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
