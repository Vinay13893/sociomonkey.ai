// ============================================================================
// PRODUCT HUB - /products/:code
// Shows product details + real client organizations subscribed to this product.
// Client cards are the only place where a client instance can be launched.
// ============================================================================

async function renderProductHub(productCode) {
  var el = document.getElementById('platContent')
  if (!el) return

  var prod = (typeof PRODUCT_CATALOGUE !== 'undefined')
    ? PRODUCT_CATALOGUE.find(function(p){ return p.code === productCode })
    : null

  if (!prod) {
    el.innerHTML = '<div class="plat-empty" style="margin-top:80px;">' +
      '<div class="plat-empty-icon"><i class="fa-solid fa-circle-xmark" style="font-size:40px;color:#fca5a5;"></i></div>' +
      '<div class="plat-empty-title">Product not found</div>' +
      '<div class="plat-empty-desc">The product "' + (productCode || '') + '" does not exist in the catalogue.</div>' +
      '<button class="plat-btn plat-btn-outline" style="margin-top:16px;" onclick="platNavigate(\'applications\')"><i class="fa-solid fa-arrow-left"></i> Back to Applications</button>' +
    '</div>'
    return
  }

  el.innerHTML = _productHubShell(prod, productCode, { loading: true })

  var responseData = null
  try {
    var res = await fetch(API_BASE + '/platform/products/' + encodeURIComponent(productCode) + '/clients', {
      headers: { Authorization: 'Bearer ' + token },
    })
    if (res.ok) {
      responseData = await res.json()
    }
  } catch (e) {}

  if (!responseData) {
    responseData = {
      product: prod,
      stats: { total_clients: 0, active_clients: 0, total_users: 0, active_users_30d: 0, usage_count: 0 },
      clients: [],
    }
  }

  var finalProduct = responseData.product || prod
  finalProduct = Object.assign({}, prod, finalProduct, {
    active: (typeof finalProduct.is_active !== 'undefined') ? !!finalProduct.is_active : !!prod.active,
  })
  var stats = responseData.stats || {}
  var clients = responseData.clients || []

  el.innerHTML = _productHubShell(finalProduct, productCode, {
    loading: false,
    stats: stats,
    clients: clients,
  })
}

function _productHubShell(prod, productCode, state) {
  var loading = !!state.loading
  var isActive = !!prod.active
  var stats = state.stats || { total_clients: 0, active_clients: 0, total_users: 0, active_users_30d: 0, usage_count: 0 }
  var clients = state.clients || []

  var headerActions = loading
    ? '<div class="plat-product-hub-actions"><button class="plat-btn plat-btn-outline" disabled>Loading...</button></div>'
    : '<div class="plat-product-hub-actions">' +
        '<button class="plat-btn plat-btn-outline" onclick="platOpenDemoAccount(\'' + _escAttr(productCode) + '\')"><i class="fa-solid fa-play"></i> Open Demo</button>' +
        (isActive
          ? '<button class="plat-btn plat-btn-primary" onclick="platShowAddClientModal(\'' + _escAttr(productCode) + '\')"><i class="fa-solid fa-plus"></i> Add Client</button>'
          : '<button class="plat-btn plat-btn-primary" disabled style="opacity:.6;cursor:not-allowed;"><i class="fa-solid fa-plus"></i> Add Client</button>') +
      '</div>'

  var statLoading = loading
    ? [
        platHubStatCard('fa-solid fa-building', '#3b82f6', '#eff6ff', 'Total Clients', '...'),
        platHubStatCard('fa-solid fa-circle-check', '#22c55e', '#f0fdf4', 'Active Clients', '...'),
        platHubStatCard('fa-solid fa-users', '#8b5cf6', '#f5f3ff', 'Total Users', '...'),
        platHubStatCard('fa-solid fa-chart-line', '#f59e0b', '#fff7ed', 'Usage Metrics', '...'),
      ].join('')
    : [
        platHubStatCard('fa-solid fa-building', '#3b82f6', '#eff6ff', 'Total Clients', String(stats.total_clients || 0)),
        platHubStatCard('fa-solid fa-circle-check', '#22c55e', '#f0fdf4', 'Active Clients', String(stats.active_clients || 0)),
        platHubStatCard('fa-solid fa-users', '#8b5cf6', '#f5f3ff', 'Total Users', String(stats.total_users || 0)),
        platHubStatCard('fa-solid fa-chart-line', '#f59e0b', '#fff7ed', 'Usage Metrics', String((stats.active_users_30d || stats.usage_count || 0))),
      ].join('')

  var clientHtml = loading
    ? '<div style="text-align:center;padding:40px;color:#94a3b8;"><i class="fa-solid fa-spinner fa-spin" style="font-size:20px;"></i></div>'
    : _productClientCards(prod, productCode, clients)

  return '' +
    '<button class="plat-back-btn" onclick="platNavigate(\'applications\')">' +
      '<i class="fa-solid fa-arrow-left"></i> Applications' +
    '</button>' +
    '<div class="plat-product-hub-header">' +
      '<div class="plat-product-hub-icon" style="background:' + (prod.bg || '#eff6ff') + ';">' +
        '<i class="' + prod.icon + '" style="color:' + (prod.color || '#3b82f6') + ';"></i>' +
      '</div>' +
      '<div class="plat-product-hub-info">' +
        '<h2>' + _escHtml(prod.fullName || prod.name || productCode) + '</h2>' +
        '<p>' + _escHtml(prod.desc || '') + '</p>' +
        '<span class="plat-badge ' + (isActive ? 'plat-badge-active' : 'plat-badge-coming') + '">' +
          (isActive ? 'Live' : 'Coming Soon') + '</span>' +
      '</div>' +
      headerActions +
    '</div>' +
    '<div id="platHubStats" style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;">' +
      statLoading +
    '</div>' +
    '<div class="plat-section-header" style="margin-bottom:14px;">' +
      '<h3 class="plat-section-title"><i class="fa-solid fa-building" style="color:#64748b;font-size:13px;margin-right:6px;"></i>Client Organizations</h3>' +
    '</div>' +
    '<div id="platHubClients">' + clientHtml + '</div>'
}

function _productClientCards(prod, productCode, clients) {
  if (!clients || !clients.length) {
    return '<div class="plat-empty" style="padding:48px;">' +
      '<div class="plat-empty-icon"><i class="fa-solid fa-building-circle-xmark" style="font-size:38px;color:#c7d2fe;"></i></div>' +
      '<div class="plat-empty-title">No clients yet</div>' +
      '<div class="plat-empty-desc">No organizations are subscribed to <strong>' + _escHtml(prod.fullName || prod.name || productCode) + '</strong> yet.</div>' +
      (prod.active ? '<button class="plat-btn plat-btn-primary" style="margin-top:16px;" onclick="platShowAddClientModal(\'' + _escAttr(productCode) + '\')"><i class="fa-solid fa-plus"></i> Add Client</button>' : '') +
    '</div>'
  }

  var cardsHtml = clients.map(function(client) {
    var name = client.brand_name || client.name || client.slug || 'Unknown'
    var slug = client.slug || ''
    var status = (client.status || 'active').toLowerCase()
    var subscriptionStatus = (client.subscription_status || 'active').toLowerCase()
    var users = client.users != null ? client.users : 0
    var activeUsers = client.active_users != null ? client.active_users : 0
    var startDate = client.subscription_start_date ? _fmtDate(client.subscription_start_date) : 'N/A'
    var renewalDate = client.renewal_date ? _fmtDate(client.renewal_date) : 'N/A'
    var initials = name.split(' ').map(function(w){ return w[0] }).join('').slice(0,2).toUpperCase()
    var statusClass = status === 'active' ? 'plat-badge-active' : 'plat-badge-inactive'

    return '<div class="plat-client-card">' +
      '<div class="plat-client-avatar">' + initials + '</div>' +
      '<div class="plat-client-info">' +
        '<div class="plat-client-name">' + _escHtml(name) + '</div>' +
        '<div class="plat-client-meta">' +
          (slug ? '<span style="color:#64748b;">@' + _escHtml(slug) + '</span> &bull; ' : '') +
          '<span style="color:#64748b;">' + users + ' users</span> &bull; ' +
          '<span style="color:#64748b;">Active users: ' + activeUsers + '</span>' +
        '</div>' +
        '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;">' +
          '<span class="plat-badge ' + statusClass + '">' + _escHtml(status.charAt(0).toUpperCase() + status.slice(1)) + '</span>' +
          '<span class="plat-badge plat-badge-coming">' + _escHtml(subscriptionStatus.charAt(0).toUpperCase() + subscriptionStatus.slice(1)) + '</span>' +
        '</div>' +
        '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;font-size:12px;color:#64748b;">' +
          '<span><strong>Plan:</strong> ' + _escHtml(client.plan || 'starter') + '</span>' +
          '<span><strong>Start:</strong> ' + startDate + '</span>' +
          '<span><strong>Renewal:</strong> ' + renewalDate + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="plat-client-actions">' +
        '<button class="plat-btn plat-btn-outline plat-btn-sm" onclick="renderTenantConfigPage(' + client.tenant_id + ')">' +
          '<i class="fa-solid fa-gear" style="font-size:11px;"></i> Manage Subscription' +
        '</button>' +
        '<button class="plat-btn plat-btn-outline plat-btn-sm" onclick="platViewOrgUsers(' + client.tenant_id + ',\'' + _escAttr(name) + '\')">' +
          '<i class="fa-solid fa-users" style="font-size:11px;"></i> Manage Users' +
        '</button>' +
        '<button class="plat-btn plat-btn-primary plat-btn-sm" onclick="platHubLaunch(\'' + _escAttr(productCode) + '\',\'' + _escAttr(slug) + '\',' + (client.tenant_id || 0) + ',\'' + _escAttr(name) + '\')">' +
          '<i class="fa-solid fa-rocket" style="font-size:11px;"></i> Open Application' +
        '</button>' +
      '</div>' +
    '</div>'
  }).join('')

  return '<div class="plat-client-grid">' + cardsHtml + '</div>'
}

function platHubStatCard(icon, color, bg, label, value) {
  return '<div class="plat-stat-card">' +
    '<div class="plat-stat-top-row">' +
      '<div class="plat-stat-label">' + label + '</div>' +
      '<div class="plat-stat-icon-badge" style="background:' + bg + ';">' +
        '<i class="' + icon + '" style="color:' + color + ';"></i>' +
      '</div>' +
    '</div>' +
    '<div class="plat-stat-value">' + value + '</div>' +
  '</div>'
}

async function platHubLaunch(productCode, slug, tenantId, tenantName) {
  if (user && user.role === 'platform_owner' && tenantId) {
    try {
      var res = await fetch(API_BASE + '/platform/tenants/' + tenantId + '/impersonate', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + token },
      })
      var data = await res.json()
      if (res.ok && data && data.token && data.user) {
        var impUrl = authBuildTenantAppPath(slug, productCode) + '?imp=' + encodeURIComponent(data.token) +
          '&user=' + encodeURIComponent(JSON.stringify(data.user))
        window.location.href = impUrl
        return
      }
      showToast((data && data.error) || 'Could not start tenant session. Opening direct view instead.', 'warning')
    } catch (e) {
      showToast('Network error during tenant session setup. Opening direct view instead.', 'warning')
    }
  }

  if (typeof launchTenantApp === 'function') {
    launchTenantApp(productCode, slug)
  } else {
    var path = authBuildTenantAppPath(slug, productCode)
    history.pushState({}, '', path)
    if (typeof dispatch === 'function') dispatch()
  }
}

async function platOpenDemoAccount(productCode) {
  if (!token) {
    showToast('Authentication required.', 'warning')
    return
  }

  try {
    var res = await fetch(API_BASE + '/platform/products/' + encodeURIComponent(productCode) + '/demo-launch', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + token },
    })
    var data = await res.json()
    if (!res.ok) {
      showToast(data.error || 'Demo account unavailable for this product.', 'warning')
      return
    }

    if (!data.token || !data.user || !data.tenant_slug || !data.product_slug) {
      showToast('Invalid demo launch response.', 'error')
      return
    }

    var demoUrl = authBuildTenantAppPath(data.tenant_slug, data.product_slug) + '?imp=' + encodeURIComponent(data.token) +
      '&user=' + encodeURIComponent(JSON.stringify(data.user))
    window.location.href = demoUrl
  } catch (e) {
    showToast('Network error while opening demo account.', 'error')
  }
}

function platShowRequestDemoModal(productCode, productName) {
  _platShowModal(
    'Request Demo',
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">' +
      _hubField('rd_name', 'Name *', 'text', '') +
      _hubField('rd_company', 'Company *', 'text', '') +
      _hubField('rd_email', 'Email *', 'email', '') +
      _hubField('rd_phone', 'Phone *', 'text', '') +
      '<div style="grid-column:1 / -1;">' +
        '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">Message *</label>' +
        '<textarea id="rd_message" rows="4" style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;resize:vertical;" placeholder="Tell us what you need"></textarea>' +
      '</div>' +
      '<input type="hidden" id="rd_product_code" value="' + _escAttr(productCode) + '" />' +
      '<input type="hidden" id="rd_product_name" value="' + _escAttr(productName) + '" />' +
    '</div>' +
    '<div style="display:flex;align-items:center;justify-content:space-between;margin-top:18px;gap:12px;">' +
      '<div style="font-size:12px;color:#64748b;">We will contact you with a tailored demo.</div>' +
      '<button class="plat-btn plat-btn-primary" onclick="platSubmitRequestDemo()">Send Request</button>' +
    '</div>'
  )
}

async function platSubmitRequestDemo() {
  var payload = {
    name: document.getElementById('rd_name')?.value?.trim(),
    company: document.getElementById('rd_company')?.value?.trim(),
    email: document.getElementById('rd_email')?.value?.trim(),
    phone: document.getElementById('rd_phone')?.value?.trim(),
    message: document.getElementById('rd_message')?.value?.trim(),
    product_code: document.getElementById('rd_product_code')?.value?.trim(),
    product_name: document.getElementById('rd_product_name')?.value?.trim(),
  }

  if (!payload.name || !payload.company || !payload.email || !payload.phone || !payload.message) {
    showToast('Please fill in all required fields.', 'warning')
    return
  }

  var btn = document.querySelector('#platOrgModalBody .plat-btn-primary')
  if (btn) { btn.disabled = true; btn.textContent = 'Sending...' }

  try {
    var res = await fetch(API_BASE + '/public/demo-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    var data = await res.json()
    if (!res.ok) {
      showToast(data.error || 'Failed to submit request.', 'error')
      if (btn) { btn.disabled = false; btn.textContent = 'Send Request' }
      return
    }

    _platUpdateModal(
      '<div style="text-align:center;padding:16px 8px;">' +
        '<div style="font-size:44px;margin-bottom:10px;">&#x2705;</div>' +
        '<h3 style="margin:0 0 8px;font-size:18px;color:#0f172a;">Demo request submitted</h3>' +
        '<p style="margin:0;color:#64748b;font-size:14px;">We have saved your request and will contact you soon.</p>' +
        '<button class="plat-btn plat-btn-primary" style="margin-top:18px;" onclick="_platCloseModal()">Close</button>' +
      '</div>'
    )
    showToast('Demo request submitted successfully.', 'success')
  } catch (e) {
    showToast('Network error. Please try again.', 'error')
    if (btn) { btn.disabled = false; btn.textContent = 'Send Request' }
  }
}

function platShowAddClientModal(productCode) {
  var productName = (typeof PRODUCT_CATALOGUE !== 'undefined' && PRODUCT_CATALOGUE.find(function(p){ return p.code === productCode }))
    ? PRODUCT_CATALOGUE.find(function(p){ return p.code === productCode }).fullName
    : productCode

  _platShowModal(
    'Add Client',
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">' +
      _hubField('ac_name', 'Organization Name *', 'text', '') +
      _hubField('ac_slug', 'Slug *', 'text', '') +
      _hubField('ac_plan', 'Plan *', 'text', 'enterprise') +
      _hubField('ac_admin_name', 'Admin Name *', 'text', '') +
      _hubField('ac_admin_email', 'Admin Email *', 'email', '') +
      _hubField('ac_admin_password', 'Admin Password *', 'password', '') +
      _hubField('ac_max_users', 'Max Users', 'number', '20') +
      _hubField('ac_product_name', 'Product', 'text', productName) +
      '<div style="grid-column:1 / -1;">' +
        '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">Notes (optional)</label>' +
        '<textarea id="ac_notes" rows="3" style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;resize:vertical;" placeholder="Internal note for the provisioned account"></textarea>' +
      '</div>' +
      '<input type="hidden" id="ac_product_code" value="' + _escAttr(productCode) + '" />' +
    '</div>' +
    '<div style="display:flex;align-items:center;justify-content:space-between;margin-top:18px;gap:12px;">' +
      '<div style="font-size:12px;color:#64748b;">This creates the tenant, admin user, and subscription in one step.</div>' +
      '<button class="plat-btn plat-btn-primary" onclick="platSubmitAddClient()">Create Client</button>' +
    '</div>'
  )
}

async function platSubmitAddClient() {
  var productCode = document.getElementById('ac_product_code')?.value?.trim()
  var name = document.getElementById('ac_name')?.value?.trim()
  var slug = document.getElementById('ac_slug')?.value?.trim().toLowerCase()
  var plan = document.getElementById('ac_plan')?.value?.trim() || 'enterprise'
  var adminName = document.getElementById('ac_admin_name')?.value?.trim()
  var adminEmail = document.getElementById('ac_admin_email')?.value?.trim()
  var adminPassword = document.getElementById('ac_admin_password')?.value?.trim()
  var maxUsers = parseInt(document.getElementById('ac_max_users')?.value || '20', 10)
  var notes = document.getElementById('ac_notes')?.value?.trim()
  var productName = document.getElementById('ac_product_name')?.value?.trim() || productCode

  if (!name || !slug || !adminName || !adminEmail || !adminPassword) {
    showToast('Please fill in all required fields.', 'warning')
    return
  }

  var btn = document.querySelector('#platOrgModalBody .plat-btn-primary')
  if (btn) { btn.disabled = true; btn.textContent = 'Creating...' }

  try {
    var payload = {
      name: name,
      slug: slug,
      plan: plan,
      max_users: maxUsers,
      notes: notes || '',
      admin_name: adminName,
      admin_email: adminEmail,
      admin_password: adminPassword,
      products: [productCode],
      brand_name: name,
    }
    var res = await fetch(API_BASE + '/platform/provision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify(payload),
    })
    var data = await res.json()
    if (!res.ok) {
      showToast(data.error || 'Failed to create client.', 'error')
      if (btn) { btn.disabled = false; btn.textContent = 'Create Client' }
      return
    }

    _platUpdateModal(
      '<div style="text-align:center;padding:16px 8px;">' +
        '<div style="font-size:44px;margin-bottom:10px;">&#x2705;</div>' +
        '<h3 style="margin:0 0 8px;font-size:18px;color:#0f172a;">Client created successfully</h3>' +
        '<p style="margin:0;color:#64748b;font-size:14px;">The organization, admin user, and product subscription have been created.</p>' +
        '<div style="display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:18px;">' +
          '<button class="plat-btn plat-btn-primary" onclick="platHubLaunch(\'' + _escAttr(productCode) + '\',\'' + _escAttr(slug) + '\',' + (data.tenant && data.tenant.id ? data.tenant.id : 0) + ',\'' + _escAttr(name) + '\')">Open Application</button>' +
          '<button class="plat-btn plat-btn-outline" onclick="renderTenantConfigPage(' + (data.tenant && data.tenant.id ? data.tenant.id : 0) + ')">Manage Subscription</button>' +
          '<button class="plat-btn plat-btn-outline" onclick="platNavigate(\'organizations\')">View Organization</button>' +
        '</div>' +
        '<div style="margin-top:14px;font-size:12px;color:#94a3b8;">Login URL: ' + _escHtml(data.login_url || authBuildTenantLoginPath(slug, productCode)) + '</div>' +
      '</div>'
    )
    showToast('Client created successfully.', 'success')
  } catch (e) {
    showToast('Network error. Please try again.', 'error')
    if (btn) { btn.disabled = false; btn.textContent = 'Create Client' }
  }
}

function _hubField(id, label, type, value) {
  return '<div>' +
    '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">' + label + '</label>' +
    '<input id="' + id + '" type="' + type + '" value="' + _escAttr(String(value || '')) + '" style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;" />' +
  '</div>'
}

function _fmtDate(value) {
  if (!value) return 'N/A'
  var d = new Date(value)
  if (isNaN(d.getTime())) return 'N/A'
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// -- Modal helpers ------------------------------------------------------------

function _platShowModal(title, bodyHtml) {
  var container = document.getElementById('platOrgModals')
  if (!container) {
    container = document.createElement('div')
    container.id = 'platOrgModals'
    document.body.appendChild(container)
  }
  container.innerHTML =
    '<div id="platOrgModalOverlay" style="position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:2000;display:flex;align-items:center;justify-content:center;">' +
      '<div style="background:#fff;border-radius:18px;width:min(720px,92vw);max-height:84vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.25);" onclick="event.stopPropagation()">' +
        '<div style="padding:20px 24px 14px;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;">' +
          '<h3 style="margin:0;font-size:17px;color:#0f172a;">' + title + '</h3>' +
          '<button onclick="_platCloseModal()" style="border:none;background:none;font-size:24px;cursor:pointer;color:#94a3b8;line-height:1;">&times;</button>' +
        '</div>' +
        '<div id="platOrgModalBody" style="padding:20px 24px;overflow-y:auto;flex:1;">' + bodyHtml + '</div>' +
      '</div>' +
    '</div>'
}

function _platUpdateModal(bodyHtml) {
  var el = document.getElementById('platOrgModalBody')
  if (el) el.innerHTML = bodyHtml
}

function _platCloseModal() {
  var el = document.getElementById('platOrgModalOverlay')
  if (el) el.remove()
}

function _escHtml(s) {
  if (s == null) return ''
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}

function _escAttr(s) {
  if (s == null) return ''
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;')
}
