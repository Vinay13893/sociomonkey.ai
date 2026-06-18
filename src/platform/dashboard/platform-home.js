// ============================================================================
// PLATFORM HOME - SaaS platform KPIs and app catalogue
// ============================================================================

async function renderPlatformHome() {
  var el = document.getElementById('platContent')
  if (!el) return

  el.innerHTML =
    '<div style="text-align:center;padding:64px;color:#94a3b8;">' +
      '<i class="fa-solid fa-spinner fa-spin" style="font-size:28px;"></i>' +
      '<div style="margin-top:12px;font-size:13px;">Loading platform dashboard...</div>' +
    '</div>'

  var analytics = await platHomeFetch('/platform/analytics', true)
  var stats = (analytics && analytics.stats) || {}
  var tenantRows = (analytics && analytics.tenants) || []
  var activeTenantUsers = tenantRows.reduce(function (sum, tenant) {
    return sum + Number((tenant && tenant.user_count) || 0)
  }, 0)
  var platformApps = platformCatalogueApps()
  var comingSoonApps = platformComingSoonApps()

  var cards = [
    platHomeCard('Total Tenants', platHomeValue(stats.active_tenants), 'Active tenant accounts', 'fa-solid fa-building', '#2563eb', '#eff6ff'),
    platHomeCard('Active Apps', platHomeValue(platformActiveAppsCount()), 'Built and enabled platform apps', 'fa-solid fa-border-all', '#0891b2', '#ecfeff'),
    platHomeCard('Active Users', platHomeValue(activeTenantUsers), 'Active tenant users only, platform admins excluded', 'fa-solid fa-user-check', '#16a34a', '#f0fdf4'),
  ].join('')

  el.innerHTML =
    '<div class="plat-stats-grid" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:24px;">' + cards + '</div>' +
    '<div class="plat-panel" style="margin-bottom:24px;">' +
      '<div class="plat-panel-header">' +
        '<div class="plat-panel-title"><i class="fa-solid fa-border-all" style="color:#2563eb;font-size:13px;margin-right:6px;"></i>Platform Apps</div>' +
        '<button class="plat-panel-viewall" onclick="platNavigate(\'applications\')">View all</button>' +
      '</div>' +
      '<div class="plat-apps-grid-full">' + platformApps.map(platHomeAppCard).join('') + '</div>' +
    '</div>' +
    '<div class="plat-panel">' +
      '<div class="plat-panel-header">' +
        '<div class="plat-panel-title"><i class="fa-solid fa-clock" style="color:#64748b;font-size:13px;margin-right:6px;"></i>Coming Soon</div>' +
      '</div>' +
      '<div class="plat-apps-grid-full">' + comingSoonApps.map(platHomeComingSoonCard).join('') + '</div>' +
    '</div>'
}

async function platHomeFetch(path, authRequired) {
  try {
    var base = API_BASE.replace(/\/api\/?$/, '')
    var url = path.indexOf('/api/') === 0 ? base + path : API_BASE + path
    var headers = authRequired && token ? { Authorization: 'Bearer ' + token } : {}
    var res = await fetch(url, { headers: headers })
    if (!res.ok) return null
    return await res.json()
  } catch (_e) {
    return null
  }
}

function platHomeCard(label, value, subtext, icon, color, bg) {
  return '<div class="plat-stat-card">' +
    '<div class="plat-stat-top-row">' +
      '<div class="plat-stat-label">' + platHomeEsc(label) + '</div>' +
      '<div class="plat-stat-icon-badge" style="background:' + bg + ';">' +
        '<i class="' + icon + '" style="color:' + color + ';"></i>' +
      '</div>' +
    '</div>' +
    '<div class="plat-stat-value">' + value + '</div>' +
    '<div class="plat-stat-footer"><span class="plat-stat-vs">' + platHomeEsc(subtext) + '</span></div>' +
  '</div>'
}

function platHomeAppCard(app) {
  var statusClass = app.lifecycle === 'live' ? 'plat-badge-active' : 'plat-badge-warning'
  var demo = app.demoAvailable
    ? '<span class="plat-badge plat-badge-info" style="margin-left:6px;">' + platHomeEsc(app.demoLabel || 'Demo Available') + '</span>'
    : ''
  return '<div class="plat-app-tile" onclick="platNavigate(\'product-hub\', { productCode: \'' + platHomeEsc(app.code) + '\' })">' +
    '<div style="position:absolute;top:12px;left:12px;">' +
      '<span class="plat-badge ' + statusClass + '">' + platHomeEsc(app.statusLabel) + '</span>' + demo +
    '</div>' +
    '<div class="plat-app-icon-area">' +
      '<i class="' + app.icon + '" style="color:' + app.color + ';"></i>' +
    '</div>' +
    '<div class="plat-app-name">' + platHomeEsc(app.name) + '</div>' +
    '<div class="plat-app-fullname">' + platHomeEsc(app.fullName) + '</div>' +
    '<button class="plat-app-open-btn" onclick="event.stopPropagation();platNavigate(\'product-hub\', { productCode: \'' + platHomeEsc(app.code) + '\' })" style="color:' + app.color + ';">' +
      'Open Hub <i class="fa-solid fa-arrow-right" style="font-size:11px;"></i>' +
    '</button>' +
  '</div>'
}

function platHomeComingSoonCard(app) {
  return '<div class="plat-app-tile" style="opacity:.74;">' +
    '<div style="position:absolute;top:12px;left:12px;">' +
      '<span class="plat-badge plat-badge-coming">' + platHomeEsc(app.statusLabel) + '</span>' +
    '</div>' +
    '<div class="plat-app-icon-area">' +
      '<i class="' + app.icon + '" style="color:' + app.color + ';"></i>' +
    '</div>' +
    '<div class="plat-app-name">' + platHomeEsc(app.name) + '</div>' +
    '<div class="plat-app-fullname">' + platHomeEsc(app.fullName) + '</div>' +
    '<button class="plat-app-open-btn inactive" disabled style="color:#94a3b8;">Coming Soon</button>' +
  '</div>'
}

function platHomeValue(value) {
  if (value === null || typeof value === 'undefined' || value === '') return 'Not available'
  var num = Number(value)
  if (!Number.isFinite(num)) return platHomeEsc(value)
  return num.toLocaleString()
}

function platHomeEsc(value) {
  if (value === null || typeof value === 'undefined') return ''
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
}
