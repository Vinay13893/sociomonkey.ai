// Platform Analytics & Reports — stub view with KPI placeholders.

async function renderPlatformAnalytics() {
  const el = document.getElementById('platContent');
  if (!el) return;

  let stats = {};
  try {
    const res = await fetch(`${API_BASE}/platform/analytics`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) { const d = await res.json(); stats = d.stats || {}; }
  } catch (e) {}

  const kpis = [
    { label: 'Total Users',      value: (stats.total_users   || 0).toLocaleString(), icon: '👤', bg: '#ede9fe' },
    { label: 'Total Tenants',    value: (stats.total_tenants || 0).toLocaleString(), icon: '🏢', bg: '#dcfce7' },
    { label: 'Active Tenants',   value: (stats.active_tenants|| 0).toLocaleString(), icon: '✅', bg: '#fff7ed' },
    { label: 'Total Leads (CRM)',value: (stats.total_leads   || 0).toLocaleString(), icon: '📋', bg: '#eff6ff' },
  ];

  const kpiHtml = kpis.map(k => `
    <div class="plat-stat-card">
      <div class="plat-stat-card-top">
        <div class="plat-stat-label">${k.label}</div>
        <div class="plat-stat-icon" style="background:${k.bg};">${k.icon}</div>
      </div>
      <div class="plat-stat-value">${k.value}</div>
    </div>`).join('');

  el.innerHTML = `
    <div class="plat-stats-grid">${kpiHtml}</div>

    <div class="plat-card">
      <div class="plat-chart-header" style="margin-bottom:20px;">
        <span class="plat-chart-title">Platform Growth</span>
        <select class="plat-chart-filter"><option>Last 30 days</option><option>Last 90 days</option></select>
      </div>
      <div class="plat-empty">
        <div class="plat-empty-icon">📊</div>
        <div class="plat-empty-title">Advanced analytics coming soon</div>
        <div class="plat-empty-desc">Detailed charts, cohort analysis, and export features will be available here.</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
      <div class="plat-card">
        <div class="plat-chart-title" style="margin-bottom:14px;">Top Products by Usage</div>
        ${['CRM', 'LMS', 'Procurement', '3D Inventory', 'Amazon Intelligence'].map((p, i) => {
          const pcts = [38, 27, 18, 11, 6];
          const colors = ['#6366f1','#22c55e','#f59e0b','#3b82f6','#8b5cf6'];
          return `<div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
              <span style="color:#374151;font-weight:500;">${p}</span>
              <span style="color:#64748b;">${pcts[i]}%</span>
            </div>
            <div style="background:#f1f5f9;border-radius:4px;height:7px;">
              <div style="background:${colors[i]};width:${pcts[i]}%;height:7px;border-radius:4px;"></div>
            </div>
          </div>`;
        }).join('')}
      </div>

      <div class="plat-card">
        <div class="plat-chart-title" style="margin-bottom:14px;">Recent Reports</div>
        <div class="plat-empty" style="padding:24px;">
          <div class="plat-empty-icon" style="font-size:28px;">📄</div>
          <div class="plat-empty-title" style="font-size:14px;">No reports generated yet</div>
          <button class="plat-btn plat-btn-primary plat-btn-sm" style="margin-top:12px;">
            Generate Report
          </button>
        </div>
      </div>
    </div>
  `;
}
