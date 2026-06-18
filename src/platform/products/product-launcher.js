// ============================================================================
// PRODUCT LAUNCHER - Applications Suite page
// ============================================================================

function renderProductLauncher() {
  var el = document.getElementById('platContent')
  if (!el) return

  var platformApps = platformCatalogueApps()
  var comingSoonApps = platformComingSoonApps()

  el.innerHTML =
    '<div class="plat-card" style="margin-bottom:24px;">' +
      '<div style="display:flex;align-items:center;gap:12px;">' +
        '<div style="width:44px;height:44px;background:#eff6ff;border-radius:12px;display:flex;align-items:center;justify-content:center;">' +
          '<i class="fa-solid fa-border-all" style="color:#2563eb;font-size:20px;"></i>' +
        '</div>' +
        '<div>' +
          '<div style="font-size:15px;font-weight:700;color:#0f172a;">Sociomonkey Application Catalogue</div>' +
          '<div style="font-size:13px;color:#64748b;margin-top:2px;">' + platformApps.length + ' platform apps &bull; ' + comingSoonApps.length + ' coming soon</div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    '<div class="plat-section-header" style="margin-bottom:14px;">' +
      '<h3 class="plat-section-title">Live Apps</h3>' +
      '<span class="plat-badge plat-badge-active" style="font-size:12px;padding:3px 12px;">' + platformApps.length + ' apps</span>' +
    '</div>' +
    '<div class="plat-apps-grid-full" style="margin-bottom:32px;">' +
      platformApps.map(platLauncherTile).join('') +
    '</div>' +

    '<div class="plat-section-header" style="margin-bottom:14px;">' +
      '<h3 class="plat-section-title">Coming Soon</h3>' +
      '<span class="plat-badge plat-badge-coming" style="font-size:12px;padding:3px 12px;">' + comingSoonApps.length + ' planned</span>' +
    '</div>' +
    '<div class="plat-apps-grid-full">' +
      comingSoonApps.map(platLauncherComingSoonTile).join('') +
    '</div>'
}

function platLauncherTile(p) {
  var statusClass = p.lifecycle === 'live' ? 'plat-badge-active' : 'plat-badge-warning'
  var demo = p.demoAvailable
    ? '<span class="plat-badge plat-badge-info" style="margin-left:6px;">' + platLauncherEsc(p.demoLabel || 'Demo Available') + '</span>'
    : ''
  return '<div class="plat-app-tile" onclick="platNavigate(\'product-hub\', { productCode: \'' + platLauncherEsc(p.code) + '\' })">' +
    '<div style="position:absolute;top:12px;left:12px;">' +
      '<span class="plat-badge ' + statusClass + '">' + platLauncherEsc(p.statusLabel) + '</span>' + demo +
    '</div>' +
    '<div class="plat-app-icon-area">' +
      '<i class="' + p.icon + '" style="color:' + p.color + ';"></i>' +
    '</div>' +
    '<div class="plat-app-name">' + platLauncherEsc(p.name) + '</div>' +
    '<div class="plat-app-fullname">' + platLauncherEsc(p.fullName) + '</div>' +
    '<button class="plat-app-open-btn" onclick="event.stopPropagation();platNavigate(\'product-hub\', { productCode: \'' + platLauncherEsc(p.code) + '\' })" style="color:' + p.color + ';">' +
      'Open Hub <i class="fa-solid fa-arrow-right" style="font-size:11px;"></i>' +
    '</button>' +
  '</div>'
}

function platLauncherComingSoonTile(p) {
  return '<div class="plat-app-tile" style="opacity:.72;">' +
    '<div style="position:absolute;top:12px;left:12px;">' +
      '<span class="plat-badge plat-badge-coming">' + platLauncherEsc(p.statusLabel) + '</span>' +
    '</div>' +
    '<div class="plat-app-icon-area">' +
      '<i class="' + p.icon + '" style="color:' + p.color + ';"></i>' +
    '</div>' +
    '<div class="plat-app-name">' + platLauncherEsc(p.name) + '</div>' +
    '<div class="plat-app-fullname">' + platLauncherEsc(p.fullName) + '</div>' +
    '<button class="plat-app-open-btn inactive" disabled style="color:#94a3b8;">Coming Soon</button>' +
  '</div>'
}

function platLauncherEsc(value) {
  if (value === null || typeof value === 'undefined') return ''
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
}

function platShowAddProductModal() {
  showToast('Product marketplace coming soon! Contact support to request a new product.', 'warning')
}
