// ─── Sidebar Performance State ────────────────────────────────────────────
var _sidebarBuilt = false
var _sidebarForProduct = null
var _sidebarForSlug = undefined   // tracks platformTenantSlug at last build

function renderApp() {
  _PERF.count('renderApp')
  _PERF.mark('renderApp')
  // Only rebuild sidebar when product/slug context changes (not on every tab click)
  if (!_sidebarBuilt || _sidebarForProduct !== currentProduct || _sidebarForSlug !== platformTenantSlug) {
    _buildSidebar()
    _sidebarBuilt = true
    _sidebarForProduct = currentProduct
    _sidebarForSlug = platformTenantSlug
  } else {
    _syncNavActive()
  }

  // Always update the main content area
  var _domT = performance.now()
  root.innerHTML = '<div id="content"></div>'
  _PERF.lap('renderApp', 'root-innerHTML: ' + (performance.now() - _domT).toFixed(1) + 'ms')
  _safeShowContent()

  // Re-apply tenant branding (logo, CSS vars) after sidebar re-renders
  if (typeof reapplyTenantBranding === 'function') reapplyTenantBranding()
  _PERF.end('renderApp')
}

function _buildSidebar() {
  _PERF.count('_buildSidebar')
  _PERF.mark('_buildSidebar')
  var navItems = getNavItems()

  // ── Product label below logo (tenant users) ──────────────────────────────────
  var productLabel = document.getElementById('sidebarProductLabel')
  if (productLabel) {
    if (user.role !== 'platform_owner' || platformTenantSlug) {
      var prod = availableProducts.find(function(p) { return p.slug === currentProduct })
      productLabel.textContent = ((prod && prod.name) || 'Lead Management System').replace(/\s*\([^)]*\)\s*$/, '').trim()
      productLabel.style.display = 'block'
    } else {
      productLabel.style.display = 'none'
    }
  }

  // ── User display ─────────────────────────────────────────────────────────────
  var userDisplay = document.getElementById('userDisplay')
  if (userDisplay) {
    userDisplay.innerHTML = '<strong>' + escape(user.name) + '</strong><br/><small>' + getRoleDisplay(user.role) + '</small>'
  }

  // ── Nav items: rebuild HTML + attach single delegated listener ─────────────────────
  var sidebarNav = document.getElementById('sidebarNav')
  if (sidebarNav) {
    sidebarNav.innerHTML = navItems.map(function(item) {
      return '<button class="sm-sidebar-nav-item' + (activeTab === item.key ? ' active' : '') + '" data-tab="' + item.key + '">' +
        item.label +
      '</button>'
    }).join('') +
    '<div class="sm-sidebar-divider"></div>' +
    '<button class="sm-sidebar-nav-item" id="logoutBtn"><i class="fas fa-sign-out-alt" style="margin-right:8px;"></i>Logout</button>'
    // Clone to drop any previous delegated listener, then re-attach once
    var freshNav = sidebarNav.cloneNode(false)
    freshNav.innerHTML = sidebarNav.innerHTML
    sidebarNav.parentNode.replaceChild(freshNav, sidebarNav)
    freshNav.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-tab]')
      if (!btn) return
      activeTab = btn.dataset.tab
      if (platformTenantSlug) {
        history.pushState({}, '', authBuildTenantTabPath(platformTenantSlug, 'lms', activeTab))
      }
      closeMobileSidebar()
      _syncNavActive()
      // If a full dispatch() is in flight it will call renderApp() → _safeShowContent()
      // with the updated activeTab when it completes. Skip the redundant render here
      // to prevent a duplicate render cycle that would show up in _PERF.count().
      if (typeof _dispatchInFlight !== 'undefined' && _dispatchInFlight) return
      root.innerHTML = '<div id="content"></div>'
      _safeShowContent()
    })
  }

  // ── Logout: clone to reset accumulated listeners ───────────────────────────────────────
  var logoutBtn = document.getElementById('logoutBtn')
  if (logoutBtn) {
    var freshBtn = logoutBtn.cloneNode(true)
    logoutBtn.parentNode.replaceChild(freshBtn, logoutBtn)
    freshBtn.addEventListener('click', function () {
      var tenantLoginSlug = ''
      try {
        if (typeof parseRoute === 'function') {
          var route = parseRoute()
          if (route && (route.layer === 'tenant' || route.layer === 'tenant-login') && route.slug) {
            tenantLoginSlug = route.slug
          }
        }
      } catch (_) {}
      if (!tenantLoginSlug && user && user.role !== 'platform_owner' && user.tenant_slug) {
        tenantLoginSlug = user.tenant_slug
      }
      var loginPath = tenantLoginSlug ? authBuildTenantLoginPath(tenantLoginSlug, 'lms') : '/login'

      _sidebarBuilt = false
      mobileNavInitialized = false
      if (typeof destroyNotifBell === 'function') destroyNotifBell()
      authClearSession()
      clearTenantContext()
      // Force public login route to avoid retaining tenant shell/branding.
      history.replaceState({}, '', loginPath)
      if (typeof _setPublicLoginMode === 'function') {
        _setPublicLoginMode(true)
      }
      if (typeof renderLogin === 'function') {
        if (tenantLoginSlug) {
          renderLogin({ type: 'tenant', slug: tenantLoginSlug, product: 'lms' })
        } else {
          renderLogin({ type: 'platform' })
        }
      }
      dispatch()
    })
  }
  _PERF.end('_buildSidebar')

  // Init notification bell after sidebar is built
  if (typeof initNotifBell === 'function') initNotifBell()
}

function _syncNavActive() {
  var navEl = document.getElementById('sidebarNav')
  if (!navEl) return
  navEl.querySelectorAll('[data-tab]').forEach(function (btn) {
    btn.classList.toggle('active', btn.dataset.tab === activeTab)
  })
}

function getNavItems() {
  // Platform owner outside tenant context
  if (user.role === 'platform_owner' && !platformTenantSlug) {
    return [
      { key: 'platform', label: '🌐 Platform Admin' },
      { key: 'profile',  label: '⚙️ My Profile' },
    ]
  }

  // LMS product nav
  var items = [
    { key: 'dashboard',    label: '📊 Dashboard' },
    { key: 'action_board', label: '🎯 Action Board' },
    { key: 'leads',        label: '👥 Leads' },
  ]

  if (isTenantFeatureEnabled('pipeline')) {
    items.push({ key: 'pipeline', label: '📈 Pipeline' })
  }
  if (user.role === 'sales_manager' || user.role === 'superadmin') {
    items.push({ key: 'assign_reassign', label: '📋 Allocation' })
  }
  if ((user.role === 'sales_manager' || user.role === 'superadmin') && isTenantFeatureEnabled('team_management')) {
    items.push({ key: 'team', label: '👨‍💼 Team' })
  }
  items.push({ key: 'projects', label: '🏢 Projects' })
  if ((user.role === 'sales_manager' || user.role === 'superadmin') && isTenantFeatureEnabled('bulk_import')) {
    items.push({ key: 'excel', label: '📤 Import Leads' })
  }
  if (user.role === 'superadmin' && isTenantFeatureEnabled('export')) {
    items.push({ key: 'export', label: '📥 Export Leads' })
  }
  if (user.role === 'superadmin' && isTenantFeatureEnabled('activity_logs')) {
    items.push({ key: 'activitylogs', label: '📋 Activity Logs' })
  }
  if (user.role === 'sales_manager') {
    items.push({ key: 'activitylogs', label: '📋 Activity Logs' })
  }
  if (user.role === 'team_member') {
    items.push({ key: 'activitylogs', label: '📋 My Activity' })
  }
  if ((user.role === 'superadmin' || user.role === 'sales_manager') && isTenantFeatureEnabled('reports')) {
    items.push({ key: 'reports', label: '📊 Reports' })
  }
  if (user.role === 'superadmin' || user.role === 'sales_manager' || user.role === 'platform_owner') {
    items.push({ key: 'lead_sources', label: '🔗 Lead Sources' })
  }

  items.push({ key: 'profile', label: '⚙️ My Profile' })
  return items
}
