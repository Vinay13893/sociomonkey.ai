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

var _PLATFORM_TAB_TITLE = 'Sociomonkey Admin'
var _DEFAULT_FAVICON = 'Assets/top-banner-logo.png'

// In-memory cache keyed by slug so repeated calls within a session are free
var _tenantConfigCache = {}

// ── Config Loading ─────────────────────────────────────────────────────────

/**
 * Fetch (or restore from cache) the public config for a tenant slug.
 * Applies branding immediately after loading.
 * Safe to call multiple times — returns early if the same slug is already loaded.
 *
 * Cache hierarchy (fastest first):
 *   1. In-memory  (_tenantConfigCache)  — same page session, instant
 *   2. sessionStorage                   — survives page refresh, instant
 *   3. Network fetch                    — cold path, only on first ever load
 */
async function loadTenantConfig(slug) {
  _PERF.mark('loadTenantConfig')
  if (!slug) { _PERF.end('loadTenantConfig'); return }

  // 1. In-memory cache (same page session)
  if (_tenantConfigCache[slug]) {
    _PERF.lap('loadTenantConfig', 'path=memory-cache')
    tenantConfig = _tenantConfigCache[slug]
    applyTenantBranding(tenantConfig)
    _PERF.end('loadTenantConfig')
    return
  }

  // 2. sessionStorage cache (survives page refresh, lost when tab closes)
  try {
    var _stored = sessionStorage.getItem('_tc_' + slug)
    if (_stored) {
      var _cached = JSON.parse(_stored)
      if (_cached) {
        _PERF.lap('loadTenantConfig', 'path=sessionStorage')
        tenantConfig = _cached
        _tenantConfigCache[slug] = _cached
        applyTenantBranding(_cached)
        _PERF.end('loadTenantConfig')
        // Refresh config from network in background — don't await
        _fetchTenantConfig(slug, true)
        return
      }
    }
  } catch (_e) {}

  // 3. Network fetch (cold path — first ever load or after sessionStorage cleared)
  _PERF.lap('loadTenantConfig', 'path=COLD-NETWORK ⚠')
  await _fetchTenantConfig(slug, false)
  _PERF.end('loadTenantConfig')
}

/**
 * Fetch tenant config from the network and update all caches.
 * @param {string} slug   - tenant slug
 * @param {boolean} background - if true, errors are silently ignored
 */
async function _fetchTenantConfig(slug, background) {
  var trace = null
  try {
    if (typeof performance !== 'undefined') {
      trace = {
        traceId: 'tenant-config-' + Date.now(),
        browserRequestStartPerf: performance.now(),
        browserRequestStartAtMs: Date.now(),
      }
      console.log('[PERF]', {
        route: 'tenant_config',
        stage: 'browser_request_start',
        traceId: trace.traceId,
        slug: slug,
        browserRequestStartAtMs: trace.browserRequestStartAtMs,
      })
      trace.apiRequestSentPerf = performance.now()
      trace.apiRequestSentAtMs = Date.now()
      console.log('[PERF]', {
        route: 'tenant_config',
        stage: 'api_request_sent',
        traceId: trace.traceId,
        apiRequestSentAtMs: trace.apiRequestSentAtMs,
      })
    }
    var res = await fetch(API_BASE + '/public/tenants/' + encodeURIComponent(slug) + '/config')
    if (trace && typeof performance !== 'undefined') {
      var totalMs = Math.round((performance.now() - trace.browserRequestStartPerf) * 100) / 100
      var backendMs = Number(res.headers.get('X-Perf-Backend-Duration-Ms') || 0)
      var dbMs = Number(res.headers.get('X-Perf-Db-Duration-Ms') || 0)
      console.log('[PERF]', {
        route: 'tenant_config',
        stage: 'browser_response_received',
        traceId: trace.traceId,
        browserResponseReceivedAtMs: Date.now(),
        serverRequestReceivedAtMs: Number(res.headers.get('X-Perf-Request-Received-At-Ms') || 0),
        serverResponseSentAtMs: Number(res.headers.get('X-Perf-Response-Sent-At-Ms') || 0),
        totalRequestDurationMs: totalMs,
        backendProcessingDurationMs: Math.round(backendMs * 100) / 100,
        databaseDurationMs: Math.round(dbMs * 100) / 100,
        networkDurationMs: Math.round(Math.max(0, totalMs - backendMs) * 100) / 100,
        dbQueryCount: Number(res.headers.get('X-Perf-Db-Query-Count') || 0),
      })
    }
    if (res.ok) {
      var data = await res.json()
      tenantConfig = data
      _tenantConfigCache[slug] = data
      applyTenantBranding(data)
      try { sessionStorage.setItem('_tc_' + slug, JSON.stringify(data)) } catch (_e) {}
    } else if (!background) {
      // Tenant not found or inactive — clear any stale branding
      clearTenantContext()
    }
  } catch (e) {
    if (trace) {
      console.log('[PERF]', {
        route: 'tenant_config',
        stage: 'request_error',
        traceId: trace.traceId,
        message: (e && e.message) || 'Request failed',
      })
    }
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
  document.title = _PLATFORM_TAB_TITLE
  _setFavicon(_DEFAULT_FAVICON)
}

// ── Branding Application ───────────────────────────────────────────────────

/**
 * Inject (or update) a <style> block with CSS custom properties derived from
 * the tenant config.  Uses !important only on structural elements so existing
 * component styles are preserved where possible.
 */
function applyTenantBranding(config) {
  if (!config) return

  // Only these 4 properties are tenant-controlled.
  // Primary buttons and global UI chrome are Sociomonkey-owned (var(--sm-ink)).
  var accent     = config.accent_color     || '#de2e2e'
  var sidebarBg  = '#1f2a37'
  var loginBg    = config.login_bg_color   || '#f1f5f9'

  // Derive darker shade and soft background for the accent
  var accentDark = _darkenHex(accent, 0.15)
  var accentSoft = _rgbaFromHex(accent, 0.10)

  // Ensure the style tag exists
  var el = document.getElementById('_tenantBrandingStyles')
  if (!el) {
    el = document.createElement('style')
    el.id = '_tenantBrandingStyles'
    document.head.appendChild(el)
  }

  // Set tenant CSS variables.
  // All button styles and nav active states resolve via these variables in styles.css.
  el.textContent = [
    ':root {',
    '  --tenant-accent:      ' + accent      + ';',
    '  --tenant-accent-dark: ' + accentDark  + ';',
    '  --tenant-accent-soft: ' + accentSoft  + ';',
    '  --tenant-sidebar-bg:  ' + sidebarBg   + ';',
    '  --tenant-login-bg:    ' + loginBg     + ';',
    '}',
  ].join('\n')

  // Update favicon (tenant-specific if configured; otherwise platform monkey icon)
  _setFavicon(config.favicon_url || _DEFAULT_FAVICON)

  // Update sidebar logo + page title
  _applyLogoAndTitle(config)
}

function _applyLogoAndTitle(config) {
  // Update sidebar logo src (unified .sm-sidebar-logo class)
  var logoEl = document.querySelector('.sm-sidebar-logo')
  if (logoEl) {
    if (config.logo_url) {
      logoEl.src = config.logo_url
      logoEl.alt = config.brand_name || config.name || 'Logo'
      logoEl.style.display = ''
    }
  }

  // Update sidebar company name
  var companyEl = document.getElementById('sidebarCompanyName')
  if (companyEl) {
    var companyName = config.brand_name || config.name || ''
    companyEl.textContent = companyName
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
    document.title = displayName + ' | LMS'
  }
}

function _setFavicon(href) {
  var link = document.querySelector("link[rel='icon']")
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = href || _DEFAULT_FAVICON
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

/** Darken a hex color by a ratio (0–1). Returns a hex string. */
function _darkenHex(hex, ratio) {
  if (!hex || hex.length < 7) return hex
  var r = Math.max(0, Math.round(parseInt(hex.slice(1, 3), 16) * (1 - ratio)))
  var g = Math.max(0, Math.round(parseInt(hex.slice(3, 5), 16) * (1 - ratio)))
  var b = Math.max(0, Math.round(parseInt(hex.slice(5, 7), 16) * (1 - ratio)))
  return '#' + r.toString(16).padStart(2, '0') + g.toString(16).padStart(2, '0') + b.toString(16).padStart(2, '0')
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
