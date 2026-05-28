// ============================================================================
// PLATFORM ORGANIZATIONS � Rich tenant management view
//
// Entry point: renderPlatformOrgs()  (called by renderPlatformView in platform-layout.js)
//
// Features:
//   - Card grid with status/plan badges, product pills, user + lead stats
//   - Search + status filter tabs
//   - Actions: Configure, Manage Users, Impersonate, Suspend/Activate, Open App
//   - "+ New Organization" -> openOrgWizard() from org-wizard.js
// ============================================================================

var _platOrgsData = { tenants: [], products: [] }
var _platOrgFilter = { query: '', status: 'all' }

// -- Main Render ---------------------------------------------------------------

async function renderPlatformOrgs() {
  var el = document.getElementById('platContent')
  if (!el) return

  el.innerHTML = '<div style="text-align:center;padding:80px;color:#94a3b8;"><div style="font-size:32px;margin-bottom:12px;">Loading...</div>Loading organizations...</div>'

  try {
    var [tRes, pRes] = await Promise.all([
      fetch(API_BASE + '/platform/tenants',  { headers: { Authorization: 'Bearer ' + token } }),
      fetch(API_BASE + '/platform/products', { headers: { Authorization: 'Bearer ' + token } }),
    ])
    if (tRes.ok) { var td = await tRes.json(); _platOrgsData.tenants  = td.tenants  || [] }
    if (pRes.ok) { var pd = await pRes.json(); _platOrgsData.products = pd.products || [] }
  } catch (e) {}

  _platRenderOrgView()
}

function _platRenderOrgView() {
  var el = document.getElementById('platContent')
  if (!el) return

  var tenants = _platOrgsData.tenants || []
  var filtered = _platApplyFilter(tenants, _platOrgFilter.query, _platOrgFilter.status)

  // Status tab counts
  var counts = { all: tenants.length, active: 0, inactive: 0, suspended: 0 }
  tenants.forEach(function(t) {
    var s = (t.status || 'active').toLowerCase()
    if (s === 'active')    counts.active++
    else if (s === 'inactive') counts.inactive++
    else if (s === 'suspended') counts.suspended++
  })

  el.innerHTML =
    // Header row
    '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;flex-wrap:wrap;gap:12px;">' +
      '<div>' +
        '<h2 style="margin:0 0 4px;font-size:22px;color:#0f172a;">Organizations</h2>' +
        '<p style="margin:0;font-size:13px;color:#64748b;">' + tenants.length + ' organization' + (tenants.length !== 1 ? 's' : '') + ' on platform</p>' +
      '</div>' +
      '<button class="plat-btn plat-btn-primary" onclick="openOrgWizard()" style="white-space:nowrap;">' +
        '+ New Organization' +
      '</button>' +
    '</div>' +

    // Search + filter bar
    '<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center;">' +
      '<div style="position:relative;flex:1;min-width:200px;">' +
        '<input id="orgSearchInput" type="text" value="' + _platEscAttr(_platOrgFilter.query) + '"' +
          ' placeholder="Search organizations..."' +
          ' oninput="_platOrgFilter.query=this.value;_platRenderOrgCards()"' +
          ' style="width:100%;padding:9px 12px 9px 36px;border:1px solid #e2e8f0;border-radius:10px;font-size:14px;outline:none;background:#fff;box-sizing:border-box;">' +
        '<span style="position:absolute;left:11px;top:50%;transform:translateY(-50%);color:#94a3b8;font-size:15px;">&#x1F50D;</span>' +
      '</div>' +
      _platStatusTabs(counts) +
    '</div>' +

    // Cards area
    '<div id="orgCardsArea">' + _platOrgCardsHtml(filtered) + '</div>' +

    // Modals container
    '<div id="platOrgModals"></div>'
}

function _platStatusTabs(counts) {
  var tabs = [
    { key: 'all',       label: 'All',       count: counts.all },
    { key: 'active',    label: 'Active',    count: counts.active },
    { key: 'inactive',  label: 'Inactive',  count: counts.inactive },
    { key: 'suspended', label: 'Suspended', count: counts.suspended },
  ]
  return '<div style="display:flex;gap:4px;background:#f1f5f9;border-radius:10px;padding:3px;">' +
    tabs.map(function(t) {
      var active = _platOrgFilter.status === t.key
      return '<button onclick="_platSetStatusFilter(\'' + t.key + '\')" style="' +
        'padding:6px 14px;border:none;border-radius:8px;font-size:13px;cursor:pointer;font-weight:' + (active ? '700' : '500') + ';' +
        'background:' + (active ? '#fff' : 'transparent') + ';' +
        'color:' + (active ? '#0f172a' : '#64748b') + ';' +
        'box-shadow:' + (active ? '0 1px 4px rgba(0,0,0,.1)' : 'none') + ';' +
        'transition:all .15s;">' +
        t.label + ' <span style="font-size:11px;font-weight:500;opacity:.7;">(' + t.count + ')</span>' +
      '</button>'
    }).join('') +
  '</div>'
}

function _platSetStatusFilter(status) {
  _platOrgFilter.status = status
  _platRenderOrgView()
}

function _platRenderOrgCards() {
  var tenants  = _platOrgsData.tenants || []
  var filtered = _platApplyFilter(tenants, _platOrgFilter.query, _platOrgFilter.status)
  var el = document.getElementById('orgCardsArea')
  if (el) el.innerHTML = _platOrgCardsHtml(filtered)
}

function _platApplyFilter(tenants, query, status) {
  return tenants.filter(function(t) {
    var matchQ = !query || (t.name || '').toLowerCase().indexOf(query.toLowerCase()) !== -1 ||
                           (t.slug || '').toLowerCase().indexOf(query.toLowerCase()) !== -1 ||
                           (t.industry || '').toLowerCase().indexOf(query.toLowerCase()) !== -1
    var matchS = status === 'all' || (t.status || 'active').toLowerCase() === status
    return matchQ && matchS
  })
}

// -- Org Cards ----------------------------------------------------------------

function _platOrgCardsHtml(tenants) {
  if (!tenants.length) {
    return '<div style="text-align:center;padding:80px;color:#94a3b8;">' +
      '<div style="font-size:40px;margin-bottom:12px;">&#x1F3E2;</div>' +
      '<p style="font-size:15px;margin:0;">No organizations found</p>' +
      '<p style="font-size:13px;margin:6px 0 20px;">Try a different search or filter</p>' +
      '<button class="plat-btn plat-btn-primary" onclick="openOrgWizard()">+ Create Organization</button>' +
    '</div>'
  }
  return '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px;">' +
    tenants.map(_platOrgCardHtml).join('') +
  '</div>'
}

function _platOrgCardHtml(t) {
  var name    = t.name || t.slug || 'Unnamed'
  var initial = name[0].toUpperCase()
  var status  = (t.status || 'active').toLowerCase()
  var plan    = (t.plan || 'starter').toLowerCase()

  var avatarBg = status === 'active'    ? 'linear-gradient(135deg,#3b82f6,#6366f1)' :
                 status === 'suspended' ? 'linear-gradient(135deg,#f59e0b,#ef4444)' :
                                         'linear-gradient(135deg,#94a3b8,#64748b)'

  var statusCfg = {
    active:    { color: '#166534', bg: '#dcfce7', label: 'Active' },
    inactive:  { color: '#374151', bg: '#f3f4f6', label: 'Inactive' },
    suspended: { color: '#9a3412', bg: '#fef2f2', label: 'Suspended' },
    trial:     { color: '#854d0e', bg: '#fef9c3', label: 'Trial' },
    expired:   { color: '#6b7280', bg: '#f3f4f6', label: 'Expired' },
    archived:  { color: '#6b7280', bg: '#f3f4f6', label: 'Archived' },
  }
  var sc = statusCfg[status] || statusCfg.active

  var planCfg = {
    starter:      { color: '#334155', bg: '#e2e8f0' },
    professional: { color: '#1e40af', bg: '#dbeafe' },
    enterprise:   { color: '#6b21a8', bg: '#f3e8ff' },
  }
  var pc = planCfg[plan] || planCfg.starter

  var products = t.subscribed_products || []
  var productPills = products.length
    ? products.map(function(s) {
        return '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;background:#e0f2fe;color:#0369a1;text-transform:uppercase;">' +
               _platEsc(s) + '</span>'
      }).join('')
    : '<span style="font-size:11px;color:#94a3b8;">No products</span>'

  var userCount = t.user_count != null ? t.user_count : '-'
  var leadCount = t.lead_count != null ? t.lead_count : '-'
  var primaryColor = t.primary_color || '#1e3a5f'
  var isActive  = status === 'active'
  var canImpersonate = status === 'active' || status === 'trial'

  return '<div style="background:#fff;border-radius:16px;border:1px solid #e2e8f0;padding:20px;' +
         'transition:box-shadow .2s;box-shadow:0 1px 4px rgba(0,0,0,.04);" ' +
         'onmouseover="this.style.boxShadow=\'0 4px 20px rgba(0,0,0,.08)\'" ' +
         'onmouseout="this.style.boxShadow=\'0 1px 4px rgba(0,0,0,.04)\'">' +

    '<div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:14px;">' +
      '<div style="width:46px;height:46px;border-radius:14px;background:' + avatarBg + ';' +
           'display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:18px;flex-shrink:0;">' +
        initial +
      '</div>' +
      '<div style="flex:1;min-width:0;">' +
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' +
          '<span style="font-weight:700;font-size:15px;color:#0f172a;">' + _platEsc(name) + '</span>' +
          '<span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;background:' + sc.bg + ';color:' + sc.color + ';">' + sc.label + '</span>' +
          '<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;background:' + pc.bg + ';color:' + pc.color + ';">' + plan.charAt(0).toUpperCase() + plan.slice(1) + '</span>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:8px;margin-top:3px;">' +
          '<span style="font-size:12px;color:#94a3b8;font-family:monospace;">/' + _platEsc(t.slug || '') + '</span>' +
          (t.industry ? '<span style="font-size:11px;color:#64748b;background:#f8fafc;padding:1px 7px;border-radius:8px;">' + _platEsc(t.industry) + '</span>' : '') +
          '<div style="width:14px;height:14px;border-radius:50%;background:' + primaryColor + ';border:1px solid rgba(0,0,0,.1);flex-shrink:0;" title="Brand color"></div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    '<div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px;min-height:20px;">' + productPills + '</div>' +

    '<div style="display:flex;gap:16px;padding:10px 14px;background:#f8fafc;border-radius:10px;margin-bottom:14px;">' +
      '<div style="text-align:center;flex:1;">' +
        '<div style="font-size:18px;font-weight:700;color:#0f172a;">' + userCount + '</div>' +
        '<div style="font-size:11px;color:#64748b;margin-top:1px;">Users</div>' +
      '</div>' +
      '<div style="width:1px;background:#e2e8f0;"></div>' +
      '<div style="text-align:center;flex:1;">' +
        '<div style="font-size:18px;font-weight:700;color:#0f172a;">' + leadCount + '</div>' +
        '<div style="font-size:11px;color:#64748b;margin-top:1px;">Leads</div>' +
      '</div>' +
      '<div style="width:1px;background:#e2e8f0;"></div>' +
      '<div style="text-align:center;flex:1;">' +
        '<div style="font-size:18px;font-weight:700;color:#0f172a;">' + (t.max_users || 20) + '</div>' +
        '<div style="font-size:11px;color:#64748b;margin-top:1px;">Limit</div>' +
      '</div>' +
    '</div>' +

    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;">' +
      '<button onclick="renderTenantConfigPage(' + t.id + ')" class="plat-btn plat-btn-outline plat-btn-sm" style="width:100%;justify-content:center;">Configure</button>' +
      '<button onclick="platViewOrgUsers(' + t.id + ',\'' + _platEscAttr(name) + '\')" class="plat-btn plat-btn-outline plat-btn-sm" style="width:100%;justify-content:center;">Users</button>' +
      (canImpersonate
        ? '<button onclick="platImpersonateOrg(' + t.id + ',\'' + _platEscAttr(name) + '\',\'' + _platEscAttr(t.slug) + '\')" class="plat-btn plat-btn-outline plat-btn-sm" style="width:100%;justify-content:center;color:#7c3aed;">Impersonate</button>'
        : '<button disabled class="plat-btn plat-btn-outline plat-btn-sm" style="width:100%;justify-content:center;opacity:.4;cursor:not-allowed;">Impersonate</button>'
      ) +
      '<button onclick="platSuspendOrg(' + t.id + ',\'' + status + '\',\'' + _platEscAttr(name) + '\')" class="plat-btn plat-btn-outline plat-btn-sm" style="width:100%;justify-content:center;color:' + (isActive ? '#dc2626' : '#16a34a') + ';">' +
        (isActive ? 'Suspend' : 'Activate') +
      '</button>' +
    '</div>' +

    '<div style="margin-top:10px;text-align:center;">' +
      '<button onclick="platOpenOrgApp(' + t.id + ',\'' + _platEscAttr(t.slug) + '\')" style="border:none;background:none;color:#3b82f6;font-size:12px;cursor:pointer;font-weight:600;">Open App &#x2192;</button>' +
    '</div>' +
  '</div>'
}

// -- Actions ------------------------------------------------------------------

async function platOpenOrgApp(tenantId, slug) {
  try {
    var res = await fetch(API_BASE + '/platform/tenants/' + tenantId + '/impersonate', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + token },
    })
    var data = await res.json()
    if (!res.ok) { showToast(data.error || 'Could not open app.', 'error'); return }
    var appUrl = '/' + slug + '/lms?imp=' + encodeURIComponent(data.token) +
                 '&user=' + encodeURIComponent(JSON.stringify(data.user))
    window.open(appUrl, '_blank')
  } catch (e) {
    showToast('Network error. Could not open app.', 'warning')
  }
}

async function platViewOrgUsers(tenantId, tenantName) {
  _platShowModal(
    'Users &mdash; ' + _platEsc(tenantName),
    '<div style="text-align:center;padding:40px;color:#94a3b8;">Loading users...</div>'
  )

  try {
    var res = await fetch(API_BASE + '/platform/tenants/' + tenantId,
      { headers: { Authorization: 'Bearer ' + token } })
    if (!res.ok) throw new Error()
    var data = await res.json()
    var users = data.users || []

    var tableHtml = users.length
      ? '<table style="width:100%;border-collapse:collapse;font-size:13px;">' +
          '<thead><tr>' +
            '<th style="text-align:left;padding:8px 10px;font-size:11px;font-weight:600;color:#64748b;border-bottom:1px solid #e2e8f0;text-transform:uppercase;">Name</th>' +
            '<th style="text-align:left;padding:8px 10px;font-size:11px;font-weight:600;color:#64748b;border-bottom:1px solid #e2e8f0;text-transform:uppercase;">Email</th>' +
            '<th style="text-align:left;padding:8px 10px;font-size:11px;font-weight:600;color:#64748b;border-bottom:1px solid #e2e8f0;text-transform:uppercase;">Role</th>' +
            '<th style="text-align:left;padding:8px 10px;font-size:11px;font-weight:600;color:#64748b;border-bottom:1px solid #e2e8f0;text-transform:uppercase;">Status</th>' +
          '</tr></thead>' +
          '<tbody>' +
          users.map(function(u, i) {
            var active = u.is_active
            var bg = i % 2 === 0 ? '#fff' : '#f8fafc'
            return '<tr style="background:' + bg + ';">' +
              '<td style="padding:9px 10px;color:#0f172a;font-weight:600;">' + _platEsc(u.name || '-') + '</td>' +
              '<td style="padding:9px 10px;color:#475569;">' + _platEsc(u.email || '-') + '</td>' +
              '<td style="padding:9px 10px;">' +
                '<span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;' +
                  'background:' + (u.role === 'superadmin' ? '#f3e8ff' : '#e0f2fe') + ';' +
                  'color:' + (u.role === 'superadmin' ? '#6b21a8' : '#0369a1') + ';">' +
                  _platEsc(u.role || 'user') +
                '</span>' +
              '</td>' +
              '<td style="padding:9px 10px;">' +
                '<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;' +
                  'background:' + (active ? '#dcfce7' : '#fef2f2') + ';' +
                  'color:' + (active ? '#166534' : '#dc2626') + ';">' +
                  (active ? 'Active' : 'Inactive') +
                '</span>' +
              '</td>' +
            '</tr>'
          }).join('') +
          '</tbody></table>'
      : '<div style="text-align:center;padding:40px;color:#94a3b8;">No users in this organization.</div>'

    _platUpdateModal(tableHtml)
  } catch (e) {
    _platUpdateModal('<div style="color:#dc2626;text-align:center;padding:30px;">Failed to load users.</div>')
  }
}

async function platImpersonateOrg(tenantId, tenantName, slug) {
  if (!await confirmDialog('Impersonate ' + escape(tenantName) + '? You will be logged in as their admin in a new tab. A 4-hour session token will be created.', 'Impersonate', '#7c3aed')) return

  try {
    var res = await fetch(API_BASE + '/platform/tenants/' + tenantId + '/impersonate', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + token },
    })
    var data = await res.json()
    if (!res.ok) { showToast(data.error || 'Impersonation failed.', 'error'); return }

    sessionStorage.setItem('_platform_token', token)
    sessionStorage.setItem('_platform_user', JSON.stringify(currentUser))

    var loginUrl = '/' + slug + '/lms?imp=' + encodeURIComponent(data.token) +
                   '&user=' + encodeURIComponent(JSON.stringify(data.user))
    window.open(loginUrl, '_blank')

    _platShowModal(
      'Impersonating ' + _platEsc(tenantName),
      '<div style="text-align:center;padding:20px;">' +
        '<div style="font-size:40px;margin-bottom:12px;">&#x2705;</div>' +
        '<p style="font-size:15px;color:#0f172a;font-weight:600;">Session opened in new tab</p>' +
        '<p style="font-size:13px;color:#64748b;">Signed in as <strong>' + _platEsc(data.user ? data.user.email : '') + '</strong></p>' +
        '<p style="font-size:12px;color:#94a3b8;margin-top:8px;">Token valid for 4 hours.</p>' +
        '<button onclick="_platCloseModal()" class="plat-btn plat-btn-primary" style="margin-top:16px;">Close</button>' +
      '</div>'
    )
  } catch (e) {
    showToast('Network error. Please try again.', 'warning')
  }
}

async function platSuspendOrg(tenantId, currentStatus, orgName) {
  var isActive   = currentStatus === 'active'
  var newStatus  = isActive ? 'suspended' : 'active'
  var actionWord = isActive ? 'Suspend' : 'Activate'

  if (!await confirmDialog(escape(actionWord) + ' &quot;' + escape(orgName) + '&quot;?' + (isActive ? '<br><span style="font-size:12px;color:#6b7280;">This will prevent all users from logging in.</span>' : ''), actionWord, isActive ? '#ef4444' : '#10b981')) return

  try {
    var res = await fetch(API_BASE + '/platform/tenants/' + tenantId + '/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({ status: newStatus }),
    })
    if (res.ok) {
      renderPlatformOrgs()
    } else {
      var d = await res.json()
      showToast(d.error || 'Failed to update status.', 'error')
    }
  } catch (e) {
    showToast('Network error.', 'error')
  }
}

// -- Modal Helpers ------------------------------------------------------------

function _platShowModal(title, bodyHtml) {
  var container = document.getElementById('platOrgModals')
  if (!container) {
    container = document.createElement('div')
    container.id = 'platOrgModals'
    document.body.appendChild(container)
  }
  container.innerHTML =
    '<div id="platOrgModalOverlay" style="position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:2000;display:flex;align-items:center;justify-content:center;">' +
      '<div style="background:#fff;border-radius:18px;width:560px;max-height:80vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.25);" onclick="event.stopPropagation()">' +
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

// -- Utilities ----------------------------------------------------------------

function _platEsc(s) {
  if (s == null) return ''
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function _platEscAttr(s) {
  if (s == null) return ''
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;')
}
