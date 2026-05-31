// ============================================================================
// ORG WIZARD — 6-step Organization Provisioning Wizard
//
// Provides a guided multi-step flow for creating a fully provisioned tenant:
//   Step 1: Organization Info   (name, slug, plan, industry, max users)
//   Step 2: Branding            (logo, theme presets, colors)
//   Step 3: Products            (which products to enable)
//   Step 4: Feature Flags       (per-product feature toggles)
//   Step 5: Admin User          (name, email, password)
//   Step 6: Review & Launch     (summary + provision button)
//
// Calls POST /api/platform/provision on completion.
// ============================================================================

var _wiz = {
  step: 1,
  products: [],        // available platform products (fetched on open)
  data: _wizBlank(),
}

function _wizBlank() {
  return {
    // Step 1
    name: '', slug: '', plan: 'starter', industry: '', max_users: 20, notes: '',
    // Step 2
    brand_name: '', logo_url: '', favicon_url: '',
    primary_color:    '#1e3a5f',
    secondary_color:  '#3b82f6',
    accent_color:     '#10b981',
    sidebar_bg_color: '#1e293b',
    login_bg_color:   '#f1f5f9',
    // Step 3
    products: ['crm'],
    // Step 4
    feature_flags: {},
    // Step 5
    admin_name: '', admin_email: '', admin_password: '', admin_confirm: '',
  }
}

// ── Open / Close ──────────────────────────────────────────────────────────────

async function openOrgWizard() {
  _wiz.step = 1
  _wiz.data = _wizBlank()
  _wiz.products = []

  // Fetch available products
  try {
    var res = await fetch(API_BASE + '/platform/products',
      { headers: { Authorization: 'Bearer ' + token } })
    if (res.ok) {
      var d = await res.json()
      _wiz.products = (d.products || []).filter(function(p) { return p.is_active })
    }
  } catch (e) {}

  // Default to CRM pre-selected
  if (_wiz.products.length > 0) {
    var crm = _wiz.products.find(function(p) { return p.slug === 'crm' })
    _wiz.data.products = crm ? ['crm'] : [_wiz.products[0].slug]
  }

  _wizRender()
}

function _wizClose() {
  var el = document.getElementById('orgWizardOverlay')
  if (el) el.remove()
}

// ── Render Shell ──────────────────────────────────────────────────────────────

function _wizRender() {
  var el = document.getElementById('orgWizardOverlay')
  if (!el) {
    el = document.createElement('div')
    el.id = 'orgWizardOverlay'
    document.body.appendChild(el)
  }

  var STEPS = ['Info', 'Branding', 'Products', 'Features', 'Admin', 'Launch']
  var STEP_TITLES = [
    'Organization Info',
    'Branding & Theme',
    'Product Selection',
    'Feature Flags',
    'Admin User',
    'Review & Launch',
  ]

  var progressHtml = '<div style="display:flex;gap:0;margin-bottom:8px;">'
  for (var i = 0; i < STEPS.length; i++) {
    var n = i + 1
    var done   = n < _wiz.step
    var active = n === _wiz.step
    var bar    = done ? '#16a34a' : active ? '#3b82f6' : '#e2e8f0'
    var txt    = done ? '#16a34a' : active ? '#3b82f6' : '#94a3b8'
    var wt     = done || active ? '700' : '500'
    progressHtml += '<div style="flex:1;text-align:center;">' +
      '<div style="height:4px;background:' + bar + ';border-radius:2px;margin-bottom:5px;"></div>' +
      '<span style="font-size:10px;font-weight:' + wt + ';color:' + txt + ';">' + STEPS[i] + '</span>' +
    '</div>'
  }
  progressHtml += '</div>'

  var backBtn = _wiz.step > 1
    ? '<button onclick="_wizBack()" class="plat-btn plat-btn-outline">&larr; Back</button>'
    : '<span></span>'

  var nextBtn = _wiz.step < 6
    ? '<button onclick="_wizNext()" class="plat-btn plat-btn-primary" id="wizNextBtn">Next &rarr;</button>'
    : '<button onclick="_wizProvision()" class="plat-btn plat-btn-primary" id="wizProvisionBtn">&#x1F680; Provision Organization</button>'

  el.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:3000;display:flex;align-items:center;justify-content:center;'
  el.innerHTML =
    '<div style="background:#fff;border-radius:20px;width:640px;max-height:92vh;display:flex;flex-direction:column;' +
         'box-shadow:0 25px 80px rgba(0,0,0,.3);overflow:hidden;" onclick="event.stopPropagation()">' +

      // Header
      '<div style="padding:24px 28px 16px;border-bottom:1px solid #f1f5f9;flex-shrink:0;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">' +
          '<div>' +
            '<h2 style="margin:0;font-size:20px;color:#0f172a;">Create Organization</h2>' +
            '<p style="margin:4px 0 0;font-size:13px;color:#64748b;">Step ' + _wiz.step + ' of 6 &mdash; ' + STEP_TITLES[_wiz.step - 1] + '</p>' +
          '</div>' +
          '<button onclick="_wizClose()" style="border:none;background:none;font-size:24px;cursor:pointer;color:#94a3b8;line-height:1;">&times;</button>' +
        '</div>' +
        progressHtml +
      '</div>' +

      // Body
      '<div id="wizBody" style="padding:24px 28px;overflow-y:auto;flex:1;">' +
        _wizStepHtml() +
      '</div>' +

      // Footer
      '<div style="padding:18px 28px;border-top:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;flex-shrink:0;">' +
        backBtn +
        '<div style="display:flex;align-items:center;gap:12px;">' +
          '<span id="wizErrMsg" style="font-size:13px;color:#dc2626;"></span>' +
          nextBtn +
        '</div>' +
      '</div>' +
    '</div>'
}

// ── Step Content ──────────────────────────────────────────────────────────────

function _wizStepHtml() {
  switch (_wiz.step) {
    case 1: return _wizStep1()
    case 2: return _wizStep2()
    case 3: return _wizStep3()
    case 4: return _wizStep4()
    case 5: return _wizStep5()
    case 6: return _wizStep6()
    default: return ''
  }
}

// Step 1: Organization Info
function _wizStep1() {
  var industries = ['Real Estate', 'Technology', 'Finance & Banking', 'Healthcare',
                    'Retail & E-commerce', 'Education', 'Construction', 'Manufacturing',
                    'Consulting', 'Other']
  var plans = [
    { value: 'starter',      label: 'Starter',      desc: 'Up to 20 users, basic features' },
    { value: 'professional', label: 'Professional', desc: 'Up to 100 users, advanced features' },
    { value: 'enterprise',   label: 'Enterprise',   desc: 'Unlimited users, full feature access' },
  ]
  return _wizGrid2(
    _wizField('org_name_input', 'Organization Name *', 'text', _wiz.data.name, 'e.g. ABC Developers',
      'oninput="_wizUpdateName(this.value)"'),
    _wizField('org_slug_input', 'Slug (URL identifier) *', 'text', _wiz.data.slug, 'e.g. abc-dev',
      'oninput="_wizSlugInput(this.value)" style="font-family:monospace;"'),
  ) +
  '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px;">' +
    '<div><label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Plan</label>' +
    '<select id="org_plan_select" oninput="_wiz.data.plan=this.value" style="' + _wizSelectStyle() + '">' +
    plans.map(function(p) {
      return '<option value="' + p.value + '"' + (_wiz.data.plan === p.value ? ' selected' : '') + '>' +
             p.label + ' — ' + p.desc + '</option>'
    }).join('') + '</select></div>' +
    '<div><label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Industry</label>' +
    '<select id="org_industry_select" oninput="_wiz.data.industry=this.value" style="' + _wizSelectStyle() + '">' +
    '<option value="">Select industry</option>' +
    industries.map(function(ind) {
      return '<option value="' + ind + '"' + (_wiz.data.industry === ind ? ' selected' : '') + '>' + ind + '</option>'
    }).join('') + '</select></div>' +
  '</div>' +
  '<div style="margin-top:16px;display:grid;grid-template-columns:100px 1fr;gap:16px;">' +
    _wizField('org_max_users', 'Max Users', 'number', _wiz.data.max_users, '20',
      'min="1" max="10000" oninput="_wiz.data.max_users=parseInt(this.value)||20"') +
    '<div><label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Internal Notes (optional)</label>' +
    '<textarea id="org_notes" oninput="_wiz.data.notes=this.value" placeholder="Notes for platform team only..." ' +
    'style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;resize:vertical;min-height:38px;box-sizing:border-box;">' +
    _wizEsc(_wiz.data.notes) + '</textarea></div>' +
  '</div>'
}

function _wizSlugInput(val) {
  _wiz.data.slug = val.toLowerCase().replace(/[^a-z0-9-]/g, '').replace(/--+/g, '-')
  _wiz.data._slugManual = true
}

function _wizUpdateName(val) {
  _wiz.data.name = val
  // Auto-update slug only if the user hasn't manually edited it
  var slugEl = document.getElementById('org_slug_input')
  if (slugEl && (!_wiz.data._slugManual)) {
    var auto = val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50)
    slugEl.value = auto
    _wiz.data.slug = auto
  }
}

// Step 2: Branding
function _wizStep2() {
  var themes = typeof TENANT_THEMES !== 'undefined' ? TENANT_THEMES : []
  var themeSwatches = themes.map(function(th) {
    return '<button onclick="_wizApplyTheme(\'' + th.id + '\')" title="' + th.name + '" style="' +
      'width:36px;height:36px;border-radius:50%;border:3px solid transparent;cursor:pointer;' +
      'background:' + th.primary_color + ';transition:border .15s;" ' +
      'onmouseover="this.style.borderColor=\'#0f172a\'" onmouseout="this.style.borderColor=\'transparent\'">' +
    '</button>'
  }).join('')

  return _wizGrid2(
    _wizField('wiz_brand_name', 'Brand Name', 'text', _wiz.data.brand_name || _wiz.data.name, 'Displayed in app & login page',
      'oninput="_wiz.data.brand_name=this.value"'),
    _wizField('wiz_logo_url', 'Logo URL', 'url', _wiz.data.logo_url, 'https://…/logo.png',
      'oninput="_wiz.data.logo_url=this.value"'),
  ) +
  _wizField('wiz_favicon_url', 'Favicon URL (optional)', 'url', _wiz.data.favicon_url, 'https://…/favicon.ico',
    'oninput="_wiz.data.favicon_url=this.value" style="margin-top:16px;"', true) +
  '<div style="margin-top:20px;">' +
    '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:10px;">Theme Presets</label>' +
    '<div style="display:flex;gap:10px;flex-wrap:wrap;">' + themeSwatches + '</div>' +
  '</div>' +
  '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:20px;">' +
    _wizColorField('wiz_pc', 'Primary Color',   'primary_color',    _wiz.data.primary_color) +
    _wizColorField('wiz_sc', 'Secondary Color', 'secondary_color',  _wiz.data.secondary_color) +
    _wizColorField('wiz_ac', 'Accent Color',    'accent_color',     _wiz.data.accent_color) +
    _wizColorField('wiz_sb', 'Sidebar BG',      'sidebar_bg_color', _wiz.data.sidebar_bg_color) +
    _wizColorField('wiz_lb', 'Login BG',        'login_bg_color',   _wiz.data.login_bg_color) +
  '</div>'
}

function _wizApplyTheme(themeId) {
  if (typeof TENANT_THEMES === 'undefined') return
  var th = TENANT_THEMES.find(function(t) { return t.id === themeId })
  if (!th) return
  var map = {
    wiz_pc: ['primary_color',    th.primary_color],
    wiz_sc: ['secondary_color',  th.secondary_color],
    wiz_ac: ['accent_color',     th.accent_color],
    wiz_sb: ['sidebar_bg_color', th.sidebar_bg_color],
    wiz_lb: ['login_bg_color',   th.login_bg_color],
  }
  Object.keys(map).forEach(function(id) {
    var val = map[id][1]; var key = map[id][0]
    var el = document.getElementById(id)
    var pk = document.getElementById(id + '_p')
    if (el) el.value = val
    if (pk) pk.value = val
    _wiz.data[key] = val
  })
}

// Step 3: Products
function _wizStep3() {
  if (!_wiz.products.length) {
    return '<p style="color:#94a3b8;text-align:center;padding:40px 0;">No active products available.</p>'
  }
  var cards = _wiz.products.map(function(p) {
    var on = _wiz.data.products.indexOf(p.slug) !== -1
    return '<div onclick="_wizToggleProduct(\'' + p.slug + '\')" style="' +
      'border:2px solid ' + (on ? p.color || '#3b82f6' : '#e2e8f0') + ';' +
      'border-radius:14px;padding:18px;cursor:pointer;transition:all .2s;' +
      'background:' + (on ? (p.color || '#3b82f6') + '0d' : '#fff') + ';">' +
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;">' +
        '<div style="width:44px;height:44px;border-radius:12px;background:' + (p.color || '#3b82f6') + '22;' +
          'display:flex;align-items:center;justify-content:center;font-size:22px;">' + (p.icon || '📦') + '</div>' +
        '<div style="width:22px;height:22px;border-radius:50%;border:2px solid ' + (on ? (p.color || '#3b82f6') : '#d1d5db') + ';' +
          'background:' + (on ? (p.color || '#3b82f6') : '#fff') + ';display:flex;align-items:center;justify-content:center;">' +
          (on ? '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M2 6l3 3 5-5" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round"/></svg>' : '') +
        '</div>' +
      '</div>' +
      '<div style="margin-top:12px;font-weight:700;font-size:14px;color:#0f172a;">' + _wizEsc(p.name) + '</div>' +
      '<div style="margin-top:4px;font-size:12px;color:#64748b;">' + _wizEsc(p.description || p.category || '') + '</div>' +
      '<div style="margin-top:8px;display:flex;gap:6px;">' +
        '<span style="font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;background:' + (p.color || '#3b82f6') + '22;color:' + (p.color || '#3b82f6') + ';">' + p.slug + '</span>' +
        (p.is_active ? '' : '<span style="font-size:10px;padding:2px 8px;border-radius:10px;background:#fef2f2;color:#dc2626;">Coming soon</span>') +
      '</div>' +
    '</div>'
  }).join('')

  return '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">' + cards + '</div>' +
    '<p style="margin:14px 0 0;font-size:12px;color:#94a3b8;">Click to toggle. At least one product must be selected.</p>'
}

function _wizToggleProduct(slug) {
  var idx = _wiz.data.products.indexOf(slug)
  if (idx === -1) {
    _wiz.data.products.push(slug)
  } else if (_wiz.data.products.length > 1) {
    _wiz.data.products.splice(idx, 1)
  }
  // Re-render step 3
  var body = document.getElementById('wizBody')
  if (body) body.innerHTML = _wizStep3()
}

// Step 4: Feature Flags
function _wizStep4() {
  var flags = typeof FEATURE_FLAGS !== 'undefined' ? FEATURE_FLAGS : []
  var relevant = flags.filter(function(f) {
    return _wiz.data.products.indexOf(f.product) !== -1 || f.product === 'platform'
  })
  if (!relevant.length) {
    return '<p style="color:#94a3b8;text-align:center;padding:40px 0;">No feature flags available for selected products.</p>'
  }
  return '<p style="font-size:13px;color:#64748b;margin:0 0 18px;">Configure which features are enabled for this organization. These can be changed later.</p>' +
    relevant.map(function(def) {
      var key = def.key
      var val = (key in _wiz.data.feature_flags) ? _wiz.data.feature_flags[key] : def.default
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid #f1f5f9;">' +
        '<div>' +
          '<div style="font-weight:600;font-size:14px;color:#0f172a;">' + _wizEsc(def.label) + '</div>' +
          '<div style="font-size:12px;color:#64748b;margin-top:2px;">' + _wizEsc(def.description) + '</div>' +
        '</div>' +
        '<label style="position:relative;display:inline-block;width:44px;height:24px;flex-shrink:0;cursor:pointer;">' +
          '<input type="checkbox"' + (val ? ' checked' : '') +
            ' onchange="_wizSetFlag(\'' + key + '\',this.checked)" style="opacity:0;width:0;height:0;">' +
          '<span id="wizFt_' + key + '" style="position:absolute;top:0;left:0;right:0;bottom:0;border-radius:24px;' +
            'background:' + (val ? '#16a34a' : '#d1d5db') + ';transition:.3s;">' +
            '<span style="position:absolute;height:18px;width:18px;left:3px;bottom:3px;border-radius:50%;' +
              'background:#fff;transition:.3s;transform:' + (val ? 'translateX(20px)' : 'translateX(0)') + ';"></span>' +
          '</span>' +
        '</label>' +
      '</div>'
    }).join('')
}

function _wizSetFlag(key, val) {
  _wiz.data.feature_flags[key] = val
  var track = document.getElementById('wizFt_' + key)
  if (track) {
    track.style.background = val ? '#16a34a' : '#d1d5db'
    var thumb = track.querySelector('span')
    if (thumb) thumb.style.transform = val ? 'translateX(20px)' : 'translateX(0)'
  }
}

// Step 5: Admin User
function _wizStep5() {
  return '<p style="font-size:13px;color:#64748b;margin:0 0 18px;">This account will have full admin access to the organization.</p>' +
    _wizGrid2(
      _wizField('wiz_admin_name', 'Admin Name *', 'text', _wiz.data.admin_name, 'e.g. John Smith',
        'oninput="_wiz.data.admin_name=this.value"'),
      _wizField('wiz_admin_email', 'Admin Email *', 'email', _wiz.data.admin_email, 'admin@organization.com',
        'oninput="_wiz.data.admin_email=this.value"'),
    ) +
    _wizGrid2(
      _wizField('wiz_admin_pw', 'Password *', 'password', _wiz.data.admin_password, 'Min. 6 characters',
        'oninput="_wiz.data.admin_password=this.value;_wizCheckPwStrength(this.value)"'),
      _wizField('wiz_admin_pw2', 'Confirm Password *', 'password', _wiz.data.admin_confirm, 'Repeat password',
        'oninput="_wiz.data.admin_confirm=this.value"'),
    ) +
    '<div id="wizPwStrength" style="margin-top:8px;"></div>'
}

function _wizCheckPwStrength(pw) {
  var el = document.getElementById('wizPwStrength')
  if (!el) return
  var score = 0
  if (pw.length >= 6)  score++
  if (pw.length >= 10) score++
  if (/[A-Z]/.test(pw)) score++
  if (/[0-9]/.test(pw)) score++
  if (/[^A-Za-z0-9]/.test(pw)) score++
  var labels = ['Too short', 'Weak', 'Fair', 'Good', 'Strong', 'Very strong']
  var colors = ['#dc2626', '#f97316', '#eab308', '#3b82f6', '#16a34a', '#16a34a']
  var widths = ['20%', '35%', '50%', '65%', '80%', '100%']
  el.innerHTML = '<div style="height:4px;background:#e2e8f0;border-radius:2px;margin-bottom:4px;">' +
    '<div style="height:4px;background:' + colors[score] + ';width:' + widths[score] + ';border-radius:2px;transition:width .3s;"></div>' +
  '</div>' +
  '<span style="font-size:11px;color:' + colors[score] + ';">' + labels[score] + '</span>'
}

// Step 6: Review & Launch
function _wizStep6() {
  var d = _wiz.data
  var productNames = _wiz.data.products.map(function(slug) {
    var p = _wiz.products.find(function(x) { return x.slug === slug })
    return p ? ((p.icon || '📦') + ' ' + p.name) : slug
  }).join('  •  ')

  return '<p style="font-size:13px;color:#64748b;margin:0 0 18px;">Review the configuration below. Everything can be changed later from the Organizations settings.</p>' +

    // Org summary
    '<div style="background:#f8fafc;border-radius:14px;padding:20px;margin-bottom:16px;">' +
      '<h4 style="margin:0 0 14px;font-size:14px;color:#0f172a;">Organization</h4>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;">' +
        _wizReviewRow('Name', d.name) +
        _wizReviewRow('Slug', '/' + d.slug) +
        _wizReviewRow('Plan', d.plan.charAt(0).toUpperCase() + d.plan.slice(1)) +
        _wizReviewRow('Industry', d.industry || '—') +
        _wizReviewRow('Max Users', d.max_users) +
      '</div>' +
    '</div>' +

    // Branding summary
    '<div style="background:#f8fafc;border-radius:14px;padding:20px;margin-bottom:16px;">' +
      '<h4 style="margin:0 0 14px;font-size:14px;color:#0f172a;">Branding</h4>' +
      '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">' +
        '<span style="font-size:13px;color:#475569;">' + _wizEsc(d.brand_name || d.name) + '</span>' +
        '<div style="display:flex;gap:6px;">' +
          ['primary_color', 'secondary_color', 'accent_color', 'sidebar_bg_color', 'login_bg_color'].map(function(k) {
            return '<div title="' + k.replace(/_/g, ' ') + '" style="width:22px;height:22px;border-radius:50%;' +
              'background:' + d[k] + ';border:2px solid rgba(0,0,0,.08);"></div>'
          }).join('') +
        '</div>' +
      '</div>' +
      (d.logo_url ? '<div style="margin-top:8px;font-size:12px;color:#64748b;">Logo: ' + _wizEsc(d.logo_url) + '</div>' : '') +
    '</div>' +

    // Products
    '<div style="background:#f8fafc;border-radius:14px;padding:20px;margin-bottom:16px;">' +
      '<h4 style="margin:0 0 10px;font-size:14px;color:#0f172a;">Products</h4>' +
      '<div style="font-size:14px;color:#334155;">' + productNames + '</div>' +
    '</div>' +

    // Admin
    '<div style="background:#f8fafc;border-radius:14px;padding:20px;">' +
      '<h4 style="margin:0 0 14px;font-size:14px;color:#0f172a;">Admin User</h4>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;">' +
        _wizReviewRow('Name',  d.admin_name) +
        _wizReviewRow('Email', d.admin_email) +
      '</div>' +
    '</div>'
}

// ── Navigation ────────────────────────────────────────────────────────────────

function _wizNext() {
  var err = _wizValidateStep(_wiz.step)
  if (err) { _wizShowErr(err); return }
  _wizClearErr()
  _wizSaveStepData()
  _wiz.step++
  _wizRender()
}

function _wizBack() {
  _wizClearErr()
  _wizSaveStepData()
  _wiz.step--
  _wizRender()
}

function _wizSaveStepData() {
  // Collect current input values back into _wiz.data
  var reads = {
    org_name_input:     ['name', 'text'],
    org_slug_input:     ['slug', 'text'],
    org_plan_select:    ['plan', 'text'],
    org_industry_select:['industry', 'text'],
    org_max_users:      ['max_users', 'number'],
    org_notes:          ['notes', 'textarea'],
    wiz_brand_name:     ['brand_name', 'text'],
    wiz_logo_url:       ['logo_url', 'text'],
    wiz_favicon_url:    ['favicon_url', 'text'],
    wiz_admin_name:     ['admin_name', 'text'],
    wiz_admin_email:    ['admin_email', 'text'],
    wiz_admin_pw:       ['admin_password', 'text'],
    wiz_admin_pw2:      ['admin_confirm', 'text'],
  }
  Object.keys(reads).forEach(function(id) {
    var el = document.getElementById(id)
    if (!el) return
    var key = reads[id][0]
    if (reads[id][1] === 'number') _wiz.data[key] = parseInt(el.value) || 0
    else _wiz.data[key] = el.value || ''
  })
  // Color fields
  var colorIds = {
    wiz_pc: 'primary_color', wiz_sc: 'secondary_color', wiz_ac: 'accent_color',
    wiz_sb: 'sidebar_bg_color', wiz_lb: 'login_bg_color',
  }
  Object.keys(colorIds).forEach(function(id) {
    var el = document.getElementById(id)
    if (el) _wiz.data[colorIds[id]] = el.value
  })
}

function _wizValidateStep(step) {
  _wizSaveStepData()
  var d = _wiz.data
  if (step === 1) {
    if (!d.name.trim()) return 'Organization name is required.'
    if (!d.slug.trim()) return 'Slug is required.'
    if (!/^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/.test(d.slug)) {
      return 'Slug must be 3–50 lowercase letters, numbers or hyphens.'
    }
  }
  if (step === 3 && d.products.length === 0) {
    return 'Select at least one product.'
  }
  if (step === 5) {
    if (!d.admin_name.trim()) return 'Admin name is required.'
    if (!d.admin_email.trim()) return 'Admin email is required.'
    if (!/^[^@]+@[^@]+\.[^@]+$/.test(d.admin_email)) return 'Invalid email address.'
    if (!d.admin_password || d.admin_password.length < 6) return 'Password must be at least 6 characters.'
    if (d.admin_password !== d.admin_confirm) return 'Passwords do not match.'
  }
  return null
}

function _wizShowErr(msg) {
  var el = document.getElementById('wizErrMsg')
  if (el) el.textContent = msg
}

function _wizClearErr() {
  var el = document.getElementById('wizErrMsg')
  if (el) el.textContent = ''
}

// ── Provision ──────────────────────────────────────────────────────────────────

async function _wizProvision() {
  _wizSaveStepData()
  var btn = document.getElementById('wizProvisionBtn')
  if (btn) { btn.disabled = true; btn.textContent = 'Provisioning…' }
  _wizClearErr()

  var d = _wiz.data
  var payload = {
    name:             d.name,
    slug:             d.slug,
    plan:             d.plan,
    industry:         d.industry,
    max_users:        d.max_users,
    notes:            d.notes,
    brand_name:       d.brand_name || d.name,
    logo_url:         d.logo_url || null,
    favicon_url:      d.favicon_url || null,
    primary_color:    d.primary_color,
    secondary_color:  d.secondary_color,
    accent_color:     d.accent_color,
    sidebar_bg_color: d.sidebar_bg_color,
    login_bg_color:   d.login_bg_color,
    products:         d.products,
    feature_flags:    d.feature_flags,
    admin_name:       d.admin_name,
    admin_email:      d.admin_email,
    admin_password:   d.admin_password,
  }

  try {
    var res = await fetch(API_BASE + '/platform/provision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify(payload),
    })
    var result = await res.json()
    if (!res.ok) {
      if (btn) { btn.disabled = false; btn.textContent = '🚀 Provision Organization' }
      _wizShowErr(result.error || 'Provisioning failed.')
      return
    }
    // Show success screen
    _wizShowSuccess(result)
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '🚀 Provision Organization' }
    _wizShowErr('Network error. Please try again.')
  }
}

function _wizShowSuccess(result) {
  var body = document.getElementById('wizBody')
  var footer = body?.closest('[style]')?.querySelector('[style*="border-top"]')

  // Update body with success state
  if (body) {
    var loginUrl = result.login_url || authBuildTenantLoginPath(_wiz.data.slug, 'lms')
    var products = (result.products_provisioned || []).join(', ')
    body.innerHTML =
      '<div style="text-align:center;padding:20px 0;">' +
        '<div style="font-size:52px;margin-bottom:12px;">🎉</div>' +
        '<h3 style="margin:0 0 6px;font-size:20px;color:#0f172a;">' + _wizEsc(result.tenant?.brand_name || _wiz.data.name) + ' is live!</h3>' +
        '<p style="color:#64748b;font-size:14px;margin:0 0 24px;">Organization provisioned successfully.</p>' +
      '</div>' +
      '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:14px;padding:20px;margin-bottom:16px;">' +
        '<h4 style="margin:0 0 12px;color:#166534;font-size:14px;">Tenant Details</h4>' +
        '<div style="font-size:13px;color:#374151;display:grid;gap:6px;">' +
          '<div><strong>Login URL:</strong> <code style="background:#e0f2fe;padding:2px 6px;border-radius:4px;font-size:12px;">' + _wizEsc(loginUrl) + '</code></div>' +
          '<div><strong>Admin Email:</strong> ' + _wizEsc(result.admin_user?.email || _wiz.data.admin_email) + '</div>' +
          '<div><strong>Products:</strong> ' + _wizEsc(products) + '</div>' +
        '</div>' +
      '</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">' +
        '<button onclick="_wizClose();renderPlatformOrgs()" class="plat-btn plat-btn-primary" style="width:100%;padding:12px;">View Organization</button>' +
        '<button onclick="_wizClose();renderPlatformOrgs()" class="plat-btn plat-btn-outline" style="width:100%;padding:12px;">Back to Organizations</button>' +
      '</div>'
  }

  // Hide footer nav
  var overlay = document.getElementById('orgWizardOverlay')
  if (overlay) {
    var footerEl = overlay.querySelector('[style*="border-top"]')
    if (footerEl) footerEl.style.display = 'none'
  }

  // Refresh the org list in the background
  renderPlatformOrgs()
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function _wizGrid2(a, b) {
  return '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">' + a + b + '</div>'
}

function _wizField(id, label, type, value, placeholder, extra, fullWidth) {
  var tag = type === 'textarea' ? 'textarea' : 'input'
  var attrs = 'id="' + id + '" ' + (tag === 'input' ? 'type="' + type + '"' : '') +
    ' placeholder="' + _wizEscAttr(placeholder) + '"' +
    (tag === 'input' ? ' value="' + _wizEscAttr(String(value || '')) + '"' : '') +
    ' style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;"' +
    (extra ? ' ' + extra : '')
  return '<div' + (fullWidth ? ' style="margin-top:16px;"' : '') + '>' +
    '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">' + label + '</label>' +
    '<' + tag + ' ' + attrs + '>' + (tag === 'textarea' ? _wizEsc(String(value || '')) + '</textarea>' : '') +
  '</div>'
}

function _wizColorField(id, label, dataKey, value) {
  return '<div>' +
    '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">' + label + '</label>' +
    '<div style="display:flex;align-items:center;gap:6px;">' +
      '<input type="color" id="' + id + '_p" value="' + _wizEscAttr(value) + '"' +
        ' oninput="document.getElementById(\'' + id + '\').value=this.value;_wiz.data.' + dataKey + '=this.value"' +
        ' style="width:34px;height:34px;padding:2px;border:1px solid #e2e8f0;border-radius:6px;cursor:pointer;">' +
      '<input type="text" id="' + id + '" value="' + _wizEscAttr(value) + '"' +
        ' oninput="document.getElementById(\'' + id + '_p\').value=this.value;_wiz.data.' + dataKey + '=this.value"' +
        ' style="flex:1;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;font-family:monospace;outline:none;">' +
    '</div>' +
  '</div>'
}

function _wizSelectStyle() {
  return 'width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;background:#fff;'
}

function _wizReviewRow(label, value) {
  return '<div style="color:#64748b;">' + label + ':</div>' +
         '<div style="color:#0f172a;font-weight:600;">' + _wizEsc(String(value || '—')) + '</div>'
}

function _wizEsc(s) {
  if (s == null) return ''
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function _wizEscAttr(s) {
  if (s == null) return ''
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
}
