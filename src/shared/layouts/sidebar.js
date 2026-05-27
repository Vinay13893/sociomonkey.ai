function renderApp() {
  const navItems = getNavItems()
  
  // Update product switcher
  const switcher = document.getElementById('productSwitcher')
  if (switcher) {
    if (user.role === 'platform_owner') {
      // Platform owner sees all active products + direct Platform Admin button
      switcher.innerHTML = `
        <div style="padding:8px 12px 4px;font-size:10px;font-weight:700;color:#94a3b8;letter-spacing:.08em;text-transform:uppercase;">Products</div>
        ${availableProducts.map(p => `
          <button onclick="switchProduct('${p.slug}')" style="
            display:block;width:100%;text-align:left;padding:6px 14px;border:none;
            background:${currentProduct === p.slug ? 'rgba(255,255,255,.15)' : 'transparent'};
            color:${currentProduct === p.slug ? '#fff' : '#cbd5e1'};
            font-size:13px;cursor:pointer;border-radius:6px;margin:1px 4px;
          ">
            ${p.icon || 'ðŸ“¦'} ${p.name}
          </button>
        `).join('')}
        <div style="border-top:1px solid rgba(255,255,255,.1);margin:6px 0;"></div>
      `
    } else if (availableProducts.length > 1) {
      switcher.innerHTML = `
        <div style="padding:8px 12px 4px;font-size:10px;font-weight:700;color:#94a3b8;letter-spacing:.08em;text-transform:uppercase;">Switch Product</div>
        ${availableProducts.map(p => `
          <button onclick="switchProduct('${p.slug}')" style="
            display:block;width:100%;text-align:left;padding:6px 14px;border:none;
            background:${currentProduct === p.slug ? 'rgba(255,255,255,.15)' : 'transparent'};
            color:${currentProduct === p.slug ? '#fff' : '#cbd5e1'};
            font-size:13px;cursor:pointer;border-radius:6px;margin:1px 4px;
          ">
            ${p.icon || 'ðŸ“¦'} ${p.name}
          </button>
        `).join('')}
        <div style="border-top:1px solid rgba(255,255,255,.1);margin:6px 0;"></div>
      `
    } else {
      switcher.innerHTML = ''
    }
  }

  // Update sidebar
  const sidebarNav = document.getElementById('sidebarNav')
  sidebarNav.innerHTML = navItems.map((item, idx) => `
    <button class="nav-item ${activeTab === item.key ? 'active' : ''}" id="nav${item.key}" data-tab="${item.key}">
      ${item.label}
    </button>
  `).join('')
  
  // Update user display
  const userDisplay = document.getElementById('userDisplay')
  userDisplay.innerHTML = `<strong>${user.name}</strong><br/><small>${getRoleDisplay(user.role)}</small>`
  
  // Render main content area
  root.innerHTML = '<div id="content"></div>'
  
  // Logout button
  const logoutBtn = document.getElementById('logoutBtn')
  logoutBtn.addEventListener('click', () => {
    mobileNavInitialized = false
    authClearSession()
    clearTenantContext()
    history.replaceState({}, '', '/login')
    dispatch()
  })
  
  // Sidebar navigation click handlers
  navItems.forEach(item => {
    const btn = document.getElementById(`nav${item.key}`)
    if (btn) {
      btn.addEventListener('click', () => {
        activeTab = item.key
        closeMobileSidebar()
        renderApp()
      })
    }
  })
  
  _safeShowContent()

  // Re-apply tenant branding (logo, CSS vars) after sidebar re-renders
  if (typeof reapplyTenantBranding === 'function') reapplyTenantBranding()
}

function getNavItems() {
  // Platform owner outside tenant context → Platform Admin nav only
  if (user.role === 'platform_owner' && !platformTenantSlug) {
    return [
      { key: 'platform', label: '🌐 Platform Admin' },
      { key: 'profile', label: '⚙️ My Profile' },
    ]
  }

  // Non-CRM/LMS product → single "Coming Soon" page
  if (currentProduct !== 'crm' && currentProduct !== 'lms') {
    const prod = availableProducts.find(p => p.slug === currentProduct)
    return [
      { key: 'product_home', label: `${prod?.icon || 'ðŸ“¦'} Overview` },
      { key: 'profile', label: 'âš™ï¸ My Profile' },
    ]
  }

  // CRM product (default)
  // CRM product (default)
  const items = [
    { key: 'dashboard', label: '📊 Dashboard' },
    { key: 'leads',     label: '👥 Leads' },
    { key: 'projects',  label: '🏢 Projects' },
  ]

  if (isTenantFeatureEnabled('pipeline')) {
    items.splice(2, 0, { key: 'pipeline', label: '📈 Pipeline' })
  }
  if ((user.role === 'sales_manager' || user.role === 'superadmin') && isTenantFeatureEnabled('team_management')) {
    items.push({ key: 'team', label: '👨‍💼 Team' })
  }
  if ((user.role === 'sales_manager' || user.role === 'superadmin') && isTenantFeatureEnabled('bulk_import')) {
    items.push({ key: 'excel', label: '📤 Import Excel' })
  }
  if ((user.role === 'superadmin' || user.role === 'sales_manager') && isTenantFeatureEnabled('reports')) {
    items.push({ key: 'reports', label: '📊 Reports' })
  }
  if (user.role === 'superadmin' && isTenantFeatureEnabled('export')) {
    items.push({ key: 'export', label: '📥 Export Leads' })
  }
  if (user.role === 'superadmin' && isTenantFeatureEnabled('activity_logs')) {
    items.push({ key: 'activitylogs', label: '📋 Activity Logs' })
  }

  items.push({ key: 'profile', label: '⚙️ My Profile' })
  return items
}


function switchProduct(slug) {
  currentProduct = slug
  localStorage.setItem('current_product', slug)
  activeTab = (slug === 'crm' || slug === 'lms') ? 'dashboard' : 'product_home'
  renderApp()
}

function renderProductHome() {
  const prod = availableProducts.find(p => p.slug === currentProduct)
  const content = document.getElementById('content')
  content.innerHTML = `
    <div style="padding:40px;text-align:center;max-width:600px;margin:0 auto;">
      <div style="font-size:64px;margin-bottom:16px;">${prod?.icon || 'ðŸ“¦'}</div>
      <h2 style="font-size:28px;margin-bottom:8px;color:${prod?.color || '#1e3a5f'}">${prod?.name || currentProduct}</h2>
      <p style="color:#64748b;font-size:15px;margin-bottom:8px;">${prod?.description || ''}</p>
      <div style="display:inline-block;padding:4px 14px;border-radius:20px;background:#fef3c7;color:#92400e;font-size:13px;font-weight:600;margin-bottom:32px;">
        ðŸš§ Coming Soon
      </div>
      <p style="color:#94a3b8;font-size:14px;">
        This module is under active development.<br/>
        Check back soon for updates.
      </p>
      <button class="button" onclick="switchProduct('crm')" style="margin-top:24px;">
        â† Back to CRM
      </button>
    </div>
  `
}

