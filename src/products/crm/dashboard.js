async function renderDashboard() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div style="max-width:1600px;margin:0 auto;padding:0;">
      <div class="dash-header-row">
        <div>
          <h2 class="dash-title">Dashboard</h2>
          <p style="margin:0;color:#64748b;font-size:13px;">Performance snapshot for ${escape(user.name)}</p>
        </div>
        <div class="dash-filters">
          <div>
            <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">Time Range</label>
            <select id="dashRangeFilter" class="select dash-filter-sel">
              <option value="">All Time</option>
              <option value="today">Today</option>
              <option value="this_week" selected>This Week</option>
              <option value="this_month">This Month</option>
              <option value="last_30_days">Last 30 Days</option>
              <option value="custom">Custom Date</option>
            </select>
          </div>
          <div id="dashCustomRange" style="display:none;gap:6px;align-items:flex-end;">
            <div>
              <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">From</label>
              <input type="date" id="dashDateFrom" class="select dash-filter-sel" style="padding:7px 10px;" />
            </div>
            <div>
              <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">To</label>
              <input type="date" id="dashDateTo" class="select dash-filter-sel" style="padding:7px 10px;" />
            </div>
          </div>
          <div>
            <label style="font-size:11px;font-weight:600;color:#64748b;display:block;margin-bottom:5px;">Project</label>
            <select id="dashProjectFilter" class="select dash-filter-sel">
              <option value="">All Projects</option>
            </select>
          </div>
        </div>
      </div>

      <div id="kpiSection" class="dash-kpi-grid">
        ${['Total Leads','Site Visit Planned','Site Visit Done','Warm Rate'].map(l=>`
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(2,6,23,0.08);">
            <div style="font-size:11px;color:#64748b;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">${l}</div>
            <div style="margin-top:8px;height:32px;background:#f1f5f9;border-radius:6px;animation:_loaderBar 1.4s infinite;"></div>
          </div>`).join('')}
      </div>

      <div class="dash-charts-row">
        <div class="card" style="padding:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <h3 style="margin:0;font-size:15px;color:#0f172a;">Drip Lead Funnel</h3>
          </div>
          <div id="dashFunnel"><div style="display:flex;align-items:center;justify-content:center;padding:40px;color:#9ca3af;font-size:13px;"><span style="animation:spin 1s linear infinite;display:inline-block;border:3px solid #e5e7eb;border-top-color:#6366f1;border-radius:50%;width:22px;height:22px;margin-right:10px;"></span>Loading…</div></div>
        </div>
        <div class="card" style="padding:16px;display:flex;flex-direction:column;">
          <h3 style="margin:0 0 8px;font-size:15px;color:#0f172a;">Leads by Source</h3>
          <div id="dashSourceChart" class="dash-source-inner"><div style="display:flex;align-items:center;justify-content:center;padding:40px;color:#9ca3af;font-size:13px;"><span style="animation:spin 1s linear infinite;display:inline-block;border:3px solid #e5e7eb;border-top-color:#6366f1;border-radius:50%;width:22px;height:22px;margin-right:10px;"></span>Loading…</div></div>
        </div>
        <div class="card" style="padding:16px;display:flex;flex-direction:column;">
          <h3 style="margin:0 0 10px;font-size:15px;color:#0f172a;">Leads by Project</h3>
          <div id="dashProjectBars" style="flex:1;display:flex;flex-direction:column;gap:8px;"><div style="display:flex;align-items:center;color:#9ca3af;font-size:13px;"><span style="animation:spin 1s linear infinite;display:inline-block;border:3px solid #e5e7eb;border-top-color:#6366f1;border-radius:50%;width:22px;height:22px;margin-right:10px;"></span>Loading…</div></div>
        </div>
      </div>

      <div class="card" style="padding:18px 18px 16px;">
        <h3 style="margin:0 0 12px;font-size:15px;color:#0f172a;">Lead Status Distribution</h3>
        <div id="statusGrid" class="dash-status-grid"><div style="display:flex;align-items:center;color:#9ca3af;font-size:13px;padding:12px 0;"><span style="animation:spin 1s linear infinite;display:inline-block;border:3px solid #e5e7eb;border-top-color:#6366f1;border-radius:50%;width:22px;height:22px;margin-right:10px;"></span>Loading…</div></div>
      </div>
    </div>
  `

  const projectSel = document.getElementById('dashProjectFilter')
  const rangeSel   = document.getElementById('dashRangeFilter')

  // Fire the dashboard stats request in parallel with the project list fetch.
  // Both hit Railway simultaneously — total time = max(projects, stats) not the sum.
  // Use _apiAuthHeaders() so X-Tenant-Slug is included when platform owner views a tenant.
  const _initStatsProm = fetch(
    API_BASE + '/leads/dashboard/stats?range=this_week',
    { headers: _apiAuthHeaders() }
  ).then(function(r) { return r.json() }).catch(function() { return null })

  await loadProjects()
  projects.forEach(p => {
    const opt = document.createElement('option')
    opt.value = p.id
    opt.textContent = p.name
    projectSel.appendChild(opt)
  })

  const SOURCE_COLORS = ['#3b82f6', '#14b8a6', '#f59e0b', '#8b5cf6', '#ef4444', '#64748b', '#10b981']

  function kpiCard(label, value, subtext, accent) {
    return `
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(2,6,23,0.08);">
        <div style="font-size:11px;color:#64748b;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">${label}</div>
        <div style="font-size:30px;font-weight:800;line-height:1.15;color:${accent};margin-top:4px;">${value}</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">${subtext}</div>
      </div>
    `
  }

  function renderStatusGrid(counts, totalLeads) {
    const grid = document.getElementById('statusGrid')
    const totalStages = STATUS_ORDER
      .filter(s => !['assigned', 'unassigned'].includes(s))
      .reduce((sum, s) => sum + (counts[s] || 0), 0)

    grid.innerHTML = STATUS_ORDER.map(status => {
      const cfg = STATUS_COLORS[status] || { bg: '#f1f5f9', color: '#334155', label: status }
      const count = counts[status] || 0
      const isAssignment = status === 'assigned' || status === 'unassigned'
      const pct = isAssignment
        ? (totalLeads > 0 ? (count / totalLeads * 100).toFixed(0) + '%' : '0%')
        : (totalStages > 0 ? (count / totalStages * 100).toFixed(0) + '%' : '0%')
      return `
        <div style="background:${cfg.bg};border:1px solid #e2e8f0;border-radius:10px;padding:11px;text-align:center;">
          <div style="font-size:11px;font-weight:700;color:${cfg.color};text-transform:uppercase;letter-spacing:0.04em;">${cfg.label}</div>
          <div style="font-size:24px;font-weight:800;color:${cfg.color};line-height:1.2;margin-top:4px;">${count}</div>
          <div style="font-size:10px;color:#64748b;">${pct}</div>
        </div>
      `
    }).join('')
  }

  function renderFunnel(counts, totalLeads) {
    const stages = [
      { key: 'new',            label: 'New Leads',      color: '#3b82f6' },
      { key: 'connected',      label: 'Contacted',      color: '#14b8a6' },
      { key: 'interested',     label: 'Interested',     color: '#f59e0b' },
      { key: 'site_visit_done',label: 'Site Visit Done',color: '#8b5cf6' },
      { key: 'negotiation',    label: 'Negotiation',    color: '#ef4444' },
    ]
    const values = stages.map(s => counts[s.key] || 0)
    // Percentage = stage count / total leads (all statuses) â€” future-ready:
    // correctly reflects each stage's share of ALL leads regardless of filters.
    const total = Math.max(totalLeads || 0, 1)

    // SVG funnel: true trapezoid polygons stacked edge-to-edge.
    // Each stage's bottom edge = next stage's top edge â†’ no gaps.
    const W = 200, H = 230, N = stages.length
    const SH = H / N          // stage height = 46px
    const topW = W, botW = 28 // funnel mouth width and tip width (scaled up)
    const wAtY = y => topW - (topW - botW) * (y / H)

    const svgContent = stages.map((s, i) => {
      const y0 = i * SH,       y1 = (i + 1) * SH
      const w0 = wAtY(y0),     w1 = wAtY(y1)
      const x0l = (W - w0) / 2, x0r = (W + w0) / 2
      const x1l = (W - w1) / 2, x1r = (W + w1) / 2
      const v = values[i]
      return `
        <polygon points="${x0l},${y0} ${x0r},${y0} ${x1r},${y1} ${x1l},${y1}" fill="${s.color}"/>
        <text x="${W / 2}" y="${(y0 + y1) / 2}" text-anchor="middle" dominant-baseline="central"
              fill="white" font-size="15" font-weight="bold" font-family="-apple-system,Arial,sans-serif">${v.toLocaleString()}</text>
      `
    }).join('')

    const legendRows = stages.map((s, i) => {
      const v = values[i]
      const pct = ((v / total) * 100).toFixed(1)
      return `
        <div style="min-height:${SH}px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:2px 0;">
          <span style="width:10px;height:10px;border-radius:50%;background:${s.color};flex-shrink:0;"></span>
          <span style="color:#334155;font-size:11.5px;font-weight:500;flex:1;min-width:60px;">${s.label}</span>
          <span style="color:#0f172a;font-size:11.5px;font-weight:700;white-space:nowrap;flex-shrink:0;">${v.toLocaleString()} (${pct}%)</span>
        </div>
      `
    }).join('')

    document.getElementById('dashFunnel').innerHTML = `
      <div class="dash-funnel-inner">
        <svg viewBox="0 0 ${W} ${H}" class="dash-funnel-svg">${svgContent}</svg>
        <div class="dash-funnel-legend">${legendRows}</div>
      </div>
    `
  }

  function renderSourcePie(sourceStats) {
    const container = document.getElementById('dashSourceChart')
    if (!sourceStats.length) {
      container.innerHTML = `
        <svg viewBox="0 0 140 140" class="dash-source-svg">
          <circle cx="70" cy="70" r="66" fill="none" stroke="#e2e8f0" stroke-width="26"/>
          <text x="70" y="65" text-anchor="middle" dominant-baseline="central"
                font-size="13" fill="#94a3b8" font-family="-apple-system,Arial,sans-serif">No data</text>
          <text x="70" y="82" text-anchor="middle" dominant-baseline="central"
                font-size="11" fill="#cbd5e1" font-family="-apple-system,Arial,sans-serif">for range</text>
        </svg>
        <div class="dash-source-legend" style="padding-left:48px;color:#94a3b8;font-size:12px;display:flex;align-items:center;">No source data</div>
      `
      return
    }

    const items = sourceStats.slice(0, 7)
    const total = items.reduce((s, d) => s + (d.count || 0), 0) || 1

    // SVG donut geometry
    const CX = 70, CY = 70, OR = 66, IR = 40
    const toXY = (angle, r) => ({ x: CX + r * Math.cos(angle), y: CY + r * Math.sin(angle) })

    let a = -Math.PI / 2  // start at top
    const paths = items.map((s, i) => {
      const sweep = (s.count / total) * 2 * Math.PI
      // Prevent degenerate path when segment is full circle
      const end = a + (sweep >= 2 * Math.PI ? sweep - 0.0001 : sweep)
      const large = sweep > Math.PI ? 1 : 0
      const p1 = toXY(a, OR),  p2 = toXY(end, OR)
      const p3 = toXY(end, IR), p4 = toXY(a, IR)
      const color = SOURCE_COLORS[i % SOURCE_COLORS.length]
      const path = `<path d="M${p1.x} ${p1.y} A${OR} ${OR} 0 ${large} 1 ${p2.x} ${p2.y} L${p3.x} ${p3.y} A${IR} ${IR} 0 ${large} 0 ${p4.x} ${p4.y}Z" fill="${color}"/>`
      a = end
      return path
    }).join('')

    const n = items.length
    const svgH = 202
    const rowH = Math.floor(svgH / n)
    const fz = n > 5 ? '11px' : '12px'

    const svg = `
      <svg viewBox="0 0 140 140" class="dash-source-svg">
        ${paths}
        <text x="70" y="62" text-anchor="middle" dominant-baseline="central"
              font-size="24" font-weight="800" fill="#0f172a"
              font-family="-apple-system,Arial,sans-serif">${total.toLocaleString()}</text>
        <text x="70" y="81" text-anchor="middle" dominant-baseline="central"
              font-size="11" fill="#94a3b8"
              font-family="-apple-system,Arial,sans-serif">Total</text>
      </svg>`

    const rows = items.map((s, i) => {
      const pct = Math.round((s.count / total) * 100)
      const color = SOURCE_COLORS[i % SOURCE_COLORS.length]
      return `
        <div style="min-height:${rowH}px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:2px 0;">
          <span style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0;"></span>
          <span style="flex:1;color:#334155;font-size:${fz};font-weight:500;min-width:60px;overflow:hidden;text-overflow:ellipsis;">${escape(s.source)}</span>
          <span style="color:#0f172a;font-size:${fz};font-weight:700;white-space:nowrap;flex-shrink:0;padding-left:8px;">${pct}% (${s.count.toLocaleString()})</span>
        </div>`
    }).join('')

    container.innerHTML = `
      ${svg}
      <div class="dash-source-legend">${rows}</div>`
  }

  function renderProjectBars(projectStats) {
    const wrap = document.getElementById('dashProjectBars')
    const rows = (projectStats || []).slice().sort((a, b) => (b.total || 0) - (a.total || 0)).slice(0, 6)
    if (!rows.length) {
      wrap.innerHTML = '<div style="font-size:12px;color:#94a3b8;">No project data</div>'
      return
    }
    const max = Math.max(...rows.map(r => r.total || 0), 1)
    const BAR_COLORS = [
      ['#3b82f6','#60a5fa'],
      ['#14b8a6','#2dd4bf'],
      ['#f59e0b','#fbbf24'],
      ['#8b5cf6','#a78bfa'],
      ['#ef4444','#f87171'],
      ['#10b981','#34d399'],
    ]
    wrap.innerHTML = rows.map((r, i) => {
      const width = Math.max(4, Math.round(((r.total || 0) / max) * 100))
      const [c1, c2] = BAR_COLORS[i % BAR_COLORS.length]
      return `
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0;">
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#334155;margin-bottom:4px;gap:8px;">
            <span style="display:flex;align-items:center;gap:6px;overflow:hidden;">
              <span style="width:8px;height:8px;border-radius:50%;background:${c1};flex-shrink:0;"></span>
              <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escape(r.project_name)}</span>
            </span>
            <span style="color:#0f172a;font-weight:700;flex-shrink:0;">${r.total || 0}</span>
          </div>
          <div style="height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden;">
            <div style="height:8px;width:${width}%;background:linear-gradient(90deg,${c1},${c2});border-radius:999px;"></div>
          </div>
        </div>
      `
    }).join('')
  }

  async function refreshDashboardViews(_preData) {
    const params = new URLSearchParams()
    const rangeVal = rangeSel.value
    const projectVal = projectSel.value

    if (rangeVal === 'custom') {
      const df = document.getElementById('dashDateFrom')?.value
      const dt = document.getElementById('dashDateTo')?.value
      if (df) params.set('date_from', df)
      if (dt) params.set('date_to', dt)
    } else {
      if (rangeVal) params.set('range', rangeVal)
    }
    if (projectVal) params.set('project_id', projectVal)

    let data = (_preData && !projectVal) ? _preData : null
    if (!data) {
      const url = `${API_BASE}/leads/dashboard/stats${params.toString() ? `?${params.toString()}` : ''}`
      const res = await fetch(url, { headers: _apiAuthHeaders() })
      data = await res.json()
    }
    const stats = data.stats || {}
    const totalLeads = stats.total_leads || stats.my_leads || 0

    document.getElementById('kpiSection').innerHTML = `
      ${kpiCard('Total Leads', totalLeads, 'within selected filters', '#1d4ed8')}
      ${kpiCard('Site Visit Planned', stats.status_counts?.site_visit_planned || 0, 'leads with visits scheduled', '#7c3aed')}
      ${kpiCard('Site Visit Done', stats.status_counts?.site_visit_done || 0, 'completed site visits', '#059669')}
      ${kpiCard('Warm Rate', `${(stats.warm_rate || 0).toFixed(1)}%`, 'interested leads share', '#c2410c')}
    `

    renderFunnel(stats.status_counts || {}, totalLeads)
    renderSourcePie(stats.source_stats || [])
    renderProjectBars(stats.project_stats || [])
    renderStatusGrid(stats.status_counts || {}, totalLeads)
  }

  rangeSel.addEventListener('change', () => {
    const customRow = document.getElementById('dashCustomRange')
    customRow.style.display = rangeSel.value === 'custom' ? 'flex' : 'none'
    if (rangeSel.value !== 'custom') refreshDashboardViews()
  })
  document.getElementById('dashDateFrom').addEventListener('change', () => { if (rangeSel.value === 'custom') refreshDashboardViews() })
  document.getElementById('dashDateTo').addEventListener('change',   () => { if (rangeSel.value === 'custom') refreshDashboardViews() })
  projectSel.addEventListener('change', refreshDashboardViews)
  // Use the already-in-flight stats data (fetched in parallel with loadProjects)
  refreshDashboardViews(await _initStatsProm)
}

