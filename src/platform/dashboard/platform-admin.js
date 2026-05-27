// ============================================================================
// PLATFORM ADMIN - Entry point and tab switcher
// ============================================================================

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

