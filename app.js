const API_BASE = window.API_BASE || 'http://127.0.0.1:5002/api'
const root = document.getElementById('app')
const storageToken = window.localStorage.getItem('lms_token')
let token = storageToken || ''
let user = null
let projects = []
let leads = []
let users = []
let activeTab = 'dashboard'
let selectedLeads = new Set()
let selectedLeadId = null
let leadsPage = 1
let leadsPageSize = 25
let activityLogs = []
let availableProducts = []
let currentProduct = localStorage.getItem('current_product') || 'crm'

// ============================================================================
// MAIN RENDER LOGIC
// ============================================================================

function render() {
  if (!token) return renderLogin()
  
  // Show sidebar when logged in
  const sidebar = document.querySelector('.sidebar')
  if (sidebar) sidebar.style.display = 'flex'
  
  const mainContent = document.querySelector('.main-content')
  if (mainContent && window.innerWidth > 768) mainContent.style.marginLeft = '220px'
  
  initMobileNav()
  renderApp()
}

let mobileNavInitialized = false
function initMobileNav() {
  if (mobileNavInitialized) return
  mobileNavInitialized = true
  const hamburger = document.getElementById('hamburgerBtn')
  const overlay = document.getElementById('mobileOverlay')
  const sidebar = document.getElementById('sidebar')
  if (!hamburger || !overlay || !sidebar) return
  hamburger.addEventListener('click', () => {
    sidebar.classList.toggle('open')
    overlay.classList.toggle('active')
  })
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open')
    overlay.classList.remove('active')
  })
}

function closeMobileSidebar() {
  document.getElementById('sidebar')?.classList.remove('open')
  document.getElementById('mobileOverlay')?.classList.remove('active')
}

function renderLogin() {
  // Hide sidebar during login
  const sidebar = document.querySelector('.sidebar')
  if (sidebar) sidebar.style.display = 'none'
  
  const mainContent = document.querySelector('.main-content')
  if (mainContent) mainContent.style.marginLeft = '0'
  
  root.innerHTML = `
  <div style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f1f5f9;">
    <div class="card" style="max-width:420px;width:100%;">
      <img src="logo.jpg" alt="Ganga Realty" style="width:160px;height:auto;border-radius:10px;display:block;margin:0 auto 16px;" />
      <h3 style="text-align:center;color:#64748b;">Enterprise Lead Management</h3>

      <!-- Password login -->
      <form id="loginForm" style="margin-top:24px;">
        <input class="input" id="email" type="email" placeholder="Email" required />
        <input class="input" id="password" type="password" placeholder="Password" required />
        <button class="button" style="width:100%;margin-top:16px;font-size:15px;">🔐 Login</button>
        <div style="text-align:center;margin-top:12px;">
          <a href="#" id="switchToOtp" style="font-size:13px;color:#0284c7;text-decoration:none;">Login with OTP instead →</a>
        </div>
      </form>

      <!-- OTP login (hidden initially) -->
      <div id="otpSection" style="display:none;margin-top:24px;">
        <div id="otpStep1">
          <input class="input" id="otpEmail" type="email" placeholder="Enter your email" required />
          <button id="sendOtpBtn" class="button" style="width:100%;margin-top:12px;font-size:15px;">📧 Send OTP</button>
        </div>
        <div id="otpStep2" style="display:none;">
          <p id="otpSentMsg" style="text-align:center;color:#16a34a;font-size:13px;margin-bottom:12px;"></p>
          <input class="input" id="otpCode" type="text" inputmode="numeric" maxlength="6" placeholder="Enter 6-digit OTP" style="letter-spacing:8px;font-size:20px;text-align:center;" required />
          <button id="verifyOtpBtn" class="button" style="width:100%;margin-top:12px;font-size:15px;">✅ Verify & Login</button>
          <div style="text-align:center;margin-top:8px;">
            <a href="#" id="resendOtp" style="font-size:12px;color:#64748b;">Resend OTP</a>
          </div>
        </div>
        <div style="text-align:center;margin-top:12px;">
          <a href="#" id="switchToPassword" style="font-size:13px;color:#0284c7;text-decoration:none;">← Back to password login</a>
        </div>
      </div>

      <div id="loginError" style="color:#dc2626;text-align:center;margin-top:10px;font-size:13px;"></div>
    </div>
  </div>
  `

  // Password login
  document.getElementById('loginForm').addEventListener('submit', async e => {
    e.preventDefault()
    const email = document.getElementById('email').value
    const password = document.getElementById('password').value
    await login(email, password)
  })

  // Toggle to OTP
  document.getElementById('switchToOtp').addEventListener('click', e => {
    e.preventDefault()
    document.getElementById('loginForm').style.display = 'none'
    document.getElementById('otpSection').style.display = 'block'
    document.getElementById('loginError').textContent = ''
  })

  // Toggle back to password
  document.getElementById('switchToPassword').addEventListener('click', e => {
    e.preventDefault()
    document.getElementById('loginForm').style.display = 'block'
    document.getElementById('otpSection').style.display = 'none'
    document.getElementById('loginError').textContent = ''
  })

  async function sendOtp() {
    const emailVal = document.getElementById('otpEmail').value.trim()
    if (!emailVal) return
    const btn = document.getElementById('sendOtpBtn')
    btn.disabled = true
    btn.textContent = 'Sending…'
    document.getElementById('loginError').textContent = ''
    try {
      const res = await fetch(`${API_BASE}/auth/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailVal }),
      })
      const data = await res.json()
      if (!res.ok) {
        document.getElementById('loginError').textContent = data.error || 'Failed to send OTP'
        btn.disabled = false
        btn.textContent = '📧 Send OTP'
        return
      }
      document.getElementById('otpStep1').style.display = 'none'
      document.getElementById('otpStep2').style.display = 'block'
      document.getElementById('otpSentMsg').textContent = `OTP sent to ${emailVal}`
      document.getElementById('otpCode').focus()
    } catch {
      document.getElementById('loginError').textContent = 'Network error. Please try again.'
      btn.disabled = false
      btn.textContent = '📧 Send OTP'
    }
  }

  document.getElementById('sendOtpBtn').addEventListener('click', sendOtp)

  document.getElementById('resendOtp').addEventListener('click', async e => {
    e.preventDefault()
    document.getElementById('otpStep1').style.display = 'block'
    document.getElementById('otpStep2').style.display = 'none'
    const btn = document.getElementById('sendOtpBtn')
    btn.disabled = false
    btn.textContent = '📧 Send OTP'
  })

  document.getElementById('verifyOtpBtn').addEventListener('click', async () => {
    const emailVal = document.getElementById('otpEmail').value.trim()
    const otpVal = document.getElementById('otpCode').value.trim()
    if (!otpVal || otpVal.length < 6) {
      document.getElementById('loginError').textContent = 'Please enter the 6-digit OTP'
      return
    }
    const btn = document.getElementById('verifyOtpBtn')
    btn.disabled = true
    btn.textContent = 'Verifying…'
    document.getElementById('loginError').textContent = ''
    try {
      const res = await fetch(`${API_BASE}/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailVal, otp: otpVal }),
      })
      const data = await res.json()
      if (!res.ok) {
        document.getElementById('loginError').textContent = data.error || 'Invalid OTP'
        btn.disabled = false
        btn.textContent = '✅ Verify & Login'
        return
      }
      token = data.token
      user = data.user
      localStorage.setItem('lms_token', token)
      render()
    } catch {
      document.getElementById('loginError').textContent = 'Network error. Please try again.'
      btn.disabled = false
      btn.textContent = '✅ Verify & Login'
    }
  })
}

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
            ${p.icon || '📦'} ${p.name}
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
            ${p.icon || '📦'} ${p.name}
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
  root.innerHTML = `
    <div id="content"></div>
    <div class="footer">API: ${API_BASE} | User: ${user.email}</div>
  `
  
  // Logout button
  const logoutBtn = document.getElementById('logoutBtn')
  logoutBtn.addEventListener('click', () => {
    token = ''
    user = null
    mobileNavInitialized = false
    localStorage.removeItem('lms_token')
    render()
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
  
  showContent()
}

function getNavItems() {
  // Platform owner always sees Platform Admin (and CRM if they want)
  if (user.role === 'platform_owner') {
    return [
      { key: 'platform', label: '🌐 Platform Admin' },
      { key: 'profile', label: '⚙️ My Profile' },
    ]
  }

  // Non-CRM product → single "Coming Soon" page
  if (currentProduct !== 'crm') {
    const prod = availableProducts.find(p => p.slug === currentProduct)
    return [
      { key: 'product_home', label: `${prod?.icon || '📦'} Overview` },
      { key: 'profile', label: '⚙️ My Profile' },
    ]
  }

  // CRM product (default)
  const items = [
    { key: 'dashboard', label: '📊 Dashboard' },
    { key: 'leads', label: '👥 Leads' },
    { key: 'pipeline', label: '📈 Pipeline' },
    { key: 'projects', label: '🏢 Projects' }
  ]
  
  if (user.role === 'sales_manager' || user.role === 'superadmin') {
    items.push({ key: 'team', label: '👨‍💼 Team' })
    items.push({ key: 'excel', label: '📤 Import Excel' })
  }
  
  if (user.role === 'superadmin' || user.role === 'sales_manager') {
    items.push({ key: 'reports', label: '📊 Reports' })
  }
  
  if (user.role === 'superadmin') {
    items.push({ key: 'export', label: '📥 Export Leads' })
  }
  
  if (user.role === 'superadmin') {
    items.push({ key: 'activitylogs', label: '📋 Activity Logs' })
  }
  
  items.push({ key: 'profile', label: '⚙️ My Profile' })
  
  return items
}

function getRoleDisplay(role) {
  const roles = {
    'superadmin': '🔐 Super Admin',
    'sales_manager': '👔 Sales Manager',
    'team_member': '👤 Team Member',
    'platform_owner': '🌐 Platform Owner',
  }
  return roles[role] || role
}

function showContent() {
  if (activeTab === 'dashboard') return renderDashboard()
  if (activeTab === 'leads') return renderLeads()
  if (activeTab === 'projects') return renderProjects()
  if (activeTab === 'team') return renderTeamManagement()
  if (activeTab === 'pipeline') return renderPipeline()
  if (activeTab === 'excel') return renderExcelUpload()
  if (activeTab === 'reports') return renderReports()
  if (activeTab === 'export') return renderExportLeads()
  if (activeTab === 'platform') return renderPlatformAdmin()
  if (activeTab === 'activitylogs') return renderActivityLogs()
  if (activeTab === 'profile') return renderMyProfile()
  if (activeTab === 'product_home') return renderProductHome()
}

function switchProduct(slug) {
  currentProduct = slug
  localStorage.setItem('current_product', slug)
  activeTab = slug === 'crm' ? 'dashboard' : 'product_home'
  renderApp()
}

function renderProductHome() {
  const prod = availableProducts.find(p => p.slug === currentProduct)
  const content = document.getElementById('content')
  content.innerHTML = `
    <div style="padding:40px;text-align:center;max-width:600px;margin:0 auto;">
      <div style="font-size:64px;margin-bottom:16px;">${prod?.icon || '📦'}</div>
      <h2 style="font-size:28px;margin-bottom:8px;color:${prod?.color || '#1e3a5f'}">${prod?.name || currentProduct}</h2>
      <p style="color:#64748b;font-size:15px;margin-bottom:8px;">${prod?.description || ''}</p>
      <div style="display:inline-block;padding:4px 14px;border-radius:20px;background:#fef3c7;color:#92400e;font-size:13px;font-weight:600;margin-bottom:32px;">
        🚧 Coming Soon
      </div>
      <p style="color:#94a3b8;font-size:14px;">
        This module is under active development.<br/>
        Check back soon for updates.
      </p>
      <button class="button" onclick="switchProduct('crm')" style="margin-top:24px;">
        ← Back to CRM
      </button>
    </div>
  `
}

// ============================================================================
// DASHBOARD
// ============================================================================

const STATUS_COLORS = {
  new:                 { bg: '#dbeafe', color: '#1d4ed8', label: 'New' },
  no_answer:           { bg: '#ffedd5', color: '#ea580c', label: 'No Answer' },
  follow_up:           { bg: '#ede9fe', color: '#7c3aed', label: 'Follow Up' },
  callback_scheduled:  { bg: '#e0e7ff', color: '#4338ca', label: 'Callback Scheduled' },
  interested:          { bg: '#dcfce7', color: '#16a34a', label: 'Interested' },
  site_visit_planned:  { bg: '#cffafe', color: '#0891b2', label: 'Site Visit Planned' },
  site_visit_done:     { bg: '#ccfbf1', color: '#0d9488', label: 'Site Visit Done' },
  negotiation:         { bg: '#fef9c3', color: '#ca8a04', label: 'Negotiation' },
  booking_done:        { bg: '#d1fae5', color: '#059669', label: 'Booking Done' },
  not_interested:      { bg: '#f1f5f9', color: '#64748b', label: 'Not Interested' },
  lost:                { bg: '#fee2e2', color: '#dc2626', label: 'Lost' },
  junk:                { bg: '#e5e7eb', color: '#374151', label: 'Junk' },
  // legacy aliases (backward compat for old activity logs / exports)
  attempted:           { bg: '#ffedd5', color: '#ea580c', label: 'No Answer' },
  connected:           { bg: '#ede9fe', color: '#7c3aed', label: 'Follow Up' },
  assigned:            { bg: '#cffafe', color: '#155e75', label: 'Assigned' },
  unassigned:          { bg: '#fce7f3', color: '#9d174d', label: 'Unassigned' },
}

// Exact display order for the dashboard status grid
const STATUS_ORDER = [
  'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
  'site_visit_planned', 'site_visit_done',
  'negotiation', 'booking_done',
  'not_interested', 'lost', 'junk',
  'assigned', 'unassigned',
]

async function renderDashboard() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div style="max-width:1600px;margin:0 auto;padding:0;">
      <div class="dash-header-row">
        <div>
          <h2 class="dash-title">Dashboard</h2>
          <p style="margin:0;color:#64748b;font-size:13px;">Performance snapshot for ${escape(user.name)}</p>
        </div>
        <div class="dash-filters">
          <div>
            <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">Time Range</label>
            <select id="dashRangeFilter" class="select dash-filter-sel">
              <option value="">All Time</option>
              <option value="today">Today</option>
              <option value="this_week" selected>This Week</option>
              <option value="this_month">This Month</option>
              <option value="last_30_days">Last 30 Days</option>
              <option value="custom">Custom Date</option>
            </select>
          </div>
          <div id="dashCustomRange" style="display:none;gap:6px;align-items:flex-end;">
            <div>
              <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">From</label>
              <input type="date" id="dashDateFrom" class="select dash-filter-sel" style="padding:7px 10px;" />
            </div>
            <div>
              <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">To</label>
              <input type="date" id="dashDateTo" class="select dash-filter-sel" style="padding:7px 10px;" />
            </div>
          </div>
          <div>
            <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">Project</label>
            <select id="dashProjectFilter" class="select dash-filter-sel">
              <option value="">All Projects</option>
            </select>
          </div>
        </div>
      </div>

      <div id="kpiSection" class="dash-kpi-grid"></div>

      <div class="dash-charts-row">
        <div class="card" style="padding:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <h3 style="margin:0;font-size:15px;color:#0f172a;">Drip Lead Funnel</h3>
          </div>
          <div id="dashFunnel"></div>
        </div>
        <div class="card" style="padding:16px;display:flex;flex-direction:column;">
          <h3 style="margin:0 0 8px;font-size:15px;color:#0f172a;">Leads by Source</h3>
          <div id="dashSourceChart" class="dash-source-inner"></div>
        </div>
        <div class="card" style="padding:16px;display:flex;flex-direction:column;">
          <h3 style="margin:0 0 10px;font-size:15px;color:#0f172a;">Leads by Project</h3>
          <div id="dashProjectBars" style="flex:1;display:flex;flex-direction:column;gap:8px;"></div>
        </div>
      </div>

      <div class="card" style="padding:18px 18px 16px;">
        <h3 style="margin:0 0 12px;font-size:15px;color:#0f172a;">Lead Status Distribution</h3>
        <div id="statusGrid" class="dash-status-grid"></div>
      </div>
    </div>
  `

  await loadProjects()
  const projectSel = document.getElementById('dashProjectFilter')
  const rangeSel = document.getElementById('dashRangeFilter')
  projects.forEach(p => {
    const opt = document.createElement('option')
    opt.value = p.id
    opt.textContent = p.name
    projectSel.appendChild(opt)
  })

  const SOURCE_COLORS = ['#3b82f6', '#14b8a6', '#f59e0b', '#8b5cf6', '#ef4444', '#64748b', '#10b981']

  function kpiCard(label, value, subtext, accent) {
    return `
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(2,6,23,0.08);">
        <div style="font-size:11px;color:#64748b;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">${label}</div>
        <div style="font-size:30px;font-weight:800;line-height:1.15;color:${accent};margin-top:4px;">${value}</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">${subtext}</div>
      </div>
    `
  }

  function renderStatusGrid(counts, totalLeads) {
    const grid = document.getElementById('statusGrid')
    const totalStages = STATUS_ORDER
      .filter(s => !['assigned', 'unassigned'].includes(s))
      .reduce((sum, s) => sum + (counts[s] || 0), 0)

    grid.innerHTML = STATUS_ORDER.map(status => {
      const cfg = STATUS_COLORS[status] || { bg: '#f1f5f9', color: '#334155', label: status }
      const count = counts[status] || 0
      const isAssignment = status === 'assigned' || status === 'unassigned'
      const pct = isAssignment
        ? (totalLeads > 0 ? (count / totalLeads * 100).toFixed(0) + '%' : '0%')
        : (totalStages > 0 ? (count / totalStages * 100).toFixed(0) + '%' : '0%')
      return `
        <div style="background:${cfg.bg};border:1px solid #e2e8f0;border-radius:10px;padding:11px;text-align:center;">
          <div style="font-size:11px;font-weight:700;color:${cfg.color};text-transform:uppercase;letter-spacing:0.04em;">${cfg.label}</div>
          <div style="font-size:24px;font-weight:800;color:${cfg.color};line-height:1.2;margin-top:4px;">${count}</div>
          <div style="font-size:10px;color:#64748b;">${pct}</div>
        </div>
      `
    }).join('')
  }

  function renderFunnel(counts, totalLeads) {
    const stages = [
      { key: 'new',            label: 'New Leads',      color: '#3b82f6' },
      { key: 'connected',      label: 'Contacted',      color: '#14b8a6' },
      { key: 'interested',     label: 'Interested',     color: '#f59e0b' },
      { key: 'site_visit_done',label: 'Site Visit Done',color: '#8b5cf6' },
      { key: 'negotiation',    label: 'Negotiation',    color: '#ef4444' },
    ]
    const values = stages.map(s => counts[s.key] || 0)
    // Percentage = stage count / total leads (all statuses) — future-ready:
    // correctly reflects each stage's share of ALL leads regardless of filters.
    const total = Math.max(totalLeads || 0, 1)

    // SVG funnel: true trapezoid polygons stacked edge-to-edge.
    // Each stage's bottom edge = next stage's top edge → no gaps.
    const W = 200, H = 230, N = stages.length
    const SH = H / N          // stage height = 46px
    const topW = W, botW = 28 // funnel mouth width and tip width (scaled up)
    const wAtY = y => topW - (topW - botW) * (y / H)

    const svgContent = stages.map((s, i) => {
      const y0 = i * SH,       y1 = (i + 1) * SH
      const w0 = wAtY(y0),     w1 = wAtY(y1)
      const x0l = (W - w0) / 2, x0r = (W + w0) / 2
      const x1l = (W - w1) / 2, x1r = (W + w1) / 2
      const v = values[i]
      return `
        <polygon points="${x0l},${y0} ${x0r},${y0} ${x1r},${y1} ${x1l},${y1}" fill="${s.color}"/>
        <text x="${W / 2}" y="${(y0 + y1) / 2}" text-anchor="middle" dominant-baseline="central"
              fill="white" font-size="15" font-weight="bold" font-family="-apple-system,Arial,sans-serif">${v.toLocaleString()}</text>
      `
    }).join('')

    const legendRows = stages.map((s, i) => {
      const v = values[i]
      const pct = ((v / total) * 100).toFixed(1)
      return `
        <div style="min-height:${SH}px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:2px 0;">
          <span style="width:10px;height:10px;border-radius:50%;background:${s.color};flex-shrink:0;"></span>
          <span style="color:#334155;font-size:11.5px;font-weight:500;flex:1;min-width:60px;">${s.label}</span>
          <span style="color:#0f172a;font-size:11.5px;font-weight:700;white-space:nowrap;flex-shrink:0;">${v.toLocaleString()} (${pct}%)</span>
        </div>
      `
    }).join('')

    document.getElementById('dashFunnel').innerHTML = `
      <div class="dash-funnel-inner">
        <svg viewBox="0 0 ${W} ${H}" class="dash-funnel-svg">${svgContent}</svg>
        <div class="dash-funnel-legend">${legendRows}</div>
      </div>
    `
  }

  function renderSourcePie(sourceStats) {
    const container = document.getElementById('dashSourceChart')
    if (!sourceStats.length) {
      container.innerHTML = `
        <svg viewBox="0 0 140 140" class="dash-source-svg">
          <circle cx="70" cy="70" r="66" fill="none" stroke="#e2e8f0" stroke-width="26"/>
          <text x="70" y="65" text-anchor="middle" dominant-baseline="central"
                font-size="13" fill="#94a3b8" font-family="-apple-system,Arial,sans-serif">No data</text>
          <text x="70" y="82" text-anchor="middle" dominant-baseline="central"
                font-size="11" fill="#cbd5e1" font-family="-apple-system,Arial,sans-serif">for range</text>
        </svg>
        <div class="dash-source-legend" style="padding-left:48px;color:#94a3b8;font-size:12px;display:flex;align-items:center;">No source data</div>
      `
      return
    }

    const items = sourceStats.slice(0, 7)
    const total = items.reduce((s, d) => s + (d.count || 0), 0) || 1

    // SVG donut geometry
    const CX = 70, CY = 70, OR = 66, IR = 40
    const toXY = (angle, r) => ({ x: CX + r * Math.cos(angle), y: CY + r * Math.sin(angle) })

    let a = -Math.PI / 2  // start at top
    const paths = items.map((s, i) => {
      const sweep = (s.count / total) * 2 * Math.PI
      // Prevent degenerate path when segment is full circle
      const end = a + (sweep >= 2 * Math.PI ? sweep - 0.0001 : sweep)
      const large = sweep > Math.PI ? 1 : 0
      const p1 = toXY(a, OR),  p2 = toXY(end, OR)
      const p3 = toXY(end, IR), p4 = toXY(a, IR)
      const color = SOURCE_COLORS[i % SOURCE_COLORS.length]
      const path = `<path d="M${p1.x} ${p1.y} A${OR} ${OR} 0 ${large} 1 ${p2.x} ${p2.y} L${p3.x} ${p3.y} A${IR} ${IR} 0 ${large} 0 ${p4.x} ${p4.y}Z" fill="${color}"/>`
      a = end
      return path
    }).join('')

    const n = items.length
    const svgH = 202
    const rowH = Math.floor(svgH / n)
    const fz = n > 5 ? '11px' : '12px'

    const svg = `
      <svg viewBox="0 0 140 140" class="dash-source-svg">
        ${paths}
        <text x="70" y="62" text-anchor="middle" dominant-baseline="central"
              font-size="24" font-weight="800" fill="#0f172a"
              font-family="-apple-system,Arial,sans-serif">${total.toLocaleString()}</text>
        <text x="70" y="81" text-anchor="middle" dominant-baseline="central"
              font-size="11" fill="#94a3b8"
              font-family="-apple-system,Arial,sans-serif">Total</text>
      </svg>`

    const rows = items.map((s, i) => {
      const pct = Math.round((s.count / total) * 100)
      const color = SOURCE_COLORS[i % SOURCE_COLORS.length]
      return `
        <div style="min-height:${rowH}px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:2px 0;">
          <span style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0;"></span>
          <span style="flex:1;color:#334155;font-size:${fz};font-weight:500;min-width:60px;overflow:hidden;text-overflow:ellipsis;">${escape(s.source)}</span>
          <span style="color:#0f172a;font-size:${fz};font-weight:700;white-space:nowrap;flex-shrink:0;padding-left:8px;">${pct}% (${s.count.toLocaleString()})</span>
        </div>`
    }).join('')

    container.innerHTML = `
      ${svg}
      <div class="dash-source-legend">${rows}</div>`
  }

  function renderProjectBars(projectStats) {
    const wrap = document.getElementById('dashProjectBars')
    const rows = (projectStats || []).slice().sort((a, b) => (b.total || 0) - (a.total || 0)).slice(0, 6)
    if (!rows.length) {
      wrap.innerHTML = '<div style="font-size:12px;color:#94a3b8;">No project data</div>'
      return
    }
    const max = Math.max(...rows.map(r => r.total || 0), 1)
    const BAR_COLORS = [
      ['#3b82f6','#60a5fa'],
      ['#14b8a6','#2dd4bf'],
      ['#f59e0b','#fbbf24'],
      ['#8b5cf6','#a78bfa'],
      ['#ef4444','#f87171'],
      ['#10b981','#34d399'],
    ]
    wrap.innerHTML = rows.map((r, i) => {
      const width = Math.max(4, Math.round(((r.total || 0) / max) * 100))
      const [c1, c2] = BAR_COLORS[i % BAR_COLORS.length]
      return `
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0;">
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#334155;margin-bottom:4px;gap:8px;">
            <span style="display:flex;align-items:center;gap:6px;overflow:hidden;">
              <span style="width:8px;height:8px;border-radius:50%;background:${c1};flex-shrink:0;"></span>
              <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escape(r.project_name)}</span>
            </span>
            <span style="color:#0f172a;font-weight:700;flex-shrink:0;">${r.total || 0}</span>
          </div>
          <div style="height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden;">
            <div style="height:8px;width:${width}%;background:linear-gradient(90deg,${c1},${c2});border-radius:999px;"></div>
          </div>
        </div>
      `
    }).join('')
  }

  async function refreshDashboardViews() {
    const params = new URLSearchParams()
    const rangeVal = rangeSel.value
    const projectVal = projectSel.value

    if (rangeVal === 'custom') {
      const df = document.getElementById('dashDateFrom')?.value
      const dt = document.getElementById('dashDateTo')?.value
      if (df) params.set('date_from', df)
      if (dt) params.set('date_to', dt)
    } else {
      if (rangeVal) params.set('range', rangeVal)
    }
    if (projectVal) params.set('project_id', projectVal)

    const url = `${API_BASE}/leads/dashboard/stats${params.toString() ? `?${params.toString()}` : ''}`
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    const data = await res.json()
    const stats = data.stats || {}
    const totalLeads = stats.total_leads || stats.my_leads || 0

    document.getElementById('kpiSection').innerHTML = `
      ${kpiCard('Total Leads', totalLeads, 'within selected filters', '#1d4ed8')}
      ${kpiCard('Site Visit Planned', stats.status_counts?.site_visit_planned || 0, 'leads with visits scheduled', '#7c3aed')}
      ${kpiCard('Site Visit Done', stats.status_counts?.site_visit_done || 0, 'completed site visits', '#059669')}
      ${kpiCard('Warm Rate', `${(stats.warm_rate || 0).toFixed(1)}%`, 'interested leads share', '#c2410c')}
    `

    renderFunnel(stats.status_counts || {}, totalLeads)
    renderSourcePie(stats.source_stats || [])
    renderProjectBars(stats.project_stats || [])
    renderStatusGrid(stats.status_counts || {}, totalLeads)
  }

  rangeSel.addEventListener('change', () => {
    const customRow = document.getElementById('dashCustomRange')
    customRow.style.display = rangeSel.value === 'custom' ? 'flex' : 'none'
    if (rangeSel.value !== 'custom') refreshDashboardViews()
  })
  document.getElementById('dashDateFrom').addEventListener('change', () => { if (rangeSel.value === 'custom') refreshDashboardViews() })
  document.getElementById('dashDateTo').addEventListener('change',   () => { if (rangeSel.value === 'custom') refreshDashboardViews() })
  projectSel.addEventListener('change', refreshDashboardViews)
  refreshDashboardViews()
}

// ============================================================================
// LEADS
// ============================================================================

async function renderLeads() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
        <h2 style="margin:0;">Leads</h2>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          ${user.role !== 'team_member' ? `<button class="button secondary" id="importLeadsBtn" style="font-size:13px;padding:8px 14px;">📤 Import Excel</button>` : ''}
          ${user.role === 'superadmin' ? `<button class="button secondary" id="exportLeadsBtn" style="font-size:13px;padding:8px 14px;">📥 Export Excel</button>` : ''}
          <button class="button" id="newLeadBtn">+ New Lead</button>
        </div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin-bottom:18px;">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:12px;flex-wrap:wrap;">
          <span style="font-size:13px;font-weight:600;color:#475569;letter-spacing:0.04em;">🔍 FILTERS</span>
          <span id="leadsActiveDateBadge" style="display:none;font-size:11px;font-weight:600;padding:2px 9px;border-radius:20px;background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;"></span>
          <button onclick="clearLeadsFilters()" id="clearFiltersBtn" style="margin-left:auto;font-size:11px;padding:3px 10px;border:1px solid #cbd5e1;border-radius:20px;background:#fff;color:#64748b;cursor:pointer;font-weight:500;">✕ Clear all</button>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px;">
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">STATUS</label>
            <select id="filterStatus" class="select" style="font-size:13px;">
              <option value="">All Statuses</option>
              <option value="new">New</option>
              <option value="attempted">Attempted</option>
              <option value="connected">Connected</option>
              <option value="interested">Interested</option>
              <option value="site_visit_planned">Site Visit Planned</option>
              <option value="site_visit_done">Site Visit Done</option>
              <option value="negotiation">Negotiation</option>
              <option value="booking_done">Booking Done</option>
              <option value="lost">Lost</option>
              <option value="junk">Junk</option>
            </select>
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">PROJECT</label>
            <select id="filterProject" class="select" style="font-size:13px;">
              <option value="">All Projects</option>
            </select>
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">SOURCE</label>
            <select id="filterSource" class="select" style="font-size:13px;">
              <option value="">All Sources</option>
              <option value="Website">Website</option>
              <option value="Referral">Referral</option>
              <option value="Walk-in">Walk-in</option>
              <option value="Meta">Meta</option>
              <option value="Google">Google</option>
              <option value="Email Campaign">Email Campaign</option>
              <option value="Direct">Direct</option>
              <option value="Other">Other</option>
              <option value="G1">G1</option>
              <option value="G2">G2</option>
              <option value="G3">G3</option>
              <option value="TP">TP</option>
            </select>
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">TEAM MEMBER</label>
            <select id="filterTeamMember" class="select" style="font-size:13px;">
              <option value="">All Members</option>
              <option value="unassigned">Unassigned</option>
            </select>
          </div>
          ${user.role === 'superadmin' ? `
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">SALES MANAGER</label>
            <select id="filterSalesManager" class="select" style="font-size:13px;">
              <option value="">All Managers</option>
            </select>
          </div>` : ''}
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;border-top:1px solid #e2e8f0;padding-top:10px;margin-top:2px;">
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">📅 LEAD CREATED FROM</label>
            <input type="date" id="filterDateFrom" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">LEAD CREATED TO</label>
            <input type="date" id="filterDateTo" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">🔄 STATUS UPDATED FROM</label>
            <input type="date" id="filterUpdatedFrom" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">STATUS UPDATED TO</label>
            <input type="date" id="filterUpdatedTo" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:120px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">QUICK MONTH</label>
            <select id="filterMonth" class="select" style="font-size:13px;">
              <option value="">All Months</option>
              ${Array.from({length:12},(_,i)=>`<option value="${i}">${new Date(2000,i,1).toLocaleString('default',{month:'long'})}</option>`).join('')}
            </select>
          </div>
        </div>
      </div>
      <div id="leadsContainer"></div>
    </div>
  `

  document.getElementById('newLeadBtn').addEventListener('click', openLeadForm)
  document.getElementById('filterStatus').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterProject').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterSource').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterTeamMember').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterDateFrom').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterDateTo').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterUpdatedFrom').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterUpdatedTo').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterMonth').addEventListener('change', e => {
    const month = e.target.value
    if (month !== '') {
      const now = new Date()
      const year = now.getFullYear()
      const from = new Date(year, parseInt(month), 1)
      const to = new Date(year, parseInt(month) + 1, 0)
      document.getElementById('filterDateFrom').value = from.toISOString().split('T')[0]
      document.getElementById('filterDateTo').value = to.toISOString().split('T')[0]
    } else {
      document.getElementById('filterDateFrom').value = ''
      document.getElementById('filterDateTo').value = ''
    }
    filterAndRenderLeads()
  })
  if (user.role === 'superadmin') {
    const smFilter = document.getElementById('filterSalesManager')
    if (smFilter) smFilter.addEventListener('change', () => {
      updateTeamMemberDropdown(smFilter.value)
      filterAndRenderLeads()
    })
  }
  if (user.role !== 'team_member') {
    document.getElementById('importLeadsBtn').addEventListener('click', openImportModal)
  }
  if (user.role === 'superadmin') {
    document.getElementById('exportLeadsBtn').addEventListener('click', quickExportLeads)
  }

  await Promise.all([loadProjects(), loadUsers()])

  const projectSelect = document.getElementById('filterProject')
  if (projectSelect) {
    projectSelect.innerHTML = '<option value="">All Projects</option>' +
      projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')
  }

  const teamSelect = document.getElementById('filterTeamMember')
  if (teamSelect) {
    const teamMembers = users.filter(u => u.role === 'team_member')
    teamSelect.innerHTML = '<option value="">All Members</option><option value="unassigned">Unassigned</option>' +
      teamMembers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
  }

  const smSelect = document.getElementById('filterSalesManager')
  if (smSelect) {
    const salesManagers = users.filter(u => u.role === 'sales_manager')
    smSelect.innerHTML = '<option value="">All Sales Managers</option>' +
      salesManagers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
  }

  function updateTeamMemberDropdown(managerId) {
    const teamSelect = document.getElementById('filterTeamMember')
    if (!teamSelect) return
    const allMembers = users.filter(u => u.role === 'team_member')
    const filtered = managerId
      ? allMembers.filter(u => String(u.manager_id) === String(managerId))
      : allMembers
    const prevVal = teamSelect.value
    teamSelect.innerHTML = '<option value="">All Members</option><option value="unassigned">Unassigned</option>' +
      filtered.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
    // restore previous selection if still valid
    if (prevVal && filtered.some(u => String(u.id) === String(prevVal))) {
      teamSelect.value = prevVal
    }
  }

  await filterAndRenderLeads()
}

function clearLeadsFilters() {
  ['filterStatus','filterProject','filterSource','filterTeamMember','filterSalesManager',
   'filterDateFrom','filterDateTo','filterUpdatedFrom','filterUpdatedTo','filterMonth'].forEach(id => {
    const el = document.getElementById(id)
    if (el) el.value = ''
  })
  leadsPage = 1
  filterAndRenderLeads()
}

function goToLeadsPage(page) {
  leadsPage = parseInt(page)
  filterAndRenderLeads(false)
}

function setLeadsPageSize(size) {
  leadsPageSize = parseInt(size)
  leadsPage = 1
  filterAndRenderLeads(false)
}

async function filterAndRenderLeads(resetPage = true) {
  if (resetPage) leadsPage = 1
  await loadLeads()

  let filtered = leads
  const statusFilter       = document.getElementById('filterStatus')?.value
  const projectFilter      = document.getElementById('filterProject')?.value
  const sourceFilter       = document.getElementById('filterSource')?.value
  const teamMemberFilter   = document.getElementById('filterTeamMember')?.value
  const salesManagerFilter = document.getElementById('filterSalesManager')?.value
  const dateFrom           = document.getElementById('filterDateFrom')?.value
  const dateTo             = document.getElementById('filterDateTo')?.value
  const updatedFrom        = document.getElementById('filterUpdatedFrom')?.value
  const updatedTo          = document.getElementById('filterUpdatedTo')?.value

  if (statusFilter)   filtered = filtered.filter(l => l.status === statusFilter)
  if (projectFilter)  filtered = filtered.filter(l => l.project_id === parseInt(projectFilter))
  if (sourceFilter)   filtered = filtered.filter(l => l.source === sourceFilter)
  if (teamMemberFilter === 'unassigned') {
    filtered = filtered.filter(l => !l.assigned_to)
  } else if (teamMemberFilter) {
    filtered = filtered.filter(l => l.assigned_to === parseInt(teamMemberFilter))
  }
  if (salesManagerFilter) {
    filtered = filtered.filter(l => l.sales_manager_id === parseInt(salesManagerFilter))
  }
  if (dateFrom) {
    const from = new Date(dateFrom)
    filtered = filtered.filter(l => new Date(l.created_at) >= from)
  }
  if (dateTo) {
    const to = new Date(dateTo); to.setHours(23,59,59,999)
    filtered = filtered.filter(l => new Date(l.created_at) <= to)
  }
  if (updatedFrom) {
    const from = new Date(updatedFrom)
    filtered = filtered.filter(l => new Date(l.updated_at) >= from)
  }
  if (updatedTo) {
    const to = new Date(updatedTo); to.setHours(23,59,59,999)
    filtered = filtered.filter(l => new Date(l.updated_at) <= to)
  }

  const container = document.getElementById('leadsContainer')
  if (!container) return

  // Keep only selections that are still visible
  const filteredIds = new Set(filtered.map(l => l.id))
  for (const id of selectedLeads) { if (!filteredIds.has(id)) selectedLeads.delete(id) }

  if (filtered.length === 0) {
    container.innerHTML = '<div class="message">No leads found</div>'
    return
  }

  // Pagination
  const totalLeads = filtered.length
  const totalPages = leadsPageSize === 0 ? 1 : Math.ceil(totalLeads / leadsPageSize)
  if (leadsPage > totalPages) leadsPage = totalPages
  if (leadsPage < 1) leadsPage = 1
  const pageStart = leadsPageSize === 0 ? 0 : (leadsPage - 1) * leadsPageSize
  const pageEnd   = leadsPageSize === 0 ? totalLeads : pageStart + leadsPageSize
  const paginated  = filtered.slice(pageStart, pageEnd)
  const showFrom   = totalLeads === 0 ? 0 : pageStart + 1
  const showTo     = Math.min(pageEnd, totalLeads)

  // Page number buttons (show up to 7 around current page)
  const pageButtons = (() => {
    if (totalPages <= 1) return ''
    const nums = []
    const delta = 3
    for (let p = 1; p <= totalPages; p++) {
      if (p === 1 || p === totalPages || (p >= leadsPage - delta && p <= leadsPage + delta)) nums.push(p)
      else if (nums[nums.length-1] !== '…') nums.push('…')
    }
    return nums.map(p => p === '…'
      ? `<span style="padding:0 4px;color:#94a3b8;font-size:13px;">…</span>`
      : `<button onclick="goToLeadsPage(${p})" style="min-width:32px;height:32px;border:1px solid ${p===leadsPage?'#2563eb':'#e2e8f0'};border-radius:6px;background:${p===leadsPage?'#2563eb':'#fff'};color:${p===leadsPage?'#fff':'#374151'};font-size:13px;font-weight:${p===leadsPage?'700':'400'};cursor:${p===leadsPage?'default':'pointer'};">${p}</button>`
    ).join('')
  })()

  const paginationBar = `
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;padding:14px 4px 4px;border-top:1px solid #e2e8f0;margin-top:4px;">
      <div style="font-size:13px;color:#64748b;">
        Showing <strong>${showFrom}–${showTo}</strong> of <strong>${totalLeads}</strong> leads
      </div>
      <div style="display:flex;align-items:center;gap:4px;">
        <button onclick="goToLeadsPage(${leadsPage-1})" ${leadsPage<=1?'disabled':''}
          style="padding:4px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:${leadsPage<=1?'#cbd5e1':'#374151'};font-size:13px;cursor:${leadsPage<=1?'default':'pointer'};">← Prev</button>
        ${pageButtons}
        <button onclick="goToLeadsPage(${leadsPage+1})" ${leadsPage>=totalPages?'disabled':''}
          style="padding:4px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:${leadsPage>=totalPages?'#cbd5e1':'#374151'};font-size:13px;cursor:${leadsPage>=totalPages?'default':'pointer'};">Next →</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:13px;color:#64748b;">Per page:</span>
        <select onchange="setLeadsPageSize(this.value)" style="border:1px solid #e2e8f0;border-radius:6px;padding:4px 8px;font-size:13px;color:#374151;background:#fff;cursor:pointer;">
          ${[25,50,100,200].map(n => `<option value="${n}" ${leadsPageSize===n?'selected':''}>${n}</option>`).join('')}
          <option value="0" ${leadsPageSize===0?'selected':''}>All</option>
        </select>
      </div>
    </div>`

  const projectMap = {}
  projects.forEach(p => { projectMap[p.id] = p.name })

  const canAssign = user.role === 'superadmin' || user.role === 'sales_manager'
  const canAssignManager = user.role === 'superadmin'
  const assignableManagers = users.filter(u => {
    if (user.role === 'superadmin') return u.role === 'sales_manager'
    return false
  })
  const assignableMembers = user.role === 'superadmin'
    ? users.filter(u => u.role === 'team_member')
    : user.role === 'sales_manager'
      ? [{ id: user.id, name: `${user.name} (me)` }, ...users.filter(u => u.manager_id === user.id)]
      : []

  const VALID_STATUSES_LIST = ['new','attempted','connected','interested','follow_up','site_visit_planned','site_visit_done','negotiation','booking_done','not_interested','lost','junk']
  const allChecked = paginated.length > 0 && paginated.every(l => selectedLeads.has(l.id))

  container.innerHTML = `
    <div id="bulkBar" style="display:${selectedLeads.size > 0 ? 'flex' : 'none'};align-items:stretch;gap:0;background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:0;margin-bottom:18px;overflow:hidden;">
      <!-- Identity section -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:6px;padding:12px 16px;background:#e0f2fe;flex-shrink:0;">
        <span style="font-size:12px;font-weight:700;color:#0369a1;letter-spacing:0.06em;white-space:nowrap;">⚡ BULK ACTIONS</span>
        <span id="bulkCount" style="font-size:12px;font-weight:600;color:#0284c7;white-space:nowrap;">${selectedLeads.size} lead${selectedLeads.size !== 1 ? 's' : ''} selected</span>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button onclick="clearLeadSelection()" style="font-size:11px;padding:3px 10px;border:1px solid #7dd3fc;border-radius:20px;background:#fff;color:#0369a1;cursor:pointer;font-weight:500;white-space:nowrap;">✕ Clear</button>
          ${user.role === 'superadmin' ? `<button onclick="bulkDeleteLeads()" style="font-size:11px;padding:3px 10px;border:1px solid #fca5a5;border-radius:20px;background:#fff;color:#ef4444;cursor:pointer;font-weight:500;white-space:nowrap;">🗑 Delete</button>` : ''}
        </div>
      </div>
      <!-- Change Status -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Change Status</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkStatusSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select status —</option>
            ${VALID_STATUSES_LIST.map(s => `<option value="${s}">${s.replace(/_/g,' ')}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkUpdateStatus()" style="padding:6px 14px;font-size:12px;background:#0369a1;white-space:nowrap;flex-shrink:0;">Update</button>
        </div>
      </div>
      <!-- Change Source -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Change Source</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkSourceSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select source —</option>
            ${['Website','Referral','Walk-in','Meta','Google','Email Campaign','Direct','Other','G1','G2','G3','TP'].map(s => `<option value="${s}">${s}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkUpdateSource()" style="padding:6px 14px;font-size:12px;background:#0369a1;white-space:nowrap;flex-shrink:0;">Update</button>
        </div>
      </div>
      ${canAssignManager ? `
      <!-- Assign Manager -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Assign Sales Manager</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkAssignManagerSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select manager —</option>
            <option value="unassign">⊘ Unassign Manager</option>
            ${assignableManagers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkAssignLeads('bulkAssignManagerSelect')" style="padding:6px 14px;font-size:12px;white-space:nowrap;flex-shrink:0;">Assign</button>
        </div>
      </div>
      ` : ''}
      ${canAssign && assignableMembers.length ? `
      <!-- Assign Team Member -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Assign Team Member</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkAssignMemberSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select member —</option>
            <option value="unassign">⊘ Unassign Member</option>
            ${assignableMembers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkAssignLeads('bulkAssignMemberSelect')" style="padding:6px 14px;font-size:12px;white-space:nowrap;flex-shrink:0;">Assign</button>
        </div>
      </div>
      ` : ''}
    </div>
    <div style="overflow-x:auto;">
      <table class="table">
        <thead>
          <tr>
            <th style="width:36px;"><input type="checkbox" id="selectAllLeads" ${allChecked ? 'checked' : ''} onchange="toggleSelectAllLeads(this.checked)" style="cursor:pointer;width:16px;height:16px;"></th>
            <th>Name</th>
            <th>Phone</th>
            <th>Source</th>
            <th>Status</th>
            <th>Project</th>
            <th>Assigned To</th>
            <th>Sales Manager</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${paginated.map(l => `
            <tr class="${selectedLeads.has(l.id) ? 'lead-row-selected' : ''}">
              <td><input type="checkbox" class="lead-checkbox" data-id="${l.id}" ${selectedLeads.has(l.id) ? 'checked' : ''} onchange="toggleSelectLead(${l.id}, this.checked)" style="cursor:pointer;width:16px;height:16px;"></td>
              <td><strong>${escape(l.name)}</strong></td>
              <td>${escape(l.phone || '-')}</td>
              <td>${escape(l.source || '-')}</td>
              <td><span class="tag" style="background:${getStatusColor(l.status)};color:#fff;">${escape(l.status)}</span></td>
              <td>${escape(projectMap[l.project_id] || '-')}</td>
              <td>${escape(l.assigned_to_name || 'Unassigned')}</td>
              <td>${escape(l.sales_manager_name || '-')}</td>
              <td>${new Date(l.created_at).toLocaleDateString()}</td>
              <td>
                <button class="button secondary" onclick="viewLeadDetails(${l.id})" style="font-size:12px;padding:6px 10px;">View</button>
                ${user.role === 'superadmin' ? `<button class="button" onclick="deleteLead(${l.id}, '${escape(l.name)}')" style="font-size:12px;padding:6px 10px;background:#ef4444;margin-left:4px;">Delete</button>` : ''}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    ${paginationBar}
  `

  // Update active date badge in filter bar
  const badge = document.getElementById('leadsActiveDateBadge')
  if (badge) {
    const df = document.getElementById('filterDateFrom')?.value
    const dt = document.getElementById('filterDateTo')?.value
    const uf = document.getElementById('filterUpdatedFrom')?.value
    const ut = document.getElementById('filterUpdatedTo')?.value
    const fmtB = d => new Date(d).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})
    const parts = []
    if (df || dt) parts.push('Created: ' + (df && dt ? `${fmtB(df)} → ${fmtB(dt)}` : df ? `From ${fmtB(df)}` : `Until ${fmtB(dt)}`))
    if (uf || ut) parts.push('Updated: ' + (uf && ut ? `${fmtB(uf)} → ${fmtB(ut)}` : uf ? `From ${fmtB(uf)}` : `Until ${fmtB(ut)}`))
    if (parts.length) { badge.textContent = '📅 ' + parts.join(' · '); badge.style.display = 'inline' }
    else badge.style.display = 'none'
  }

  // Cascade: bulk Assign Sales Manager → filter Assign Team Member
  const bulkMgrSel = document.getElementById('bulkAssignManagerSelect')
  const bulkMemSel = document.getElementById('bulkAssignMemberSelect')
  if (bulkMgrSel && bulkMemSel) {
    const allBulkMembers = users.filter(u => u.role === 'team_member')
    bulkMgrSel.addEventListener('change', () => {
      const mid = bulkMgrSel.value
      const filtered = mid
        ? allBulkMembers.filter(u => String(u.manager_id) === String(mid))
        : allBulkMembers
      bulkMemSel.innerHTML = '<option value="">— Select member —</option>' +
        filtered.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
    })
  }
}

function toggleSelectLead(id, checked) {
  if (checked) selectedLeads.add(id)
  else selectedLeads.delete(id)
  renderBulkBar()
  // sync select-all checkbox
  const allBox = document.getElementById('selectAllLeads')
  if (allBox) {
    const all = document.querySelectorAll('.lead-checkbox')
    allBox.checked = all.length > 0 && [...all].every(c => c.checked)
    allBox.indeterminate = !allBox.checked && selectedLeads.size > 0
  }
  // highlight row
  const cb = document.querySelector(`.lead-checkbox[data-id="${id}"]`)
  if (cb) cb.closest('tr').classList.toggle('lead-row-selected', checked)
}

function toggleSelectAllLeads(checked) {
  document.querySelectorAll('.lead-checkbox').forEach(cb => {
    const id = parseInt(cb.dataset.id)
    cb.checked = checked
    if (checked) selectedLeads.add(id)
    else selectedLeads.delete(id)
    cb.closest('tr').classList.toggle('lead-row-selected', checked)
  })
  renderBulkBar()
}

function renderBulkBar() {
  const bar = document.getElementById('bulkBar')
  if (!bar) return
  bar.style.display = selectedLeads.size > 0 ? 'flex' : 'none'
  const countEl = document.getElementById('bulkCount')
  if (countEl) countEl.textContent = `${selectedLeads.size} lead${selectedLeads.size !== 1 ? 's' : ''} selected`
}

function clearLeadSelection() {
  selectedLeads.clear()
  filterAndRenderLeads()
}

async function bulkUpdateStatus() {
  const newStatus = document.getElementById('bulkStatusSelect')?.value
  if (!newStatus) { alert('Please select a status to apply.'); return }
  if (selectedLeads.size === 0) { alert('No leads selected.'); return }
  try {
    const res = await fetch(`${API_BASE}/leads/bulk-status`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_ids: [...selectedLeads], status: newStatus }),
    })
    const data = await res.json()
    if (!res.ok) { alert(data.error || 'Bulk status update failed'); return }
    selectedLeads.clear()
    await filterAndRenderLeads()
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#10b981;font-weight:600;">✅ ${data.updated} lead${data.updated !== 1 ? 's' : ''} updated to "${newStatus.replace(/_/g,' ')}"</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) { alert('Error: ' + err.message) }
}

async function bulkUpdateSource() {
  const newSource = document.getElementById('bulkSourceSelect')?.value
  if (!newSource) { alert('Please select a source to apply.'); return }
  if (selectedLeads.size === 0) { alert('No leads selected.'); return }
  try {
    const res = await fetch(`${API_BASE}/leads/bulk-source`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_ids: [...selectedLeads], source: newSource }),
    })
    const data = await res.json()
    if (!res.ok) { alert(data.error || 'Bulk source update failed'); return }
    selectedLeads.clear()
    await filterAndRenderLeads()
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#10b981;font-weight:600;">✅ ${data.updated} lead${data.updated !== 1 ? 's' : ''} source updated to "${data.source}"</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) { alert('Error: ' + err.message) }
}

async function bulkAssignLeads(selectId = 'bulkAssignMemberSelect') {
  const assignTo = document.getElementById(selectId)?.value
  if (!assignTo) { alert('Please select a person to assign to.'); return }
  if (selectedLeads.size === 0) { alert('No leads selected.'); return }
  const assignType = selectId === 'bulkAssignManagerSelect' ? 'manager' : 'member'
  const isUnassign = assignTo === 'unassign'
  const btn = document.querySelector('#bulkBar .button')
  if (btn) { btn.disabled = true; btn.textContent = 'Assigning…' }
  try {
    const res = await fetch(`${API_BASE}/leads/bulk-assign`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_ids: [...selectedLeads], assigned_to: isUnassign ? null : parseInt(assignTo), assign_type: assignType }),
    })
    const data = await res.json()
    if (!res.ok) { alert(data.error || 'Bulk assign failed'); return }
    selectedLeads.clear()
    await filterAndRenderLeads()
    // flash success
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#10b981;font-weight:600;">✅ ${data.updated} lead${data.updated !== 1 ? 's' : ''} assigned to ${escape(data.assigned_to_name)}</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) {
    alert('Error: ' + err.message)
    if (btn) { btn.disabled = false; btn.textContent = 'Assign' }
  }
}

async function deleteLead(leadId, leadName) {
  if (!confirm(`Delete lead "${leadName}"? This cannot be undone.`)) return
  try {
    const res = await fetch(`${API_BASE}/leads/${leadId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.ok) {
      selectedLeads.delete(leadId)
      await loadLeads()
      filterAndRenderLeads()
    } else {
      const err = await res.json().catch(() => ({}))
      alert(err.error || 'Error deleting lead')
    }
  } catch (err) { alert('Error: ' + err.message) }
}

async function bulkDeleteLeads() {
  if (selectedLeads.size === 0) { alert('No leads selected.'); return }
  if (!confirm(`Delete ${selectedLeads.size} selected lead${selectedLeads.size !== 1 ? 's' : ''}? This cannot be undone.`)) return
  try {
    const res = await fetch(`${API_BASE}/leads/bulk-delete`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_ids: [...selectedLeads] })
    })
    const data = await res.json()
    if (!res.ok) { alert(data.error || 'Bulk delete failed'); return }
    selectedLeads.clear()
    await loadLeads()
    filterAndRenderLeads()
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#ef4444;font-weight:600;">🗑 ${data.deleted} lead${data.deleted !== 1 ? 's' : ''} deleted</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) { alert('Error: ' + err.message) }
}

// ── Import modal ─────────────────────────────────────────────────────────────
function openImportModal() {
  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.id = 'importModal'
  overlay.innerHTML = `
    <div class="modal-box">
      <button class="modal-close" id="closeImportModal">&times;</button>
      <h3>📤 Import Leads from Excel</h3>
      <form id="importModalForm">
        <div style="margin-bottom:14px;">
          <label style="display:block;font-weight:600;margin-bottom:6px;font-size:14px;">Select File (.xlsx, .xls, .csv)</label>
          <input type="file" id="importModalFile" accept=".xlsx,.xls,.csv" required
            style="display:block;width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px;" />
        </div>
        <div style="display:flex;gap:8px;">
          <button type="submit" class="button" style="flex:1;">📤 Upload & Import</button>
          <button type="button" class="button secondary" id="downloadTplBtn" style="flex:1;">⬇️ Download Template</button>
        </div>
      </form>
      <div id="importModalResult" style="margin-top:16px;"></div>
    </div>
  `
  document.body.appendChild(overlay)

  document.getElementById('closeImportModal').addEventListener('click', () => overlay.remove())
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove() })
  document.getElementById('downloadTplBtn').addEventListener('click', downloadExcelTemplate)
  document.getElementById('importModalForm').addEventListener('submit', async e => {
    e.preventDefault()
    const file = document.getElementById('importModalFile').files[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    const resultDiv = document.getElementById('importModalResult')
    resultDiv.innerHTML = '<div style="color:#64748b;font-size:14px;">Uploading…</div>'
    try {
      const res = await fetch(`${API_BASE}/leads/import/excel`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: formData
      })
      const data = await res.json()
      if (!res.ok) {
        resultDiv.innerHTML = `<div style="background:#fee2e2;padding:12px;border-radius:6px;color:#991b1b;">❌ ${escape(data.error || 'Upload failed')}</div>`
        return
      }
      window._importReportB64 = data.report_b64 || null
      const dlBtn = data.report_b64
        ? `<button onclick="downloadImportReport()" style="margin-top:10px;padding:8px 16px;background:#1e3a5f;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">📥 Download Report (.xlsx)</button>`
        : ''
      resultDiv.innerHTML = `
        <div style="background:#f0fdf4;border:1px solid #86efac;padding:14px;border-radius:8px;color:#166534;">
          <strong>✅ Import complete</strong><br>
          <span>Imported: ${data.success} &nbsp;|&nbsp; Failed: ${data.failed} &nbsp;|&nbsp; Total rows: ${data.total}</span>
          ${data.errors?.length ? `<div style="margin-top:8px;font-size:13px;">${data.errors.slice(0,5).map(e=>`Row ${e.row}: ${escape(e.error)}`).join('<br>')}</div>` : ''}
          ${dlBtn}
        </div>
      `
      await filterAndRenderLeads()
    } catch (err) {
      resultDiv.innerHTML = `<div style="background:#fee2e2;padding:12px;border-radius:6px;color:#991b1b;">❌ ${escape(err.message)}</div>`
    }
  })
}

// ── Quick export (uses active filters) ───────────────────────────────────────
async function quickExportLeads() {
  const status    = document.getElementById('filterStatus')?.value
  const projectId = document.getElementById('filterProject')?.value
  const params = []
  if (status)    params.push(`status=${encodeURIComponent(status)}`)
  if (projectId) params.push(`project_id=${encodeURIComponent(projectId)}`)
  const query = params.length ? '?' + params.join('&') : ''
  try {
    const res = await fetch(`${API_BASE}/leads/export/excel${query}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) { alert('Export failed'); return }
    const blob = await res.blob()
    const url  = window.URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url
    a.download = `leads_export_${Date.now()}.xlsx`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (err) { alert('Export error: ' + err.message) }
}

function getStatusColor(status) {
  const colors = {
    'new':                '#3b82f6',
    'attempted':          '#f59e0b',
    'connected':          '#10b981',
    'interested':         '#8b5cf6',
    'follow_up':          '#f97316',
    'site_visit_planned': '#0ea5e9',
    'site_visit_done':    '#06b6d4',
    'negotiation':        '#ec4899',
    'booking_done':       '#22c55e',
    'not_interested':     '#f43f5e',
    'lost':               '#ef4444',
    'junk':               '#6b7280'
  }
  return colors[status] || '#6b7280'
}

async function viewLeadDetails(leadId) {
  selectedLeadId = leadId
  const lead = leads.find(l => l.id === leadId)
  if (!lead) return
  
  const content = document.getElementById('content')
  
  // Load lead details, notes, and status history
  await loadProjects()
  const [notesRes, historyRes, assignmentRes] = await Promise.all([
    fetch(`${API_BASE}/leads/${leadId}/notes`, { headers: { Authorization: `Bearer ${token}` } }),
    fetch(`${API_BASE}/leads/${leadId}/status-history`, { headers: { Authorization: `Bearer ${token}` } }),
    fetch(`${API_BASE}/leads/${leadId}/assignment-history`, { headers: { Authorization: `Bearer ${token}` } })
  ])
  
  const notesData = await notesRes.json()
  const historyData = await historyRes.json()
  const assignmentData = await assignmentRes.json()
  
  const notes = notesData.notes || []
  const statusHistory = historyData.status_history || []
  const assignmentHistory = assignmentData.assignment_history || []
  
  content.innerHTML = `
    <div class="card" style="max-width:900px;">
      <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:20px;">
        <div>
          <h2>${escape(lead.name)}</h2>
          <p style="color:#64748b;margin:0;">Status: <span class="tag" style="background:${getStatusColor(lead.status)};color:#fff;">${escape(lead.status)}</span></p>
        </div>
        <button class="button secondary" id="closeLead" style="padding:8px 16px;">← Back</button>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
        <div>
          <h3>Lead Information</h3>
          <table class="table" style="margin-top:10px;">
            <tr><td><strong>Phone</strong></td><td>${escape(lead.phone || '-')}</td></tr>
            <tr><td><strong>Email</strong></td><td>${escape(lead.email || '-')}</td></tr>
            <tr><td><strong>Source</strong></td><td>${escape(lead.source || '-')}</td></tr>
            <tr><td><strong>Budget</strong></td><td>${lead.budget_min ? fmtBudget(lead.budget_min) + ' – ' + fmtBudget(lead.budget_max) : '-'}</td></tr>
            <tr><td><strong>Assigned To</strong></td><td>${escape(lead.assigned_to_name || 'Unassigned')}</td></tr>
            <tr><td><strong>Created</strong></td><td>${new Date(lead.created_at).toLocaleDateString()}</td></tr>
          </table>
          
          ${user.role !== 'team_member' ? `
            <div style="margin-top:20px;">
              <h3>Update Status</h3>
              <form id="updateStatusForm" style="display:flex;gap:10px;">
                <select id="newStatus" class="select" style="flex:1;">
                  <option value="new">New</option>
                  <option value="attempted">Attempted</option>
                  <option value="connected">Connected</option>
                  <option value="interested">Interested</option>
                  <option value="site_visit_planned">Site Visit Planned</option>
                  <option value="site_visit_done">Site Visit Done</option>
                  <option value="negotiation">Negotiation</option>
                  <option value="booking_done">Booking Done</option>
                  <option value="lost">Lost</option>
                  <option value="junk">Junk</option>
                </select>
                <button type="submit" class="button">Update</button>
              </form>
            </div>
            <div style="margin-top:16px;">
              <h3>Update Project</h3>
              <form id="updateProjectForm" style="display:flex;gap:10px;">
                <select id="newProject" class="select" style="flex:1;">
                  <option value="">— No Project —</option>
                  ${projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')}
                </select>
                <button type="submit" class="button">Update</button>
              </form>
            </div>
            <div style="margin-top:16px;">
              <h3>Update Source</h3>
              <form id="updateSourceForm" style="display:flex;gap:10px;">
                <select id="newSource" class="select" style="flex:1;">
                  <option value="">— Select Source —</option>
                  <option value="Website">Website</option>
                  <option value="Referral">Referral</option>
                  <option value="Walk-in">Walk-in</option>
                  <option value="Meta">Meta</option>
                  <option value="Google">Google</option>
                  <option value="Email Campaign">Email Campaign</option>
                  <option value="Direct">Direct</option>
                  <option value="Other">Other</option>
                  <option value="G1">G1</option>
                  <option value="G2">G2</option>
                  <option value="G3">G3</option>
                  <option value="TP">TP</option>
                </select>
                <button type="submit" class="button">Update</button>
              </form>
            </div>
          ` : ''}
          
          ${user.role === 'sales_manager' || user.role === 'superadmin' ? `
            <div style="margin-top:20px;">
              <h3>Assign Lead</h3>
              <form id="assignForm" style="display:flex;flex-direction:column;gap:8px;">
                ${user.role === 'superadmin' ? `<select id="assignToManager" class="select" style="font-size:13px;"><option value="">— Filter by Sales Manager —</option></select>` : ''}
                <div style="display:flex;gap:10px;">
                  <select id="assignTo" class="select" style="flex:1;"></select>
                  <button type="submit" class="button">Assign</button>
                </div>
              </form>
            </div>
          ` : ''}
        </div>
        
        <div>
          <h3>Notes</h3>
          <div id="notesContainer" style="border:1px solid #e2e8f0;border-radius:8px;padding:10px;height:200px;overflow-y:auto;margin-bottom:10px;background:#f8fafc;">
            ${notes.length === 0 ? '<div style="color:#94a3b8;">No notes yet</div>' : notes.map(n => `
              <div style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:13px;">
                <div style="font-weight:bold;color:#0f172a;margin-bottom:2px;">${escape(n.created_by_name || 'Unknown')}</div>
                <div>${escape(n.note)}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">${new Date(n.created_at).toLocaleDateString()}</div>
              </div>
            `).join('')}
          </div>
          
          <form id="addNoteForm" style="display:flex;gap:8px;">
            <textarea id="noteText" class="input" style="flex:1;height:60px;" placeholder="Add a note..."></textarea>
            <button type="submit" class="button" style="align-self:flex-end;">Add</button>
          </form>
        </div>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
        <div>
          <h3>Status History</h3>
          <div style="border:1px solid #e2e8f0;border-radius:8px;padding:10px;max-height:250px;overflow-y:auto;">
            ${statusHistory.length === 0 ? '<div style="color:#94a3b8;font-size:13px;">No status changes yet</div>' : statusHistory.map(h => `
              <div style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:12px;">
                <div style="font-weight:bold;color:#0f172a;">${escape(h.old_status)} → ${escape(h.new_status)}</div>
                <div style="color:#64748b;font-size:11px;">${escape(h.changed_by_name || 'Unknown')} on ${new Date(h.changed_at).toLocaleDateString()}</div>
              </div>
            `).join('')}
          </div>
        </div>
        
        <div>
          <h3>Assignment History</h3>
          <div style="border:1px solid #e2e8f0;border-radius:8px;padding:10px;max-height:250px;overflow-y:auto;">
            ${assignmentHistory.length === 0 ? '<div style="color:#94a3b8;font-size:13px;">No assignments yet</div>' : assignmentHistory.map(a => `
              <div style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:12px;">
                <div style="font-weight:bold;color:#0f172a;">${escape(a.assigned_from_name || 'Unassigned')} → ${escape(a.assigned_to_name)}</div>
                <div style="color:#64748b;font-size:11px;">${escape(a.assigned_by_name || 'Unknown')} on ${new Date(a.assigned_at).toLocaleDateString()}</div>
                ${a.reason ? `<div style="color:#64748b;font-size:11px;margin-top:4px;">Reason: ${escape(a.reason)}</div>` : ''}
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    </div>
  `
  
  document.getElementById('closeLead').addEventListener('click', renderLeads)
  
  // Set current values in dropdowns
  const newStatusSelect = document.getElementById('newStatus')
  if (newStatusSelect) newStatusSelect.value = lead.status

  const newProjectSelect = document.getElementById('newProject')
  if (newProjectSelect && lead.project_id) newProjectSelect.value = lead.project_id

  const newSourceSelect = document.getElementById('newSource')
  if (newSourceSelect && lead.source) newSourceSelect.value = lead.source

  // Update status handler
  if (document.getElementById('updateStatusForm')) {
    document.getElementById('updateStatusForm').addEventListener('submit', async e => {
      e.preventDefault()
      const newStatus = document.getElementById('newStatus').value
      const res = await fetch(`${API_BASE}/leads/${leadId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: newStatus })
      })
      if (res.ok) { await loadLeads(); viewLeadDetails(leadId) }
    })
  }

  // Update project handler
  if (document.getElementById('updateProjectForm')) {
    document.getElementById('updateProjectForm').addEventListener('submit', async e => {
      e.preventDefault()
      const projectId = document.getElementById('newProject').value
      const res = await fetch(`${API_BASE}/leads/${leadId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ project_id: projectId ? parseInt(projectId) : null })
      })
      if (res.ok) { await loadLeads(); viewLeadDetails(leadId) }
    })
  }

  // Update source handler
  if (document.getElementById('updateSourceForm')) {
    document.getElementById('updateSourceForm').addEventListener('submit', async e => {
      e.preventDefault()
      const source = document.getElementById('newSource').value
      const res = await fetch(`${API_BASE}/leads/${leadId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ source })
      })
      if (res.ok) { await loadLeads(); viewLeadDetails(leadId) }
    })
  }
  
  // Add note handler
  if (document.getElementById('addNoteForm')) {
    document.getElementById('addNoteForm').addEventListener('submit', async e => {
      e.preventDefault()
      const noteText = document.getElementById('noteText').value
      const res = await fetch(`${API_BASE}/leads/${leadId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ note: noteText })
      })
      if (res.ok) {
        await loadLeads()
        viewLeadDetails(leadId)
      }
    })
  }
  
  // Assign lead handler
  if (document.getElementById('assignForm')) {
    const assignSelect = document.getElementById('assignTo')
    await loadUsers()

    function updateAssignToOptions(managerId) {
      const allTM = users.filter(u => u.role === 'team_member')
      const filtered = managerId ? allTM.filter(u => String(u.manager_id) === String(managerId)) : allTM
      // If current user is a sales_manager, also include themselves in the list
      const selfOption = (user.role === 'sales_manager')
        ? `<option value="${user.id}">${escape(user.name)} (me)</option>` : ''
      assignSelect.innerHTML = '<option value="">Select team member</option>' + selfOption +
        filtered.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
      if (lead.assigned_to) assignSelect.value = lead.assigned_to
    }

    const mgrFilterSel = document.getElementById('assignToManager')
    if (mgrFilterSel) {
      const managers = users.filter(u => u.role === 'sales_manager')
      mgrFilterSel.innerHTML = '<option value="">— Filter by Sales Manager —</option>' +
        managers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
      // Pre-select manager based on currently assigned team member's manager
      const assignedUser = users.find(u => u.id === lead.assigned_to)
      const preManagerId = assignedUser?.manager_id || null
      if (preManagerId) mgrFilterSel.value = preManagerId
      mgrFilterSel.addEventListener('change', () => updateAssignToOptions(mgrFilterSel.value))
      updateAssignToOptions(preManagerId)
    } else {
      // sales_manager: show only own team
      updateAssignToOptions(user.id)
    }

    document.getElementById('assignForm').addEventListener('submit', async e => {
      e.preventDefault()
      const assignedTo = parseInt(document.getElementById('assignTo').value)
      const res = await fetch(`${API_BASE}/leads/${leadId}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ assigned_to: assignedTo })
      })
      if (res.ok) {
        await loadLeads()
        viewLeadDetails(leadId)
      }
    })
  }
}

async function openLeadForm() {
  const content = document.getElementById('content')
  await loadProjects()
  
  const projectOptions = projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')
  
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>New Lead</h2>
      <form id="leadForm">
        <input class="input" id="leadName" placeholder="Full Name" required />
        <input class="input" id="leadPhone" placeholder="Phone Number" />
        <input class="input" id="leadEmail" placeholder="Email Address" />
        <select class="select" id="leadSource">
          <option value="">Select Source</option>
          <option value="Website">Website</option>
          <option value="Referral">Referral</option>
          <option value="Walk-in">Walk-in</option>
          <option value="Meta">Meta</option>
          <option value="Google">Google</option>
          <option value="Email Campaign">Email Campaign</option>
          <option value="Direct">Direct</option>
          <option value="Other">Other</option>
          <option value="G1">G1</option>
          <option value="G2">G2</option>
          <option value="G3">G3</option>
          <option value="TP">TP</option>
        </select>
        
        <label style="font-size:13px;color:#64748b;margin-bottom:4px;display:block;">Budget Range (₹ Cr)</label>
        <select class="select" id="leadBudget">
          ${budgetRangeOptions()}
        </select>
        
        <select class="select" id="leadProject">
          <option value="">Select a project</option>
          ${projectOptions}
        </select>
        
        <select class="select" id="leadStatus">
          <option value="new">New</option>
          <option value="attempted">Attempted</option>
          <option value="connected">Connected</option>
          <option value="interested">Interested</option>
          <option value="site_visit_planned">Site Visit Planned</option>
          <option value="site_visit_done">Site Visit Done</option>
          <option value="negotiation">Negotiation</option>
          <option value="booking_done">Booking Done</option>
          <option value="lost">Lost</option>
          <option value="junk">Junk</option>
        </select>
        
        <div id="dupWarn"></div>
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">Save Lead</button>
          <button type="button" class="button secondary" id="cancelLead">Cancel</button>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('leadForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('leadName').value
    const phone = document.getElementById('leadPhone').value
    const email = document.getElementById('leadEmail').value
    const source = document.getElementById('leadSource').value
    const leadBudgetParts = (document.getElementById('leadBudget').value || '').split('|')
    const budget_min = Number(leadBudgetParts[0]) || null
    const budget_max = Number(leadBudgetParts[1]) || null
    const project_id = Number(document.getElementById('leadProject').value) || null
    const status = document.getElementById('leadStatus').value
    
    const submitLead = async (force = false) => {
      const res = await fetch(`${API_BASE}/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name, phone, email, source, budget_min, budget_max, project_id, status, ...(force && { force: true }) })
      })
      if (res.ok) { renderLeads(); return }
      if (res.status === 409) {
        const err = await res.json()
        const ex = err.existing_lead
        document.getElementById('dupWarn').innerHTML = `
          <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:12px 14px;margin-top:12px;">
            <div style="font-size:13px;font-weight:600;color:#92400e;">⚠ Duplicate phone number</div>
            <div style="font-size:12px;color:#78350f;margin-top:4px;">
              Lead <strong>${escape(ex.name)}</strong> (ID #${ex.id}, status: <em>${ex.status.replace(/_/g,' ')}</em>) already has this phone number.
            </div>
            <div style="display:flex;gap:8px;margin-top:10px;">
              <button type="button" class="button" onclick="viewLeadDetails(${ex.id})" style="font-size:12px;padding:6px 14px;">View Existing</button>
              ${user && user.role === 'superadmin' ? '<button type="button" id="forceCreate" class="button secondary" style="font-size:12px;padding:6px 14px;">Create Anyway</button>' : ''}
            </div>
          </div>`
        document.getElementById('forceCreate').addEventListener('click', () => submitLead(true))
        return
      }
      alert('Failed to save lead')
    }
    await submitLead()
  })
  
  document.getElementById('cancelLead').addEventListener('click', renderLeads)
}

// ============================================================================
// PIPELINE / KANBAN
// ============================================================================

const PIPELINE_STAGE_LABELS = {
  new: 'New', attempted: 'Attempted', connected: 'Connected',
  interested: 'Interested', site_visit_planned: 'Site Visit Planned',
  site_visit_done: 'Site Visit Done', negotiation: 'Negotiation',
  booking_done: 'Booking Done', lost: 'Lost', junk: 'Junk',
}
const PIPELINE_STAGES = Object.keys(PIPELINE_STAGE_LABELS)

async function renderPipeline() {
  const content = document.getElementById('content')

  await Promise.all([loadUsers(), loadProjects()])
  const salesManagers = users.filter(u => u.role === 'sales_manager')

  content.innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:10px;">
        <h2 style="margin:0;">Pipeline View</h2>
      </div>

      <!-- Pipeline Filters -->
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin-bottom:16px;display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
        ${user.role === 'superadmin' ? `
        <div style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1;">
          <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">SALES MANAGER</label>
          <select id="pipelineManagerFilter" class="select" style="font-size:13px;">
            <option value="">All Sales Managers</option>
            ${salesManagers.map(m => `<option value="${m.id}">${escape(m.name)}</option>`).join('')}
          </select>
        </div>` : ''}
        <div style="display:flex;flex-direction:column;gap:4px;min-width:160px;flex:1;">
          <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">PROJECT</label>
          <select id="pipelineProjectFilter" class="select" style="font-size:13px;">
            <option value="">All Projects</option>
            ${projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')}
          </select>
        </div>
        <div style="display:flex;align-items:flex-end;">
          <button onclick="clearPipelineFilters()" class="button secondary" style="font-size:12px;padding:7px 14px;">✕ Clear</button>
        </div>
      </div>

      <p style="color:#94a3b8;font-size:12px;margin:0 0 16px;">Click any status header to view all leads in that stage</p>
      <div id="pipelineContainer" class="pipeline-grid"></div>
    </div>
  `

  const res = await fetch(`${API_BASE}/pipeline/stages`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  window._pipelineData = data.pipeline || {}

  document.getElementById('pipelineManagerFilter')?.addEventListener('change', applyPipelineFilters)
  document.getElementById('pipelineProjectFilter')?.addEventListener('change', applyPipelineFilters)

  applyPipelineFilters()
}

function applyPipelineFilters() {
  const managerId  = document.getElementById('pipelineManagerFilter')?.value || ''
  const projectId  = document.getElementById('pipelineProjectFilter')?.value || ''
  const pipeline   = window._pipelineData || {}

  // Build the set of user IDs under this manager (including manager themselves)
  let managerUserIds = null
  if (managerId) {
    managerUserIds = new Set(users.filter(u => String(u.manager_id) === managerId).map(u => u.id))
    managerUserIds.add(parseInt(managerId))
  }

  document.getElementById('pipelineContainer').innerHTML = PIPELINE_STAGES.map(stage => {
    const stageData = pipeline[stage] || { count: 0, leads: [] }
    let filtered = stageData.leads
    if (managerUserIds) filtered = filtered.filter(l => l.assigned_to && managerUserIds.has(l.assigned_to))
    if (projectId)      filtered = filtered.filter(l => String(l.project_id) === projectId)

    const color   = getStatusColor(stage)
    const preview = filtered.slice(0, 5)
    const more    = filtered.length - preview.length
    const safeM   = managerId.replace(/'/g,"\'")
    const safeP   = projectId.replace(/'/g,"\'")
    return `
      <div class="pipeline-col">
        <div class="pipeline-col-header" style="border-bottom:3px solid ${color};background:${color}18;"
             onclick="openPipelineStage('${stage}','${safeM}','${safeP}')">
          <div style="font-size:11px;font-weight:700;color:${color};letter-spacing:.6px;">${PIPELINE_STAGE_LABELS[stage].toUpperCase()}</div>
          <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1.1;">${filtered.length}</div>
        </div>
        <div class="pipeline-col-body">
          ${preview.map(lead => {
            const mgrName = (() => {
              const u = users.find(u => u.id === lead.assigned_to)
              if (!u) return null
              const mgr = users.find(m => m.id === u.manager_id)
              return mgr ? mgr.name : null
            })()
            return `
            <div class="pipeline-card" style="border-left:3px solid ${color};" onclick="viewLeadDetails(${lead.id})">
              <div style="font-weight:600;font-size:12px;color:#0f172a;">${escape(lead.name)}</div>
              <div style="font-size:11px;color:#64748b;margin-top:2px;">${escape(lead.phone || '-')}</div>
              <div style="font-size:11px;color:#94a3b8;margin-top:3px;">${escape(lead.assigned_to_name || 'Unassigned')}${mgrName ? ` <span style="color:#2563eb;">· ${escape(mgrName)}</span>` : ''}</div>
            </div>`
          }).join('')}
          ${more > 0 ? `<div class="pipeline-more" onclick="openPipelineStage('${stage}','${safeM}','${safeP}')">+${more} more</div>` : ''}
          ${filtered.length === 0 ? `<div class="pipeline-empty">No leads</div>` : ''}
        </div>
      </div>
    `
  }).join('')
}

function clearPipelineFilters() {
  const mf = document.getElementById('pipelineManagerFilter')
  const pf = document.getElementById('pipelineProjectFilter')
  if (mf) mf.value = ''
  if (pf) pf.value = ''
  applyPipelineFilters()
}

function openPipelineStage(stage, managerId = '', projectId = '') {
  const pipeline = window._pipelineData || {}
  const stageData = pipeline[stage] || { count: 0, leads: [] }
  const color = getStatusColor(stage)

  // Apply active filters from dropdowns (dropdown values take precedence over args)
  const activeMgr = document.getElementById('pipelineManagerFilter')?.value || managerId
  const activePrj = document.getElementById('pipelineProjectFilter')?.value || projectId

  let managerUserIds = null
  if (activeMgr) {
    managerUserIds = new Set(users.filter(u => String(u.manager_id) === activeMgr).map(u => u.id))
    managerUserIds.add(parseInt(activeMgr))
  }

  let leads = stageData.leads || []
  if (managerUserIds) leads = leads.filter(l => l.assigned_to && managerUserIds.has(l.assigned_to))
  if (activePrj)      leads = leads.filter(l => String(l.project_id) === activePrj)

  const leadsHtml = leads.length === 0
    ? `<div style="text-align:center;color:#94a3b8;padding:48px 0;font-size:14px;">No leads in this stage</div>`
    : leads.map(lead => {
        const assignedUser = users.find(u => u.id === lead.assigned_to)
        const mgrName = assignedUser ? users.find(m => m.id === assignedUser.manager_id)?.name : null
        return `
        <div class="pipeline-modal-row" onclick="closePipelineModal();viewLeadDetails(${lead.id})">
          <div class="pipeline-modal-avatar" style="background:${color}20;color:${color};">
            ${escape(lead.name.charAt(0).toUpperCase())}
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;color:#0f172a;font-size:14px;">${escape(lead.name)}</div>
            <div style="color:#64748b;font-size:12px;margin-top:2px;">${escape(lead.phone || '-')}${lead.email ? ' · ' + escape(lead.email) : ''}</div>
            ${lead.project_name ? `<div style="font-size:11px;color:#2563eb;margin-top:2px;">${escape(lead.project_name)}</div>` : ''}
          </div>
          <div style="text-align:right;flex-shrink:0;">
            <div style="font-size:12px;color:#475569;">${escape(lead.assigned_to_name || 'Unassigned')}</div>
            ${mgrName ? `<div style="font-size:11px;color:#7c3aed;margin-top:1px;">${escape(mgrName)}</div>` : ''}
            ${lead.budget_min || lead.budget_max ? `<div style="font-size:11px;color:#94a3b8;margin-top:2px;">${fmtBudget(lead.budget_min)} – ${fmtBudget(lead.budget_max)}</div>` : ''}
          </div>
        </div>`
      }).join('')

  const modal = document.createElement('div')
  modal.className = 'modal-overlay'
  modal.id = 'pipelineModal'
  modal.innerHTML = `
    <div class="modal-box" style="width:600px;padding:0;overflow:hidden;">
      <div style="background:${color}18;border-bottom:3px solid ${color};padding:20px 24px;display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div style="font-size:11px;font-weight:700;color:${color};letter-spacing:.8px;text-transform:uppercase;">Pipeline Stage</div>
          <div style="font-size:20px;font-weight:800;color:#0f172a;">${PIPELINE_STAGE_LABELS[stage]}</div>
          <div style="font-size:13px;color:#64748b;margin-top:2px;">${leads.length} lead${leads.length !== 1 ? 's' : ''}</div>
        </div>
        <button onclick="closePipelineModal()" class="modal-close" style="position:static;">✕</button>
      </div>
      <div style="max-height:480px;overflow-y:auto;">${leadsHtml}</div>
    </div>
  `
  modal.addEventListener('click', e => { if (e.target === modal) closePipelineModal() })
  document.body.appendChild(modal)
}

function closePipelineModal() {
  const m = document.getElementById('pipelineModal')
  if (m) m.remove()
}

function fmtBudget(val) {
  if (!val) return '?'
  if (val >= 10000000) return '₹' + (val / 10000000).toFixed(1) + ' Cr'
  if (val >= 100000) return '₹' + (val / 100000).toFixed(1) + ' L'
  return '₹' + val
}

function budgetRangeOptions(selMin, selMax) {
  let opts = '<option value="">Select Budget Range</option>'
  for (let i = 0.5; i < 10; i = Math.round((i + 0.5) * 10) / 10) {
    const lo = i
    const hi = Math.round((i + 0.5) * 10) / 10
    const min = Math.round(lo * 1e7)
    const max = Math.round(hi * 1e7)
    const label = `₹${lo} Cr – ₹${hi} Cr`
    const sel = (selMin === min && selMax === max) ? ' selected' : ''
    opts += `<option value="${min}|${max}"${sel}>${label}</option>`
  }
  return opts
}

// ============================================================================
// PROJECTS
// ============================================================================

async function renderProjects() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <div class="header" style="margin-bottom:20px;">
        <h2>Projects</h2>
        ${user && user.role === 'superadmin' ? '<button class="button" id="newProjectBtn">+ New Project</button>' : ''}
      </div>
      <div id="projectsContainer"></div>
    </div>
  `
  
  const newProjBtn = document.getElementById('newProjectBtn')
  if (newProjBtn) newProjBtn.addEventListener('click', openProjectForm)
  
  await loadProjects()
  
  const container = document.getElementById('projectsContainer')
  if (projects.length === 0) {
    container.innerHTML = '<div class="message">No projects found</div>'
    return
  }
  
  container.innerHTML = `
    <div style="overflow-x:auto;">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Location</th>
            <th>Developer</th>
            <th>Type</th>
            <th>Budget Range</th>
            <th>Created By</th>
            ${user && user.role === 'superadmin' ? '<th>Actions</th>' : ''}
          </tr>
        </thead>
        <tbody>
          ${projects.map(p => `
            <tr>
              <td><strong>${escape(p.name)}</strong></td>
              <td>${escape(p.location || '-')}</td>
              <td>${escape(p.developer || '-')}</td>
              <td>${escape(p.project_type || '-')}</td>
              <td>${p.budget_min ? fmtBudget(p.budget_min) + ' – ' + fmtBudget(p.budget_max) : '-'}</td>
              <td>${escape(p.created_by_name || '-')}</td>
              ${user && user.role === 'superadmin' ? '<td><button class="button secondary" data-id="' + p.id + '" style="font-size:12px;padding:6px 10px;">Edit</button><button class="button" data-del-id="' + p.id + '" data-del-name="' + escape(p.name) + '" style="font-size:12px;padding:6px 10px;background:#ef4444;border-color:#ef4444;margin-left:4px;">Delete</button></td>' : ''}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `

  container.querySelectorAll('button[data-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = projects.find(x => x.id === Number(btn.dataset.id))
      if (p) openProjectForm(p)
    })
  })

  container.querySelectorAll('button[data-del-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm(`Delete project "${btn.dataset.delName}"? This cannot be undone.`)) return
      const res = await fetch(`${API_BASE}/projects/${btn.dataset.delId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) renderProjects()
      else alert('Error deleting project')
    })
  })
}

async function openProjectForm(project = null) {
  const isEdit = project !== null
  const content = document.getElementById('content')
  const budgetVal = (project && project.budget_min && project.budget_max)
    ? `${project.budget_min}|${project.budget_max}` : ''
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>${isEdit ? 'Edit Project' : 'New Project'}</h2>
      <form id="projectForm">
        <input class="input" id="projName" placeholder="Project Name" required value="${isEdit ? escape(project.name) : ''}" />
        <input class="input" id="projLocation" placeholder="Location" value="${isEdit ? escape(project.location || '') : ''}" />
        <input class="input" id="projDeveloper" placeholder="Developer Name" value="${isEdit ? escape(project.developer || '') : ''}" />
        <input class="input" id="projType" placeholder="Project Type" value="${isEdit ? escape(project.project_type || '') : ''}" />
        <textarea class="input" id="projDescription" placeholder="Description" style="height:80px;">${isEdit ? escape(project.description || '') : ''}</textarea>
        
        <label style="font-size:13px;color:#64748b;margin-bottom:4px;display:block;">Budget Range (₹ Cr)</label>
        <select class="select" id="projBudget">
          ${budgetRangeOptions(project ? project.budget_min : null, project ? project.budget_max : null)}
        </select>
        
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">${isEdit ? 'Update Project' : 'Save Project'}</button>
          <button type="button" class="button secondary" id="cancelProject">Cancel</button>
        </div>
      </form>
    </div>
  `

  // Pre-select dropdown for existing project if value matches an option
  if (budgetVal) {
    const sel = document.getElementById('projBudget')
    const opt = Array.from(sel.options).find(o => o.value === budgetVal)
    if (opt) opt.selected = true
  }
  
  document.getElementById('projectForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('projName').value
    const location = document.getElementById('projLocation').value
    const developer = document.getElementById('projDeveloper').value
    const project_type = document.getElementById('projType').value
    const description = document.getElementById('projDescription').value
    const budgetParts = (document.getElementById('projBudget').value || '').split('|')
    const budget_min = Number(budgetParts[0]) || null
    const budget_max = Number(budgetParts[1]) || null
    
    const url = isEdit ? `${API_BASE}/projects/${project.id}` : `${API_BASE}/projects`
    const method = isEdit ? 'PUT' : 'POST'
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name, location, developer, project_type, description, budget_min, budget_max })
    })
    if (res.ok) renderProjects()
  })
  
  document.getElementById('cancelProject').addEventListener('click', renderProjects)
}

// ============================================================================
// TEAM MANAGEMENT
// ============================================================================

async function renderTeamManagement() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <div class="header" style="margin-bottom:20px;">
        <h2>Team Management</h2>
        <button class="button" id="newUserBtn">+ Add Team Member</button>
      </div>
      <div id="teamContainer"></div>
    </div>
  `
  
  document.getElementById('newUserBtn').addEventListener('click', openUserForm)
  
  await loadUsers()
  
  const container = document.getElementById('teamContainer')

  const TABLE_HEADERS_BASE = `<thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead>`
  const TABLE_HEADERS_TEAM = `<thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Sales Manager</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead>`

  function userRow(u, showManager) {
    const managerName = showManager
      ? (users.find(m => m.id === u.manager_id)?.name || '<span style="color:#94a3b8;">Unassigned</span>')
      : null
    return `<tr>
      <td><strong>${escape(u.name)}</strong></td>
      <td>${escape(u.email)}</td>
      <td>${escape(u.phone || '-')}</td>
      ${showManager ? `<td><span style="font-size:12px;font-weight:500;color:#0369a1;">${managerName}</span></td>` : ''}
      <td>${u.is_active ? '<span class="tag" style="background:#dcfce7;color:#166534;">Active</span>' : '<span class="tag" style="background:#fee2e2;color:#991b1b;">Inactive</span>'}</td>
      <td>${u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}</td>
      <td>
        <button class="button secondary edit-user-btn" data-id="${u.id}" style="font-size:12px;padding:6px 10px;">Edit</button>
        <button class="button del-user-btn" data-id="${u.id}" data-name="${escape(u.name)}" style="font-size:12px;padding:6px 10px;background:#ef4444;border-color:#ef4444;margin-left:4px;">Delete</button>
      </td>
    </tr>`
  }

  function sectionHTML(title, color, textColor, bgColor, members, showManager) {
    if (members.length === 0) return ''
    const headers = showManager ? TABLE_HEADERS_TEAM : TABLE_HEADERS_BASE
    return `
      <div style="margin-bottom:28px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
          <span style="font-size:14px;font-weight:700;color:${textColor};">${title}</span>
          <span style="font-size:12px;font-weight:600;background:${bgColor};color:${textColor};padding:2px 10px;border-radius:20px;">${members.length}</span>
          <div style="flex:1;height:1px;background:${color};opacity:0.3;"></div>
        </div>
        <div style="overflow-x:auto;">
          <table class="table">
            ${headers}
            <tbody>${members.map(u => userRow(u, showManager)).join('')}</tbody>
          </table>
        </div>
      </div>
    `
  }

  if (user.role === 'sales_manager') {
    const myTeam = users.filter(u => u.manager_id === user.id)
    if (myTeam.length === 0) {
      container.innerHTML = '<div class="message">No team members assigned to you yet.</div>'
      return
    }
    container.innerHTML = sectionHTML('Team Members', '#6366f1', '#4338ca', '#ede9fe', myTeam, false)
  } else {
    // superadmin: split into sections by role
    const superAdmins  = users.filter(u => u.role === 'superadmin')
    const salesManagers = users.filter(u => u.role === 'sales_manager')
    const teamMembers   = users.filter(u => u.role === 'team_member')
    if (superAdmins.length === 0 && salesManagers.length === 0 && teamMembers.length === 0) {
      container.innerHTML = '<div class="message">No team members found.</div>'
      return
    }
    container.innerHTML =
      sectionHTML('Super Admins',   '#94a3b8', '#475569', '#f1f5f9', superAdmins,  false) +
      sectionHTML('Sales Managers', '#0ea5e9', '#0369a1', '#e0f2fe', salesManagers, false) +
      sectionHTML('Team Members',   '#6366f1', '#4338ca', '#ede9fe', teamMembers,  true)
  }
  
  // Add click handlers for edit buttons
  document.querySelectorAll('.edit-user-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const userId = parseInt(e.target.getAttribute('data-id'))
      const editUser = users.find(u => u.id === userId)
      if (editUser) openEditUserForm(editUser)
    })
  })

  document.querySelectorAll('.del-user-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm(`Delete team member "${btn.dataset.name}"? This cannot be undone.`)) return
      const res = await fetch(`${API_BASE}/users/${btn.dataset.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        await loadUsers()
        renderTeamManagement()
      } else {
        const err = await res.json().catch(() => ({}))
        alert(err.error || 'Error deleting user')
      }
    })
  })
}

async function openEditUserForm(editUser) {
  const content = document.getElementById('content')
  
  let salesManagerOptions = ''
  if (user.role === 'superadmin') {
    const managers = users.filter(u => u.role === 'sales_manager')
    salesManagerOptions = '<option value="">Unassigned</option>' + managers.map(m => 
      `<option value="${m.id}" ${editUser.manager_id === m.id ? 'selected' : ''}>${escape(m.name)}</option>`
    ).join('')
  }
  
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>Edit ${editUser.role === 'sales_manager' ? 'Sales Manager' : editUser.role === 'superadmin' ? 'Super Admin' : 'Team Member'}</h2>
      <form id="userForm">
        <input class="input" id="userName" placeholder="Full Name" value="${escape(editUser.name)}" required />
        <input class="input" id="userEmail" placeholder="Email Address" type="email" value="${escape(editUser.email)}" required />
        <input class="input" id="userPhone" placeholder="Phone Number" value="${escape(editUser.phone || '')}" />
        
        ${user.role === 'superadmin' ? `
          <select class="select" id="userRole" required>
            <option value="team_member" ${editUser.role === 'team_member' ? 'selected' : ''}>Team Member</option>
            <option value="sales_manager" ${editUser.role === 'sales_manager' ? 'selected' : ''}>Sales Manager</option>
            <option value="superadmin" ${editUser.role === 'superadmin' ? 'selected' : ''}>Super Admin</option>
          </select>
        ` : '<input type="hidden" id="userRole" value="' + editUser.role + '" />'}
        
        ${user.role === 'superadmin' && editUser.role === 'team_member' ? `
          <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">Sales Manager</label>
          <select class="select" id="userManager">
            ${salesManagerOptions}
          </select>
        ` : '<input type="hidden" id="userManager" value="' + (editUser.manager_id || '') + '" />'}
        
        <label style="display:flex;align-items:center;gap:8px;margin:10px 0;font-weight:500;">
          <input type="checkbox" id="isActive" ${editUser.is_active ? 'checked' : ''} />
          Active User
        </label>
        
        ${user.role === 'superadmin' ? `
          <div style="border-top:1px solid #e2e8f0;padding-top:16px;margin-top:16px;">
            <label style="display:block;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">Change Password (Optional)</label>
            <input class="input" id="userPassword" placeholder="New Password" type="password" />
            <p style="font-size:12px;color:#94a3b8;margin-top:6px;">Leave blank to keep current password unchanged</p>
          </div>
        ` : ''}
        
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">Save Changes</button>
          <button type="button" class="button secondary" id="cancelUser">Cancel</button>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('userForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('userName').value
    const email = document.getElementById('userEmail').value
    const phone = document.getElementById('userPhone').value
    const role = document.getElementById('userRole').value
    const isActive = document.getElementById('isActive').checked
    const managerId = document.getElementById('userManager')?.value || ''
    const password = user.role === 'superadmin' ? (document.getElementById('userPassword')?.value || '') : ''
    
    const body = { name, email, phone, role, is_active: isActive }
    if (user.role === 'superadmin' && editUser.role === 'team_member' && managerId) {
      body.manager_id = parseInt(managerId)
    }
    if (user.role === 'superadmin' && editUser.role === 'team_member' && !managerId) {
      body.manager_id = null
    }
    if (password) body.password = password
    
    const res = await fetch(`${API_BASE}/users/${editUser.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body)
    })
    if (res.ok) {
      await loadUsers()
      renderTeamManagement()
    } else {
      alert('Error updating user')
    }
  })
  
  document.getElementById('cancelUser').addEventListener('click', renderTeamManagement)
}

async function openUserForm() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>Add Team Member</h2>
      <form id="userForm">
        <input class="input" id="userName" placeholder="Full Name" required />
        <input class="input" id="userEmail" placeholder="Email Address" type="email" required />
        <input class="input" id="userPhone" placeholder="Phone Number" />
        
        ${user.role === 'superadmin' ? `
          <select class="select" id="userRole">
            <option value="team_member">Team Member</option>
            <option value="sales_manager">Sales Manager</option>
            <option value="superadmin">Super Admin</option>
          </select>
        ` : '<input type="hidden" id="userRole" value="team_member" />'}
        
        <input class="input" id="userPassword" placeholder="Temporary Password" type="password" value="TeamMember@123" />
        
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">Create User</button>
          <button type="button" class="button secondary" id="cancelUser">Cancel</button>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('userForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('userName').value
    const email = document.getElementById('userEmail').value
    const phone = document.getElementById('userPhone').value
    const role = document.getElementById('userRole').value
    const password = document.getElementById('userPassword').value
    
    const res = await fetch(`${API_BASE}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name, email, phone, role, password })
    })
    if (res.ok) renderTeamManagement()
  })
  
  document.getElementById('cancelUser').addEventListener('click', renderTeamManagement)
}

// ============================================================================
// ACTIVITY LOGS
// ============================================================================

async function renderActivityLogs() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <h2 style="margin:0;">Activity Logs</h2>
        <button class="button" onclick="downloadActivityLogs()" style="font-size:13px;padding:8px 16px;">⬇ Download Excel</button>
      </div>
      <div style="display:flex;gap:10px;margin:0 0 20px;">
        <select id="filterUser" class="select" style="width:200px;">
          <option value="">All Users</option>
        </select>
        <select id="filterAction" class="select" style="width:200px;">
          <option value="">All Actions</option>
          <option value="login">Login</option>
          <option value="logout">Logout</option>
          <option value="create_lead">Create Lead</option>
          <option value="update_lead">Update Lead</option>
          <option value="assign_lead">Assign Lead</option>
          <option value="add_note">Add Note</option>
          <option value="create_project">Create Project</option>
        </select>
        <select id="filterModule" class="select" style="width:200px;">
          <option value="">All Modules</option>
          <option value="auth">Auth</option>
          <option value="leads">Leads</option>
          <option value="projects">Projects</option>
          <option value="users">Users</option>
        </select>
      </div>
      <div id="logsContainer"></div>
    </div>
  `
  
  await loadActivityLogs()
  await loadUsers()
  
  const userSelect = document.getElementById('filterUser')
  userSelect.innerHTML = '<option value="">All Users</option>' +
    users.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
  
  document.getElementById('filterUser').addEventListener('change', filterAndRenderLogs)
  document.getElementById('filterAction').addEventListener('change', filterAndRenderLogs)
  document.getElementById('filterModule').addEventListener('change', filterAndRenderLogs)
  
  filterAndRenderLogs()
}

async function downloadActivityLogs() {
  const userFilter   = document.getElementById('filterUser')?.value || ''
  const actionFilter = document.getElementById('filterAction')?.value || ''
  const moduleFilter = document.getElementById('filterModule')?.value || ''
  const params = new URLSearchParams()
  if (userFilter)   params.set('user_id', userFilter)
  if (actionFilter) params.set('action', actionFilter)
  if (moduleFilter) params.set('module', moduleFilter)
  const url = `${API_BASE}/reports/activity-logs/download?${params.toString()}`
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) { alert('Failed to download'); return }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `activity_logs_${new Date().toISOString().slice(0,10)}.xlsx`
  a.click()
  URL.revokeObjectURL(a.href)
}

async function loadActivityLogs() {
  const res = await fetch(`${API_BASE}/reports/activity-logs?limit=500`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  activityLogs = data.activity_logs || []
}

function filterAndRenderLogs() {
  const userFilter = document.getElementById('filterUser')?.value
  const actionFilter = document.getElementById('filterAction')?.value
  const moduleFilter = document.getElementById('filterModule')?.value
  
  let filtered = activityLogs
  if (userFilter) filtered = filtered.filter(l => l.user_id === parseInt(userFilter))
  if (actionFilter) filtered = filtered.filter(l => l.action === actionFilter)
  if (moduleFilter) filtered = filtered.filter(l => l.module === moduleFilter)
  
  filtered = filtered.reverse() // Most recent first
  
  const container = document.getElementById('logsContainer')
  if (filtered.length === 0) {
    container.innerHTML = '<div class="message">No activity logs found</div>'
    return
  }
  
  container.innerHTML = `
    <div style="overflow-x:auto;">
      <table class="table">
        <thead>
          <tr>
            <th>User</th>
            <th>Action</th>
            <th>Module</th>
            <th>Resource ID</th>
            <th>Description</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.slice(0, 100).map(l => `
            <tr>
              <td>${escape(l.user_name || 'Unknown')}</td>
              <td><span class="tag" style="background:#e0f2fe;color:#0369a1;">${escape(l.action)}</span></td>
              <td>${escape(l.module)}</td>
              <td>${l.resource_id || '-'}</td>
              <td>${escape(l.description || '-')}</td>
              <td>${new Date(l.created_at).toLocaleString()}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
}

// ============================================================================
// MY PROFILE
// ============================================================================

async function renderMyProfile() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>My Profile & Password</h2>
      
      <div style="background:#f8fafc;padding:16px;border-radius:10px;margin-bottom:24px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;font-size:14px;">
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Name</span>
            <div style="color:#1e293b;font-weight:500;margin-top:4px;">${escape(user.name)}</div>
          </div>
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Email</span>
            <div style="color:#1e293b;font-weight:500;margin-top:4px;">${escape(user.email)}</div>
          </div>
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Role</span>
            <div style="color:#1e293b;font-weight:500;margin-top:4px;">${getRoleDisplay(user.role)}</div>
          </div>
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Status</span>
            <div style="color:#059669;font-weight:500;margin-top:4px;">✓ Active</div>
          </div>
        </div>
      </div>

      <form id="passwordForm">
        <div style="border-top:1px solid #e2e8f0;padding-top:20px;">
          <h3 style="margin:0 0 16px;font-size:1.05rem;color:#1e293b;font-weight:600;">Change Password</h3>
          
          <div style="margin-bottom:14px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">Current Password *</label>
            <input class="input" id="currentPassword" placeholder="Enter your current password" type="password" required />
          </div>
          
          <div style="margin-bottom:14px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">New Password *</label>
            <input class="input" id="newPassword" placeholder="Enter new password (min. 8 characters)" type="password" required minlength="8" />
            <p style="font-size:12px;color:#94a3b8;margin-top:4px;">Use uppercase, lowercase, numbers, and special characters for security</p>
          </div>
          
          <div style="margin-bottom:20px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">Confirm New Password *</label>
            <input class="input" id="confirmPassword" placeholder="Confirm your new password" type="password" required />
          </div>
          
          <div style="display:flex;gap:10px;">
            <button type="submit" class="button">🔐 Update Password</button>
            <button type="button" class="button secondary" onclick="renderApp(); showContent()">Cancel</button>
          </div>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('passwordForm').addEventListener('submit', async e => {
    e.preventDefault()
    const currentPassword = document.getElementById('currentPassword').value
    const newPassword = document.getElementById('newPassword').value
    const confirmPassword = document.getElementById('confirmPassword').value
    
    if (newPassword !== confirmPassword) {
      alert('New passwords do not match')
      return
    }
    
    if (newPassword.length < 8) {
      alert('New password must be at least 8 characters')
      return
    }
    
    const res = await fetch(`${API_BASE}/auth/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    })
    
    const data = await res.json()
    if (res.ok) {
      alert('Password updated successfully! Please log in again.')
      token = ''
      user = null
      localStorage.removeItem('lms_token')
      render()
    } else {
      alert(data.error || 'Error updating password')
    }
  })
}

// ============================================================================
// API FUNCTIONS
// ============================================================================

async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  const data = await res.json()
  if (!res.ok) {
    const errEl = document.getElementById('loginError')
    if (errEl) errEl.textContent = data.error || 'Login failed'
    else alert(data.error || 'Login failed')
    return
  }
  token = data.token
  window.localStorage.setItem('lms_token', token)
  availableProducts = data.products || []
  // Stay on CRM if available, else first available product
  if (availableProducts.length > 0) {
    const hasCrm = availableProducts.find(p => p.slug === 'crm')
    currentProduct = hasCrm ? 'crm' : (availableProducts[0]?.slug || 'crm')
    localStorage.setItem('current_product', currentProduct)
  }
  await loadMe()
  render()
}

async function loadMe() {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) {
    token = ''
    localStorage.removeItem('lms_token')
    render()
    return
  }
  const data = await res.json()
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
  const res = await fetch(`${API_BASE}/projects`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  projects = data.projects || []
}

async function loadLeads() {
  const res = await fetch(`${API_BASE}/leads`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  leads = data.leads || []
}

async function loadUsers() {
  const res = await fetch(`${API_BASE}/users`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  users = data.users || []
}

// ============================================================================
// EXCEL IMPORT
// ============================================================================

async function renderExcelUpload() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <h2>📤 Bulk Import Leads from Excel</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
        <div>
          <h3>Import File</h3>
          <form id="uploadForm">
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">Select Excel File (.xlsx, .xls, .csv)</label>
              <input type="file" id="excelFile" accept=".xlsx,.xls,.csv" required style="display:block;margin-bottom:10px;padding:10px;border:1px solid #cbd5e1;border-radius:6px;width:100%;box-sizing:border-box;" />
              <small style="color:#64748b;">Maximum file size: 5MB</small>
            </div>
            <button type="submit" class="button" style="width:100%;margin-bottom:10px;">📤 Upload File</button>
            <button type="button" class="button secondary" id="downloadTemplate" style="width:100%;">⬇️ Download Template</button>
          </form>
        </div>
        
        <div>
          <h3>Required Columns</h3>
          <ul style="list-style:none;padding:0;color:#475569;">
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>name</strong>
              <div style="font-size:12px;color:#94a3b8;">Lead name (REQUIRED)</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>phone</strong>
              <div style="font-size:12px;color:#94a3b8;">Contact number</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>email</strong>
              <div style="font-size:12px;color:#94a3b8;">Email address</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>source</strong>
              <div style="font-size:12px;color:#94a3b8;">Lead source (e.g., Website)</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>status</strong>
              <div style="font-size:12px;color:#94a3b8;">new, attempted, connected, interested, site_visit_planned, site_visit_done, negotiation, booking_done, lost, junk</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>assigned_to_email</strong>
              <div style="font-size:12px;color:#94a3b8;">Email of team member</div>
            </li>
          </ul>
        </div>
      </div>
      
      <div id="importResult" style="margin-top:30px;"></div>
    </div>
  `
  
  document.getElementById('uploadForm').addEventListener('submit', handleExcelUpload)
  document.getElementById('downloadTemplate').addEventListener('click', downloadExcelTemplate)
}

async function handleExcelUpload(e) {
  e.preventDefault()
  const fileInput = document.getElementById('excelFile')
  const file = fileInput.files[0]
  
  if (!file) {
    alert('Please select a file')
    return
  }
  
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    const res = await fetch(`${API_BASE}/leads/import/excel`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData
    })
    
    const data = await res.json()
    
    if (!res.ok) {
      showImportResult({
        success: 0,
        failed: 0,
        total: 0,
        errors: [{ row: 1, error: data.error || 'Upload failed' }],
        imported_leads: []
      }, false)
      return
    }
    
    showImportResult(data, res.ok)
    if (res.ok) {
      fileInput.value = ''
      await loadLeads() // Refresh leads
    }
  } catch (err) {
    showImportResult({
      success: 0,
      failed: 0,
      total: 0,
      errors: [{ row: 1, error: err.message }],
      imported_leads: []
    }, false)
  }
}

function showImportResult(data, success) {
  const resultDiv = document.getElementById('importResult')
  
  if (!success) {
    resultDiv.innerHTML = `
      <div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:6px;padding:16px;color:#7f1d1d;">
        <h3 style="margin:0 0 10px 0;">❌ Import Failed</h3>
        <p>${data.errors[0]?.error || 'An error occurred'}</p>
      </div>
    `
    return
  }
  
  const downloadBtn = data.report_b64
    ? `<button onclick="downloadImportReport()" style="margin-top:16px;padding:10px 20px;background:#1e3a5f;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;">📥 Download Import Report (.xlsx)</button>`
    : ''

  // Store b64 for the download handler
  window._importReportB64 = data.report_b64 || null

  let resultHtml = `
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:16px;color:#166534;">
      <h3 style="margin:0 0 10px 0;">✅ Import Complete</h3>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px;">
        <div style="padding:12px;background:#dcfce7;border-radius:4px;">
          <div style="font-size:12px;color:#6b7280;">Successfully Imported</div>
          <div style="font-size:24px;font-weight:bold;color:#16a34a;">${data.success}</div>
        </div>
        <div style="padding:12px;background:#fee2e2;border-radius:4px;">
          <div style="font-size:12px;color:#6b7280;">Failed</div>
          <div style="font-size:24px;font-weight:bold;color:#dc2626;">${data.failed}</div>
        </div>
        <div style="padding:12px;background:#dbeafe;border-radius:4px;">
          <div style="font-size:12px;color:#6b7280;">Total Rows</div>
          <div style="font-size:24px;font-weight:bold;color:#2563eb;">${data.total}</div>
        </div>
      </div>
  `
  
  if (data.errors && data.errors.length > 0) {
    resultHtml += `
      <h4 style="margin:20px 0 10px 0;color:#991b1b;">Errors (${data.errors.length}):</h4>
      <div style="max-height:300px;overflow-y:auto;background:#fff;border:1px solid #fca5a5;border-radius:4px;padding:12px;">
        <ul style="margin:0;padding-left:20px;">
          ${data.errors.map(err => `<li style="margin:5px 0;font-size:13px;"><strong>Row ${err.row}:</strong> ${escape(err.error)}</li>`).join('')}
        </ul>
      </div>
    `
  }

  resultHtml += downloadBtn
  resultHtml += '</div>'
  resultDiv.innerHTML = resultHtml
}

function downloadImportReport() {
  if (!window._importReportB64) return
  const byteChars = atob(window._importReportB64)
  const byteNums = new Array(byteChars.length)
  for (let i = 0; i < byteChars.length; i++) byteNums[i] = byteChars.charCodeAt(i)
  const blob = new Blob([new Uint8Array(byteNums)], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `import_report_${new Date().toISOString().slice(0,10)}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

async function downloadExcelTemplate() {
  try {
    const res = await fetch(`${API_BASE}/leads/import/template`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (!res.ok) {
      alert('Failed to download template')
      return
    }
    
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'lead_import_template.xlsx'
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (err) {
    alert('Error downloading template: ' + err.message)
  }
}

function escape(text) {
  return String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// ============================================================================
// REPORTS
// ============================================================================

async function renderReports(dateFrom = '', dateTo = '') {
  const content = document.getElementById('content')

  // Generate month options
  const monthOptions = Array.from({length:12}, (_,i) =>
    `<option value="${i}">${new Date(2000,i,1).toLocaleString('default',{month:'long'})}</option>`
  ).join('')

  const activeFilter = dateFrom || dateTo
  const fmtD = d => new Date(d).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})
  const filterLabel = !activeFilter      ? 'All Time'
    : dateFrom && dateTo ? `${fmtD(dateFrom)} → ${fmtD(dateTo)}`
    : dateFrom           ? `From ${fmtD(dateFrom)}`
    :                      `Until ${fmtD(dateTo)}`

  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:16px;">
      <div class="card" style="padding:20px 24px;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:18px;">
          <div>
            <h2 style="margin:0;color:#0f172a;font-size:1.6rem;letter-spacing:-0.5px;font-weight:700;">📊 Reports & Analytics</h2>
            <div style="margin-top:4px;display:flex;align-items:center;gap:8px;">
              <span style="font-size:12px;color:#64748b;">Period:</span>
              <span style="font-size:12px;font-weight:600;color:${activeFilter ? '#2563eb' : '#64748b'};background:${activeFilter ? '#eff6ff' : '#f1f5f9'};padding:2px 10px;border-radius:20px;border:1px solid ${activeFilter ? '#bfdbfe' : '#e2e8f0'};">${filterLabel}</span>
            </div>
          </div>
          <button class="button" onclick="downloadLeadReport()" style="font-size:13px;padding:9px 18px;background:#2563eb;border-color:#2563eb;">⬇ Export Excel</button>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;">
          <div style="font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:0.08em;margin-bottom:12px;text-transform:uppercase;">🗓 Filter by Date Range</div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;">
            <div style="display:flex;flex-direction:column;gap:5px;flex:1;min-width:130px;">
              <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.04em;">FROM</label>
              <input type="date" id="reportDateFrom" class="input" style="font-size:13px;padding:8px 10px;" value="${dateFrom}" />
            </div>
            <div style="display:flex;flex-direction:column;gap:5px;flex:1;min-width:130px;">
              <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.04em;">TO</label>
              <input type="date" id="reportDateTo" class="input" style="font-size:13px;padding:8px 10px;" value="${dateTo}" />
            </div>
            <div style="display:flex;flex-direction:column;gap:5px;flex:1;min-width:130px;">
              <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.04em;">QUICK SELECT</label>
              <select id="reportMonth" class="select" style="font-size:13px;padding:8px 10px;">
                <option value="">— Select Month —</option>
                ${monthOptions}
              </select>
            </div>
            <div style="display:flex;gap:8px;align-items:flex-end;padding-bottom:1px;">
              <button id="applyReportFilter" class="button" style="font-size:13px;padding:9px 20px;">Apply</button>
              <button id="clearReportFilter" class="button secondary" style="font-size:13px;padding:9px 14px;">✕ Clear</button>
            </div>
          </div>
        </div>
      </div>
      <div id="reportContainer"><div class="message">Loading analytics…</div></div>
    </div>
  `

  document.getElementById('reportMonth').addEventListener('change', e => {
    const m = e.target.value
    if (m !== '') {
      const yr = new Date().getFullYear()
      document.getElementById('reportDateFrom').value = new Date(yr, parseInt(m), 1).toISOString().split('T')[0]
      document.getElementById('reportDateTo').value   = new Date(yr, parseInt(m)+1, 0).toISOString().split('T')[0]
    }
  })
  document.getElementById('applyReportFilter').addEventListener('click', () => {
    const from = document.getElementById('reportDateFrom').value
    const to   = document.getElementById('reportDateTo').value
    renderReports(from, to)
  })
  document.getElementById('clearReportFilter').addEventListener('click', () => renderReports())

  // Fetch lead report + team report in parallel
  const headers = { Authorization: `Bearer ${token}` }
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo)   params.set('date_to',   dateTo)
  const qs = params.toString() ? '?' + params.toString() : ''
  const [leadsRes, teamRes] = await Promise.all([
    fetch(`${API_BASE}/reports/leads${qs}`, { headers }),
    fetch(`${API_BASE}/reports/team${qs}`,  { headers }),
  ])
  const leadsData = await leadsRes.json()
  const teamData  = await teamRes.json()

  const total       = leadsData.total_leads || 0
  const convRate    = leadsData.conversion_rate || 0
  const byStatus    = leadsData.leads_by_status || {}
  const bySource    = leadsData.leads_by_source || {}
  const byProject   = leadsData.leads_by_project || {}
  const byDate      = leadsData.leads_by_date || {}
  const teamGroups  = teamData.team_groups || []
  const unassignedMembers = teamData.unassigned_members || []

  // ---- helpers ----
  const maxOf  = obj => Math.max(1, ...Object.values(obj))
  const pct    = (v, t) => t ? ((v / t) * 100).toFixed(1) : '0.0'

  function hBar(count, max, color) {
    const w = Math.max(2, Math.round((count / max) * 100))
    return `<div style="flex:1;background:#f1f5f9;border-radius:4px;height:10px;overflow:hidden;">
              <div style="width:${w}%;height:100%;background:${color};border-radius:4px;transition:width .4s;"></div>
            </div>`
  }

  // ---- STATUS breakdown ----
  const statusOrder = ['new','attempted','connected','interested','site_visit_planned','site_visit_done','negotiation','booking_done','lost','junk']
  const statusMax = maxOf(byStatus)
  const statusRows = statusOrder
    .filter(s => byStatus[s] !== undefined)
    .map(s => {
      const c = byStatus[s]
      return `
        <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #f1f5f9;">
          <div class="rpt-bar-lbl-status">
            <span class="tag" style="background:${getStatusColor(s)};color:#fff;font-size:11px;">${s.replace(/_/g,' ')}</span>
          </div>
          ${hBar(c, statusMax, getStatusColor(s))}
          <div style="width:28px;text-align:right;font-weight:700;font-size:13px;color:#0f172a;">${c}</div>
          <div style="width:42px;text-align:right;font-size:12px;color:#94a3b8;">${pct(c,total)}%</div>
        </div>`
    }).join('')

  // ---- SOURCE distribution ----
  const sourceMax = maxOf(bySource)
  const SOURCE_COLORS = ['#6366f1','#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#0ea5e9','#84cc16','#f43f5e']
  const sourceRows = Object.entries(bySource)
    .sort((a,b) => b[1]-a[1])
    .map(([src, c], i) => {
      const col = SOURCE_COLORS[i % SOURCE_COLORS.length]
      return `
        <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #f1f5f9;">
          <div class="rpt-bar-lbl-source">${escape(src)}</div>
          ${hBar(c, sourceMax, col)}
          <div style="width:28px;text-align:right;font-weight:700;font-size:13px;color:#0f172a;">${c}</div>
          <div style="width:42px;text-align:right;font-size:12px;color:#94a3b8;">${pct(c,total)}%</div>
        </div>`
    }).join('')

  // ---- PROJECT distribution ----
  const projectMax = maxOf(byProject)
  const projectRows = Object.entries(byProject)
    .sort((a,b) => b[1]-a[1])
    .map(([proj, c], i) => {
      const col = SOURCE_COLORS[(i+3) % SOURCE_COLORS.length]
      return `
        <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #f1f5f9;">
          <div class="rpt-bar-lbl-project">${escape(proj)}</div>
          ${hBar(c, projectMax, col)}
          <div style="width:28px;text-align:right;font-weight:700;font-size:13px;color:#0f172a;">${c}</div>
          <div style="width:42px;text-align:right;font-size:12px;color:#94a3b8;">${pct(c,total)}%</div>
        </div>`
    }).join('')

  // ---- LEADS TREND (last 30 days) ----
  const sortedDates = Object.keys(byDate).sort()
  const dateMax = maxOf(byDate)
  const trendBars = sortedDates.length === 0
    ? `<div style="color:#94a3b8;font-size:13px;padding:20px 0;">No data for last 30 days</div>`
    : sortedDates.map(d => {
        const c = byDate[d]
        const h = Math.max(4, Math.round((c / dateMax) * 80))
        const label = d.slice(5)  // MM-DD
        return `
          <div style="display:flex;flex-direction:column;align-items:center;gap:3px;flex:1;min-width:0;">
            <div style="font-size:10px;color:#475569;font-weight:600;">${c}</div>
            <div style="width:100%;max-width:28px;height:${h}px;background:#6366f1;border-radius:3px 3px 0 0;" title="${d}: ${c} leads"></div>
            <div style="font-size:9px;color:#94a3b8;writing-mode:vertical-lr;transform:rotate(180deg);height:28px;">${label}</div>
          </div>`
      }).join('')

  // ---- TEAM PERFORMANCE (grouped by manager) ----
  const MANAGER_PALETTE = ['#6366f1','#0ea5e9','#10b981','#f59e0b','#ec4899','#8b5cf6','#14b8a6']

  const TABLE_HEADERS = `<tr>
    <th>Name</th><th>Email</th>
    <th style="text-align:center;">All Leads</th>
    <th style="text-align:center;">Interested</th>
    <th style="text-align:center;">Site Visit Planned</th>
    <th style="text-align:center;">Site Visit Done</th>
    <th style="text-align:center;">Booking Done</th>
    <th style="text-align:center;">Warm Rate</th>
  </tr>`

  function personRow(s, isManager, color) {
    const warmCol = s.warm_rate >= 50 ? '#10b981' : s.warm_rate >= 20 ? '#f59e0b' : '#ef4444'
    const nameCell = isManager
      ? `<td style="font-weight:700;color:${color || '#0f172a'};">⭐ ${escape(s.name)} <span style="font-size:10px;font-weight:600;background:${color}18;color:${color};border-radius:8px;padding:1px 7px;margin-left:6px;">Manager</span></td>`
      : `<td style="font-weight:500;padding-left:24px;">↳ ${escape(s.name)}</td>`
    const rowStyle = isManager ? `style="background:${color}08;border-left:3px solid ${color};"` : ''
    return `
      <tr ${rowStyle}>
        ${nameCell}
        <td style="font-size:11px;color:#64748b;">${escape(s.email || '')}</td>
        <td style="text-align:center;font-weight:700;">${s.total_leads}</td>
        <td style="text-align:center;color:#0891b2;font-weight:600;">${s.interested}</td>
        <td style="text-align:center;color:#7c3aed;font-weight:600;">${s.site_visit_planned}</td>
        <td style="text-align:center;color:#6366f1;font-weight:600;">${s.site_visit_done}</td>
        <td style="text-align:center;color:#10b981;font-weight:700;">${s.booking_done}</td>
        <td style="text-align:center;">
          <span style="background:${warmCol}18;color:${warmCol};border-radius:12px;padding:2px 10px;font-size:12px;font-weight:700;">${s.warm_rate}%</span>
        </td>
      </tr>`
  }

  function managerGroupHTML(group, colorIdx) {
    const mgr = group.manager
    const color = MANAGER_PALETTE[colorIdx % MANAGER_PALETTE.length]
    const allRows      = [mgr, ...group.members]
    const teamTotal    = allRows.reduce((s, p) => s + p.total_leads, 0)
    const teamBooking  = allRows.reduce((s, p) => s + p.booking_done, 0)
    const teamInterest = allRows.reduce((s, p) => s + p.interested, 0)
    const teamSVP      = allRows.reduce((s, p) => s + p.site_visit_planned, 0)
    const teamSVD      = allRows.reduce((s, p) => s + p.site_visit_done, 0)
    const teamWarm     = teamTotal > 0 ? ((teamInterest / teamTotal) * 100).toFixed(1) : '0.0'
    const totalsRow    = `
      <tr style="background:${color}10;border-top:2px solid ${color}30;font-weight:700;">
        <td colspan="2" style="font-weight:700;color:${color};font-size:12px;text-transform:uppercase;letter-spacing:0.05em;">
          ∑ Team Total
        </td>
        <td style="text-align:center;font-weight:800;font-size:14px;">${teamTotal}</td>
        <td style="text-align:center;color:#0891b2;font-weight:800;">${teamInterest}</td>
        <td style="text-align:center;color:#7c3aed;font-weight:800;">${teamSVP}</td>
        <td style="text-align:center;color:#6366f1;font-weight:800;">${teamSVD}</td>
        <td style="text-align:center;color:#10b981;font-weight:800;">${teamBooking}</td>
        <td style="text-align:center;">
          <span style="background:${color}20;color:${color};border-radius:12px;padding:2px 10px;font-size:12px;font-weight:800;">${teamWarm}%</span>
        </td>
      </tr>`
    return `
      <div style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
        <div style="background:${color}12;border-bottom:2px solid ${color}30;padding:12px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          <div style="width:36px;height:36px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:700;flex-shrink:0;">
            ${escape(mgr.name).charAt(0)}
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:14px;font-weight:700;color:#0f172a;">${escape(mgr.name)}</div>
            <div style="font-size:12px;color:#64748b;">${escape(mgr.email)} &nbsp;·&nbsp; ${group.members.length} team member${group.members.length !== 1 ? 's' : ''}</div>
          </div>
          <div style="display:flex;gap:20px;flex-wrap:wrap;">
            <div style="text-align:center;">
              <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">All Leads</div>
              <div style="font-size:18px;font-weight:700;color:${color};">${teamTotal}</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">Booking Done</div>
              <div style="font-size:18px;font-weight:700;color:#10b981;">${teamBooking}</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">Team Warm Rate</div>
              <div style="font-size:18px;font-weight:700;color:#f59e0b;">${teamWarm}%</div>
            </div>
          </div>
        </div>
        <div class="table-scroll">
          <table class="table" style="margin:0;min-width:580px;">
            <thead>${TABLE_HEADERS}</thead>
            <tbody>
              ${personRow(mgr, true, color)}
              ${group.members.map(m => personRow(m, false, color)).join('')}
              ${totalsRow}
            </tbody>
          </table>
        </div>
      </div>`
  }

  const teamGroupsHTML = teamGroups.length === 0
    ? '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No team data available</div>'
    : teamGroups.map((g, i) => managerGroupHTML(g, i)).join('')

  const unassignedHTML = unassignedMembers.length === 0 ? '' : `
    <div style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
      <div style="background:#f8fafc;border-bottom:2px solid #e2e8f0;padding:12px 16px;display:flex;align-items:center;gap:10px;">
        <div style="width:36px;height:36px;border-radius:50%;background:#94a3b8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:16px;flex-shrink:0;">?</div>
        <div>
          <div style="font-size:14px;font-weight:700;color:#475569;">Unassigned Members</div>
          <div style="font-size:12px;color:#94a3b8;">${unassignedMembers.length} member${unassignedMembers.length !== 1 ? 's' : ''} without a sales manager</div>
        </div>
      </div>
      <div class="table-scroll">
        <table class="table" style="margin:0;min-width:580px;">
          <thead>${TABLE_HEADERS}</thead>
          <tbody>${unassignedMembers.map(m => personRow(m, false, '#94a3b8')).join('')}</tbody>
        </table>
      </div>
    </div>`

  // ---- BOOKING stats ----
  const booked        = byStatus['booking_done']       || 0
  const interested    = byStatus['interested']         || 0
  const siteVisitPlan = byStatus['site_visit_planned'] || 0
  const siteVisitDone = byStatus['site_visit_done']    || 0
  const junk          = byStatus['junk']               || 0
  const negotiation   = byStatus['negotiation']        || 0

  const hotRate  = total > 0 ? ((negotiation  / total) * 100).toFixed(1) : '0.0'
  const warmRate = total > 0 ? ((interested   / total) * 100).toFixed(1) : '0.0'

  document.getElementById('reportContainer').innerHTML = `
    <!-- KPI row -->
    <div class="rpt-kpi-grid">
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">All Leads</div>
        <div class="analytics-kpi-value" style="color:#2563eb;">${total}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Interested</div>
        <div class="analytics-kpi-value" style="color:#0891b2;">${interested}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Site Visit Planned</div>
        <div class="analytics-kpi-value" style="color:#7c3aed;">${siteVisitPlan}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Site Visit Done</div>
        <div class="analytics-kpi-value" style="color:#6366f1;">${siteVisitDone}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Booking Done</div>
        <div class="analytics-kpi-value" style="color:#10b981;">${booked}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Junk</div>
        <div class="analytics-kpi-value" style="color:#94a3b8;">${junk}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Hot Rate</div>
        <div class="analytics-kpi-value" style="color:#ef4444;">${hotRate}%</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">Negotiation / Total</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Warm Rate</div>
        <div class="analytics-kpi-value" style="color:#f59e0b;">${warmRate}%</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">Interested / Total</div>
      </div>
    </div>

    <!-- Status + Source charts side by side -->
    <div class="rpt-two-col">
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads by Status</h3>
        ${statusRows || '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No data</div>'}
      </div>
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads by Source</h3>
        ${sourceRows || '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No data</div>'}
      </div>
    </div>

    <!-- Project + Trend side by side -->
    <div class="rpt-two-col">
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads by Project</h3>
        ${Object.keys(byProject).length
          ? projectRows
          : '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No data</div>'}
      </div>
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads Trend – Last 30 Days</h3>
        <div style="display:flex;align-items:flex-end;gap:3px;height:120px;padding-top:10px;">
          ${trendBars}
        </div>
      </div>
    </div>

    <!-- Team performance -->
    <div class="card" style="margin:0;">
      <h3 class="analytics-section-title">Team Performance</h3>
      <div style="margin-top:14px;">
        ${teamGroupsHTML}
        ${unassignedHTML}
      </div>
    </div>
  `
}

async function downloadLeadReport() {
  const a = document.createElement('a')
  a.href = `${API_BASE}/reports/leads/download`
  a.setAttribute('download', '')
  // Add auth via query param not ideal; use fetch + blob instead
  const res = await fetch(`${API_BASE}/reports/leads/download`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) { alert('Export failed'); return }
  const blob = await res.blob()
  const url  = URL.createObjectURL(blob)
  a.href = url
  a.download = 'leads_report.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

// ============================================================================
// EXPORT LEADS
// ============================================================================

async function renderExportLeads() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <h2>📥 Export Leads to Excel</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
        <div>
          <h3>Export Options</h3>
          <form id="exportForm">
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">Filter by Status (optional)</label>
              <select id="exportStatus" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;">
                <option value="">All Status</option>
                <option value="new">New</option>
                <option value="attempted">Attempted</option>
                <option value="connected">Connected</option>
                <option value="interested">Interested</option>
                <option value="site_visit_planned">Site Visit Planned</option>
                <option value="site_visit_done">Site Visit Done</option>
                <option value="negotiation">Negotiation</option>
                <option value="booking_done">Booking Done</option>
                <option value="lost">Lost</option>
                <option value="junk">Junk</option>
              </select>
            </div>
            
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">Filter by Project (optional)</label>
              <select id="exportProject" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;">
                <option value="">All Projects</option>
                ${projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')}
              </select>
            </div>
            
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">From Date (optional)</label>
              <input type="date" id="exportDateFrom" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;" />
            </div>
            
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">To Date (optional)</label>
              <input type="date" id="exportDateTo" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;" />
            </div>
            
            <button type="submit" class="button" style="width:100%;">📥 Export to Excel</button>
          </form>
        </div>
        
        <div>
          <h3>Export Information</h3>
          <ul style="list-style:none;padding:0;color:#475569;">
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Format:</strong>
              <div style="font-size:12px;color:#94a3b8;">Microsoft Excel (.xlsx)</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Included Columns:</strong>
              <div style="font-size:12px;color:#94a3b8;">ID, Name, Phone, Email, Source, Status, Project, Assigned To, Budget Min/Max, Created Date, Created By</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Summary Sheet:</strong>
              <div style="font-size:12px;color:#94a3b8;">Automatic status breakdown included</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Filtering:</strong>
              <div style="font-size:12px;color:#94a3b8;">Role-based (you only see your visible leads)</div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  `
  
  await loadProjects()
  
  document.getElementById('exportForm').addEventListener('submit', handleExportLeads)
}

async function handleExportLeads(e) {
  e.preventDefault()
  
  const status = document.getElementById('exportStatus')?.value
  const projectId = document.getElementById('exportProject')?.value
  const dateFrom = document.getElementById('exportDateFrom')?.value
  const dateTo = document.getElementById('exportDateTo')?.value
  
  let query = '/leads/export/excel?'
  const params = []
  
  if (status) params.push(`status=${status}`)
  if (projectId) params.push(`project_id=${projectId}`)
  if (dateFrom) params.push(`date_from=${dateFrom}`)
  if (dateTo) params.push(`date_to=${dateTo}`)
  
  query += params.join('&')
  
  try {
    const res = await fetch(`${API_BASE}${query}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (!res.ok) {
      alert('Export failed: ' + (await res.text()))
      return
    }
    
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `leads_export_${new Date().getTime()}.xlsx`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    alert('Export successful!')
  } catch (err) {
    alert('Error exporting: ' + err.message)
  }
}

function escape(text) {
  return String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// ============================================================================
// PLATFORM ADMIN (platform_owner only)
// ============================================================================

let platformTab = 'tenants'

async function renderPlatformAdmin() {
  const content = document.getElementById('content')
  content.innerHTML = `<div style="padding:24px;"><h2>🌐 Platform Admin</h2><p style="color:#64748b;">Loading…</p></div>`

  if (platformTab === 'tenants') return renderPlatformTenants()
  if (platformTab === 'products') return renderPlatformProducts()
}

function platformTabBar() {
  return `
    <div style="display:flex;gap:4px;margin-bottom:24px;border-bottom:2px solid #e2e8f0;padding-bottom:0;">
      ${[['tenants','🏢 Tenants'],['products','📦 Products']].map(([k,l]) => `
        <button onclick="platformTab='${k}';renderPlatformAdmin()" style="
          padding:10px 20px;border:none;background:none;cursor:pointer;font-size:14px;
          color:${platformTab===k?'#1e3a5f':'#64748b'};font-weight:${platformTab===k?'700':'400'};
          border-bottom:${platformTab===k?'3px solid #1e3a5f':'3px solid transparent'};
          margin-bottom:-2px;">${l}</button>
      `).join('')}
    </div>
  `
}

async function renderPlatformTenants() {
  const content = document.getElementById('content')
  content.innerHTML = `<div style="padding:24px;"><h2>🌐 Platform Admin</h2><p style="color:#64748b;">Loading…</p></div>`

  const res = await fetch(`${API_BASE}/platform/analytics`, {
    headers: { 'Authorization': `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    content.innerHTML = `<div style="padding:24px;"><p style="color:#dc2626;">Failed to load: ${err.error || res.status}</p></div>`
    return
  }
  const data = await res.json()
  const { stats, tenants } = data

  content.innerHTML = `
  <div style="padding:24px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
      <h2 style="margin:0;">🌐 SocioMonkey Platform Admin</h2>
      <button class="button" onclick="showCreateTenantModal()">+ New Tenant</button>
    </div>
    ${platformTabBar()}

    <!-- Stats row -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px;">
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#1e3a5f;">${stats.total_tenants}</div>
        <div style="color:#64748b;font-size:13px;">Total Tenants</div>
      </div>
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#16a34a;">${stats.active_tenants}</div>
        <div style="color:#64748b;font-size:13px;">Active Tenants</div>
      </div>
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#3b82f6;">${stats.total_users}</div>
        <div style="color:#64748b;font-size:13px;">Total Users</div>
      </div>
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#8b5cf6;">${stats.total_leads}</div>
        <div style="color:#64748b;font-size:13px;">Total Leads</div>
      </div>
    </div>

    <!-- Tenants table -->
    <div class="card" style="overflow:auto;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#f1f5f9;">
            <th style="padding:10px 12px;text-align:left;">Tenant</th>
            <th style="padding:10px 12px;text-align:left;">Slug</th>
            <th style="padding:10px 12px;text-align:left;">Plan</th>
            <th style="padding:10px 12px;text-align:center;">Users</th>
            <th style="padding:10px 12px;text-align:center;">Leads</th>
            <th style="padding:10px 12px;text-align:center;">Status</th>
            <th style="padding:10px 12px;text-align:center;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${tenants.map(t => `
            <tr style="border-top:1px solid #e2e8f0;">
              <td style="padding:10px 12px;font-weight:600;">${escape(t.name)}</td>
              <td style="padding:10px 12px;font-family:monospace;color:#64748b;">${escape(t.slug)}</td>
              <td style="padding:10px 12px;">${escape(t.plan)}</td>
              <td style="padding:10px 12px;text-align:center;">${t.user_count}</td>
              <td style="padding:10px 12px;text-align:center;">${t.lead_count}</td>
              <td style="padding:10px 12px;text-align:center;">
                <span style="padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;
                  background:${t.status === 'active' ? '#dcfce7' : '#fee2e2'};
                  color:${t.status === 'active' ? '#16a34a' : '#dc2626'};">
                  ${t.status}
                </span>
              </td>
              <td style="padding:10px 12px;text-align:center;white-space:nowrap;">
                <button class="button" style="font-size:12px;padding:4px 10px;"
                  onclick="toggleTenantStatus(${t.id},'${t.status === 'active' ? 'inactive' : 'active'}','${escape(t.name)}')">
                  ${t.status === 'active' ? 'Deactivate' : 'Activate'}
                </button>
                <button class="button" style="font-size:12px;padding:4px 10px;background:#f1f5f9;color:#1e293b;margin-left:4px;"
                  onclick="showTenantProductsModal(${t.id},'${escape(t.name)}')">
                  📦 Products
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>

    <!-- Create tenant modal -->
    <div id="createTenantModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center;">
      <div class="card" style="max-width:480px;width:100%;max-height:90vh;overflow-y:auto;">
        <h3>New Tenant</h3>
        <input class="input" id="ctName" placeholder="Tenant name *" />
        <input class="input" id="ctSlug" placeholder="Slug (e.g. acme) *" />
        <input class="input" id="ctAdminEmail" placeholder="Admin email *" />
        <input class="input" id="ctAdminName" placeholder="Admin name" />
        <input class="input" id="ctAdminPassword" placeholder="Admin password (default: Admin@123)" />
        <select class="input" id="ctPlan" style="margin-bottom:8px;">
          <option value="starter">Starter</option>
          <option value="growth">Growth</option>
          <option value="enterprise" selected>Enterprise</option>
        </select>
        <input class="input" id="ctMaxUsers" type="number" value="20" placeholder="Max users" />
        <div id="ctError" style="color:#dc2626;font-size:13px;margin-bottom:8px;"></div>
        <div style="display:flex;gap:8px;">
          <button class="button" onclick="submitCreateTenant()" style="flex:1;">Create</button>
          <button class="button" style="flex:1;background:#e2e8f0;color:#1e293b;" onclick="document.getElementById('createTenantModal').style.display='none'">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Tenant products modal -->
    <div id="tenantProductsModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center;">
      <div class="card" style="max-width:540px;width:100%;max-height:90vh;overflow-y:auto;">
        <h3 id="tpmTitle">Products</h3>
        <div id="tpmBody"><p style="color:#64748b;">Loading…</p></div>
        <div style="text-align:right;margin-top:12px;">
          <button class="button" style="background:#e2e8f0;color:#1e293b;" onclick="document.getElementById('tenantProductsModal').style.display='none'">Close</button>
        </div>
      </div>
    </div>
  </div>`
}

async function showTenantProductsModal(tenantId, tenantName) {
  const modal = document.getElementById('tenantProductsModal')
  document.getElementById('tpmTitle').textContent = `📦 Products — ${tenantName}`
  document.getElementById('tpmBody').innerHTML = '<p style="color:#64748b;">Loading…</p>'
  modal.style.display = 'flex'

  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/products`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  if (!res.ok) {
    document.getElementById('tpmBody').innerHTML = '<p style="color:#dc2626;">Failed to load</p>'
    return
  }
  const data = await res.json()
  const subscribed = new Set((data.subscriptions || []).map(s => s.product_id))

  document.getElementById('tpmBody').innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <thead><tr style="background:#f1f5f9;">
        <th style="padding:8px 10px;text-align:left;">Product</th>
        <th style="padding:8px 10px;text-align:center;">Status</th>
        <th style="padding:8px 10px;text-align:center;">Action</th>
      </tr></thead>
      <tbody>
        ${(data.available_products || []).map(p => `
          <tr style="border-top:1px solid #e2e8f0;">
            <td style="padding:8px 10px;">${p.icon || '📦'} <strong>${escape(p.name)}</strong></td>
            <td style="padding:8px 10px;text-align:center;">
              ${subscribed.has(p.id)
                ? `<span style="padding:2px 10px;border-radius:12px;font-size:11px;background:#dcfce7;color:#16a34a;font-weight:600;">Active</span>`
                : `<span style="padding:2px 10px;border-radius:12px;font-size:11px;background:#f1f5f9;color:#94a3b8;">Not subscribed</span>`}
            </td>
            <td style="padding:8px 10px;text-align:center;">
              ${subscribed.has(p.id)
                ? `<button class="button" style="font-size:11px;padding:3px 10px;background:#fee2e2;color:#dc2626;"
                    onclick="tenantUnsubscribeProduct(${tenantId},${p.id})">Revoke</button>`
                : `<button class="button" style="font-size:11px;padding:3px 10px;"
                    onclick="tenantSubscribeProduct(${tenantId},${p.id},'${escape(tenantName)}')">Enable</button>`}
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `
}

async function tenantSubscribeProduct(tenantId, productId, tenantName) {
  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ product_id: productId, status: 'active' }),
  })
  if (res.ok) showTenantProductsModal(tenantId, tenantName)
}

async function tenantUnsubscribeProduct(tenantId, productId) {
  const modal = document.getElementById('tenantProductsModal')
  const title = document.getElementById('tpmTitle').textContent.replace('📦 Products — ', '')
  if (!confirm('Remove this product subscription?')) return
  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/products/${productId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` },
  })
  if (res.ok) showTenantProductsModal(tenantId, title)
}

async function renderPlatformProducts() {
  const content = document.getElementById('content')
  content.innerHTML = `<div style="padding:24px;"><h2>🌐 Platform Admin</h2><p style="color:#64748b;">Loading…</p></div>`

  const res = await fetch(`${API_BASE}/platform/products`, {
    headers: { 'Authorization': `Bearer ${token}` },
  })
  if (!res.ok) {
    content.innerHTML = `<div style="padding:24px;"><p style="color:#dc2626;">Failed to load products</p></div>`
    return
  }
  const data = await res.json()
  const products = data.products || []

  content.innerHTML = `
  <div style="padding:24px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
      <h2 style="margin:0;">🌐 SocioMonkey Platform Admin</h2>
    </div>
    ${platformTabBar()}

    <div class="card" style="overflow:auto;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#f1f5f9;">
            <th style="padding:10px 12px;text-align:left;">Product</th>
            <th style="padding:10px 12px;text-align:left;">Slug</th>
            <th style="padding:10px 12px;text-align:left;">Category</th>
            <th style="padding:10px 12px;text-align:center;">Tenants</th>
            <th style="padding:10px 12px;text-align:center;">Version</th>
            <th style="padding:10px 12px;text-align:center;">Status</th>
            <th style="padding:10px 12px;text-align:center;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${products.map(p => `
            <tr style="border-top:1px solid #e2e8f0;">
              <td style="padding:10px 12px;">
                <span style="font-size:20px;margin-right:8px;">${p.icon || '📦'}</span>
                <strong>${escape(p.name)}</strong>
              </td>
              <td style="padding:10px 12px;font-family:monospace;color:#64748b;">${escape(p.slug)}</td>
              <td style="padding:10px 12px;color:#64748b;">${escape(p.category || '')}</td>
              <td style="padding:10px 12px;text-align:center;">${p.tenant_count ?? '—'}</td>
              <td style="padding:10px 12px;text-align:center;font-family:monospace;font-size:12px;">${escape(p.version || '')}</td>
              <td style="padding:10px 12px;text-align:center;">
                <span style="padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;
                  background:${p.is_active ? '#dcfce7' : '#f1f5f9'};
                  color:${p.is_active ? '#16a34a' : '#94a3b8'};">
                  ${p.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td style="padding:10px 12px;text-align:center;">
                <button class="button" style="font-size:12px;padding:4px 10px;"
                  onclick="toggleProductStatus(${p.id},${!p.is_active},'${escape(p.name)}')">
                  ${p.is_active ? 'Deactivate' : 'Activate'}
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  </div>`
}

async function toggleProductStatus(productId, newActive, name) {
  if (!confirm(`${newActive ? 'Activate' : 'Deactivate'} "${name}"?`)) return
  const res = await fetch(`${API_BASE}/platform/products/${productId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ is_active: newActive }),
  })
  if (res.ok) renderPlatformProducts()
}

function showCreateTenantModal() {
  const modal = document.getElementById('createTenantModal')
  if (modal) { modal.style.display = 'flex' }
}

async function submitCreateTenant() {
  const name = document.getElementById('ctName').value.trim()
  const slug = document.getElementById('ctSlug').value.trim()
  const adminEmail = document.getElementById('ctAdminEmail').value.trim()
  const adminName = document.getElementById('ctAdminName').value.trim()
  const adminPassword = document.getElementById('ctAdminPassword').value.trim()
  const plan = document.getElementById('ctPlan').value
  const maxUsers = parseInt(document.getElementById('ctMaxUsers').value) || 20
  const errEl = document.getElementById('ctError')
  errEl.textContent = ''
  if (!name || !slug) { errEl.textContent = 'Name and slug are required'; return }
  try {
    const res = await fetch(`${API_BASE}/platform/tenants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ name, slug, admin_email: adminEmail, admin_name: adminName,
        admin_password: adminPassword || 'Admin@123', plan, max_users: maxUsers }),
    })
    const data = await res.json()
    if (!res.ok) { errEl.textContent = data.error || 'Failed to create tenant'; return }
    document.getElementById('createTenantModal').style.display = 'none'
    renderPlatformAdmin()
  } catch(e) { errEl.textContent = 'Network error' }
}

async function toggleTenantStatus(tenantId, newStatus, name) {
  if (!confirm(`Set "${name}" to ${newStatus}?`)) return
  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ status: newStatus }),
  })
  if (res.ok) renderPlatformAdmin()
}

// ============================================================================
// INITIALIZATION
// ============================================================================

async function init() {
  if (token) {
    await loadMe()
  }
  render()
}

init()
