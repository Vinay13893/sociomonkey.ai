// REPORTS
// ============================================================================

var _reportsRenderId = 0

async function renderReports(dateFrom = '', dateTo = '') {
  var myId = ++_reportsRenderId
  const content = document.getElementById('content')
  if (!content) return

  function _fmtLocalInputDate(d) {
    var y = d.getFullYear()
    var m = String(d.getMonth() + 1).padStart(2, '0')
    var day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  function _parseYmd(v) {
    if (!v || !/^\d{4}-\d{2}-\d{2}$/.test(v)) return null
    var parts = v.split('-').map(Number)
    return new Date(parts[0], parts[1] - 1, parts[2])
  }

  function _selectedYear() {
    var from = _parseYmd(document.getElementById('reportDateFrom')?.value || dateFrom)
    var to = _parseYmd(document.getElementById('reportDateTo')?.value || dateTo)
    if (from) return from.getFullYear()
    if (to) return to.getFullYear()
    return new Date().getFullYear()
  }

  // Generate month options
  const monthOptions = Array.from({length:12}, (_,i) =>
    `<option value="${i}">${new Date(2000,i,1).toLocaleString('default',{month:'long'})}</option>`
  ).join('')

  function _formatRangeFromPreset(key) {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    if (key === 'today') {
      return { from: _fmtLocalInputDate(today), to: _fmtLocalInputDate(today) }
    }
    if (key === 'yesterday') {
      const y = new Date(today)
      y.setDate(y.getDate() - 1)
      return { from: _fmtLocalInputDate(y), to: _fmtLocalInputDate(y) }
    }
    if (key === 'last_week') {
      const thisWeekStart = new Date(today)
      thisWeekStart.setDate(thisWeekStart.getDate() - thisWeekStart.getDay() + 1)
      const start = new Date(thisWeekStart)
      start.setDate(start.getDate() - 7)
      const end = new Date(thisWeekStart)
      end.setDate(end.getDate() - 1)
      return { from: _fmtLocalInputDate(start), to: _fmtLocalInputDate(end) }
    }
    if (key === 'last_30_days') {
      const start = new Date(today)
      start.setDate(start.getDate() - 29)
      return { from: _fmtLocalInputDate(start), to: _fmtLocalInputDate(today) }
    }
    if (key === 'this_month') {
      const start = new Date(now.getFullYear(), now.getMonth(), 1)
      return { from: _fmtLocalInputDate(start), to: _fmtLocalInputDate(today) }
    }
    if (key === 'last_month') {
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      const end = new Date(now.getFullYear(), now.getMonth(), 0)
      return { from: _fmtLocalInputDate(start), to: _fmtLocalInputDate(end) }
    }
    return { from: '', to: '' }
  }

  const activeFilter = dateFrom || dateTo
  const fmtD = d => new Date(d).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric'})
  const filterLabel = !activeFilter      ? 'All Time'
    : dateFrom && dateTo ? `${fmtD(dateFrom)} → ${fmtD(dateTo)}`
    : dateFrom           ? `From ${fmtD(dateFrom)}`
    :                      `Until ${fmtD(dateTo)}`

  content.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:16px;">
      <div class="card" style="padding:20px 24px;">
          <div class="sm-page-header" style="margin-bottom:18px;">
            <div>
              <h2 class="sm-page-title">📊 Reports & Analytics</h2>
            <div style="margin-top:4px;display:flex;align-items:center;gap:8px;">
              <span style="font-size:12px;color:#64748b;">Period:</span>
              <span style="font-size:12px;font-weight:600;color:${activeFilter ? '#2563eb' : '#64748b'};background:${activeFilter ? '#eff6ff' : '#f1f5f9'};padding:2px 10px;border-radius:20px;border:1px solid ${activeFilter ? '#bfdbfe' : '#e2e8f0'};">${filterLabel}</span>
            </div>
          </div>
          <button class="sm-btn sm-btn-primary" onclick="downloadLeadReport()">⬇ Export Excel</button>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;">
          <div style="font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:0.08em;margin-bottom:12px;text-transform:uppercase;">🗓 Filter by Date Range</div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;">
            <div style="display:flex;flex-direction:column;gap:5px;flex:1;min-width:130px;">
              <label class="sm-label">FROM</label>
              <input type="date" id="reportDateFrom" class="input" style="font-size:13px;padding:8px 10px;" value="${dateFrom}" />
            </div>
            <div style="display:flex;flex-direction:column;gap:5px;flex:1;min-width:130px;">
              <label class="sm-label">TO</label>
              <input type="date" id="reportDateTo" class="input" style="font-size:13px;padding:8px 10px;" value="${dateTo}" />
            </div>
            <div style="display:flex;flex-direction:column;gap:5px;flex:1;min-width:130px;">
              <label class="sm-label">MONTH QUICK SELECT</label>
              <select id="reportMonth" class="select" style="font-size:13px;padding:8px 10px;">
                <option value="">— Select Month —</option>
                ${monthOptions}
              </select>
            </div>
            <div style="display:flex;flex-direction:column;gap:5px;flex:1;min-width:160px;">
              <label class="sm-label">TEAM RANGE</label>
              <select id="reportTeamRange" class="select" style="font-size:13px;padding:8px 10px;">
                <option value="">Custom</option>
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="last_week">Last Week</option>
                <option value="last_30_days">Last 30 Days</option>
                <option value="this_month">This Month</option>
                <option value="last_month">Last Month</option>
              </select>
            </div>
            <div style="display:flex;gap:8px;align-items:flex-end;padding-bottom:1px;">
              <button id="applyReportFilter" class="sm-btn sm-btn-primary">Apply</button>
              <button id="clearReportFilter" class="sm-btn sm-btn-secondary">✕ Clear</button>
            </div>
          </div>
        </div>
      </div>
      <div id="reportContainer"><div class="message">Loading analytics…</div></div>
    </div>
  `

  document.getElementById('reportMonth').addEventListener('change', e => {
    const m = e.target.value
    if (m !== '') {
      const monthIdx = parseInt(m, 10)
      const yr = _selectedYear()
      const start = new Date(yr, monthIdx, 1)
      const end = new Date(yr, monthIdx + 1, 0)
      document.getElementById('reportDateFrom').value = _fmtLocalInputDate(start)
      document.getElementById('reportDateTo').value   = _fmtLocalInputDate(end)
      document.getElementById('reportTeamRange').value = ''
    }
  })

  document.getElementById('reportTeamRange').addEventListener('change', e => {
    const key = (e.target.value || '').trim()
    if (!key) return
    const range = _formatRangeFromPreset(key)
    document.getElementById('reportDateFrom').value = range.from
    document.getElementById('reportDateTo').value = range.to
    document.getElementById('reportMonth').value = ''
  })

  ;(function syncMonthPickerFromRange() {
    const monthEl = document.getElementById('reportMonth')
    const from = _parseYmd(dateFrom)
    const to = _parseYmd(dateTo)
    if (!monthEl || !from || !to) return
    const sameYear = from.getFullYear() === to.getFullYear()
    const sameMonth = from.getMonth() === to.getMonth()
    const isStartOfMonth = from.getDate() === 1
    const lastDay = new Date(to.getFullYear(), to.getMonth() + 1, 0).getDate()
    const isEndOfMonth = to.getDate() === lastDay
    if (sameYear && sameMonth && isStartOfMonth && isEndOfMonth) {
      monthEl.value = String(from.getMonth())
    }
  })()
  document.getElementById('applyReportFilter').addEventListener('click', () => {
    const from = document.getElementById('reportDateFrom').value
    const to   = document.getElementById('reportDateTo').value
    renderReports(from, to)
  })
  document.getElementById('clearReportFilter').addEventListener('click', () => renderReports())

  // Fetch lead report + team report in parallel
  const headers = _apiAuthHeaders()
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo)   params.set('date_to',   dateTo)
  const qs = params.toString() ? '?' + params.toString() : ''
  const teamRange = document.getElementById('reportTeamRange')?.value || ''
  if (teamRange) params.set('range', teamRange)
  const [leadsRes, teamRes, compareRes] = await Promise.all([
    fetch(`${API_BASE}/reports/leads${qs}`, { headers }),
    fetch(`${API_BASE}/reports/team${qs}`,  { headers }),
    fetch(`${API_BASE}/reports/comparison`,  { headers }),
  ])
  const leadsData = await leadsRes.json()
  const teamData  = await teamRes.json()
  const compareData = await compareRes.json().catch(() => ({}))

  const total       = leadsData.total_leads || 0
  const convRate    = leadsData.conversion_rate || 0
  const byStatus    = leadsData.leads_by_status || {}
  const bySource    = leadsData.leads_by_source || {}
  const byProject   = leadsData.leads_by_project || {}
  const byDate      = leadsData.leads_by_date || {}
  const teamGroups  = teamData.team_groups || []
  const unassignedMembers = teamData.unassigned_members || []
  const comparison = compareData.comparison || {}

  // ---- helpers ----
  const maxOf  = obj => Math.max(1, ...Object.values(obj))
  const pct    = (v, t) => t ? ((v / t) * 100).toFixed(1) : '0.0'

  function hBar(count, max, color) {
    const w = Math.max(2, Math.round((count / max) * 100))
    return `<div style="flex:1;background:#f1f5f9;border-radius:4px;height:10px;overflow:hidden;">
              <div style="width:${w}%;height:100%;background:${color};border-radius:4px;transition:width .4s;"></div>
            </div>`
  }

  function renderComparisonTable(block) {
    if (!block || !block.current || !block.previous) {
      return '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No comparison data</div>'
    }
    const labels = {
      leads_added: 'Leads Added',
      calls_done: 'Calls Done',
      follow_ups: 'Follow Ups',
      site_visits: 'Site Visits',
      closures: 'Closures',
      conversion_pct: 'Conversion %',
    }
    const keys = ['leads_added', 'calls_done', 'follow_ups', 'site_visits', 'closures', 'conversion_pct']
    const rows = keys.map(k => {
      const curr = Number(block.current[k] || 0)
      const prev = Number(block.previous[k] || 0)
      const delta = curr - prev
      const deltaText = `${delta > 0 ? '+' : ''}${k === 'conversion_pct' ? delta.toFixed(2) : delta}`
      const color = delta > 0 ? '#059669' : delta < 0 ? '#dc2626' : '#64748b'
      return `
        <tr>
          <td style="font-weight:600;">${labels[k]}</td>
          <td style="text-align:center;">${k === 'conversion_pct' ? curr.toFixed(2) + '%' : curr}</td>
          <td style="text-align:center;">${k === 'conversion_pct' ? prev.toFixed(2) + '%' : prev}</td>
          <td style="text-align:center;font-weight:700;color:${color};">${deltaText}${k === 'conversion_pct' ? '%' : ''}</td>
        </tr>`
    }).join('')

    return `
      <div class="table-scroll">
        <table class="table" style="margin:0;min-width:520px;">
          <thead>
            <tr>
              <th>Metric</th>
              <th style="text-align:center;">${escape(block.label_current || 'Current')}</th>
              <th style="text-align:center;">${escape(block.label_previous || 'Previous')}</th>
              <th style="text-align:center;">Delta</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`
  }

  // ---- STATUS breakdown ----
  const statusOrder = ['new','attempted','connected','interested','site_visit_planned','site_visit_done','negotiation','booking_done','lost']
  const statusMax = maxOf(byStatus)
  const statusRows = statusOrder
    .filter(s => byStatus[s] !== undefined)
    .map(s => {
      const c = byStatus[s]
      return `
        <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #f1f5f9;">
          <div class="rpt-bar-lbl-status">
            <span class="tag" style="background:${getStatusColor(s)};color:#fff;font-size:11px;">${s.replace(/_/g,' ')}</span>
          </div>
          ${hBar(c, statusMax, getStatusColor(s))}
          <div style="width:28px;text-align:right;font-weight:700;font-size:13px;color:#0f172a;">${c}</div>
          <div style="width:42px;text-align:right;font-size:12px;color:#94a3b8;">${pct(c,total)}%</div>
        </div>`
    }).join('')

  // ---- SOURCE distribution ----
  const sourceMax = maxOf(bySource)
  const SOURCE_COLORS = ['#6366f1','#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#0ea5e9','#84cc16','#f43f5e']
  const sourceRows = Object.entries(bySource)
    .sort((a,b) => b[1]-a[1])
    .map(([src, c], i) => {
      const col = SOURCE_COLORS[i % SOURCE_COLORS.length]
      return `
        <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #f1f5f9;">
          <div class="rpt-bar-lbl-source">${escape(src)}</div>
          ${hBar(c, sourceMax, col)}
          <div style="width:28px;text-align:right;font-weight:700;font-size:13px;color:#0f172a;">${c}</div>
          <div style="width:42px;text-align:right;font-size:12px;color:#94a3b8;">${pct(c,total)}%</div>
        </div>`
    }).join('')

  // ---- PROJECT distribution ----
  const projectMax = maxOf(byProject)
  const projectRows = Object.entries(byProject)
    .sort((a,b) => b[1]-a[1])
    .map(([proj, c], i) => {
      const col = SOURCE_COLORS[(i+3) % SOURCE_COLORS.length]
      return `
        <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #f1f5f9;">
          <div class="rpt-bar-lbl-project">${escape(proj)}</div>
          ${hBar(c, projectMax, col)}
          <div style="width:28px;text-align:right;font-weight:700;font-size:13px;color:#0f172a;">${c}</div>
          <div style="width:42px;text-align:right;font-size:12px;color:#94a3b8;">${pct(c,total)}%</div>
        </div>`
    }).join('')

  // ---- LEADS TREND (last 30 days) ----
  const sortedDates = Object.keys(byDate).sort()
  const dateMax = maxOf(byDate)
  const trendBars = sortedDates.length === 0
    ? `<div style="color:#94a3b8;font-size:13px;padding:20px 0;">No data for last 30 days</div>`
    : sortedDates.map(d => {
        const c = byDate[d]
        const h = Math.max(4, Math.round((c / dateMax) * 80))
        const label = d.slice(5)  // MM-DD
        return `
          <div style="display:flex;flex-direction:column;align-items:center;gap:3px;flex:1;min-width:0;">
            <div style="font-size:10px;color:#475569;font-weight:600;">${c}</div>
            <div style="width:100%;max-width:28px;height:${h}px;background:#6366f1;border-radius:3px 3px 0 0;" title="${d}: ${c} leads"></div>
            <div style="font-size:9px;color:#94a3b8;writing-mode:vertical-lr;transform:rotate(180deg);height:28px;">${label}</div>
          </div>`
      }).join('')

  // ---- TEAM PERFORMANCE (grouped by manager) ----
  const MANAGER_PALETTE = ['#6366f1','#0ea5e9','#10b981','#f59e0b','#ec4899','#8b5cf6','#14b8a6']

  const TABLE_HEADERS = `<tr>
    <th>Name</th>
    <th style="text-align:center;">All Leads</th>
    <th style="text-align:center;">Interested</th>
    <th style="text-align:center;">Site Visit Planned</th>
    <th style="text-align:center;">Site Visit Done</th>
    <th style="text-align:center;">Negotiation</th>
    <th style="text-align:center;">Booking Done</th>
    <th style="text-align:center;">Warm Leads</th>
    <th style="text-align:center;">Hot Leads</th>
  </tr>`

  function personRow(s, isManager, color) {
    const warmCol = s.warm_rate >= 50 ? '#10b981' : s.warm_rate >= 20 ? '#f59e0b' : '#ef4444'
    const hotCol = s.hot_rate >= 50 ? '#ef4444' : s.hot_rate >= 20 ? '#f59e0b' : '#0284c7'
    const nameCell = isManager
      ? `<td style="font-weight:700;color:${color || '#0f172a'};">⭐ ${escape(s.name)} <span style="font-size:10px;font-weight:600;background:${color}18;color:${color};border-radius:8px;padding:1px 7px;margin-left:6px;">Manager</span></td>`
      : `<td style="font-weight:500;padding-left:24px;">↳ ${escape(s.name)}</td>`
    const rowStyle = isManager ? `style="background:${color}08;border-left:3px solid ${color};"` : ''
    return `
      <tr ${rowStyle}>
        ${nameCell}
        <td style="text-align:center;font-weight:700;">${s.total_leads}</td>
        <td style="text-align:center;font-weight:600;">${s.interested}</td>
        <td style="text-align:center;font-weight:600;">${s.site_visit_planned}</td>
        <td style="text-align:center;font-weight:600;">${s.site_visit_done}</td>
        <td style="text-align:center;font-weight:600;">${s.negotiation || 0}</td>
        <td style="text-align:center;font-weight:700;">${s.booking_done}</td>
        <td style="text-align:center;">
          <span style="background:${warmCol}18;color:${warmCol};border-radius:12px;padding:2px 10px;font-size:12px;font-weight:700;">${s.warm_leads || 0}</span>
        </td>
        <td style="text-align:center;">
          <span style="background:${hotCol}18;color:${hotCol};border-radius:12px;padding:2px 10px;font-size:12px;font-weight:700;">${s.hot_leads || 0}</span>
        </td>
      </tr>`
  }

  function managerGroupHTML(group, colorIdx) {
    const mgr = group.manager
    const color = MANAGER_PALETTE[colorIdx % MANAGER_PALETTE.length]
    const people = [mgr].concat(group.members || [])
    const teamTotal = people.reduce((sum, p) => sum + Number(p.total_leads || 0), 0)
    const teamBooking = people.reduce((sum, p) => sum + Number(p.booking_done || 0), 0)
    const teamInterest = people.reduce((sum, p) => sum + Number(p.interested || 0), 0)
    const teamSVP = people.reduce((sum, p) => sum + Number(p.site_visit_planned || 0), 0)
    const teamSVD = people.reduce((sum, p) => sum + Number(p.site_visit_done || 0), 0)
    const teamNegotiation = people.reduce((sum, p) => sum + Number(p.negotiation || 0), 0)
    const teamWarmLeads = people.reduce((sum, p) => sum + Number(p.warm_leads || 0), 0)
    const teamHotLeads = people.reduce((sum, p) => sum + Number(p.hot_leads || 0), 0)
    const teamWarm = teamTotal > 0 ? (((teamInterest + teamSVP) / teamTotal) * 100).toFixed(1) : '0.0'
    const teamHot = teamTotal > 0 ? (((teamSVD + teamNegotiation) / teamTotal) * 100).toFixed(1) : '0.0'
    const totalsRow    = `
      <tr style="background:${color}10;border-top:2px solid ${color}30;font-weight:700;">
        <td style="font-weight:700;color:${color};font-size:12px;text-transform:uppercase;letter-spacing:0.05em;">
          ∑ Team Total
        </td>
        <td style="text-align:center;font-weight:800;font-size:14px;">${teamTotal}</td>
        <td style="text-align:center;font-weight:800;">${teamInterest}</td>
        <td style="text-align:center;font-weight:800;">${teamSVP}</td>
        <td style="text-align:center;font-weight:800;">${teamSVD}</td>
        <td style="text-align:center;font-weight:800;">${teamNegotiation}</td>
        <td style="text-align:center;font-weight:800;">${teamBooking}</td>
        <td style="text-align:center;">
          <span style="background:${color}20;color:${color};border-radius:12px;padding:2px 10px;font-size:12px;font-weight:800;">${teamWarmLeads}</span>
        </td>
        <td style="text-align:center;">
          <span style="background:${color}20;color:${color};border-radius:12px;padding:2px 10px;font-size:12px;font-weight:800;">${teamHotLeads}</span>
        </td>
      </tr>`
    return `
      <div style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
        <div style="background:${color}12;border-bottom:2px solid ${color}30;padding:12px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          <div style="width:36px;height:36px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:700;flex-shrink:0;">
            ${escape(mgr.name).charAt(0)}
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:14px;font-weight:700;color:#0f172a;">${escape(mgr.name)}</div>
            <div style="font-size:12px;color:#64748b;">${group.members.length} team member${group.members.length !== 1 ? 's' : ''}</div>
          </div>
          <div style="display:flex;gap:20px;flex-wrap:wrap;">
            <div style="text-align:center;">
              <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">All Leads</div>
              <div style="font-size:18px;font-weight:700;color:#0f172a;">${teamTotal}</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">Booking Done</div>
              <div style="font-size:18px;font-weight:700;color:#0f172a;">${teamBooking}</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">Team Warm Rate</div>
              <div style="font-size:18px;font-weight:700;color:#0f172a;">${teamWarm}%</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">Team Hot Rate</div>
              <div style="font-size:18px;font-weight:700;color:#0f172a;">${teamHot}%</div>
            </div>
          </div>
        </div>
        <div class="table-scroll">
          <table class="table rpt-team-table" style="margin:0;min-width:580px;">
            <thead>${TABLE_HEADERS}</thead>
            <tbody>
              ${personRow(mgr, true, color)}
              ${group.members.map(m => personRow(m, false, color)).join('')}
              ${totalsRow}
            </tbody>
          </table>
        </div>
      </div>`
  }

  const teamGroupsHTML = teamGroups.length === 0
    ? '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No team data available</div>'
    : teamGroups.map((g, i) => managerGroupHTML(g, i)).join('')

  const unassignedHTML = unassignedMembers.length === 0 ? '' : `
    <div style="margin-bottom:20px;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
      <div style="background:#f8fafc;border-bottom:2px solid #e2e8f0;padding:12px 16px;display:flex;align-items:center;gap:10px;">
        <div style="width:36px;height:36px;border-radius:50%;background:#94a3b8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:16px;flex-shrink:0;">?</div>
        <div>
          <div style="font-size:14px;font-weight:700;color:#475569;">Unassigned Members</div>
          <div style="font-size:12px;color:#94a3b8;">${unassignedMembers.length} member${unassignedMembers.length !== 1 ? 's' : ''} without a sales manager</div>
        </div>
      </div>
      <div class="table-scroll">
        <table class="table rpt-team-table" style="margin:0;min-width:580px;">
          <thead>${TABLE_HEADERS}</thead>
          <tbody>${unassignedMembers.map(m => personRow(m, false, '#94a3b8')).join('')}</tbody>
        </table>
      </div>
    </div>`

  // ---- BOOKING stats ----
  const booked        = byStatus['booking_done']       || 0
  const interested    = byStatus['interested']         || 0
  const siteVisitPlan = byStatus['site_visit_planned'] || 0
  const siteVisitDone = byStatus['site_visit_done']    || 0
  const negotiation   = byStatus['negotiation']        || 0

  const hotLeads = siteVisitDone + negotiation
  const warmLeads = interested + siteVisitPlan
  const hotRate  = total > 0 ? ((hotLeads / total) * 100).toFixed(1) : '0.0'
  const warmRate = total > 0 ? ((warmLeads / total) * 100).toFixed(1) : '0.0'

  if (myId !== _reportsRenderId) return
  var reportContainer = document.getElementById('reportContainer')
  if (!reportContainer) return
  reportContainer.innerHTML = `
    <!-- KPI row -->
    <div class="rpt-kpi-grid">
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">All Leads</div>
        <div class="analytics-kpi-value">${total}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Interested</div>
        <div class="analytics-kpi-value">${interested}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Site Visit Planned</div>
        <div class="analytics-kpi-value">${siteVisitPlan}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Site Visit Done</div>
        <div class="analytics-kpi-value">${siteVisitDone}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Booking Done</div>
        <div class="analytics-kpi-value">${booked}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Negotiation</div>
        <div class="analytics-kpi-value">${negotiation}</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Hot Rate</div>
        <div class="analytics-kpi-value">${hotRate}%</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">(Site Visit Done + Negotiation) / Total</div>
      </div>
      <div class="analytics-kpi">
        <div class="analytics-kpi-label">Warm Rate</div>
        <div class="analytics-kpi-value">${warmRate}%</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">(Interested + Site Visit Planned) / Total</div>
      </div>
    </div>

    <!-- Status + Source charts side by side -->
    <div class="rpt-two-col">
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads by Status</h3>
        ${statusRows || '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No data</div>'}
      </div>
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads by Source</h3>
        ${sourceRows || '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No data</div>'}
      </div>
    </div>

    <!-- Project + Trend side by side -->
    <div class="rpt-two-col">
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads by Project</h3>
        ${Object.keys(byProject).length
          ? projectRows
          : '<div style="color:#94a3b8;padding:12px 0;font-size:13px;">No data</div>'}
      </div>
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Leads Trend – Last 30 Days</h3>
        <div style="display:flex;align-items:flex-end;gap:3px;height:120px;padding-top:10px;">
          ${trendBars}
        </div>
      </div>
    </div>

    <!-- Team performance -->
    <div class="card" style="margin:0;">
      <h3 class="analytics-section-title">Team Performance</h3>
      <div style="margin-top:14px;">
        ${teamGroupsHTML}
        ${unassignedHTML}
      </div>
    </div>

    <!-- WoW / MoM comparison -->
    <div class="rpt-two-col">
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Week-on-Week Comparison</h3>
        ${renderComparisonTable(comparison.week)}
      </div>
      <div class="card" style="margin:0;">
        <h3 class="analytics-section-title">Month-on-Month Comparison</h3>
        ${renderComparisonTable(comparison.month)}
      </div>
    </div>
  `
}

async function downloadLeadReport() {
  const params = new URLSearchParams()
  const from = document.getElementById('reportDateFrom')?.value || ''
  const to = document.getElementById('reportDateTo')?.value || ''
  const range = document.getElementById('reportTeamRange')?.value || ''
  if (from) params.set('date_from', from)
  if (to) params.set('date_to', to)
  if (range) params.set('range', range)
  const qs = params.toString() ? '?' + params.toString() : ''
  const a = document.createElement('a')
  const res = await fetch(`${API_BASE}/reports/management/download${qs}`, {
    headers: _apiAuthHeaders()
  })
  if (!res.ok) { showToast('Export failed', 'error'); return }
  const blob = await res.blob()
  const url  = URL.createObjectURL(blob)
  a.href = url
  a.download = 'management_report.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

// ============================================================================
