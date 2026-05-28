async function renderPlatformTenants() {
  const content = document.getElementById('content')
  content.innerHTML = `<div style="padding:24px;"><h2>🌐 Platform Admin</h2><p style="color:#64748b;">Loading…</p></div>`

  const res = await fetch(`${API_BASE}/platform/analytics`, {
    headers: { 'Authorization': `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    content.innerHTML = `<div style="padding:24px;"><p style="color:#dc2626;">Failed to load: ${err.error || res.status}</p></div>`
    return
  }
  const data = await res.json()
  const { stats, tenants } = data

  content.innerHTML = `
  <div style="padding:24px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
      <h2 style="margin:0;">🌐 SocioMonkey Platform Admin</h2>
      <button class="button" onclick="showCreateTenantModal()">+ New Tenant</button>
    </div>
    ${platformTabBar()}

    <!-- Stats row -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px;">
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#1e3a5f;">${stats.total_tenants}</div>
        <div style="color:#64748b;font-size:13px;">Total Tenants</div>
      </div>
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#16a34a;">${stats.active_tenants}</div>
        <div style="color:#64748b;font-size:13px;">Active Tenants</div>
      </div>
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#3b82f6;">${stats.total_users}</div>
        <div style="color:#64748b;font-size:13px;">Total Users</div>
      </div>
      <div class="card" style="text-align:center;padding:20px;">
        <div style="font-size:28px;font-weight:700;color:#8b5cf6;">${stats.total_leads}</div>
        <div style="color:#64748b;font-size:13px;">Total Leads</div>
      </div>
    </div>

    <!-- Tenants table -->
    <div class="card" style="overflow:auto;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#f1f5f9;">
            <th style="padding:10px 12px;text-align:left;">Tenant</th>
            <th style="padding:10px 12px;text-align:left;">Slug</th>
            <th style="padding:10px 12px;text-align:left;">Plan</th>
            <th style="padding:10px 12px;text-align:center;">Users</th>
            <th style="padding:10px 12px;text-align:center;">Leads</th>
            <th style="padding:10px 12px;text-align:center;">Status</th>
            <th style="padding:10px 12px;text-align:center;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${tenants.map(t => `
            <tr style="border-top:1px solid #e2e8f0;">
              <td style="padding:10px 12px;font-weight:600;">${escape(t.name)}</td>
              <td style="padding:10px 12px;font-family:monospace;color:#64748b;">${escape(t.slug)}</td>
              <td style="padding:10px 12px;">${escape(t.plan)}</td>
              <td style="padding:10px 12px;text-align:center;">${t.user_count}</td>
              <td style="padding:10px 12px;text-align:center;">${t.lead_count}</td>
              <td style="padding:10px 12px;text-align:center;">
                <span style="padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;
                  background:${t.status === 'active' ? '#dcfce7' : '#fee2e2'};
                  color:${t.status === 'active' ? '#16a34a' : '#dc2626'};">
                  ${t.status}
                </span>
              </td>
              <td style="padding:10px 12px;text-align:center;white-space:nowrap;">
                <button class="button" style="font-size:12px;padding:4px 10px;"
                  onclick="toggleTenantStatus(${t.id},'${t.status === 'active' ? 'inactive' : 'active'}','${escape(t.name)}')">
                  ${t.status === 'active' ? 'Deactivate' : 'Activate'}
                </button>
                <button class="button" style="font-size:12px;padding:4px 10px;background:#64748b;color:#fff;margin-left:4px;"
                  onclick="showTenantProductsModal(${t.id},'${escape(t.name)}')">
                  📦 Products
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>

    <!-- Create tenant modal -->
    <div id="createTenantModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center;">
      <div class="card" style="max-width:480px;width:100%;max-height:90vh;overflow-y:auto;">
        <h3>New Tenant</h3>
        <input class="input" id="ctName" placeholder="Tenant name *" />
        <input class="input" id="ctSlug" placeholder="Slug (e.g. acme) *" />
        <input class="input" id="ctAdminEmail" placeholder="Admin email *" />
        <input class="input" id="ctAdminName" placeholder="Admin name" />
        <input class="input" id="ctAdminPassword" placeholder="Admin password (default: Admin@123)" />
        <select class="input" id="ctPlan" style="margin-bottom:8px;">
          <option value="starter">Starter</option>
          <option value="growth">Growth</option>
          <option value="enterprise" selected>Enterprise</option>
        </select>
        <input class="input" id="ctMaxUsers" type="number" value="20" placeholder="Max users" />
        <div id="ctError" style="color:#dc2626;font-size:13px;margin-bottom:8px;"></div>
        <div style="display:flex;gap:8px;">
          <button class="button" onclick="submitCreateTenant()" style="flex:1;">Create</button>
          <button class="button" style="flex:1;background:#64748b;color:#fff;" onclick="document.getElementById('createTenantModal').style.display='none'">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Tenant products modal -->
    <div id="tenantProductsModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center;">
      <div class="card" style="max-width:540px;width:100%;max-height:90vh;overflow-y:auto;">
        <h3 id="tpmTitle">Products</h3>
        <div id="tpmBody"><p style="color:#64748b;">Loading…</p></div>
        <div style="text-align:right;margin-top:12px;">
          <button class="button" style="background:#64748b;color:#fff;" onclick="document.getElementById('tenantProductsModal').style.display='none'">Close</button>
        </div>
      </div>
    </div>
  </div>`
}


async function showTenantProductsModal(tenantId, tenantName) {
  const modal = document.getElementById('tenantProductsModal')
  document.getElementById('tpmTitle').textContent = `📦 Products — ${tenantName}`
  document.getElementById('tpmBody').innerHTML = '<p style="color:#64748b;">Loading…</p>'
  modal.style.display = 'flex'

  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/products`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  if (!res.ok) {
    document.getElementById('tpmBody').innerHTML = '<p style="color:#dc2626;">Failed to load</p>'
    return
  }
  const data = await res.json()
  const subscribed = new Set((data.subscriptions || []).map(s => s.product_id))

  document.getElementById('tpmBody').innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <thead><tr style="background:#f1f5f9;">
        <th style="padding:8px 10px;text-align:left;">Product</th>
        <th style="padding:8px 10px;text-align:center;">Status</th>
        <th style="padding:8px 10px;text-align:center;">Action</th>
      </tr></thead>
      <tbody>
        ${(data.available_products || []).map(p => `
          <tr style="border-top:1px solid #e2e8f0;">
            <td style="padding:8px 10px;">${p.icon || '📦'} <strong>${escape(p.name)}</strong></td>
            <td style="padding:8px 10px;text-align:center;">
              ${subscribed.has(p.id)
                ? `<span style="padding:2px 10px;border-radius:12px;font-size:11px;background:#dcfce7;color:#16a34a;font-weight:600;">Active</span>`
                : `<span style="padding:2px 10px;border-radius:12px;font-size:11px;background:#f1f5f9;color:#94a3b8;">Not subscribed</span>`}
            </td>
            <td style="padding:8px 10px;text-align:center;">
              ${subscribed.has(p.id)
                ? `<button class="button" style="font-size:11px;padding:3px 10px;background:#ef4444;color:#fff;"
                    onclick="tenantUnsubscribeProduct(${tenantId},${p.id})">Revoke</button>`
                : `<button class="button" style="font-size:11px;padding:3px 10px;"
                    onclick="tenantSubscribeProduct(${tenantId},${p.id},'${escape(tenantName)}')">Enable</button>`}
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `
}

async function tenantSubscribeProduct(tenantId, productId, tenantName) {
  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ product_id: productId, status: 'active' }),
  })
  if (res.ok) showTenantProductsModal(tenantId, tenantName)
}

async function tenantUnsubscribeProduct(tenantId, productId) {
  const modal = document.getElementById('tenantProductsModal')
  const title = document.getElementById('tpmTitle').textContent.replace('📦 Products — ', '')
  if (!await confirmDialog('Remove this product subscription?', 'Remove')) return
  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/products/${productId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` },
  })
  if (res.ok) showTenantProductsModal(tenantId, title)
}


function showCreateTenantModal() {
  const modal = document.getElementById('createTenantModal')
  if (modal) { modal.style.display = 'flex' }
}

async function submitCreateTenant() {
  const name = document.getElementById('ctName').value.trim()
  const slug = document.getElementById('ctSlug').value.trim()
  const adminEmail = document.getElementById('ctAdminEmail').value.trim()
  const adminName = document.getElementById('ctAdminName').value.trim()
  const adminPassword = document.getElementById('ctAdminPassword').value.trim()
  const plan = document.getElementById('ctPlan').value
  const maxUsers = parseInt(document.getElementById('ctMaxUsers').value) || 20
  const errEl = document.getElementById('ctError')
  errEl.textContent = ''
  if (!name || !slug) { errEl.textContent = 'Name and slug are required'; return }
  try {
    const res = await fetch(`${API_BASE}/platform/tenants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ name, slug, admin_email: adminEmail, admin_name: adminName,
        admin_password: adminPassword || 'Admin@123', plan, max_users: maxUsers }),
    })
    const data = await res.json()
    if (!res.ok) { errEl.textContent = data.error || 'Failed to create tenant'; return }
    document.getElementById('createTenantModal').style.display = 'none'
    renderPlatformAdmin()
  } catch(e) { errEl.textContent = 'Network error' }
}

async function toggleTenantStatus(tenantId, newStatus, name) {
  if (!await confirmDialog('Set &quot;' + escape(name) + '&quot; to ' + escape(newStatus) + '?', 'Confirm', newStatus === 'active' ? '#10b981' : '#ef4444')) return
  const res = await fetch(`${API_BASE}/platform/tenants/${tenantId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ status: newStatus }),
  })
  if (res.ok) renderPlatformAdmin()
}

// ============================================================================
