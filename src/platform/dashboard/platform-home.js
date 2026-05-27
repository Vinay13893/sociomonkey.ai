// ============================================================================
// PLATFORM HOME — Dashboard for the SocioMonkey Platform layer
// v2: Matches reference screenshot — stat cards, app tiles, charts, panels
// ============================================================================

function renderPlatformHome() {
  var el = document.getElementById('platContent')
  if (!el) return

  // -- Stat cards -----------------------------------------------------------
  var stats = [
    { label: 'Total Users',             value: '24,560', change: '+12.5', up: true,  icon: 'fa-solid fa-user-group', color: '#8b5cf6', bg: '#f5f3ff' },
    { label: 'Organizations',           value: '148',    change: '+8.3',  up: true,  icon: 'fa-solid fa-building',   color: '#3b82f6', bg: '#eff6ff' },
    { label: 'Active Subscriptions',    value: '312',    change: '+5.7',  up: true,  icon: 'fa-solid fa-circle-check', color: '#22c55e', bg: '#f0fdf4' },
    { label: 'Monthly Recurring Rev.',  value: '$286K',  change: '+18.2', up: true,  icon: 'fa-solid fa-coins',      color: '#f59e0b', bg: '#fff7ed' },
    { label: 'Platform Usage',          value: '78.4%',  change: '+3.1',  up: true,  icon: 'fa-solid fa-chart-bar',  color: '#06b6d4', bg: '#ecfeff' },
  ]

  var statsHtml = stats.map(function(s) {
    return '<div class="plat-stat-card">' +
      '<div class="plat-stat-top-row">' +
        '<div class="plat-stat-label">' + s.label + '</div>' +
        '<div class="plat-stat-icon-badge" style="background:' + s.bg + ';">' +
          '<i class="' + s.icon + '" style="color:' + s.color + ';"></i>' +
        '</div>' +
      '</div>' +
      '<div class="plat-stat-value">' + s.value + '</div>' +
      '<div class="plat-stat-footer">' +
        '<span class="plat-stat-pill ' + (s.up ? 'up' : 'dn') + '">' +
          '<i class="fa-solid fa-arrow-' + (s.up ? 'up' : 'down') + '" style="font-size:9px;"></i>' +
          s.change + '%' +
        '</span>' +
        '<span class="plat-stat-vs">vs last 7 days</span>' +
      '</div>' +
    '</div>'
  }).join('')

  // -- Active app tiles (dashboard shows first 5 active products) ------------
  var activeTiles = PRODUCT_CATALOGUE.filter(function(p){ return p.active }).slice(0, 5)
  var tilesHtml = activeTiles.map(function(p) {
    return '<div class="plat-app-tile" onclick="platNavigate(\'product-hub\', { productCode: \'' + p.code + '\' })">' +
      '<button class="plat-app-tile-menu" onclick="event.stopPropagation();platAppMenu(\'' + p.code + '\', event)">&#8942;</button>' +
      '<div class="plat-app-icon-area">' +
        '<i class="' + p.icon + '" style="color:' + p.color + ';"></i>' +
      '</div>' +
      '<div class="plat-app-name">' + p.name + '</div>' +
      '<div class="plat-app-fullname">' + p.fullName + '</div>' +
      '<button class="plat-app-open-btn" style="color:' + p.color + ';">' +
        'Open App <i class="fa-solid fa-arrow-right" style="font-size:11px;"></i>' +
      '</button>' +
    '</div>'
  }).join('')

  // -- Charts ----------------------------------------------------------------
  var lineChart  = buildPlatLineChart()
  var donutChart = buildPlatDonutChart()

  // -- System Alerts ---------------------------------------------------------
  var alerts = [
    { icon: 'fa-solid fa-triangle-exclamation', bg: '#fff7ed', color: '#f59e0b', title: 'High Server Load',          desc: 'API server CPU above 85% for 15 min',       time: '5m ago'  },
    { icon: 'fa-solid fa-circle-info',          bg: '#eff6ff', color: '#3b82f6', title: 'Scheduled Maintenance',     desc: 'Planned downtime: May 19, 02:00–04:00 UTC',  time: '1h ago'  },
    { icon: 'fa-solid fa-circle-check',         bg: '#f0fdf4', color: '#22c55e', title: 'Backup Completed',          desc: 'Daily database backup finished successfully', time: '3h ago'  },
    { icon: 'fa-solid fa-shield-halved',        bg: '#fdf4ff', color: '#a855f7', title: 'Security Scan Passed',      desc: 'No vulnerabilities found in latest scan',   time: '6h ago'  },
  ]

  var alertsHtml = alerts.map(function(a) {
    return '<div class="plat-alert-item">' +
      '<div class="plat-alert-icon" style="background:' + a.bg + ';">' +
        '<i class="' + a.icon + '" style="color:' + a.color + ';font-size:13px;"></i>' +
      '</div>' +
      '<div class="plat-alert-body">' +
        '<div class="plat-alert-title">' + a.title + '</div>' +
        '<div class="plat-alert-desc">' + a.desc + '</div>' +
      '</div>' +
      '<div class="plat-alert-time">' + a.time + '</div>' +
    '</div>'
  }).join('')

  // -- Recent Activity -------------------------------------------------------
  var activities = [
    { icon: 'fa-solid fa-user-plus',    bg: '#f0fdf4', color: '#22c55e', title: 'New Organization Added',   desc: 'TechCorp Pvt Ltd registered on the platform', time: '12m ago' },
    { icon: 'fa-solid fa-bolt',         bg: '#fff7ed', color: '#f97316', title: 'Automation Triggered',     desc: 'Onboarding workflow started for Ganga Realty', time: '1h ago'  },
    { icon: 'fa-solid fa-credit-card',  bg: '#eff6ff', color: '#3b82f6', title: 'Subscription Renewed',     desc: 'Ganga Realty renewed CRM + LMS plan',          time: '3h ago'  },
    { icon: 'fa-solid fa-circle-check', bg: '#f5f3ff', color: '#8b5cf6', title: 'Deployment Successful',    desc: 'Platform v2.4.1 deployed to production',       time: '5h ago'  },
  ]

  var activityHtml = activities.map(function(a) {
    return '<div class="plat-activity-item">' +
      '<div class="plat-activity-icon" style="background:' + a.bg + ';">' +
        '<i class="' + a.icon + '" style="color:' + a.color + ';font-size:14px;"></i>' +
      '</div>' +
      '<div class="plat-activity-body">' +
        '<div class="plat-activity-title">' + a.title + '</div>' +
        '<div class="plat-activity-desc">' + a.desc + '</div>' +
      '</div>' +
      '<div class="plat-activity-time">' + a.time + '</div>' +
    '</div>'
  }).join('')

  // -- Product stat cards (bottom) -------------------------------------------
  var prodStats = [
    { code: 'lms',         metric: 'Courses',           value: '2,345',  change: '+15.6' },
    { code: 'crm',         metric: 'Leads',             value: '18,932', change: '+11.8' },
    { code: 'procurement', metric: 'POs Created',       value: '7,892',  change: '+13.4' },
    { code: 'wms',         metric: 'Items Managed',     value: '12,456', change: '+10.3' },
    { code: 'amazon',      metric: 'Insights Generated',value: '4,321',  change: '+16.7' },
  ]

  var prodStatsHtml = prodStats.map(function(ps) {
    var prod = PRODUCT_CATALOGUE.find(function(p){ return p.code === ps.code }) || {}
    return '<div class="plat-prod-stat-card">' +
      '<div class="plat-prod-stat-head">' +
        '<i class="' + (prod.icon || 'fa-solid fa-circle') + '" style="color:' + (prod.color || '#94a3b8') + ';"></i>' +
        '<span class="plat-prod-stat-name">' + (prod.name || ps.code) + '</span>' +
      '</div>' +
      '<div class="plat-prod-stat-metric">' + ps.metric + '</div>' +
      '<div class="plat-prod-stat-value">' + ps.value + '</div>' +
      '<div class="plat-prod-stat-change">' +
        '<i class="fa-solid fa-arrow-trend-up" style="font-size:11px;"></i>' + ps.change + '% vs last 7 days' +
      '</div>' +
    '</div>'
  }).join('')

  // -- Assemble full dashboard -----------------------------------------------
  el.innerHTML =
    '<div class="plat-stats-grid">' + statsHtml + '</div>' +

    '<div class="plat-section-header" style="margin-bottom:12px;">' +
      '<h3 class="plat-section-title">Applications Suite</h3>' +
      '<button class="plat-section-link" onclick="platNavigate(\'applications\')">View all applications &#x2192;</button>' +
    '</div>' +
    '<div class="plat-apps-grid">' + tilesHtml + '</div>' +

    '<div class="plat-dash-grid">' +
      '<div>' +
        '<div class="plat-charts-row">' +
          '<div class="plat-chart-card">' +
            '<div class="plat-chart-header">' +
              '<div>' +
                '<div class="plat-chart-title">Platform Overview</div>' +
                '<div class="plat-chart-legend" style="margin-top:6px;">' +
                  '<span><span class="plat-legend-dot" style="background:#6366f1;"></span>Users</span>' +
                  '<span><span class="plat-legend-dot" style="background:#22c55e;"></span>Sessions</span>' +
                  '<span><span class="plat-legend-dot" style="background:#3b82f6;"></span>Transactions</span>' +
                '</div>' +
              '</div>' +
              '<select class="plat-chart-filter"><option>7 Days</option><option>30 Days</option><option>90 Days</option></select>' +
            '</div>' +
            lineChart +
          '</div>' +
          '<div class="plat-chart-card">' +
            '<div class="plat-chart-header"><div class="plat-chart-title">Application Usage</div></div>' +
            donutChart +
          '</div>' +
        '</div>' +
        '<div class="plat-section-header" style="margin-bottom:12px;margin-top:4px;">' +
          '<h3 class="plat-section-title">Product Performance</h3>' +
          '<span class="plat-stat-vs">Last 7 days</span>' +
        '</div>' +
        '<div class="plat-product-stats">' + prodStatsHtml + '</div>' +
      '</div>' +

      '<div class="plat-right-col">' +
        '<div class="plat-panel">' +
          '<div class="plat-panel-header">' +
            '<div class="plat-panel-title"><i class="fa-solid fa-bell" style="color:#f59e0b;font-size:13px;margin-right:6px;"></i>System Alerts</div>' +
            '<button class="plat-panel-viewall">View all</button>' +
          '</div>' +
          alertsHtml +
        '</div>' +
        '<div class="plat-panel">' +
          '<div class="plat-panel-header">' +
            '<div class="plat-panel-title"><i class="fa-solid fa-clock-rotate-left" style="color:#6366f1;font-size:13px;margin-right:6px;"></i>Recent Activity</div>' +
            '<button class="plat-panel-viewall">View all</button>' +
          '</div>' +
          activityHtml +
        '</div>' +
      '</div>' +
    '</div>'
}

// -- Line chart (SVG) ---------------------------------------------------------

function buildPlatLineChart() {
  var W = 440, H = 200, padL = 44, padR = 16, padT = 12, padB = 36
  var labels = ['May 12','May 13','May 14','May 15','May 16','May 17','May 18']

  var users   = [18000, 22000, 19500, 25000, 28000, 24000, 32000]
  var sessions = [12000, 15000, 13500, 18000, 20000, 17500, 24000]
  var txns    = [8000,  10000, 9000,  12000, 14000, 11000, 16000]

  var allVals  = users.concat(sessions).concat(txns)
  var maxVal   = Math.max.apply(null, allVals)
  var chartW   = W - padL - padR
  var chartH   = H - padT - padB

  function toX(i) { return padL + (i / (labels.length - 1)) * chartW }
  function toY(v) { return padT + chartH - (v / (maxVal * 1.1)) * chartH }

  function makePath(vals, color) {
    var d = vals.map(function(v, i) { return (i === 0 ? 'M' : 'L') + toX(i) + ',' + toY(v) }).join(' ')
    return '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
  }

  function makeArea(vals, color) {
    var d = vals.map(function(v, i) { return (i === 0 ? 'M' : 'L') + toX(i) + ',' + toY(v) }).join(' ')
    d += ' L' + toX(vals.length-1) + ',' + (padT+chartH) + ' L' + toX(0) + ',' + (padT+chartH) + ' Z'
    return '<path d="' + d + '" fill="' + color + '" fill-opacity="0.07"/>'
  }

  // Y-axis labels
  var yTicks = [0, 10000, 20000, 30000, 40000].filter(function(v){ return v <= maxVal * 1.15 })
  var yLabels = yTicks.map(function(v) {
    return '<text x="' + (padL - 6) + '" y="' + (toY(v) + 4) + '" text-anchor="end" font-size="10" fill="#94a3b8">' + (v >= 1000 ? (v/1000) + 'K' : v) + '</text>' +
           '<line x1="' + padL + '" y1="' + toY(v) + '" x2="' + (W - padR) + '" y2="' + toY(v) + '" stroke="#f1f5f9" stroke-width="1"/>'
  }).join('')

  // X-axis labels
  var xLabels = labels.map(function(l, i) {
    return '<text x="' + toX(i) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="10" fill="#94a3b8">' + l + '</text>'
  }).join('')

  return '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block;">' +
    yLabels + xLabels +
    makeArea(users,   '#6366f1') +
    makeArea(sessions,'#22c55e') +
    makeArea(txns,    '#3b82f6') +
    makePath(users,   '#6366f1') +
    makePath(sessions,'#22c55e') +
    makePath(txns,    '#3b82f6') +
  '</svg>'
}

// -- Donut chart (SVG) --------------------------------------------------------

function buildPlatDonutChart() {
  var segments = [
    { label: 'LMS',                  pct: 24.5, color: '#8b5cf6' },
    { label: 'CRM',                  pct: 21.3, color: '#22c55e' },
    { label: 'Procurement',          pct: 18.7, color: '#f59e0b' },
    { label: '3D Inventory',         pct: 17.2, color: '#3b82f6' },
    { label: 'Amazon Intelligence',  pct: 18.3, color: '#f97316' },
  ]

  var cx = 90, cy = 90, R = 72, r = 48
  var total = segments.reduce(function(a, s){ return a + s.pct }, 0)
  var angle = -Math.PI / 2

  function arc(pct) {
    var a  = (pct / total) * 2 * Math.PI
    var x1 = cx + R * Math.cos(angle)
    var y1 = cy + R * Math.sin(angle)
    angle += a
    var x2 = cx + R * Math.cos(angle)
    var y2 = cy + R * Math.sin(angle)
    var xi1 = cx + r * Math.cos(angle)
    var yi1 = cy + r * Math.sin(angle)
    var xi2 = cx + r * Math.cos(angle - a)
    var yi2 = cy + r * Math.sin(angle - a)
    var large = a > Math.PI ? 1 : 0
    return 'M' + x1 + ',' + y1 +
           ' A' + R + ',' + R + ' 0 ' + large + ',1 ' + x2 + ',' + y2 +
           ' L' + xi1 + ',' + yi1 +
           ' A' + r + ',' + r + ' 0 ' + large + ',0 ' + xi2 + ',' + yi2 + ' Z'
  }

  var paths = segments.map(function(s) {
    return '<path d="' + arc(s.pct) + '" fill="' + s.color + '" stroke="#fff" stroke-width="2"/>'
  }).join('')

  var legendHtml = segments.map(function(s) {
    return '<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">' +
      '<span style="width:10px;height:10px;border-radius:50%;background:' + s.color + ';flex-shrink:0;"></span>' +
      '<span style="font-size:12px;color:#374151;">' + s.label + '</span>' +
      '<span style="margin-left:auto;font-size:12px;font-weight:700;color:#0f172a;">' + s.pct + '%</span>' +
    '</div>'
  }).join('')

  return '<div style="display:flex;align-items:center;gap:14px;">' +
    '<div style="flex-shrink:0;">' +
      '<svg viewBox="0 0 180 180" width="160" height="160">' +
        paths +
        '<text x="' + cx + '" y="' + (cy - 7) + '" text-anchor="middle" font-size="11" fill="#64748b">Total Usage</text>' +
        '<text x="' + cx + '" y="' + (cy + 12) + '" text-anchor="middle" font-size="20" font-weight="800" fill="#0f172a">78.4%</text>' +
      '</svg>' +
    '</div>' +
    '<div style="flex:1;">' + legendHtml + '</div>' +
  '</div>'
}

// -- App tile context menu -----------------------------------------------------

function platAppMenu(code, evt) {
  evt.stopPropagation()
  var prod = PRODUCT_CATALOGUE.find(function(p){ return p.code === code }) || { name: code }
  var existing = document.getElementById('platAppMenuPopup')
  if (existing) existing.remove()

  var menu = document.createElement('div')
  menu.id = 'platAppMenuPopup'
  menu.style.cssText = 'position:fixed;background:#fff;border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:9999;min-width:160px;padding:6px 0;font-size:13px;'
  menu.innerHTML =
    '<div style="padding:6px 14px;color:#374151;cursor:pointer;" onmouseover="this.style.background=\'#f8fafc\'" onmouseout="this.style.background=\'\'">View Clients</div>' +
    '<div style="padding:6px 14px;color:#374151;cursor:pointer;" onmouseover="this.style.background=\'#f8fafc\'" onmouseout="this.style.background=\'\'">Configure</div>' +
    '<div style="padding:6px 14px;color:#374151;cursor:pointer;" onmouseover="this.style.background=\'#f8fafc\'" onmouseout="this.style.background=\'\'">Analytics</div>' +
    '<div style="height:1px;background:#f1f5f9;margin:4px 0;"></div>' +
    '<div style="padding:6px 14px;color:#ef4444;cursor:pointer;" onmouseover="this.style.background=\'#fef2f2\'" onmouseout="this.style.background=\'\'">Disable App</div>'

  var r = evt.target.getBoundingClientRect()
  menu.style.top  = (r.bottom + 4) + 'px'
  menu.style.left = (r.left - 80) + 'px'

  document.body.appendChild(menu)
  setTimeout(function() { document.addEventListener('click', function h() { menu.remove(); document.removeEventListener('click', h) }) }, 10)
}
