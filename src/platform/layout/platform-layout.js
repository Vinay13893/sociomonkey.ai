// ============================================================================
// PLATFORM LAYOUT � Sidebar + Topbar chrome for the SocioMonkey Platform layer
// v2: Font Awesome icons, refined premium design
// ============================================================================

const PLAT_NAV = [
  { view: 'dashboard',    icon: 'fa-solid fa-gauge-high',     label: 'Dashboard',               color: '#6366f1' },
  { view: 'applications', icon: 'fa-solid fa-border-all',     label: 'Applications',            color: '#8b5cf6' },
  { view: 'users',        icon: 'fa-solid fa-user-group',     label: 'Users & Roles',           color: '#22c55e' },
  { view: 'organizations',icon: 'fa-solid fa-building',       label: 'Organizations',           color: '#3b82f6' },
  { view: 'analytics',    icon: 'fa-solid fa-chart-line',     label: 'Analytics & Reports',     color: '#f59e0b' },
  { view: 'billing',      icon: 'fa-solid fa-credit-card',    label: 'Billing & Subscriptions', color: '#ec4899' },
  { view: 'integrations', icon: 'fa-solid fa-plug',           label: 'Integrations',            color: '#06b6d4' },
  { view: 'automation',   icon: 'fa-solid fa-bolt',           label: 'Automation',              color: '#f97316' },
  { view: 'settings',     icon: 'fa-solid fa-gear',           label: 'Settings',                color: '#94a3b8' },
  { view: 'audit-logs',   icon: 'fa-solid fa-clipboard-list', label: 'Audit Logs',              color: '#64748b' },
  { view: 'support',      icon: 'fa-solid fa-headset',        label: 'Support',                 color: '#10b981' },
]

const PLAT_ROUTE_MAP = {
  dashboard:     '/',
  applications:  '/applications',
  users:         '/users',
  organizations: '/organizations',
  analytics:     '/analytics',
  billing:       '/billing',
  integrations:  '/integrations',
  automation:    '/automation',
  settings:      '/settings',
  'audit-logs':  '/audit-logs',
  support:       '/support',
}

// -- Main render --------------------------------------------------------------

function renderPlatformLayout(activeView) {
  const platRoot     = document.getElementById('platformRoot')
  const tenantLayout = document.getElementById('tenantLayout')
  platRoot.style.display  = 'flex'
  if (tenantLayout) tenantLayout.style.display = 'none'

  const userName = (user && user.name) ? user.name : 'Admin User'
  const initials = userName.split(' ').map(function(w){ return w[0] }).join('').slice(0,2).toUpperCase()
  const pageInfo = getPlatViewInfo(activeView)
  const highlightView = (activeView === 'product-hub') ? 'applications' : activeView

  const navItems = PLAT_NAV.map(function(n) {
    var isActive = n.view === highlightView
    return '<button class="sm-sidebar-nav-item' + (isActive ? ' active' : '') + '"' +
           ' onclick="platNavigate(\'' + n.view + '\')">' +
           '<i class="' + n.icon + '" style="color:' + (isActive ? '#fff' : n.color) + ';"></i>' +
           n.label + '</button>'
  }).join('')

  platRoot.innerHTML =
    '<aside class="sm-sidebar">' +
      '<div class="sm-sidebar-brand">' +
        '<div class="sm-sidebar-logo-wrap">' +
          '<img src="Assets/credentials-card-logo.png" alt="Sociomonkey" class="sm-sidebar-logo" />' +
        '</div>' +
        '<div class="sm-sidebar-tagline">AI Powered Software Suite for Businesses</div>' +
      '</div>' +
      '<nav class="sm-sidebar-nav">' +
        navItems +
        '<div class="sm-sidebar-divider"></div>' +
        '<button class="sm-sidebar-nav-item" onclick="platLogout()">' +
          '<i class="fa-solid fa-right-from-bracket"></i> Sign Out' +
        '</button>' +
      '</nav>' +
      '<div class="sm-sidebar-footer">' +
        '<div class="sm-sidebar-status-row">' +
          '<span class="sm-sidebar-status-dot"></span>' +
          '<span class="sm-sidebar-status-label">All Systems Operational</span>' +
        '</div>' +
        '<div class="sm-sidebar-status-uptime">Uptime 99.98%</div>' +
        '<div class="sm-sidebar-copy">&#169; 2026 sociomonkey.ai<br>All rights reserved.</div>' +
      '</div>' +
    '</aside>' +
    '<div class="plat-wrapper">' +
      '<header class="plat-topbar">' +
        '<div class="plat-topbar-title">' +
          '<h2>' + pageInfo.title + '</h2>' +
          '<p>' + pageInfo.subtitle + '</p>' +
        '</div>' +
        '<div class="plat-search">' +
          '<i class="fa-solid fa-magnifying-glass plat-search-icon"></i>' +
          '<input type="text" placeholder="Search users, modules, reports\u2026  \u2318K" />' +
        '</div>' +
        '<div class="plat-topbar-actions">' +
          '<div class="plat-date-badge">' +
            '<i class="fa-regular fa-calendar" style="color:#94a3b8;font-size:13px;"></i>' +
            platDateRange() +
          '</div>' +
          '<div class="plat-icon-btn" title="Notifications">' +
            '<i class="fa-solid fa-bell"></i>' +
            '<span class="plat-notif-badge">3</span>' +
          '</div>' +
          '<div class="plat-icon-btn" title="Help">' +
            '<i class="fa-regular fa-circle-question"></i>' +
          '</div>' +
          '<div class="plat-user-chip">' +
            '<div class="plat-avatar">' + initials + '</div>' +
            '<div class="plat-user-info">' +
              '<div class="plat-user-name">' + platEsc(userName) + '</div>' +
              '<div class="plat-user-role">Super Admin</div>' +
            '</div>' +
            '<i class="fa-solid fa-chevron-down" style="color:#94a3b8;font-size:10px;margin-left:4px;"></i>' +
          '</div>' +
        '</div>' +
      '</header>' +
      '<main class="plat-main" id="platContent">' +
        '<div style="text-align:center;padding:60px;color:#94a3b8;">' +
          '<i class="fa-solid fa-spinner fa-spin" style="font-size:28px;"></i>' +
        '</div>' +
      '</main>' +
    '</div>'

  renderPlatformView(activeView)
}

// -- View info ----------------------------------------------------------------

function getPlatViewInfo(view) {
  var map = {
    'dashboard':     { title: 'Welcome back, Admin &#x1F44B;', subtitle: "Here&#x27;s what&#x27;s happening across your platform today." },
    'applications':  { title: 'Applications Suite',             subtitle: 'Manage, launch and configure your product ecosystem.' },
    'product-hub':   { title: 'Product Hub',                    subtitle: 'View subscribed clients and launch applications.' },
    'users':         { title: 'Users &amp; Roles',              subtitle: 'Manage platform users, roles and permissions.' },
    'organizations': { title: 'Organizations',                  subtitle: 'Manage client organizations and tenant accounts.' },
    'analytics':     { title: 'Analytics &amp; Reports',        subtitle: 'Platform-wide insights, metrics and reports.' },
    'billing':       { title: 'Billing &amp; Subscriptions',    subtitle: 'Revenue, invoices and subscription management.' },
    'integrations':  { title: 'Integrations',                   subtitle: 'Third-party services and API connections.' },
    'automation':    { title: 'Automation',                     subtitle: 'Workflow automation, triggers and sequences.' },
    'settings':      { title: 'Platform Settings',              subtitle: 'Configure platform preferences and security.' },
    'audit-logs':    { title: 'Audit Logs',                     subtitle: 'Full audit trail of all platform activities.' },
    'support':       { title: 'Support',                        subtitle: 'Help desk, tickets and support resources.' },
  }
  return map[view] || { title: 'Platform', subtitle: '' }
}

// -- View dispatcher ----------------------------------------------------------

function renderPlatformView(view) {
  switch (view) {
    case 'dashboard':     renderPlatformHome();                          break
    case 'applications':  renderProductLauncher();                       break
    case 'product-hub':   renderProductHub(platformContext.productCode); break
    case 'organizations': renderPlatformOrgs();                          break
    case 'analytics':     renderPlatformAnalytics();                     break
    case 'billing':       renderPlatformBilling();                       break
    case 'settings':      renderPlatformSettings();                      break
    default:              renderPlatStub(view);                          break
  }
}

// -- Navigation ---------------------------------------------------------------

function platNavigate(view, context) {
  platformView    = view
  platformContext = context || {}
  var path = (view === 'product-hub' && platformContext.productCode)
    ? '/products/' + platformContext.productCode
    : (PLAT_ROUTE_MAP[view] || '/')
  history.pushState({}, '', path)
  renderPlatformLayout(view)
}

function platLogout() {
  authClearSession()
  clearTenantContext()
  history.replaceState({}, '', '/login')
  if (typeof _setPublicLoginMode === 'function') {
    _setPublicLoginMode(true)
  } else {
    document.getElementById('platformRoot').style.display = 'none'
    var tl = document.getElementById('tenantLayout')
    if (tl) tl.style.display = 'none'
  }
  if (typeof renderLogin === 'function') renderLogin({ type: 'platform' })
  if (typeof dispatch === 'function') dispatch()
}

function platOpenStatus() {
  showToast('Status page coming soon!', 'warning')
}

// -- Stub renderer ------------------------------------------------------------

function renderPlatStub(view) {
  var el = document.getElementById('platContent')
  if (!el) return
  var info = getPlatViewInfo(view)
  el.innerHTML =
    '<div class="plat-empty" style="margin-top:80px;">' +
      '<div class="plat-empty-icon"><i class="fa-solid fa-wrench" style="font-size:40px;color:#c7d2fe;"></i></div>' +
      '<div class="plat-empty-title">' + info.title + '</div>' +
      '<div class="plat-empty-desc">This section is under construction and will be available soon.</div>' +
    '</div>'
}

// -- Helpers ------------------------------------------------------------------

function platDateRange() {
  var now   = new Date()
  var start = new Date(now); start.setDate(now.getDate() - 6)
  var fmt   = function(d) { return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }
  return fmt(start) + ' \u2013 ' + fmt(now) + ', ' + now.getFullYear()
}

function platEsc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
