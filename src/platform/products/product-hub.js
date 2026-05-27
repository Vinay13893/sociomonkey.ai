// ============================================================================
// PRODUCT HUB � /products/:code
// Shows product details + all client organisations subscribed to this product
// with a per-client "Launch App" button that opens the tenant app.
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

  // Show loading skeleton
  el.innerHTML =
    '<button class="plat-back-btn" onclick="platNavigate(\'applications\')">' +
      '<i class="fa-solid fa-arrow-left"></i> Applications' +
    '</button>' +
    '<div class="plat-product-hub-header">' +
      '<div class="plat-product-hub-icon" style="background:' + prod.bg + ';">' +
        '<i class="' + prod.icon + '" style="color:' + prod.color + ';"></i>' +
      '</div>' +
      '<div class="plat-product-hub-info">' +
        '<h2>' + prod.fullName + '</h2>' +
        '<p>' + prod.desc + '</p>' +
        '<span class="plat-badge ' + (prod.active ? 'plat-badge-active' : 'plat-badge-coming') + '">' +
          (prod.active ? 'Active' : 'Coming Soon') + '</span>' +
      '</div>' +
      '<div class="plat-product-hub-actions">' +
        '<button class="plat-btn plat-btn-outline" onclick="showToast(\'Demo request sent! We will be in touch.\', \'success\'")><i class="fa-solid fa-play"></i> Request Demo</button>' +
        '<button class="plat-btn plat-btn-primary" onclick="platShowAddClientModal(\'' + productCode + '\')">' +
          '<i class="fa-solid fa-plus"></i> Add Client' +
        '</button>' +
      '</div>' +
    '</div>' +
    '<div id="platHubStats" style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px;">' +
      platHubStatCard('fa-solid fa-building', '#3b82f6', '#eff6ff', 'Total Clients', '...') +
      platHubStatCard('fa-solid fa-circle-check', '#22c55e', '#f0fdf4', 'Active Clients', '...') +
      platHubStatCard('fa-solid fa-users', '#8b5cf6', '#f5f3ff', 'Total Users', '...') +
    '</div>' +
    '<div class="plat-section-header" style="margin-bottom:14px;">' +
      '<h3 class="plat-section-title"><i class="fa-solid fa-building" style="color:#64748b;font-size:13px;margin-right:6px;"></i>Client Organisations</h3>' +
    '</div>' +
    '<div id="platHubClients"><div style="text-align:center;padding:40px;color:#94a3b8;"><i class="fa-solid fa-spinner fa-spin" style="font-size:20px;"></i></div></div>'

  // Fetch tenants
  var tenants = []
  try {
    var resp = await fetch(API_BASE + '/platform/analytics', {
      headers: { 'Authorization': 'Bearer ' + token }
    })
    if (resp.ok) {
      var data = await resp.json()
      var all = data.tenants || data.organizations || []
      tenants = all.filter(function(t) {
        var subs = t.subscribed_products || t.products || []
        return subs.indexOf(productCode) !== -1
      })
    }
  } catch (e) {
    // network error � show empty state
  }

  // Update stats
  var statsEl = document.getElementById('platHubStats')
  if (statsEl) {
    var activeCount = tenants.filter(function(t){ return t.is_active !== false }).length
    var totalUsers  = tenants.reduce(function(a, t){ return a + (t.user_count || t.users || 0) }, 0)
    statsEl.innerHTML =
      platHubStatCard('fa-solid fa-building', '#3b82f6', '#eff6ff', 'Total Clients', tenants.length.toString()) +
      platHubStatCard('fa-solid fa-circle-check', '#22c55e', '#f0fdf4', 'Active Clients', activeCount.toString()) +
      platHubStatCard('fa-solid fa-users', '#8b5cf6', '#f5f3ff', 'Total Users', totalUsers > 0 ? totalUsers.toLocaleString() : '�')
  }

  // Render clients
  var clientsEl = document.getElementById('platHubClients')
  if (!clientsEl) return

  if (tenants.length === 0) {
    clientsEl.innerHTML =
      '<div class="plat-empty" style="padding:48px;">' +
        '<div class="plat-empty-icon"><i class="fa-solid fa-building-circle-xmark" style="font-size:38px;color:#c7d2fe;"></i></div>' +
        '<div class="plat-empty-title">No clients yet</div>' +
        '<div class="plat-empty-desc">No organisations are subscribed to <strong>' + prod.name + '</strong> yet.</div>' +
        '<button class="plat-btn plat-btn-primary" style="margin-top:16px;" onclick="platShowAddClientModal(\'' + productCode + '\')">' +
          '<i class="fa-solid fa-plus"></i> Subscribe First Client' +
        '</button>' +
      '</div>'
    return
  }

  var cardsHtml = tenants.map(function(t) {
    var name     = t.name || t.org_name || t.slug || 'Unknown'
    var slug     = t.slug || ''
    var isActive = t.is_active !== false
    var users    = t.user_count || t.users || 0
    var initials = name.split(' ').map(function(w){ return w[0] }).join('').slice(0,2).toUpperCase()

    return '<div class="plat-client-card">' +
      '<div class="plat-client-avatar">' + initials + '</div>' +
      '<div class="plat-client-info">' +
        '<div class="plat-client-name">' + platEsc(name) + '</div>' +
        '<div class="plat-client-meta">' +
          (slug ? '<span style="color:#64748b;">@' + slug + '</span> &bull; ' : '') +
          (users ? users + ' users &bull; ' : '') +
          '<span class="plat-badge ' + (isActive ? 'plat-badge-active' : 'plat-badge-inactive') + '">' +
            (isActive ? 'Active' : 'Inactive') +
          '</span>' +
        '</div>' +
      '</div>' +
      '<div class="plat-client-actions">' +
        '<button class="plat-btn plat-btn-outline plat-btn-sm" onclick="platNavigate(\'organizations\')">' +
          '<i class="fa-solid fa-gear" style="font-size:11px;"></i> Manage' +
        '</button>' +
        (slug ? '<button class="plat-btn plat-btn-primary plat-btn-sm" onclick="platHubLaunch(\'' + productCode + '\',\'' + slug + '\')">' +
          '<i class="fa-solid fa-rocket" style="font-size:11px;"></i> Launch App' +
        '</button>' : '') +
      '</div>' +
    '</div>'
  }).join('')

  clientsEl.innerHTML = '<div class="plat-client-grid">' + cardsHtml + '</div>'
}

// -- Helpers ------------------------------------------------------------------

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

function platHubLaunch(productCode, slug) {
  if (typeof launchTenantApp === 'function') {
    launchTenantApp(productCode, slug)
  } else {
    var path = '/' + slug + '/' + productCode
    history.pushState({}, '', path)
    if (typeof dispatch === 'function') dispatch()
  }
}

function platShowAddClientModal(productCode) {
  showToast('To subscribe a client to ' + productCode.toUpperCase() + ', go to Organizations → Manage Products for the desired client.', 'info')
}
