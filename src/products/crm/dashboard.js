// ── Dashboard lifecycle state ─────────────────────────────────────────────
// These live at module scope so a new renderDashboard() call can cancel all
// async callbacks (network requests, DOM writes) from the previous render.
var _dashboardRenderId     = 0    // incremented on every renderDashboard() entry
var _dashboardAbortCtrl    = null // AbortController for the render lifecycle signal
var _dashboardRefreshAbort   = null  // AbortController for filter-triggered refreshes
var _statsPromise            = null  // deduplicated in-flight stats request (shared across renders)
var _dashboardRenderInFlight = false // dedup: prevents concurrent renderDashboard() calls

async function renderDashboard() {  // ── Dedup: if a render is already in flight, skip rather than cancel it ──
  if (_dashboardRenderInFlight) {
    console.warn('[renderDashboard] dedup: render already in flight, skipping')
    return
  }
  _dashboardRenderInFlight = true  // ── Cancel any prior render immediately ───────────────────────────────────
  _dashboardRenderId++
  var myId = _dashboardRenderId
  if (_dashboardAbortCtrl) { _dashboardAbortCtrl.abort(); _dashboardAbortCtrl = null }
  var ctrl = new AbortController()
  _dashboardAbortCtrl = ctrl
  var signal = ctrl.signal

  // Claim global render ownership — any navigation away sets _ACTIVE_ROUTE to a
  // different value which immediately invalidates _guard() for all stale callbacks.
  window._ACTIVE_RENDER_ID = myId
  window._ACTIVE_ROUTE     = 'dashboard'

  // _guard(): true only while THIS render is still the active one on the dashboard route
  function _guard() {
    return myId === _dashboardRenderId
        && !signal.aborted
        && window._ACTIVE_ROUTE === 'dashboard'
  }
  // safeMutate(): ONLY permitted path for all innerHTML mutations in this render.
  // Validates: render token, route, dispatch-in-flight, element existence + connection.
  // Logs every write to [DOM WRITE] and wraps in try/catch to prevent null explosions.
  function safeMutate(elOrId, html) {
    if (!_guard()) { return false }
    if (typeof _dispatchInFlight !== 'undefined' && _dispatchInFlight) { return false }
    var el = typeof elOrId === 'string' ? document.getElementById(elOrId) : elOrId
    if (!el || !el.isConnected) { return false }
    var _id = typeof elOrId === 'string' ? elOrId : (el.id || '(el)')
    console.log('[DOM WRITE]', _id, window._ACTIVE_ROUTE, window._ACTIVE_RENDER_ID)
    try { el.innerHTML = html; return true }
    catch (err) { console.error('[DOM WRITE ERROR]', _id, err); return false }
  }

  _PERF.count('renderDashboard')
  _PERF.mark('renderDashboard')
  var content = document.getElementById('content')
  if (!content) { _dashboardRenderInFlight = false; _PERF.end('renderDashboard'); return }
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
  _PERF.lap('renderDashboard', 'shell-injected')

  const projectSel = document.getElementById('dashProjectFilter')
  const rangeSel   = document.getElementById('dashRangeFilter')

  // ── Stats: stale-while-revalidate — show cached data instantly, refresh in background ──
  var _statsKey = '_ds_' + (platformTenantSlug || 'def') + '_week'
  var _cachedStats = null
  try {
    var _sc = sessionStorage.getItem(_statsKey)
    if (_sc) _cachedStats = JSON.parse(_sc)
  } catch (_e) {}

  // ── Request deduplication: if a stats fetch is already in flight, reuse its promise ────
  if (!_statsPromise) {
    _PERF.mark('stats-api')
    _statsPromise = fetch(
      API_BASE + '/leads/dashboard/stats?range=this_week',
      { headers: _apiAuthHeaders() }   // no AbortSignal — promise is shared across renders
    ).then(function(r) { return r.json() })
     .then(function(data) {
       _PERF.end('stats-api')
       try { sessionStorage.setItem(_statsKey, JSON.stringify(data)) } catch (_e) {}
       return data
     })
     .catch(function() {
       _PERF.cancel('stats-api')
       return null
     })
     .finally(function() { _statsPromise = null })
  }
  var _initStatsProm = _statsPromise

  // ── Projects: populate dropdown in background — don't block event wiring ──
  _PERF.mark('projects-api')
  loadProjects().then(function() {
    if (!_guard()) return  // navigated away — DOM is gone
    _PERF.end('projects-api')
    var selEl = document.getElementById('dashProjectFilter')
    if (!selEl) return
    projects.forEach(function(p) {
      var opt = document.createElement('option')
      opt.value = p.id
      opt.textContent = p.name
      selEl.appendChild(opt)
    })
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
    if (!grid || !grid.isConnected) return  // DOM removed or disconnected
    const totalStages = STATUS_ORDER
      .filter(s => !['assigned', 'unassigned'].includes(s))
      .reduce((sum, s) => sum + (counts[s] || 0), 0)

    var _statusHtml = STATUS_ORDER.map(status => {
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
    safeMutate(grid, _statusHtml)
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

    var _funnelEl = document.getElementById('dashFunnel')
    if (!_funnelEl || !_funnelEl.isConnected) return
    safeMutate(_funnelEl, `
      <div class="dash-funnel-inner">
        <svg viewBox="0 0 ${W} ${H}" class="dash-funnel-svg">${svgContent}</svg>
        <div class="dash-funnel-legend">${legendRows}</div>
      </div>
    `)
  }

  function renderSourcePie(sourceStats) {
    const container = document.getElementById('dashSourceChart')
    if (!container || !container.isConnected) return  // DOM removed or disconnected
    if (!sourceStats.length) {
      safeMutate(container, `
        <svg viewBox="0 0 140 140" class="dash-source-svg">
          <circle cx="70" cy="70" r="66" fill="none" stroke="#e2e8f0" stroke-width="26"/>
          <text x="70" y="65" text-anchor="middle" dominant-baseline="central"
                font-size="13" fill="#94a3b8" font-family="-apple-system,Arial,sans-serif">No data</text>
          <text x="70" y="82" text-anchor="middle" dominant-baseline="central"
                font-size="11" fill="#cbd5e1" font-family="-apple-system,Arial,sans-serif">for range</text>
        </svg>
        <div class="dash-source-legend" style="padding-left:48px;color:#94a3b8;font-size:12px;display:flex;align-items:center;">No source data</div>
      `)
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

    safeMutate(container, `
      ${svg}
      <div class="dash-source-legend">${rows}</div>`)
  }

  function renderProjectBars(projectStats) {
    const wrap = document.getElementById('dashProjectBars')
    if (!wrap || !wrap.isConnected) return  // DOM removed or disconnected
    const rows = (projectStats || []).slice().sort((a, b) => (b.total || 0) - (a.total || 0)).slice(0, 6)
    if (!rows.length) {
      safeMutate(wrap, '<div style="font-size:12px;color:#94a3b8;">No project data</div>')
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
    var _projHtml = rows.map((r, i) => {
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
    safeMutate(wrap, _projHtml)
  }

  async function refreshDashboardViews(_preData) {
    // Guard 1: bail immediately if this render has been superseded by a new renderDashboard()
    if (!_guard()) return
    // Guard 2: abort any in-flight concurrent refresh (rapid filter changes)
    if (_dashboardRefreshAbort) {
      _dashboardRefreshAbort.abort()
      _dashboardRefreshAbort = null
      _PERF.cancel('refreshDashboardViews')  // clean up abandoned mark before re-opening
    }
    var rCtrl = new AbortController()
    _dashboardRefreshAbort = rCtrl

    _PERF.count('refreshDashboardViews')
    _PERF.mark('refreshDashboardViews')
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
      try {
        const res = await fetch(url, { headers: _apiAuthHeaders(), signal: rCtrl.signal })
        data = await res.json()
        if (!projectVal && (rangeVal === 'this_week' || !rangeVal)) {
          try { sessionStorage.setItem(_statsKey, JSON.stringify(data)) } catch (_e) {}
        }
      } catch (err) {
        _PERF.cancel('refreshDashboardViews')
        if (err && err.name === 'AbortError') return  // superseded by newer filter change
        return
      }
    }

    // Re-check after any await — render may have changed while fetching
    if (!_guard() || rCtrl.signal.aborted) {
      _PERF.cancel('refreshDashboardViews')
      return
    }

    _PERF.lap('refreshDashboardViews', 'data-ready src=' + (_preData && !projectVal ? 'pre/cache' : 'network'))
    const stats = data.stats || {}
    const totalLeads = stats.total_leads || stats.my_leads || 0

    var _ct = performance.now()
    safeMutate('kpiSection', `
      ${kpiCard('Total Leads', totalLeads, 'within selected filters', '#1d4ed8')}
      ${kpiCard('Site Visit Planned', stats.status_counts?.site_visit_planned || 0, 'leads with visits scheduled', '#7c3aed')}
      ${kpiCard('Site Visit Done', stats.status_counts?.site_visit_done || 0, 'completed site visits', '#059669')}
      ${kpiCard('Warm Rate', `${(stats.warm_rate || 0).toFixed(1)}%`, 'interested leads share', '#c2410c')}
    `)
    _PERF.lap('refreshDashboardViews', 'kpiSection: ' + (performance.now() - _ct).toFixed(1) + 'ms')

    if (!_guard()) return
    _ct = performance.now()
    renderFunnel(stats.status_counts || {}, totalLeads)
    _PERF.lap('refreshDashboardViews', 'funnel: ' + (performance.now() - _ct).toFixed(1) + 'ms')

    if (!_guard()) return
    _ct = performance.now()
    renderSourcePie(stats.source_stats || [])
    _PERF.lap('refreshDashboardViews', 'sourcePie: ' + (performance.now() - _ct).toFixed(1) + 'ms')

    if (!_guard()) return
    _ct = performance.now()
    renderProjectBars(stats.project_stats || [])
    _PERF.lap('refreshDashboardViews', 'projectBars: ' + (performance.now() - _ct).toFixed(1) + 'ms')

    if (!_guard()) return
    _ct = performance.now()
    renderStatusGrid(stats.status_counts || {}, totalLeads)
    _PERF.lap('refreshDashboardViews', 'statusGrid: ' + (performance.now() - _ct).toFixed(1) + 'ms')
    _PERF.end('refreshDashboardViews')
  }

  rangeSel.addEventListener('change', function() {
    if (!_guard()) return  // stale element — render was superseded
    var customRow = document.getElementById('dashCustomRange')
    if (customRow) customRow.style.display = rangeSel.value === 'custom' ? 'flex' : 'none'
    if (rangeSel.value !== 'custom') refreshDashboardViews()
  })
  document.getElementById('dashDateFrom').addEventListener('change', function() {
    if (_guard() && rangeSel.value === 'custom') refreshDashboardViews()
  })
  document.getElementById('dashDateTo').addEventListener('change', function() {
    if (_guard() && rangeSel.value === 'custom') refreshDashboardViews()
  })
  projectSel.addEventListener('change', function() { if (_guard()) refreshDashboardViews() })

  _PERF.lap('renderDashboard', 'events-wired')
  _PERF.end('renderDashboard')

  // ── Initial hydration: shell is visible; fill with data ──────────────────
  if (_cachedStats) {
    // Cache hit: paint immediately with stale data, revalidate silently in background
    refreshDashboardViews(_cachedStats)
    _initStatsProm.then(function(data) {
      if (!_guard()) return   // navigated away while the network request was in flight
      if (data) refreshDashboardViews(data)
    })
  } else {
    // Cold load: no cache — must await fresh data before painting
    var _freshData = await _initStatsProm
    if (!_guard()) { _dashboardRenderInFlight = false; return }  // navigated away while waiting
    if (_freshData) refreshDashboardViews(_freshData)
  }
  _dashboardRenderInFlight = false
}

