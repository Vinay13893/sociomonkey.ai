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
  // Stay on CRM if available, else first available product
  if (availableProducts.length > 0) {
    const hasCrm = availableProducts.find(p => p.slug === 'crm')
    currentProduct = hasCrm ? 'crm' : ((availableProducts[0] && availableProducts[0].slug) || 'crm')
    localStorage.setItem('current_product', currentProduct)
  }
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
      history.replaceState({}, '', '/' + user.tenant_slug + '/crm')
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

async function loadProjects() {
  try {
    const data = await _apiRequest('/projects', {
      headers: _apiAuthHeaders(),
      retries: 1,
      timeoutMs: 15000,
    })
    projects = data.projects || []
  } catch (_e) {
    projects = []
  }
}

async function loadLeads() {
  try {
    const data = await _apiRequest('/leads', {
      headers: _apiAuthHeaders(),
      retries: 1,
      timeoutMs: 15000,
    })
    leads = data.leads || []
  } catch (_e) {
    leads = []
    if (typeof showToast === 'function') showToast('Could not load leads. Check your connection.', 'warning')
  }
}

async function loadUsers() {
  try {
    const data = await _apiRequest('/users', {
      headers: _apiAuthHeaders(),
      retries: 1,
      timeoutMs: 15000,
    })
    users = data.users || []
  } catch (_e) {
    users = []
  }
}

// ============================================================================
