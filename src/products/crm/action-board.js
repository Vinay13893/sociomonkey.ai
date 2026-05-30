// ============================================================================
// DAILY ACTION BOARD — Sales Task Engine
// "What should I do today?" for team members and managers
// ============================================================================

var _actionBoardRenderId = 0
var _actionBoardRenderInFlight = false
var _abRange = 'today'
var _abViewMode = 'detailed'
var _abFocusedLeadId = null
var _abFocusedLeadPhone = ''
var _abUpdatedTimer = null
var _abDateFrom = ''
var _abDateTo = ''
var _abSectionPages = {
  today_callbacks: 1,
  overdue_callbacks: 1,
  new_leads_today: 1,
  follow_up: 1,
  no_answer: 1,
  warm_leads: 1,
  hot_leads: 1,
}

async function renderActionBoard(dateFrom, dateTo, rangeKey) {
  if (_actionBoardRenderInFlight) return
  _actionBoardRenderInFlight = true
  _actionBoardRenderId++
  var myId = _actionBoardRenderId
  window._ACTIVE_ROUTE = 'action_board'

  if (typeof dateFrom === 'string') _abDateFrom = dateFrom
  if (typeof dateTo === 'string') _abDateTo = dateTo
  if (typeof rangeKey === 'string') _abRange = rangeKey

  function _guard() {
    return myId === _actionBoardRenderId && window._ACTIVE_ROUTE === 'action_board'
  }

  const content = document.getElementById('content')
  if (!content) { _actionBoardRenderInFlight = false; return }

  if (_abUpdatedTimer) {
    clearInterval(_abUpdatedTimer)
    _abUpdatedTimer = null
  }

  const now   = new Date()
  const today = now.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  function _iso(d) {
    return d.toISOString().split('T')[0]
  }
  function _resolveRange(range, customFrom, customTo) {
    const n = new Date()
    const startToday = new Date(n.getFullYear(), n.getMonth(), n.getDate())
    if (range === 'custom') {
      return { from: customFrom || '', to: customTo || '' }
    }
    if (range === 'today') {
      const t = _iso(startToday)
      return { from: t, to: t }
    }
    if (range === 'this_week') {
      const start = new Date(startToday)
      start.setDate(start.getDate() - ((start.getDay() + 6) % 7))
      return { from: _iso(start), to: _iso(startToday) }
    }
    if (range === 'this_month') {
      const start = new Date(n.getFullYear(), n.getMonth(), 1)
      return { from: _iso(start), to: _iso(startToday) }
    }
    if (range === 'last_30_days') {
      const start = new Date(startToday)
      start.setDate(start.getDate() - 29)
      return { from: _iso(start), to: _iso(startToday) }
    }
    return { from: '', to: '' }
  }

  const resolved = _resolveRange(_abRange, _abDateFrom, _abDateTo)
  const queryFrom = resolved.from
  const queryTo = resolved.to
  const activeFilter = Boolean(queryFrom || queryTo)
  const fmtD = function (d) { return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) }
  const filterLabel = !activeFilter ? 'All Time'
    : queryFrom && queryTo ? `${fmtD(queryFrom)} → ${fmtD(queryTo)}`
    : queryFrom ? `From ${fmtD(queryFrom)}`
    : `Until ${fmtD(queryTo)}`
  const isTodayScope = _abRange === 'today'
  const isAllTimeScope = _abRange === ''
  const boardScopeLabel = isAllTimeScope ? 'All Time' : (isTodayScope ? 'Today' : 'Selected Range')
  const callbacksLabel = isAllTimeScope ? 'Callbacks' : (isTodayScope ? "Today's Callbacks" : 'Callbacks in Range')
  const newLeadsLabel = isAllTimeScope ? 'New Leads' : (isTodayScope ? 'New Leads Today' : 'New Leads in Range')
  const followUpLabel = isAllTimeScope ? 'Follow Up' : (isTodayScope ? 'Follow Up' : 'Follow Up in Range')
  const noAnswerLabel = isAllTimeScope ? 'No Answer' : (isTodayScope ? 'No Answer' : 'No Answer in Range')
  const warmLeadsLabel = isAllTimeScope ? 'Warm Leads' : (isTodayScope ? 'Warm Leads' : 'Warm Leads in Range')
  const hotLeadsLabel = isAllTimeScope ? 'Hot Leads' : (isTodayScope ? 'Hot Leads' : 'Hot Leads in Range')

  // Skeleton shell
  content.innerHTML = `
    <div style="max-width:1200px;margin:0 auto;padding:20px 16px 60px;" id="actionBoardRoot">
      <div class="sm-page-header" style="margin-bottom:20px;">
        <div>
          <h2 class="sm-page-title">${boardScopeLabel} Action Board</h2>
          <p class="sm-small sm-text-muted" style="margin:4px 0 0;">${today}</p>
        </div>
        <button onclick="renderActionBoard(_abDateFrom, _abDateTo, _abRange)" class="sm-btn sm-btn-secondary"><i class="fa-solid fa-rotate" style="margin-right:6px;"></i>Refresh</button>
      </div>

      <div id="abBriefing" style="margin:-8px 0 18px;padding:10px 12px;border-radius:8px;border:1px solid #e2e8f0;background:#f8fafc;color:#334155;font-size:13px;">
        Loading your day briefing...
      </div>

      <div class="dash-filters" style="margin-bottom:18px;">
        <div class="dash-filter-group">
          <label class="dash-filter-label">Time Range</label>
          <select id="abRangeFilter" class="dash-filter-ctl">
            <option value="" ${_abRange === '' ? 'selected' : ''}>All Time</option>
            <option value="today" ${_abRange === 'today' ? 'selected' : ''}>Today</option>
            <option value="this_week" ${_abRange === 'this_week' ? 'selected' : ''}>This Week</option>
            <option value="this_month" ${_abRange === 'this_month' ? 'selected' : ''}>This Month</option>
            <option value="last_30_days" ${_abRange === 'last_30_days' ? 'selected' : ''}>Last 30 Days</option>
            <option value="custom" ${_abRange === 'custom' ? 'selected' : ''}>Custom Date</option>
          </select>
        </div>
        <div id="abCustomRange" style="display:${_abRange === 'custom' ? 'flex' : 'none'};gap:8px;align-items:flex-end;">
          <div class="dash-filter-group">
            <label class="dash-filter-label">From</label>
            <input type="date" id="abDateFrom" class="dash-filter-ctl" value="${_abDateFrom}" />
          </div>
          <div class="dash-filter-group">
            <label class="dash-filter-label">To</label>
            <input type="date" id="abDateTo" class="dash-filter-ctl" value="${_abDateTo}" />
          </div>
        </div>
        <div class="dash-filter-group">
          <label class="dash-filter-label" style="visibility:hidden;">p</label>
          <span style="font-size:12px;font-weight:600;color:${activeFilter ? '#2563eb' : '#64748b'};background:${activeFilter ? '#eff6ff' : '#f8fafc'};padding:8px 10px;border-radius:8px;border:1px solid ${activeFilter ? '#bfdbfe' : '#e2e8f0'};white-space:nowrap;">${filterLabel}</span>
        </div>
      </div>

      <!-- Summary strip -->
      <div id="abSummary" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px;">
        ${['Today\'s Callbacks','Overdue','New Leads','Follow Up','No Answer','Hot Leads'].map(l => `
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;text-align:center;">
            <div style="height:28px;background:#f1f5f9;border-radius:6px;margin-bottom:6px;animation:_loaderBar 1.4s infinite;"></div>
            <div style="font-size:11px;color:#64748b;font-weight:600;">${l}</div>
          </div>`).join('')}
      </div>

      <!-- Section container -->
      <div id="abSections" style="display:flex;flex-direction:column;gap:20px;">
        ${[1,2,3,4,5,6].map(() => `
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;">
            <div style="height:18px;width:200px;background:#f1f5f9;border-radius:6px;margin-bottom:14px;animation:_loaderBar 1.4s infinite;"></div>
            <div style="height:12px;width:100%;background:#f8fafc;border-radius:4px;"></div>
          </div>`).join('')}
      </div>
    </div>
  `

  const abRangeFilter = document.getElementById('abRangeFilter')
  const abCustomRange = document.getElementById('abCustomRange')
  const abDateFrom = document.getElementById('abDateFrom')
  const abDateTo = document.getElementById('abDateTo')

  if (abRangeFilter) {
    abRangeFilter.addEventListener('change', function () {
      var v = abRangeFilter.value || ''
      _abRange = v
      if (abCustomRange) abCustomRange.style.display = v === 'custom' ? 'flex' : 'none'
      if (v !== 'custom') {
        _abDateFrom = ''
        _abDateTo = ''
        renderActionBoard('', '', v)
      }
    })
  }
  if (abDateFrom) {
    abDateFrom.addEventListener('change', function () {
      if (_abRange === 'custom') renderActionBoard(abDateFrom.value || '', abDateTo ? abDateTo.value : '', 'custom')
    })
  }
  if (abDateTo) {
    abDateTo.addEventListener('change', function () {
      if (_abRange === 'custom') renderActionBoard(abDateFrom ? abDateFrom.value : '', abDateTo.value || '', 'custom')
    })
  }

  _actionBoardRenderInFlight = false

  // Fetch data
  let data
  try {
    const params = new URLSearchParams()
    if (queryFrom) params.set('date_from', queryFrom)
    if (queryTo) params.set('date_to', queryTo)
    Object.keys(_abSectionPages).forEach(function (key) {
      var page = Number(_abSectionPages[key] || 1)
      if (page > 1 || page === 1) params.set(key + '_page', String(page))
    })
    const qs = params.toString() ? '?' + params.toString() : ''
    const res = await fetch(`${API_BASE}/leads/action-board${qs}`, { headers: _apiAuthHeaders() })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data = await res.json()

    // Callback rows may not always include project/latest note fields depending on backend version.
    // Enrich missing fields from lead details so Action Board columns remain complete.
    const callbackRows = (data.today_callbacks || []).concat(data.overdue_callbacks || [])
    const needsEnrichment = []
    const seenLeadIds = {}
    callbackRows.forEach(function (r) {
      const lid = Number(r.lead_id || 0)
      if (!lid || seenLeadIds[lid]) return
      if (!r.project_name || typeof r.latest_note === 'undefined' || !r.lead_phone || !r.lead_status) {
        needsEnrichment.push(lid)
      }
      seenLeadIds[lid] = true
    })

    if (needsEnrichment.length) {
      const leadPairs = await Promise.all(needsEnrichment.map(async function (lid) {
        try {
          const lr = await fetch(`${API_BASE}/leads/${lid}`, { headers: _apiAuthHeaders() })
          if (!lr.ok) return null
          const lj = await lr.json()
          return lj && lj.lead ? [lid, lj.lead] : null
        } catch (_) {
          return null
        }
      }))

      const leadMap = {}
      leadPairs.forEach(function (pair) {
        if (!pair) return
        leadMap[pair[0]] = pair[1]
      })

      callbackRows.forEach(function (r) {
        const lead = leadMap[Number(r.lead_id || 0)]
        if (!lead) return
        if (!r.project_name) r.project_name = lead.project_name || '-'
        if (typeof r.latest_note === 'undefined' || r.latest_note === null) r.latest_note = lead.latest_note || ''
        if (!r.lead_phone) r.lead_phone = lead.phone || ''
        if (!r.lead_status) r.lead_status = lead.status || ''
        if (!r.lead_name) r.lead_name = lead.name || ('Lead #' + r.lead_id)
      })
    }
  } catch (err) {
    if (!_guard()) return
    document.getElementById('abSections').innerHTML = `
      <div style="text-align:center;padding:60px 20px;">
        <div style="font-size:36px;margin-bottom:12px;">⚠️</div>
        <p style="color:#64748b;">Failed to load action board. <button class="button" onclick="renderActionBoard(_abDateFrom, _abDateTo)" style="font-size:13px;">Retry</button></p>
      </div>`
    return
  }
  if (!_guard()) return

  const s = data.summary || {}
  const nowMs = Date.now()

  const briefingParts = []
  if ((s.today_callbacks_count || 0) > 0) briefingParts.push(`${s.today_callbacks_count} callbacks`)
  if ((s.overdue_count || 0) > 0) briefingParts.push(`${s.overdue_count} overdue`)
  if ((s.warm_leads_count || 0) > 0) briefingParts.push(`${s.warm_leads_count} warm leads`)
  if ((s.hot_leads_count || 0) > 0) briefingParts.push(`${s.hot_leads_count} hot leads`)
  if ((s.new_leads_count || 0) > 0) briefingParts.push(`${s.new_leads_count} new leads`)
  const briefing = briefingParts.length
    ? `${boardScopeLabel}: You have ${briefingParts.join(', ')} to action now.`
    : `${boardScopeLabel}: No urgent actions right now. Focus on quality follow-ups and notes hygiene.`
  const briefingEl = document.getElementById('abBriefing')
  if (briefingEl) briefingEl.textContent = briefing

  // ── Summary strip ────────────────────────────────────────────────────────
  const summaryItems = [
    { count: s.today_callbacks_count || 0, label: callbacksLabel, color: '#2563eb', icon: 'fa-solid fa-phone' },
    { count: s.overdue_count          || 0, label: 'Overdue Callbacks', color: '#dc2626', icon: 'fa-solid fa-triangle-exclamation' },
    { count: s.new_leads_count        || 0, label: newLeadsLabel,      color: '#0891b2', icon: 'fa-solid fa-user-plus' },
    { count: s.follow_up_count        || 0, label: followUpLabel,      color: '#7c3aed', icon: 'fa-solid fa-rotate' },
    { count: s.no_answer_count        || 0, label: noAnswerLabel,      color: '#ea580c', icon: 'fa-solid fa-phone-slash' },
    { count: s.warm_leads_count       || 0, label: warmLeadsLabel,     color: '#f59e0b', icon: 'fa-solid fa-sun' },
    { count: s.hot_leads_count        || 0, label: hotLeadsLabel,      color: '#de2e2e', icon: 'fa-solid fa-fire' },
  ]
  const sumEl = document.getElementById('abSummary')
  if (sumEl) {
    sumEl.innerHTML = summaryItems.map(function (i) {
      if (_abViewMode === 'compact') {
        return `
          <div style="background:#fff;border:1px solid #e2e8f0;border-left:3px solid ${i.color};border-radius:8px;padding:10px 12px;box-shadow:0 1px 2px rgba(2,6,23,0.04);display:flex;align-items:center;gap:10px;min-height:54px;">
            <div style="width:28px;height:28px;border-radius:7px;background:${i.color}12;display:flex;align-items:center;justify-content:center;color:${i.color};font-size:13px;flex-shrink:0;"><i class="${i.icon}"></i></div>
            <div style="min-width:0;flex:1;">
              <div style="font-size:18px;font-weight:800;color:#0f172a;line-height:1;">${i.count}</div>
              <div style="font-size:10px;color:#64748b;font-weight:600;margin-top:3px;line-height:1.2;">${i.label}</div>
            </div>
          </div>
        `
      }
      return `
        <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid ${i.color};border-radius:10px;padding:16px 18px;box-shadow:0 1px 3px rgba(2,6,23,0.06);display:flex;align-items:center;gap:14px;min-height:74px;">
          <div style="width:38px;height:38px;border-radius:8px;background:${i.color}15;display:flex;align-items:center;justify-content:center;color:${i.color};font-size:16px;flex-shrink:0;"><i class="${i.icon}"></i></div>
          <div>
            <div style="font-size:26px;font-weight:800;color:#0f172a;line-height:1;">${i.count}</div>
            <div style="font-size:11px;color:#64748b;font-weight:600;margin-top:4px;">${i.label}</div>
          </div>
        </div>
      `
    }).join('')
  }

  // ── Helper: lead mini-card ───────────────────────────────────────────────
  function _leadCard(l, extra) {
    const priority = _abLeadPriority(l)
    const sc = (typeof STATUS_COLORS !== 'undefined' ? STATUS_COLORS : {})[l.status]
    const badge = sc ? `<span style="background:${sc.bg};color:${sc.color};font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px;flex-shrink:0;">${sc.label}</span>`
                     : `<span style="background:#f1f5f9;color:#475569;font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px;flex-shrink:0;">${(l.status||'').replace(/_/g,' ')}</span>`
    const age = l.created_at ? _leadAge(new Date(l.created_at)) : ''
    const compact = _abViewMode === 'compact'
    const phone = l.phone || ''
    const project = l.project_name || '-'
    const latestNote = (l.latest_note || '').trim()
    const statusText = sc ? sc.label : (l.status || '').replace(/_/g, ' ')
    const safePhone = escape(phone)
    const callPhoneArg = JSON.stringify(phone)
    const callNameArg = JSON.stringify(l.name || 'Lead')
    const compactNameStyle = compact ? 'font-weight:700;font-size:12.5px;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;' : 'font-weight:600;font-size:13px;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
    const compactPhoneStyle = compact ? 'display:none;' : 'font-size:11px;color:#94a3b8;'
    const avatarStyle = compact ? 'width:30px;height:30px;border-radius:7px;background:#e0e7ff;color:#4f46e5;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;flex-shrink:0;' : 'width:36px;height:36px;border-radius:8px;background:#e0e7ff;color:#4f46e5;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0;'
    const callBtn = phone
      ? `<button onclick='_abStartCallFlow(${l.id}, ${callPhoneArg}, ${callNameArg})' style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #dbeafe;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#1d4ed8;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-phone" style="margin-right:${compact ? '0' : '4px'};font-size:10px;"></i>${compact ? '' : 'Call'}</button>`
      : ''
    return `
      <div class="ab-lead-card" data-lead-id="${l.id}" data-phone="${safePhone}" tabindex="0" style="display:flex;align-items:center;gap:${compact ? '8px' : '12px'};padding:${compact ? '6px 10px' : '10px 14px'};background:${compact ? '#fff' : '#f8fafc'};border-radius:${compact ? '6px' : '8px'};border:1px solid #e2e8f0;border-left:4px solid ${priority.color};outline:none;">
        <div style="${avatarStyle}">
          ${escape((l.name||'?')[0]).toUpperCase()}
        </div>
        <div style="flex:1;min-width:0;">
          <button onclick="_abOpenLead(${l.id})" style="${compactNameStyle}background:none;border:none;padding:0;cursor:pointer;color:#1e40af;text-decoration:underline;text-underline-offset:2px;text-decoration-color:rgba(30,64,175,.35);">${escape(l.name||'')}</button>
          <div style="font-size:11px;color:#64748b;display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
            <span><strong style="color:#334155;">Phone:</strong> ${escape(phone || '—')}</span>
            <span><strong style="color:#334155;">Status:</strong> ${escape(statusText || '—')}</span>
            <span><strong style="color:#334155;">Project:</strong> ${escape(project)}</span>
            <span style="display:inline-flex;align-items:center;gap:6px;min-width:220px;">
              <strong style="color:#334155;">Latest Note:</strong>
              <span title="${escape(latestNote || 'No notes')}" style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:${latestNote ? '#475569' : '#94a3b8'};">${escape(latestNote || '—')}</span>
              <button onclick="_abQuickNote(${l.id})" style="font-size:10px;font-weight:700;background:#fff;border:1px solid #cbd5e1;border-radius:6px;padding:2px 7px;color:#334155;cursor:pointer;">Update</button>
            </span>
          </div>
          <div style="${compactPhoneStyle}">${age ? '<span style="color:#f59e0b;font-weight:600;">'+age+'</span>' : ''}</div>
          ${compact ? `<div style="font-size:10px;color:${priority.color};font-weight:700;margin-top:1px;">${priority.label}</div>` : `<div style="font-size:10px;color:${priority.color};font-weight:700;margin-top:2px;">${priority.label}</div>`}
        </div>
        ${compact ? '' : badge}
        ${extra || ''}
        <div style="display:flex;gap:6px;flex-shrink:0;">
          ${callBtn}
          <button onclick="_abOpenLead(${l.id})" style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#4f46e5;cursor:pointer;white-space:nowrap;">${compact ? '<i class="fa-solid fa-folder-open"></i>' : 'Open Lead'}</button>
          ${compact ? '' : `<button onclick="_abQuickNote(${l.id})" style="font-size:11px;font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#64748b;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-pen-to-square" style="margin-right:4px;font-size:10px;"></i>Note</button>`}
          ${compact ? '' : `<button onclick="_abCallCallback(${l.id})" style="font-size:11px;font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#0369a1;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-calendar-plus" style="margin-right:4px;font-size:10px;"></i>Callback</button>`}
        </div>
      </div>`
  }

  // ── Helper: callback row ─────────────────────────────────────────────────
  function _callbackRow(c) {
    const dt = new Date(c.callback_datetime)
    const isPast = dt < new Date()
    const col  = isPast ? '#dc2626' : '#2563eb'
    const bg   = isPast ? '#fef2f2' : '#f8faff'
    const faIcon = isPast ? 'fa-solid fa-triangle-exclamation' : 'fa-solid fa-bell'
    const compact = _abViewMode === 'compact'
    const phone = c.lead_phone || c.phone || ''
    const project = c.project_name || c.project || c.project_title || '-'
    const latestNote = (c.latest_note || '').trim()
    const safePhone = escape(phone)
    const callPhoneArg = JSON.stringify(phone)
    const callNameArg = JSON.stringify(c.lead_name || 'Lead')
    const compactNameStyle = compact ? 'font-weight:700;font-size:12.5px;color:#0f172a;' : 'font-weight:600;font-size:13px;color:#0f172a;'
    const callBtn = phone
      ? `<button onclick='_abStartCallFlow(${c.lead_id}, ${callPhoneArg}, ${callNameArg})' style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #dbeafe;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#1d4ed8;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-phone" style="margin-right:${compact ? '0' : '4px'};font-size:10px;"></i>${compact ? '' : 'Call'}</button>`
      : ''
    const timeStr = dt.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
    return `
      <div class="ab-lead-card" data-lead-id="${c.lead_id}" data-phone="${safePhone}" tabindex="0" style="display:flex;align-items:center;gap:${compact ? '8px' : '12px'};padding:${compact ? '6px 10px' : '10px 14px'};background:${compact ? '#fff' : bg};border-radius:${compact ? '6px' : '8px'};border:1px solid ${col}22;border-left:4px solid ${col};outline:none;">
        <div style="width:${compact ? '28px' : '32px'};height:${compact ? '28px' : '32px'};border-radius:8px;background:${col}15;display:flex;align-items:center;justify-content:center;color:${col};font-size:${compact ? '12px' : '14px'};flex-shrink:0;">
          <i class="${faIcon}"></i>
        </div>
        <div style="flex:1;min-width:0;">
          <button onclick="_abOpenLead(${c.lead_id})" style="${compactNameStyle}background:none;border:none;padding:0;cursor:pointer;color:#1e40af;text-decoration:underline;text-underline-offset:2px;text-decoration-color:rgba(30,64,175,.35);">${escape(c.lead_name||'')}</button>
          <div style="font-size:${compact ? '10px' : '11px'};color:${col};font-weight:600;">${timeStr}</div>
          <div style="font-size:11px;color:#64748b;display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
            <span><strong style="color:#334155;">Phone:</strong> ${escape(phone || '—')}</span>
            <span><strong style="color:#334155;">Status:</strong> ${escape((c.lead_status || '').replace(/_/g,' ') || '—')}</span>
            <span><strong style="color:#334155;">Project:</strong> ${escape(project)}</span>
            <span style="display:inline-flex;align-items:center;gap:6px;min-width:220px;">
              <strong style="color:#334155;">Latest Note:</strong>
              <span title="${escape(latestNote || 'No notes')}" style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:${latestNote ? '#475569' : '#94a3b8'};">${escape(latestNote || '—')}</span>
              <button onclick="_abQuickNote(${c.lead_id})" style="font-size:10px;font-weight:700;background:#fff;border:1px solid #cbd5e1;border-radius:6px;padding:2px 7px;color:#334155;cursor:pointer;">Update</button>
            </span>
          </div>
          ${c.notes ? `<div style="font-size:11px;color:#64748b;margin-top:2px;">${escape(c.notes)}</div>` : ''}
        </div>
        ${compact || !c.lead_status ? '' : `<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px;background:#f1f5f9;color:#475569;">${c.lead_status.replace(/_/g,' ')}</span>`}
        <div style="display:flex;gap:6px;flex-shrink:0;">
          ${callBtn}
          <button onclick="_abOpenLead(${c.lead_id})" style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#4f46e5;cursor:pointer;white-space:nowrap;">${compact ? '<i class="fa-solid fa-folder-open"></i>' : 'Open Lead'}</button>
          ${compact ? '' : `<button onclick="markCallbackDone(${c.id}, ${c.lead_id})" style="font-size:11px;font-weight:600;background:#fff;border:1px solid #d1fae5;border-radius:6px;padding:5px 10px;color:#059669;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-check" style="margin-right:4px;font-size:10px;"></i>Done</button>`}
        </div>
      </div>`
  }

  // ── Helper: section wrapper ──────────────────────────────────────────────
  function _section(key, title, icon, items, emptyMsg, accentColor, paging) {
    const collapsed = items.length === 0
    const compact = _abViewMode === 'compact'
    const totalCount = paging && typeof paging.total === 'number' ? paging.total : items.length
    const showingLabel = paging && paging.total > 0
      ? ('Showing ' + paging.shown + ' of ' + paging.total)
      : ''
    const pager = paging && paging.total > 0
      ? `<div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:11px;color:#94a3b8;white-space:nowrap;">${showingLabel}</span>
            <button type="button" class="ab-page-btn" data-section-key="${key}" data-page-action="prev" ${paging.has_prev ? '' : 'disabled'} style="font-size:11px;font-weight:600;padding:4px 8px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:${paging.has_prev ? '#334155' : '#cbd5e1'};cursor:${paging.has_prev ? 'pointer' : 'default'};">Prev</button>
            <button type="button" class="ab-page-btn" data-section-key="${key}" data-page-action="next" ${paging.has_next ? '' : 'disabled'} style="font-size:11px;font-weight:600;padding:4px 8px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:${paging.has_next ? '#334155' : '#cbd5e1'};cursor:${paging.has_next ? 'pointer' : 'default'};">Next</button>
          </div>`
      : ''
    return `
      <div class="ab-section" data-section-key="${key}" data-collapsed="${collapsed ? '1' : '0'}" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(2,6,23,0.04);">
        <div class="ab-section-toggle" data-section-key="${key}" style="padding:${compact ? '11px 16px' : '14px 20px'};border-bottom:1px solid #f1f5f9;display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:${compact ? '28px' : '32px'};height:${compact ? '28px' : '32px'};border-radius:8px;background:${accentColor}15;display:flex;align-items:center;justify-content:center;color:${accentColor};font-size:${compact ? '13px' : '14px'};">${icon}</div>
            <h3 style="font-size:${compact ? '13px' : '14px'};font-weight:700;color:#0f172a;margin:0;">${title}</h3>
            <span style="background:${accentColor}15;color:${accentColor};font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;min-width:22px;text-align:center;">${totalCount}</span>
          </div>
          <div style="display:flex;align-items:center;gap:10px;">
            ${compact ? '' : pager}
            ${compact ? '' : `<span class="ab-updated" data-updated-at="${nowMs}" style="font-size:11px;color:#94a3b8;">Updated just now</span>`}
            <i class="fa-solid ${collapsed ? 'fa-chevron-down' : 'fa-chevron-up'}" style="font-size:11px;color:#94a3b8;"></i>
          </div>
        </div>
        <div class="ab-section-body" style="padding:${compact ? '8px 12px' : '12px 16px'};display:${collapsed ? 'none' : 'flex'};flex-direction:column;gap:${compact ? '6px' : '8px'};">
          ${items.length ? items.join('') : `<p style="color:#94a3b8;font-size:13px;margin:12px 0;text-align:center;font-style:italic;">${emptyMsg}</p>`}
        </div>
      </div>`
  }

  // ── Build sections ───────────────────────────────────────────────────────
  const sectionData = [
    {
      key: 'today_callbacks',
      title: callbacksLabel,
      icon: '<i class="fa-solid fa-phone"></i>',
      items: (data.today_callbacks || []).map(_callbackRow),
      emptyMsg: 'No callbacks scheduled for today.',
      accentColor: '#2563eb',
      paging: (data.pagination || {}).today_callbacks || null
    },
    {
      key: 'overdue_callbacks',
      title: 'Overdue Callbacks',
      icon: '<i class="fa-solid fa-triangle-exclamation"></i>',
      items: (data.overdue_callbacks || []).map(_callbackRow),
      emptyMsg: 'No overdue callbacks - great work!',
      accentColor: '#dc2626',
      paging: (data.pagination || {}).overdue_callbacks || null
    },
    {
      key: 'new_leads_today',
      title: newLeadsLabel,
      icon: '<i class="fa-solid fa-user-plus"></i>',
      items: (data.new_leads_today || []).map(l => {
        const age = l.created_at ? _leadAge(new Date(l.created_at)) : ''
        return _leadCard(l, age ? `<span style="background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px;">${age}</span>` : '')
      }),
      emptyMsg: 'No new leads assigned today.',
      accentColor: '#0891b2',
      paging: (data.pagination || {}).new_leads_today || null
    },
    {
      key: 'follow_up',
      title: followUpLabel,
      icon: '<i class="fa-solid fa-rotate"></i>',
      items: (data.follow_up_leads || []).map(l => _leadCard(l)),
      emptyMsg: 'No leads in Follow Up or Callback Scheduled status.',
      accentColor: '#7c3aed',
      paging: (data.pagination || {}).follow_up || null
    },
    {
      key: 'no_answer',
      title: noAnswerLabel,
      icon: '<i class="fa-solid fa-phone-slash"></i>',
      items: (data.no_answer_leads || []).map(l => _leadCard(l)),
      emptyMsg: 'No unanswered leads pending retry.',
      accentColor: '#ea580c',
      paging: (data.pagination || {}).no_answer || null
    },
    {
      key: 'warm_leads',
      title: warmLeadsLabel,
      icon: '<i class="fa-solid fa-sun"></i>',
      items: (data.warm_leads || []).map(l => _leadCard(l)),
      emptyMsg: 'No warm leads at the moment.',
      accentColor: '#f59e0b',
      paging: (data.pagination || {}).warm_leads || null
    },
    {
      key: 'hot_leads',
      title: hotLeadsLabel,
      icon: '<i class="fa-solid fa-fire"></i>',
      items: (data.hot_leads || []).map(l => _leadCard(l)),
      emptyMsg: 'No hot leads at the moment.',
      accentColor: '#6d28d9',
      paging: (data.pagination || {}).hot_leads || null
    }
  ]

  const sections = sectionData.map(function (sec) {
    return _section(sec.key, sec.title, sec.icon, sec.items, sec.emptyMsg, sec.accentColor, sec.paging)
  })

  const secEl = document.getElementById('abSections')
  if (secEl && _guard()) {
    secEl.innerHTML = sections.join('')
    _abWireSectionToggles(secEl)
    _abWirePagination(secEl)
    _abWireCardFocus(secEl)
  }

  _abRefreshUpdatedLabels()
  _abUpdatedTimer = setInterval(_abRefreshUpdatedLabels, 60000)
}


// ── Quick Actions ─────────────────────────────────────────────────────────

function _abLeadPriority(l) {
  const st = (l && l.status ? String(l.status) : '').toLowerCase()
  if (st.indexOf('hot') >= 0 || st === 'negotiation' || st === 'booking_done') {
    return { color: '#dc2626', label: 'High Priority' }
  }
  if (st === 'follow_up' || st === 'callback_scheduled' || st === 'interested' || st === 'site_visit_planned') {
    return { color: '#ea580c', label: 'Medium Priority' }
  }
  return { color: '#0891b2', label: 'Normal Priority' }
}

function _abWireSectionToggles(root) {
  var toggles = root.querySelectorAll('.ab-section-toggle')
  toggles.forEach(function (toggle) {
    toggle.onclick = function () {
      var section = toggle.closest('.ab-section')
      if (!section) return
      var body = section.querySelector('.ab-section-body')
      var chevron = toggle.querySelector('.fa-chevron-up, .fa-chevron-down')
      if (!body) return
      var collapsed = section.getAttribute('data-collapsed') === '1'
      if (collapsed) {
        body.style.display = 'flex'
        section.setAttribute('data-collapsed', '0')
        if (chevron) { chevron.classList.remove('fa-chevron-down'); chevron.classList.add('fa-chevron-up') }
      } else {
        body.style.display = 'none'
        section.setAttribute('data-collapsed', '1')
        if (chevron) { chevron.classList.remove('fa-chevron-up'); chevron.classList.add('fa-chevron-down') }
      }
    }
  })
}

function _abWireCardFocus(root) {
  var cards = root.querySelectorAll('.ab-lead-card')
  cards.forEach(function (card) {
    card.addEventListener('focus', function () {
      cards.forEach(function (c) { c.style.boxShadow = '' })
      card.style.boxShadow = '0 0 0 2px rgba(79,70,229,0.18)'
      _abFocusedLeadId = Number(card.getAttribute('data-lead-id') || 0) || null
      _abFocusedLeadPhone = card.getAttribute('data-phone') || ''
    })
    card.addEventListener('click', function () {
      card.focus()
    })
  })
}

function _abWirePagination(root) {
  var buttons = root.querySelectorAll('.ab-page-btn')
  buttons.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault()
      e.stopPropagation()
      if (btn.disabled) return
      var key = btn.getAttribute('data-section-key') || ''
      var action = btn.getAttribute('data-page-action') || ''
      if (!key || !action || typeof _abSectionPages[key] === 'undefined') return
      var currentPage = Number(_abSectionPages[key] || 1)
      _abSectionPages[key] = action === 'prev' ? Math.max(1, currentPage - 1) : (currentPage + 1)
      renderActionBoard(_abDateFrom, _abDateTo, _abRange)
    })
  })
}

function _abRefreshUpdatedLabels() {
  var labels = document.querySelectorAll('#abSections .ab-updated')
  labels.forEach(function (el) {
    var ts = Number(el.getAttribute('data-updated-at') || 0)
    if (!ts) return
    var mins = Math.max(0, Math.floor((Date.now() - ts) / 60000))
    el.textContent = mins === 0 ? 'Updated just now' : ('Updated ' + mins + ' min ago')
  })
}

function _abCallLead(phone, leadName) {
  if (!phone) {
    showToast('No phone number available for this lead.', 'warning')
    return
  }
  var sanitized = String(phone).replace(/[^0-9+]/g, '')
  if (!sanitized) {
    showToast('Invalid phone number.', 'warning')
    return
  }
  showToast('Opening dialer for ' + (leadName || 'lead') + '...', 'info')
  window.location.href = 'tel:' + sanitized
}

async function _abStartCallFlow(leadId, phone, leadName) {
  var id = Number(leadId)
  if (!Number.isFinite(id) || id <= 0) {
    showToast('Invalid lead selected.', 'warning')
    return
  }

  try {
    await fetch(`${API_BASE}/leads/${id}/call-activity`, {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ event_type: 'initiated', source: 'action_board' }),
    })
  } catch (_) {
    // Proceed even if the audit ping fails; the outcome log still matters.
  }

  _abOpenCallOutcomeModal(id, phone, leadName)
}

function _abOpenCallOutcomeModal(leadId, phone, leadName) {
  var id = Number(leadId)
  if (!Number.isFinite(id) || id <= 0) return

  var overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.setAttribute('data-call-modal', '1')
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:520px;width:100%;">
      <h3 class="sm-section-heading" style="margin-bottom:8px;">📞 Log Call Outcome</h3>
      <div style="font-size:13px;color:#64748b;margin-bottom:16px;line-height:1.5;">
        ${escape(leadName || 'Lead')} ${phone ? '· ' + escape(phone) : ''}
      </div>
      <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:6px;">Outcome *</label>
      <select id="abCallOutcome" class="select" style="width:100%;font-size:13px;margin-bottom:12px;">
        <option value="">Select outcome</option>
        <option value="connected">Connected</option>
        <option value="no_answer">No Answer</option>
        <option value="busy">Busy</option>
        <option value="wrong_number">Wrong Number</option>
        <option value="callback_scheduled">Callback Scheduled</option>
      </select>
      <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:6px;">Note</label>
      <textarea id="abCallNote" class="select" rows="3" style="width:100%;resize:vertical;font-size:13px;margin-bottom:14px;" placeholder="Optional call notes"></textarea>
      <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;">
        ${phone ? `<button class="button secondary" id="abDialNowBtn" type="button" style="font-size:13px;">Dial Now</button>` : ''}
        <button class="button secondary" id="abCancelCallBtn" type="button" style="font-size:13px;">Cancel</button>
        <button class="button" id="abSaveCallBtn" type="button" style="font-size:13px;">Save Outcome</button>
      </div>
    </div>`

  document.body.appendChild(overlay)

  function closeModal() {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay)
  }

  var cancelBtn = overlay.querySelector('#abCancelCallBtn')
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal)

  var dialBtn = overlay.querySelector('#abDialNowBtn')
  if (dialBtn && phone) {
    dialBtn.addEventListener('click', function () {
      _abCallLead(phone, leadName)
    })
  }

  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) closeModal()
  })

  var saveBtn = overlay.querySelector('#abSaveCallBtn')
  if (saveBtn) {
    saveBtn.addEventListener('click', async function () {
      var outcome = (overlay.querySelector('#abCallOutcome') || {}).value || ''
      var note = (overlay.querySelector('#abCallNote') || {}).value || ''
      if (!outcome) {
        showToast('Please select a call outcome.', 'warning')
        return
      }
      try {
        // For callback scheduling, do not block UX on call-activity logging.
        if (outcome === 'callback_scheduled' && typeof openCallbackModal === 'function') {
          _apiRequest(`/leads/${id}/call-activity`, {
            method: 'POST',
            headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
            body: JSON.stringify({
              event_type: 'outcome',
              outcome: outcome,
              note: note,
              source: 'action_board',
              phone: phone || '',
            }),
            retries: 0,
            timeoutMs: 15000,
          }).catch(function () {
            // Best-effort audit log only; scheduler flow must continue.
          })

          closeModal()
          setTimeout(function () {
            openCallbackModal(id, { requireSchedule: true })
          }, 200)
          return
        }

        await _apiRequest(`/leads/${id}/call-activity`, {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({
            event_type: 'outcome',
            outcome: outcome,
            note: note,
            source: 'action_board',
            phone: phone || '',
          }),
          retries: 0,
          timeoutMs: 20000,
        })

        closeModal()
        showToast('Call outcome saved.', 'success')

        if (typeof window.viewLeadDetails === 'function') {
          try {
            await window.viewLeadDetails(id)
            setTimeout(function () {
              var statusSelect = document.getElementById('newStatus')
              if (statusSelect) {
                statusSelect.scrollIntoView({ behavior: 'smooth', block: 'center' })
                statusSelect.focus()
              }
            }, 150)
          } catch (_) {
            // Save already succeeded; avoid surfacing this as an outcome failure.
          }
        }
      } catch (err) {
        showToast((err && err.message) || 'Failed to save call outcome.', 'error')
      }
    })
  }
  var outcomeSel = overlay.querySelector('#abCallOutcome')
  if (outcomeSel) outcomeSel.focus()
}

function _abHandleShortcut(e) {
  if (window._ACTIVE_ROUTE !== 'action_board') return
  var t = e && e.target
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
  var key = (e.key || '').toLowerCase()
  if (key === 'o' && _abFocusedLeadId) {
    e.preventDefault()
    _abOpenLead(_abFocusedLeadId)
    return
  }
  if (key === 'n' && _abFocusedLeadId) {
    e.preventDefault()
    _abQuickNote(_abFocusedLeadId)
    return
  }
  if (key === 'c' && _abFocusedLeadPhone) {
    e.preventDefault()
    _abCallLead(_abFocusedLeadPhone, 'lead')
  }
}

function _abOpenLead(leadId) {
  var id = Number(leadId)
  if (!Number.isFinite(id) || id <= 0) {
    showToast('Invalid lead selected.', 'warning')
    return
  }
  var openFn = (typeof window.viewLeadDetails === 'function')
    ? window.viewLeadDetails
    : (typeof viewLeadDetails === 'function' ? viewLeadDetails : null)
  if (!openFn) {
    showToast('Lead detail page is still loading. Try again.', 'warning')
    return
  }
  Promise.resolve().then(function () {
    return openFn(id)
  }).catch(function () {
    showToast('Lead page failed to load. Please retry.', 'error')
  })
}

if (!window.__abShortcutBound) {
  window.addEventListener('keydown', _abHandleShortcut)
  window.__abShortcutBound = true
}

function _leadAge(created) {
  const mins = Math.floor((Date.now() - created.getTime()) / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs  = Math.floor(mins / 60)
  if (hrs  < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)

  return `${days}d ago`
}

function _abQuickNote(leadId) {
  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:440px;width:100%;">
      <h3 class="sm-section-heading" style="margin-bottom:14px;">✏️ Quick Note</h3>
      <textarea id="abNoteText" class="select" rows="4" style="width:100%;resize:vertical;font-size:13px;" placeholder="Write a note..."></textarea>
      <div style="display:flex;gap:8px;margin-top:14px;">
        <button class="button" onclick="_abSubmitNote(${leadId})" style="flex:1;">Save Note</button>
        <button class="button secondary" onclick="this.closest('.modal-overlay').remove()" style="flex:1;">Cancel</button>
      </div>
    </div>`
  document.body.appendChild(overlay)
  overlay.querySelector('#abNoteText').focus()
}

async function _abSubmitNote(leadId) {
  const overlay = document.querySelector('.modal-overlay')
  const text = (document.getElementById('abNoteText') || {}).value?.trim()
  if (!text) { showToast('Please enter a note.', 'warning'); return }
  try {
    await _apiRequest(`/leads/${leadId}/notes`, {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ note: text }),
      retries: 0,
    })
    showToast('Note saved.', 'success')
    if (overlay) overlay.remove()
  } catch {
    showToast('Failed to save note.', 'error')
  }
}

function _abCallCallback(leadId) {
  if (typeof openCallbackModal === 'function') {
    openCallbackModal(leadId)
  } else {
    showToast('Callback scheduler is loading...', 'info')
  }
}
