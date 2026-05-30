// ============================================================================
// SOCIOMONKEY DESIGN SYSTEM — Theme Utilities
//
// Lightweight helpers for reading / applying design tokens at runtime.
// Used by tenant-context.js and any JS that needs to manipulate CSS vars.
//
// Tenants may ONLY set: accent, accentDark, accentSoft, sidebarBg, loginBg.
// All other design tokens are Sociomonkey-owned and must not be overridden.
// ============================================================================

/* eslint-disable */
var SMTheme = {

  /** Read a CSS custom property from :root */
  get: function (varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim()
  },

  /** Write a CSS custom property to :root */
  set: function (varName, value) {
    document.documentElement.style.setProperty(varName, value)
  },

  /**
   * Apply tenant branding overrides.
   * Only the five permitted tenant variables are touched.
   * @param {{ accent?: string, accentDark?: string, accentSoft?: string,
   *            sidebarBg?: string, loginBg?: string }} opts
   */
  applyTenant: function (opts) {
    if (!opts) return
    if (opts.accent)     this.set('--tenant-accent',      opts.accent)
    if (opts.accentDark) this.set('--tenant-accent-dark', opts.accentDark)
    if (opts.accentSoft) this.set('--tenant-accent-soft', opts.accentSoft)
    if (opts.sidebarBg)  this.set('--tenant-sidebar-bg',  opts.sidebarBg)
    if (opts.loginBg)    this.set('--tenant-login-bg',    opts.loginBg)
  },

  /** Reset tenant slots to Sociomonkey brand defaults */
  resetTenant: function () {
    this.applyTenant({
      accent:     '#de2e2e',
      accentDark: '#c22828',
      accentSoft: 'rgba(222,46,46,.10)',
      sidebarBg:  '#c22828',
      loginBg:    '#ffffff',
    })
  },

  /** Update the sidebar brand section with tenant data */
  applySidebarBrand: function (opts) {
    // Logo
    var logoEl = document.querySelector('.sm-sidebar-logo')
    if (logoEl) {
      if (opts.logoUrl) {
        logoEl.src = opts.logoUrl
        logoEl.alt = opts.companyName || 'Logo'
        logoEl.style.display = ''
      }
    }
    // Company name
    var companyEl = document.getElementById('sidebarCompanyName')
    if (companyEl && opts.companyName) {
      companyEl.textContent = opts.companyName
    }
    // Product label
    var productEl = document.getElementById('sidebarProductLabel')
    if (productEl && opts.productName) {
      productEl.textContent = opts.productName
      productEl.style.display = ''
    }
    // Mobile topbar brand text
    var mobileEl = document.getElementById('mobileBrandText')
    if (mobileEl && opts.companyName) {
      mobileEl.textContent = opts.companyName
    }
  },
}
