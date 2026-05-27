// ============================================================================
// TENANT CONTEXT — White-label engine
//
// Loads per-tenant configuration from the backend public API and applies:
//   • Branding  (CSS variables for colors, sidebar, login background)
//   • Logo      (updates .sidebar-logo src + page title)
//   • Favicon   (replaces <link rel="icon">)
//   • Products  (list of enabled product slugs for this tenant)
//   • Feature flags (per-tenant flag map used by isTenantFeatureEnabled())
//
// LOADING ORDER: Must be loaded AFTER feature-flags.js and BEFORE sidebar.js
// ============================================================================

// Active tenant config (null = no tenant loaded / platform view)
var tenantConfig = null

// In-memory cache keyed by slug so repeated calls within a session are free
var _tenantConfigCache = {}

// ── Config Loading ─────────────────────────────────────────────────────────

/**
 * Fetch (or restore from cache) the public config for a tenant slug.
 * Applies branding immediately after loading.
 * Safe to call multiple times — returns early if the same slug is already loaded.
 */
async function loadTenantConfig(slug) {
  if (!slug) return

  if (_tenantConfigCache[slug]) {
    tenantConfig = _tenantConfigCache[slug]
    applyTenantBranding(tenantConfig)
    return
  }

  try {
    var res = await fetch(API_BASE + '/public/tenants/' + encodeURIComponent(slug) + '/config')
    if (res.ok) {
      var data = await res.json()
      tenantConfig = data
      _tenantConfigCache[slug] = data
      applyTenantBranding(data)
    } else {
      // Tenant not found or inactive — clear any stale branding
      clearTenantContext()
    }
  } catch (e) {
    // Network error — continue with defaults; don't break the app
  }
}

/**
 * Remove the active tenant context and branding overrides.
 * Called when navigating back to the platform layer.
 */
function clearTenantContext() {
  tenantConfig = null
  var el = document.getElementById('_tenantBrandingStyles')
  if (el) el.remove()
  // Restore page title
  document.title = 'SocioMonkey Platform'
}

// ── Branding Application ───────────────────────────────────────────────────

/**
 * Inject (or update) a <style> block with CSS custom properties derived from
 * the tenant config.  Uses !important only on structural elements so existing
 * component styles are preserved where possible.
 */
function applyTenantBranding(config) {
  if (!config) return

  var primary    = config.primary_color    || '#0284c7'
  var secondary  = config.secondary_color  || '#0ea5e9'
  var accent     = config.accent_color     || '#10b981'
  var sidebarBg  = config.sidebar_bg_color || '#1e293b'
  var loginBg    = config.login_bg_color   || '#f1f5f9'

  // Ensure the style tag exists
  var el = document.getElementById('_tenantBrandingStyles')
  if (!el) {
    el = document.createElement('style')
    el.id = '_tenantBrandingStyles'
    document.head.appendChild(el)
  }

  el.textContent = [
    ':root {',
    '  --tenant-primary:   ' + primary   + ';',
    '  --tenant-secondary: ' + secondary + ';',
    '  --tenant-accent:    ' + accent    + ';',
    '  --tenant-sidebar:   ' + sidebarBg + ';',
    '  --tenant-login-bg:  ' + loginBg   + ';',
    '}',
    // Sidebar background
    '.sidebar { background: var(--tenant-sidebar) !important; }',
    // Primary action buttons
    'button.button { background: var(--tenant-primary) !important; }',
    // Active nav item
    '.nav-item.active {',
    '  background: var(--tenant-primary) !important;',
    '  color: #fff !important;',
    '}',
    // Hover state (semi-transparent primary)
    '.nav-item:not(.active):hover {',
    '  background: ' + _rgbaFromHex(primary, 0.15) + ' !important;',
    '}',
    // Login page background
    '.login-bg-override { background: var(--tenant-login-bg) !important; }',
  ].join('\n')

  // Update favicon
  if (config.favicon_url) {
    var link = document.querySelector("link[rel='icon']")
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = config.favicon_url
  }

  // Update sidebar logo + page title
  _applyLogoAndTitle(config)
}

function _applyLogoAndTitle(config) {
  // Update sidebar logo src
  var logoEl = document.querySelector('.sidebar-logo')
  if (logoEl) {
    if (config.logo_url) {
      logoEl.src = config.logo_url
      logoEl.alt = config.brand_name || config.name || 'Logo'
      logoEl.style.display = ''
    }
  }

  // Update mobile topbar brand text
  var mobileBrand = document.getElementById('mobileBrandText')
  if (mobileBrand) {
    var displayName = config.brand_name || config.name
    if (displayName) mobileBrand.textContent = displayName
  }

  // Update browser tab title
  var displayName = config.brand_name || config.name
  if (displayName) {
    document.title = displayName
  }
}

// Re-apply logo after the sidebar is re-rendered (called from renderApp)
function reapplyTenantBranding() {
  if (tenantConfig) _applyLogoAndTitle(tenantConfig)
}

/** Convert a hex colour + alpha to rgba() string */
function _rgbaFromHex(hex, alpha) {
  if (!hex || hex.length < 7) return 'rgba(0,0,0,' + alpha + ')'
  var r = parseInt(hex.slice(1, 3), 16)
  var g = parseInt(hex.slice(3, 5), 16)
  var b = parseInt(hex.slice(5, 7), 16)
  return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')'
}

// ── Feature Flags ──────────────────────────────────────────────────────────

/**
 * Check whether a feature flag is enabled for the current tenant.
 * Precedence: tenant-specific override > FEATURE_FLAGS default > true (unknown flag)
 */
function isTenantFeatureEnabled(flagKey) {
  if (tenantConfig && tenantConfig.feature_flags) {
    var flags = tenantConfig.feature_flags
    if (typeof flags[flagKey] !== 'undefined') return !!flags[flagKey]
  }
  // Fall back to the definition default
  if (typeof FEATURE_FLAGS !== 'undefined') {
    for (var i = 0; i < FEATURE_FLAGS.length; i++) {
      if (FEATURE_FLAGS[i].key === flagKey) return FEATURE_FLAGS[i].default
    }
  }
  return true  // Unknown flags default to enabled
}

/** Return the array of enabled product slugs for the current tenant. */
function getTenantEnabledProducts() {
  if (tenantConfig && tenantConfig.products && tenantConfig.products.length > 0) {
    return tenantConfig.products
  }
  // Fall back to the products from the login response
  if (typeof availableProducts !== 'undefined' && availableProducts.length > 0) {
    return availableProducts.map(function (p) { return p.slug })
  }
  return ['crm']
}

/**
 * Returns true if this tenant has the given product enabled.
 * Always true for platform owners (they can access everything).
 */
function isTenantProductEnabled(productSlug) {
  if (typeof user !== 'undefined' && user && typeof authIsPlatformUser === 'function' && authIsPlatformUser()) {
    return true
  }
  return getTenantEnabledProducts().indexOf(productSlug) !== -1
}
