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
  if (!await confirmDialog((newActive ? 'Activate' : 'Deactivate') + ' &quot;' + escape(name) + '&quot;?', newActive ? 'Activate' : 'Deactivate', newActive ? '#10b981' : '#ef4444')) return
  const res = await fetch(`${API_BASE}/platform/products/${productId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ is_active: newActive }),
  })
  if (res.ok) renderPlatformProducts()
}

