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
        '<div class="plat-topbar-actions">' +
          '<div class="plat-icon-btn" title="Notifications" onclick="platToggleNotifications(event)">' +
            '<i class="fa-solid fa-bell"></i>' +
            '<span id="platNotifBadge" class="plat-notif-badge" style="display:none;">0</span>' +
          '</div>' +
          '<div class="plat-user-chip" onclick="platToggleUserMenu(event)">' +
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
    'dashboard':     { title: 'Welcome back, Admin &#x1F44B;', subtitle: '' },
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

function platEsc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function platToggleNotifications(event) {
  event.stopPropagation()
  platCloseMenus('notifications')
  var existing = document.getElementById('platNotificationsMenu')
  if (existing) return existing.remove()

  var menu = document.createElement('div')
  menu.id = 'platNotificationsMenu'
  menu.style.cssText = 'position:fixed;right:176px;top:58px;width:min(360px,calc(100vw - 24px));background:#fff;border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 18px 50px rgba(15,23,42,.18);z-index:1800;overflow:hidden;'
  menu.innerHTML =
    '<div style="padding:14px 16px;border-bottom:1px solid #f1f5f9;font-size:14px;font-weight:800;color:#0f172a;">Platform Notifications</div>' +
    '<div style="padding:18px 16px;color:#64748b;font-size:13px;line-height:1.5;">No platform notifications are available yet.</div>'
  document.body.appendChild(menu)
}

function platToggleUserMenu(event) {
  event.stopPropagation()
  platCloseMenus('user')
  var existing = document.getElementById('platUserMenu')
  if (existing) return existing.remove()

  var menu = document.createElement('div')
  menu.id = 'platUserMenu'
  menu.style.cssText = 'position:fixed;right:24px;top:58px;width:190px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 18px 50px rgba(15,23,42,.18);z-index:1800;overflow:hidden;padding:6px;'
  menu.innerHTML =
    '<button onclick="platUserMenuAction(\'profile\')" style="width:100%;border:0;background:#fff;text-align:left;padding:10px 12px;border-radius:8px;font-size:13px;color:#0f172a;cursor:pointer;"><i class="fa-solid fa-user" style="width:18px;color:#64748b;"></i>Profile</button>' +
    '<button onclick="platUserMenuAction(\'settings\')" style="width:100%;border:0;background:#fff;text-align:left;padding:10px 12px;border-radius:8px;font-size:13px;color:#0f172a;cursor:pointer;"><i class="fa-solid fa-gear" style="width:18px;color:#64748b;"></i>Settings</button>' +
    '<div style="height:1px;background:#f1f5f9;margin:4px;"></div>' +
    '<button onclick="platLogout()" style="width:100%;border:0;background:#fff;text-align:left;padding:10px 12px;border-radius:8px;font-size:13px;color:#dc2626;cursor:pointer;"><i class="fa-solid fa-right-from-bracket" style="width:18px;"></i>Sign Out</button>'
  document.body.appendChild(menu)
}

function platUserMenuAction(action) {
  platCloseMenus()
  if (action === 'settings') {
    platNavigate('settings')
    return
  }
  showToast('Profile page coming soon.', 'warning')
}

function platCloseMenus(keep) {
  if (keep !== 'notifications') {
    var n = document.getElementById('platNotificationsMenu')
    if (n) n.remove()
  }
  if (keep !== 'user') {
    var u = document.getElementById('platUserMenu')
    if (u) u.remove()
  }
}

document.addEventListener('click', function () {
  platCloseMenus()
})
