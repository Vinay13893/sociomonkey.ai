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

  // ── Product switcher: platform_owner only ──────────────────────────────────────────
  var switcher = document.getElementById('productSwitcher')
  if (switcher) {
    if (user.role === 'platform_owner' && availableProducts.length > 0) {
      switcher.innerHTML =
        '<div style="padding:6px 12px 2px;font-size:10px;font-weight:700;color:rgba(255,255,255,.5);letter-spacing:.08em;text-transform:uppercase;">Products</div>' +
        availableProducts.map(function(p) {
          return '<button onclick="switchProduct(\'' + p.slug + '\')" class="sm-sidebar-nav-item' + (currentProduct === p.slug ? ' active' : '') + '">' +
            (p.icon || '&#x1F4E6;') + ' ' + p.name +
          '</button>'
        }).join('') +
        '<div class="sm-sidebar-divider"></div>'
    } else {
      // Tenant users: no product switcher
      switcher.innerHTML = ''
    }
  }

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
      _sidebarBuilt = false
      mobileNavInitialized = false
      // Capture slug BEFORE clearing session (user becomes null after clear)
      var _slug = (user && user.tenant_slug) ? user.tenant_slug : null
      authClearSession()
      clearTenantContext()
      history.replaceState({}, '', _slug ? '/' + _slug + '/login' : '/login')
      dispatch()
    })
  }
  _PERF.end('_buildSidebar')
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

  // Non-CRM/LMS product → single page
  if (currentProduct !== 'crm' && currentProduct !== 'lms') {
    var prod0 = availableProducts.find(function(p) { return p.slug === currentProduct })
    return [
      { key: 'product_home', label: (prod0 && prod0.icon ? prod0.icon + ' ' : '📦 ') + 'Overview' },
      { key: 'profile',      label: '⚙️ My Profile' },
    ]
  }

  // LMS / CRM product nav
  var items = [
    { key: 'dashboard',    label: '📊 Dashboard' },
    { key: 'action_board', label: '🎯 Action Board' },
    { key: 'leads',        label: '👥 Leads' },
  ]

  if (isTenantFeatureEnabled('pipeline')) {
    items.push({ key: 'pipeline', label: '📈 Pipeline' })
  }
  if (user.role === 'sales_manager' || user.role === 'superadmin') {
    items.push({ key: 'recycle_queue', label: '♻️ Recycle Queue' })
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
  if ((user.role === 'superadmin' || user.role === 'sales_manager') && isTenantFeatureEnabled('reports')) {
    items.push({ key: 'reports', label: '📊 Reports' })
  }

  items.push({ key: 'profile', label: '⚙️ My Profile' })
  return items
}


function switchProduct(slug) {
  currentProduct = slug
  localStorage.setItem('current_product', slug)
  activeTab = (slug === 'crm' || slug === 'lms') ? 'dashboard' : 'product_home'
  _sidebarBuilt = false   // force full sidebar rebuild on product switch
  renderApp()
}

function renderProductHome() {
  var prod = availableProducts.find(function(p) { return p.slug === currentProduct })
  var content = document.getElementById('content')
  var icon  = prod && prod.icon  ? prod.icon  : '📦'
  var name  = prod && prod.name  ? prod.name  : currentProduct
  var color = prod && prod.color ? prod.color : '#1e3a5f'
  var desc  = prod && prod.description ? prod.description : ''
  content.innerHTML =
    '<div style="padding:40px;text-align:center;max-width:600px;margin:0 auto;">' +
      '<div style="font-size:64px;margin-bottom:16px;">' + icon + '</div>' +
      '<h2 style="font-size:28px;margin-bottom:8px;color:' + color + '">' + name + '</h2>' +
      '<p style="color:#64748b;font-size:15px;margin-bottom:8px;">' + desc + '</p>' +
      '<div style="display:inline-block;padding:4px 14px;border-radius:20px;background:#fef3c7;color:#92400e;font-size:13px;font-weight:600;margin-bottom:32px;">' +
        '🚧 Coming Soon' +
      '</div>' +
      '<p style="color:#94a3b8;font-size:14px;">This module is under active development.<br/>Check back soon for updates.</p>' +
      '<button class="button" onclick="switchProduct(\'lms\')" style="margin-top:24px;">' +
        '← Back to LMS' +
      '</button>' +
    '</div>'
}
