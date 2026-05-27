// ============================================================================
// PLATFORM ADMIN — Tenant Configuration & White-Label Editor
//
// Rendered inside #platContent when a platform admin clicks "Configure" on
// a tenant row in the Organizations view.
//
// Sections:
//   1. Branding  (brand name, logo URL, favicon URL, colors, theme presets)
//   2. Products  (enable / disable subscriptions for this tenant)
//   3. Features  (per-tenant feature flag toggles)
//   4. Plan      (plan tier, max users, status)
// ============================================================================

// State for the editor
var _tcTenantId   = null
var _tcTenantData = null   // { tenant, subscriptions, available_products }

async function renderTenantConfigPage(tenantId) {
  var el = document.getElementById('platContent')
  if (!el) return

  _tcTenantId = tenantId
  el.innerHTML = '<div style="padding:40px;text-align:center;color:#94a3b8;">&#x23F3; Loading configuration&hellip;</div>'

  try {
    var [tenantRes, subsRes, flagsRes] = await Promise.all([
      fetch(API_BASE + '/platform/tenants/' + tenantId,
        { headers: { Authorization: 'Bearer ' + token } }),
      fetch(API_BASE + '/platform/tenants/' + tenantId + '/products',
        { headers: { Authorization: 'Bearer ' + token } }),
      fetch(API_BASE + '/platform/feature-flags?tenant_id=' + tenantId,
        { headers: { Authorization: 'Bearer ' + token } }),
    ])

    var tenantJson = tenantRes.ok ? await tenantRes.json() : {}
    var subsJson   = subsRes.ok   ? await subsRes.json()   : {}
    var flagsJson  = flagsRes.ok  ? await flagsRes.json()  : {}

    _tcTenantData = {
      tenant:             tenantJson.tenant || {},
      subscriptions:      subsJson.subscriptions || [],
      available_products: subsJson.available_products || [],
      feature_flags:      flagsJson.feature_flags || [],
    }
    _renderTenantConfigUI()
  } catch (e) {
    el.innerHTML = '<div style="padding:40px;text-align:center;color:#dc2626;">Failed to load tenant configuration.</div>'
  }
}

function _renderTenantConfigUI() {
  var el = document.getElementById('platContent')
  if (!el || !_tcTenantData) return

  var t = _tcTenantData.tenant
  var subs = _tcTenantData.subscriptions
  var allProducts = _tcTenantData.available_products
  var flags = _tcTenantData.feature_flags

  // Build subscribed product_id set
  var subbedProductIds = new Set(subs.map(function(s) { return s.product_id }))

  // Build flag map
  var flagMap = {}
  flags.forEach(function(f) { flagMap[f.flag_key] = f.is_enabled })

  // ── Theme swatches ─────────────────────────────────────────────────────────
  var themeSwatches = (typeof TENANT_THEMES !== 'undefined' ? TENANT_THEMES : []).map(function(th) {
    return '<button onclick="_tcApplyTheme(\'' + th.id + '\')" title="' + th.name + '" style="' +
      'width:32px;height:32px;border-radius:50%;border:3px solid transparent;cursor:pointer;' +
      'background:' + th.primary_color + ';transition:border .15s;' +
      '" onmouseover="this.style.borderColor=\'#0f172a\'" onmouseout="this.style.borderColor=\'transparent\'"></button>'
  }).join('')

  // ── Feature flag rows ──────────────────────────────────────────────────────
  var featureFlagDefs = typeof FEATURE_FLAGS !== 'undefined' ? FEATURE_FLAGS : []
  var flagRows = featureFlagDefs.map(function(def) {
    var savedFlag = flags.find(function(f) { return f.flag_key === def.key })
    var isOn = savedFlag ? savedFlag.is_enabled : def.default
    return '<div style="display:flex;align-items:center;justify-content:space-between;' +
      'padding:12px 0;border-bottom:1px solid #f1f5f9;">' +
      '<div>' +
        '<div style="font-weight:600;font-size:14px;color:#0f172a;">' + def.label + '</div>' +
        '<div style="font-size:12px;color:#64748b;margin-top:2px;">' + def.description + '</div>' +
      '</div>' +
      '<label style="position:relative;display:inline-block;width:44px;height:24px;flex-shrink:0;">' +
        '<input type="checkbox" data-flag="' + def.key + '" ' + (isOn ? 'checked' : '') +
          ' onchange="_tcToggleFlag(\'' + def.key + '\',this.checked)"' +
          ' style="opacity:0;width:0;height:0;">' +
        '<span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;' +
          'border-radius:24px;transition:.3s;background:' + (isOn ? '#16a34a' : '#d1d5db') + ';" ' +
          'id="flagTrack_' + def.key + '">' +
          '<span style="position:absolute;height:18px;width:18px;left:3px;bottom:3px;' +
            'border-radius:50%;background:#fff;transition:.3s;transform:' + (isOn ? 'translateX(20px)' : 'translateX(0)') + ';" ' +
            'id="flagThumb_' + def.key + '"></span>' +
        '</span>' +
      '</label>' +
    '</div>'
  }).join('')

  // ── Product rows ───────────────────────────────────────────────────────────
  var productRows = allProducts.map(function(p) {
    var isEnabled = subbedProductIds.has(p.id)
    return '<div style="display:flex;align-items:center;justify-content:space-between;' +
      'padding:12px 0;border-bottom:1px solid #f1f5f9;">' +
      '<div style="display:flex;align-items:center;gap:12px;">' +
        '<div style="width:40px;height:40px;border-radius:10px;background:' + (p.color || '#3b82f6') +
          '22;display:flex;align-items:center;justify-content:center;font-size:18px;">' + (p.icon || '&#x1F4E6;') + '</div>' +
        '<div>' +
          '<div style="font-weight:600;font-size:14px;color:#0f172a;">' + _escHtml(p.name) + '</div>' +
          '<div style="font-size:11px;color:#64748b;">' + p.slug + ' &bull; ' + (p.category || '') + '</div>' +
        '</div>' +
      '</div>' +
      '<label style="position:relative;display:inline-block;width:44px;height:24px;flex-shrink:0;">' +
        '<input type="checkbox" data-product-id="' + p.id + '" ' + (isEnabled ? 'checked' : '') +
          ' onchange="_tcToggleProduct(' + p.id + ',this.checked)"' +
          ' style="opacity:0;width:0;height:0;">' +
        '<span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;' +
          'border-radius:24px;transition:.3s;background:' + (isEnabled ? '#16a34a' : '#d1d5db') + ';" ' +
          'id="prodTrack_' + p.id + '">' +
          '<span style="position:absolute;height:18px;width:18px;left:3px;bottom:3px;' +
            'border-radius:50%;background:#fff;transition:.3s;transform:' + (isEnabled ? 'translateX(20px)' : 'translateX(0)') + ';" ' +
            'id="prodThumb_' + p.id + '"></span>' +
        '</span>' +
      '</label>' +
    '</div>'
  }).join('') || '<p style="color:#94a3b8;font-size:14px;">No products available.</p>'

  el.innerHTML =
    '<div style="max-width:900px;">' +
      // Header
      '<div style="display:flex;align-items:center;gap:12px;margin-bottom:28px;">' +
        '<button onclick="platNavigate(\'organizations\')" class="plat-btn plat-btn-outline" style="padding:6px 14px;">' +
          '&larr; Organizations' +
        '</button>' +
        '<div>' +
          '<h2 style="margin:0;font-size:20px;color:#0f172a;">' + _escHtml(t.brand_name || t.name) + ' &mdash; Configuration</h2>' +
          '<p style="margin:4px 0 0;font-size:13px;color:#64748b;">slug: ' + _escHtml(t.slug) + ' &bull; plan: ' + _escHtml(t.plan) + '</p>' +
        '</div>' +
      '</div>' +

      // ── Section: Branding ────────────────────────────────────────────────
      '<div class="plat-card" style="margin-bottom:20px;">' +
        '<h3 style="margin:0 0 20px;font-size:16px;color:#0f172a;display:flex;align-items:center;gap:8px;">' +
          '<i class="fa-solid fa-palette" style="color:#8b5cf6;"></i> Branding' +
        '</h3>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">' +
          _tcField('Brand Name', 'tcBrandName', t.brand_name || t.name, 'text', 'Display name shown in the sidebar and login page') +
          _tcField('Logo URL', 'tcLogoUrl', t.logo_url || '', 'url', 'Full URL to company logo (PNG/JPG, 300×300 recommended)') +
          _tcField('Favicon URL', 'tcFaviconUrl', t.favicon_url || '', 'url', 'Full URL to 32×32 favicon (.ico or PNG)') +
          _tcField('Custom Domain', 'tcCustomDomain', t.custom_domain || '', 'text', 'e.g. crm.yourcompany.com (optional)') +
        '</div>' +
        // Color row
        '<div style="margin-top:16px;">' +
          '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:8px;">Theme Presets</label>' +
          '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">' + themeSwatches + '</div>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;">' +
          _tcColorField('Primary Color', 'tcPrimaryColor', t.primary_color || '#0284c7') +
          _tcColorField('Secondary Color', 'tcSecondaryColor', t.secondary_color || '#0ea5e9') +
          _tcColorField('Accent Color', 'tcAccentColor', t.accent_color || '#10b981') +
          _tcColorField('Sidebar Background', 'tcSidebarBg', t.sidebar_bg_color || '#1e293b') +
          _tcColorField('Login Background', 'tcLoginBg', t.login_bg_color || '#f1f5f9') +
        '</div>' +
        // Save branding
        '<div style="margin-top:20px;display:flex;align-items:center;gap:12px;">' +
          '<button class="plat-btn plat-btn-primary" onclick="_tcSaveBranding()">Save Branding</button>' +
          '<span id="tcBrandingMsg" style="font-size:13px;"></span>' +
        '</div>' +
      '</div>' +

      // ── Section: Products ────────────────────────────────────────────────
      '<div class="plat-card" style="margin-bottom:20px;">' +
        '<h3 style="margin:0 0 20px;font-size:16px;color:#0f172a;display:flex;align-items:center;gap:8px;">' +
          '<i class="fa-solid fa-cubes" style="color:#3b82f6;"></i> Product Access' +
        '</h3>' +
        productRows +
      '</div>' +

      // ── Section: Feature Flags ───────────────────────────────────────────
      '<div class="plat-card" style="margin-bottom:20px;">' +
        '<h3 style="margin:0 0 20px;font-size:16px;color:#0f172a;display:flex;align-items:center;gap:8px;">' +
          '<i class="fa-solid fa-toggle-on" style="color:#16a34a;"></i> Feature Flags' +
        '</h3>' +
        flagRows +
      '</div>' +

      // ── Section: Plan ────────────────────────────────────────────────────
      '<div class="plat-card" style="margin-bottom:40px;">' +
        '<h3 style="margin:0 0 20px;font-size:16px;color:#0f172a;display:flex;align-items:center;gap:8px;">' +
          '<i class="fa-solid fa-star" style="color:#f59e0b;"></i> Plan & Status' +
        '</h3>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;">' +
          '<div>' +
            '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Plan Tier</label>' +
            '<select id="tcPlan" style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;">' +
              ['starter','professional','enterprise'].map(function(p) {
                return '<option value="' + p + '"' + (t.plan === p ? ' selected' : '') + '>' + p.charAt(0).toUpperCase() + p.slice(1) + '</option>'
              }).join('') +
            '</select>' +
          '</div>' +
          '<div>' +
            '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Status</label>' +
            '<select id="tcStatus" style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;">' +
              ['active','inactive','suspended'].map(function(s) {
                return '<option value="' + s + '"' + (t.status === s ? ' selected' : '') + '>' + s.charAt(0).toUpperCase() + s.slice(1) + '</option>'
              }).join('') +
            '</select>' +
          '</div>' +
          _tcField('Max Users', 'tcMaxUsers', t.max_users || 20, 'number', '') +
        '</div>' +
        '<div style="margin-top:20px;display:flex;align-items:center;gap:12px;">' +
          '<button class="plat-btn plat-btn-primary" onclick="_tcSavePlan()">Save Plan</button>' +
          '<span id="tcPlanMsg" style="font-size:13px;"></span>' +
        '</div>' +
      '</div>' +
    '</div>'
}

// ── Helper: render a form field ───────────────────────────────────────────
function _tcField(label, id, value, type, hint) {
  return '<div>' +
    '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">' + label + '</label>' +
    '<input id="' + id + '" type="' + (type || 'text') + '" value="' + _escAttr(String(value)) + '"' +
    ' style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;" />' +
    (hint ? '<p style="margin:4px 0 0;font-size:11px;color:#94a3b8;">' + hint + '</p>' : '') +
  '</div>'
}

function _tcColorField(label, id, value) {
  return '<div>' +
    '<label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">' + label + '</label>' +
    '<div style="display:flex;align-items:center;gap:8px;">' +
      '<input type="color" id="' + id + 'Picker" value="' + _escAttr(value) + '"' +
        ' oninput="document.getElementById(\'' + id + '\').value=this.value"' +
        ' style="width:36px;height:36px;padding:2px;border:1px solid #e2e8f0;border-radius:6px;cursor:pointer;">' +
      '<input type="text" id="' + id + '" value="' + _escAttr(value) + '"' +
        ' oninput="document.getElementById(\'' + id + 'Picker\').value=this.value"' +
        ' style="flex:1;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;">' +
    '</div>' +
  '</div>'
}

// ── Theme preset ──────────────────────────────────────────────────────────
function _tcApplyTheme(themeId) {
  if (typeof TENANT_THEMES === 'undefined') return
  var th = TENANT_THEMES.find(function(t) { return t.id === themeId })
  if (!th) return
  var map = {
    tcPrimaryColor: th.primary_color,
    tcSecondaryColor: th.secondary_color,
    tcAccentColor: th.accent_color,
    tcSidebarBg: th.sidebar_bg_color,
    tcLoginBg: th.login_bg_color,
  }
  Object.keys(map).forEach(function(fieldId) {
    var el = document.getElementById(fieldId)
    var picker = document.getElementById(fieldId + 'Picker')
    if (el) el.value = map[fieldId]
    if (picker) picker.value = map[fieldId]
  })
}

// ── Save branding ─────────────────────────────────────────────────────────
async function _tcSaveBranding() {
  var payload = {
    brand_name:      document.getElementById('tcBrandName')?.value?.trim(),
    logo_url:        document.getElementById('tcLogoUrl')?.value?.trim() || null,
    favicon_url:     document.getElementById('tcFaviconUrl')?.value?.trim() || null,
    custom_domain:   document.getElementById('tcCustomDomain')?.value?.trim() || null,
    primary_color:   document.getElementById('tcPrimaryColor')?.value,
    secondary_color: document.getElementById('tcSecondaryColor')?.value,
    accent_color:    document.getElementById('tcAccentColor')?.value,
    sidebar_bg_color: document.getElementById('tcSidebarBg')?.value,
    login_bg_color:  document.getElementById('tcLoginBg')?.value,
  }
  var msg = document.getElementById('tcBrandingMsg')
  if (msg) { msg.style.color = '#64748b'; msg.textContent = 'Saving…' }
  try {
    var res = await fetch(API_BASE + '/platform/tenants/' + _tcTenantId, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify(payload),
    })
    if (res.ok) {
      // Bust cache so next tenant route load picks up fresh config
      if (typeof _tenantConfigCache !== 'undefined' && _tcTenantData?.tenant?.slug) {
        delete _tenantConfigCache[_tcTenantData.tenant.slug]
      }
      if (msg) { msg.style.color = '#16a34a'; msg.textContent = '&#x2713; Branding saved' }
    } else {
      var data = await res.json()
      if (msg) { msg.style.color = '#dc2626'; msg.textContent = data.error || 'Save failed' }
    }
  } catch (e) {
    if (msg) { msg.style.color = '#dc2626'; msg.textContent = 'Network error' }
  }
}

// ── Save plan ─────────────────────────────────────────────────────────────
async function _tcSavePlan() {
  var payload = {
    plan:      document.getElementById('tcPlan')?.value,
    status:    document.getElementById('tcStatus')?.value,
    max_users: parseInt(document.getElementById('tcMaxUsers')?.value || '20', 10),
  }
  var msg = document.getElementById('tcPlanMsg')
  if (msg) { msg.style.color = '#64748b'; msg.textContent = 'Saving…' }
  try {
    var res = await fetch(API_BASE + '/platform/tenants/' + _tcTenantId, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify(payload),
    })
    if (res.ok) {
      if (msg) { msg.style.color = '#16a34a'; msg.textContent = '&#x2713; Plan saved' }
    } else {
      var data = await res.json()
      if (msg) { msg.style.color = '#dc2626'; msg.textContent = data.error || 'Save failed' }
    }
  } catch (e) {
    if (msg) { msg.style.color = '#dc2626'; msg.textContent = 'Network error' }
  }
}

// ── Toggle product subscription ───────────────────────────────────────────
async function _tcToggleProduct(productId, enable) {
  var track = document.getElementById('prodTrack_' + productId)
  var thumb = document.getElementById('prodThumb_' + productId)
  try {
    var res
    if (enable) {
      res = await fetch(API_BASE + '/platform/tenants/' + _tcTenantId + '/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({ product_id: productId, status: 'active' }),
      })
    } else {
      res = await fetch(
        API_BASE + '/platform/tenants/' + _tcTenantId + '/products/' + productId,
        { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } }
      )
    }
    if (res.ok) {
      if (track) track.style.background = enable ? '#16a34a' : '#d1d5db'
      if (thumb) thumb.style.transform  = enable ? 'translateX(20px)' : 'translateX(0)'
      // Bust tenant config cache
      if (typeof _tenantConfigCache !== 'undefined' && _tcTenantData?.tenant?.slug) {
        delete _tenantConfigCache[_tcTenantData.tenant.slug]
      }
    } else {
      // Revert checkbox on failure
      var cb = document.querySelector('[data-product-id="' + productId + '"]')
      if (cb) cb.checked = !enable
    }
  } catch (e) {
    var cb = document.querySelector('[data-product-id="' + productId + '"]')
    if (cb) cb.checked = !enable
  }
}

// ── Toggle feature flag ────────────────────────────────────────────────────
async function _tcToggleFlag(flagKey, enable) {
  var track = document.getElementById('flagTrack_' + flagKey)
  var thumb = document.getElementById('flagThumb_' + flagKey)
  try {
    var res = await fetch(API_BASE + '/platform/feature-flags', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({
        flag_key:   flagKey,
        tenant_id:  _tcTenantId,
        is_enabled: enable,
      }),
    })
    if (res.ok) {
      if (track) track.style.background = enable ? '#16a34a' : '#d1d5db'
      if (thumb) thumb.style.transform  = enable ? 'translateX(20px)' : 'translateX(0)'
      // Bust tenant config cache
      if (typeof _tenantConfigCache !== 'undefined' && _tcTenantData?.tenant?.slug) {
        delete _tenantConfigCache[_tcTenantData.tenant.slug]
      }
    } else {
      var cb = document.querySelector('[data-flag="' + flagKey + '"]')
      if (cb) cb.checked = !enable
    }
  } catch (e) {
    var cb = document.querySelector('[data-flag="' + flagKey + '"]')
    if (cb) cb.checked = !enable
  }
}

// ── Utility ────────────────────────────────────────────────────────────────
function _escHtml(s) {
  if (s == null) return ''
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}
function _escAttr(s) {
  if (s == null) return ''
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;')
}
