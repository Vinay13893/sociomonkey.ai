// ============================================================================
// PRODUCT LAUNCHER � Applications Suite page (/applications)
// v2: Uses PRODUCT_CATALOGUE, clicks navigate to Product Hub (/products/:code)
// ============================================================================

function renderProductLauncher() {
  var el = document.getElementById('platContent')
  if (!el) return

  var activeProducts  = PRODUCT_CATALOGUE.filter(function(p){ return p.active })
  var comingProducts  = PRODUCT_CATALOGUE.filter(function(p){ return !p.active })

  function tileHtml(p, coming) {
    var badge = coming ? '<span class="plat-badge plat-badge-coming" style="position:absolute;top:12px;left:12px;font-size:10px;">Coming Soon</span>' : ''
    return '<div class="plat-app-tile' + (coming ? '" style="opacity:.7;' : '"') + '" ' +
      (coming ? '' : 'onclick="platNavigate(\'product-hub\', { productCode: \'' + p.code + '\' })"') + '>' +
      badge +
      '<button class="plat-app-tile-menu" onclick="event.stopPropagation();platAppMenu(\'' + p.code + '\', event)">&#8942;</button>' +
      '<div class="plat-app-icon-area">' +
        '<i class="' + p.icon + '" style="color:' + p.color + ';"></i>' +
      '</div>' +
      '<div class="plat-app-name">' + p.name + '</div>' +
      '<div class="plat-app-fullname">' + p.fullName + '</div>' +
      '<button class="plat-app-open-btn ' + (coming ? 'inactive' : '') + '"' +
        (coming ? '' : ' onclick="event.stopPropagation();platNavigate(\'product-hub\', { productCode: \'' + p.code + '\' })"') +
        ' style="color:' + (coming ? '#94a3b8' : p.color) + ';">' +
        (coming ? 'Coming Soon' : 'Open Hub <i class="fa-solid fa-arrow-right" style="font-size:11px;"></i>') +
      '</button>' +
    '</div>'
  }

  el.innerHTML =
    '<div class="plat-card" style="margin-bottom:24px;">' +
      '<div style="display:flex;align-items:center;gap:12px;">' +
        '<div style="width:44px;height:44px;background:#f5f3ff;border-radius:12px;display:flex;align-items:center;justify-content:center;">' +
          '<i class="fa-solid fa-border-all" style="color:#8b5cf6;font-size:20px;"></i>' +
        '</div>' +
        '<div>' +
          '<div style="font-size:15px;font-weight:700;color:#0f172a;">SocioMonkey Product Ecosystem</div>' +
          '<div style="font-size:13px;color:#64748b;margin-top:2px;">' + activeProducts.length + ' active products &bull; ' + comingProducts.length + ' coming soon</div>' +
        '</div>' +
        '<div style="margin-left:auto;display:flex;gap:10px;">' +
          '<button class="plat-btn plat-btn-outline plat-btn-sm" onclick="platShowAddProductModal()">' +
            '<i class="fa-solid fa-plus"></i> Add Product' +
          '</button>' +
          '<button class="plat-btn plat-btn-primary plat-btn-sm">' +
            '<i class="fa-solid fa-sliders"></i> Manage' +
          '</button>' +
        '</div>' +
      '</div>' +
    '</div>' +

    '<div class="plat-section-header" style="margin-bottom:14px;">' +
      '<h3 class="plat-section-title">Active Products</h3>' +
      '<span class="plat-badge plat-badge-active" style="font-size:12px;padding:3px 12px;">' + activeProducts.length + ' products</span>' +
    '</div>' +
    '<div class="plat-apps-grid-full" style="margin-bottom:32px;">' +
      activeProducts.map(function(p){ return tileHtml(p, false) }).join('') +
    '</div>' +

    '<div class="plat-section-header" style="margin-bottom:14px;">' +
      '<h3 class="plat-section-title">Coming Soon</h3>' +
      '<span class="plat-badge plat-badge-coming" style="font-size:12px;padding:3px 12px;">' + comingProducts.length + ' in development</span>' +
    '</div>' +
    '<div class="plat-apps-grid-full">' +
      comingProducts.map(function(p){ return tileHtml(p, true) }).join('') +
    '</div>'
}

// -- Add product modal (stub) -------------------------------------------------

function platShowAddProductModal() {
  showToast('Product marketplace coming soon! Contact support to request a new product.', 'warning')
}
