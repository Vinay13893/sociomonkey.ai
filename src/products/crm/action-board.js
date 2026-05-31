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
var _abSearchQuery = ''
var _abActiveSectionKey = 'today_callbacks'
var _abCurrentSections = []
var _abLastRenderMs = 0
var _abPageSize = 6
var _abPageSizeMode = 'auto'
var _abResizeTimer = null
var _abSectionPages = {
  today_callbacks: 1,
  overdue_callbacks: 1,
  new_leads_today: 1,
  follow_up: 1,
  no_answer: 1,
  warm_leads: 1,
  hot_leads: 1,
}

function _abRefreshPreservingState() {
  var scrollY = window.scrollY || 0
  var activeKey = _abActiveSectionKey
  var search = _abSearchQuery
  var pageSize = _abPageSize
  var pageSizeMode = _abPageSizeMode
  var sectionPages = {}
  Object.keys(_abSectionPages).forEach(function (key) {
    sectionPages[key] = _abSectionPages[key]
  })
  return Promise.resolve(renderActionBoard(_abDateFrom, _abDateTo, _abRange)).then(function () {
    _abActiveSectionKey = activeKey
    _abSearchQuery = search
    _abPageSize = pageSize
    _abPageSizeMode = pageSizeMode
    Object.keys(sectionPages).forEach(function (key) {
      _abSectionPages[key] = sectionPages[key]
    })
    window.scrollTo(0, scrollY)
  })
}

function _abOpenStatusModal(leadId, preferredStatus) {
  var id = Number(leadId)
  if (!Number.isFinite(id) || id <= 0) return
  var overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:420px;width:100%;">
      <h3 class="sm-section-heading" style="margin-bottom:10px;">Update Lead Status</h3>
      <select id="abNextStatus" class="select" style="width:100%;font-size:13px;margin-bottom:14px;">
        <option value="">Select status</option>
        ${_abStatusOptions.map(function (opt) { return `<option value="${opt.value}" ${opt.value === preferredStatus ? 'selected' : ''}>${opt.label}</option>` }).join('')}
      </select>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button class="button secondary" id="abCancelStatusBtn" type="button" style="font-size:13px;">Cancel</button>
        <button class="button" id="abSaveStatusBtn" type="button" style="font-size:13px;">Save Status</button>
      </div>
    </div>`
  document.body.appendChild(overlay)

  function closeModal() {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay)
  }

  var cancelBtn = overlay.querySelector('#abCancelStatusBtn')
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal)
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) closeModal()
  })

  var saveBtn = overlay.querySelector('#abSaveStatusBtn')
  if (saveBtn) {
    saveBtn.addEventListener('click', async function () {
      var nextStatus = (overlay.querySelector('#abNextStatus') || {}).value || ''
      if (!nextStatus) {
        showToast('Please select a status.', 'warning')
        return
      }
      try {
        await _apiRequest(`/leads/${id}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ status: nextStatus }),
          retries: 0,
        })
        closeModal()
        showToast('Lead status updated.', 'success')
        await _abRefreshPreservingState()
        if (await confirmDialog('Add Note?', 'Yes', '#4f46e5')) {
          _abQuickNote(id)
        }
      } catch (err) {
        showToast((err && err.message) || 'Failed to update status.', 'error')
      }
    })
  }
}
var _abStatusOptions = [
  { value: 'interested', label: 'Interested' },
  { value: 'site_visit_planned', label: 'Site Visit Planned' },
  { value: 'negotiation', label: 'Negotiation' },
  { value: 'no_answer', label: 'No Answer' },
  { value: 'not_interested', label: 'Not Interested' },
  { value: 'follow_up', label: 'Follow Up' },
  { value: 'callback_scheduled', label: 'Callback Scheduled' },
  { value: 'new', label: 'New' },
  { value: 'site_visit_done', label: 'Site Visit Done' },
  { value: 'booking_done', label: 'Closed' },
  { value: 'lost', label: 'Lost' },
  { value: 'junk', label: 'Junk' },
]
var _abStatusMeta = {
  new: { label: 'New', bg: '#eaf2ff', color: '#1d4ed8', border: '#bfdbfe' },
  interested: { label: 'Interested', bg: '#ecfeff', color: '#0e7490', border: '#a5f3fc' },
  site_visit_planned: { label: 'Site Visit Planned', bg: '#f5f3ff', color: '#6d28d9', border: '#ddd6fe' },
  site_visit_done: { label: 'Site Visit Done', bg: '#ecfdf5', color: '#166534', border: '#bbf7d0' },
  negotiation: { label: 'Negotiation', bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' },
  follow_up: { label: 'Follow Up', bg: '#eef2ff', color: '#4338ca', border: '#c7d2fe' },
  callback_scheduled: { label: 'Callback Scheduled', bg: '#fefce8', color: '#a16207', border: '#fde68a' },
  no_answer: { label: 'No Answer', bg: '#fffbeb', color: '#b45309', border: '#fcd34d' },
  not_interested: { label: 'Not Interested', bg: '#f8fafc', color: '#475569', border: '#cbd5e1' },
  booking_done: { label: 'Closed', bg: '#ecfdf3', color: '#14532d', border: '#86efac' },
  lost: { label: 'Lost', bg: '#f8fafc', color: '#64748b', border: '#cbd5e1' },
  junk: { label: 'Junk', bg: '#f8fafc', color: '#64748b', border: '#cbd5e1' },
}

function _abRangeShortLabel(range) {
  if (range === 'today') return 'Today'
  if (range === 'this_week') return 'This Week'
  if (range === 'this_month') return 'This Month'
  if (range === 'last_30_days') return 'Last 30 Days'
  if (range === 'custom') return 'Custom'
  return 'All Time'
}

function _abNextCallbackLabel(item) {
  if (!item) return '—'
  var raw = item.next_callback_datetime || item.next_callback_at || item.next_callback || ''
  if (!raw) return '—'
  var dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).replace(',', '')
}

function _abRecommendedPageSize() {
  var viewportH = window.innerHeight || 820
  var customPenalty = _abRange === 'custom' ? 38 : 0
  var fixedLayout = 288 + customPenalty
  var available = Math.max(280, viewportH - fixedLayout)
  var rowHeight = 52
  var rawRows = Math.max(1, Math.floor(available / rowHeight))
  var stepRows = Math.max(1, Math.floor(rawRows / 6))
  return Math.max(6, Math.min(18, stepRows * 6))
}

function _abBindResizeAutofit() {
  if (window.__abResizeFitBound) return
  window.__abResizeFitBound = true
  window.addEventListener('resize', function () {
    if (window._ACTIVE_ROUTE !== 'action_board' || _abPageSizeMode !== 'auto') return
    if (_abResizeTimer) clearTimeout(_abResizeTimer)
    _abResizeTimer = setTimeout(function () {
      var nextSize = _abRecommendedPageSize()
      if (nextSize !== _abPageSize) {
        _abPageSize = nextSize
        Object.keys(_abSectionPages).forEach(function (key) { _abSectionPages[key] = 1 })
        renderActionBoard(_abDateFrom, _abDateTo, _abRange)
      }
    }, 180)
  })
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
  _abBindResizeAutofit()

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
  function _iso(d) {
    var y = d.getFullYear()
    var m = String(d.getMonth() + 1).padStart(2, '0')
    var day = String(d.getDate()).padStart(2, '0')
    return y + '-' + m + '-' + day
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
  const fmtHeader = function (d) { return new Date(d).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) }
  const callbacksLabel = 'Today\'s Callbacks'
  const newLeadsLabel = 'New Leads'
  const followUpLabel = 'Follow Up'
  const noAnswerLabel = 'No Answer'
  const warmLeadsLabel = 'Warm Leads'
  const hotLeadsLabel = 'Hot Leads'
  const boardTitle = "Today's Action Board"
  const greetingPrefix = now.getHours() < 12 ? 'Good Morning' : (now.getHours() < 17 ? 'Good Afternoon' : 'Good Evening')
  const headerDateLabel = fmtHeader(_iso(now))
  if (_abPageSizeMode === 'auto') _abPageSize = _abRecommendedPageSize()

  // Skeleton shell
  content.innerHTML = `
    <div class="ab-root-shell" style="width:100%;max-width:none;margin:0 auto;padding:10px 14px 12px;" id="actionBoardRoot">
      <div class="sm-page-header ab-header-shell" style="margin-bottom:8px;align-items:flex-start;gap:8px;">
        <div style="min-width:0;">
          <h2 class="sm-page-title ab-page-title" style="margin:0 0 2px;">${boardTitle}</h2>
          <p id="abHeaderMeta" class="sm-small sm-text-muted ab-header-meta" style="margin:0;">Loading workbench status...</p>
        </div>
        <span id="abHeaderDate" class="ab-header-date" style="white-space:nowrap;">${headerDateLabel}</span>
      </div>

      <div class="dash-filters ab-filter-bar" style="margin-bottom:8px;">
        <div class="dash-filter-group">
          <label class="dash-filter-label">Range</label>
          <select id="abRangeFilter" class="dash-filter-ctl">
            <option value="" ${_abRange === '' ? 'selected' : ''}>All Time</option>
            <option value="today" ${_abRange === 'today' ? 'selected' : ''}>Today</option>
            <option value="this_week" ${_abRange === 'this_week' ? 'selected' : ''}>This Week</option>
            <option value="this_month" ${_abRange === 'this_month' ? 'selected' : ''}>This Month</option>
            <option value="last_30_days" ${_abRange === 'last_30_days' ? 'selected' : ''}>Last 30 Days</option>
            <option value="custom" ${_abRange === 'custom' ? 'selected' : ''}>Custom Date</option>
          </select>
        </div>
        <div id="abCustomRange" class="ab-custom-range" style="display:${_abRange === 'custom' ? 'flex' : 'none'};gap:8px;align-items:flex-end;">
          <div class="dash-filter-group">
            <label class="dash-filter-label">From Date</label>
            <input type="date" id="abDateFrom" class="dash-filter-ctl" value="${_abDateFrom}" />
          </div>
          <div class="dash-filter-group">
            <label class="dash-filter-label">To Date</label>
            <input type="date" id="abDateTo" class="dash-filter-ctl" value="${_abDateTo}" />
          </div>
        </div>
        <div class="dash-filter-group ab-search-group">
          <label class="dash-filter-label">Lead Search</label>
          <input type="text" id="abSearchInput" class="dash-filter-ctl ab-search-input" value="${escape(_abSearchQuery)}" placeholder="Search by name, mobile, email, or project" />
        </div>
        <div class="dash-filter-group ab-search-actions">
          <label class="dash-filter-label" style="visibility:hidden;">Search</label>
          <div style="display:flex;gap:8px;align-items:center;">
            <button id="abSearchBtn" type="button" class="dash-refresh-btn" style="background:#1e3a5f;">Search</button>
            <button id="abSearchResetBtn" type="button" class="sm-btn sm-btn-secondary" style="height:34px;">Reset</button>
          </div>
        </div>
      </div>

      <div id="abWorkspace" class="ab-workspace-shell">
        <div class="ab-kpi-strip-skeleton">
          ${[1,2,3,4,5,6,7].map(() => `<div class="ab-kpi-skeleton-tile"></div>`).join('')}
        </div>
        <div class="ab-panel-skeleton">
          <div style="height:18px;width:220px;background:#f1f5f9;border-radius:6px;margin-bottom:14px;animation:_loaderBar 1.4s infinite;"></div>
          <div style="height:12px;width:100%;background:#f8fafc;border-radius:4px;margin-bottom:10px;"></div>
          <div style="height:12px;width:100%;background:#f8fafc;border-radius:4px;margin-bottom:10px;"></div>
          <div style="height:12px;width:86%;background:#f8fafc;border-radius:4px;"></div>
        </div>
      </div>
    </div>
  `

  const abRangeFilter = document.getElementById('abRangeFilter')
  const abCustomRange = document.getElementById('abCustomRange')
  const abDateFrom = document.getElementById('abDateFrom')
  const abDateTo = document.getElementById('abDateTo')
  const abSearchInput = document.getElementById('abSearchInput')
  const abSearchBtn = document.getElementById('abSearchBtn')
  const abSearchResetBtn = document.getElementById('abSearchResetBtn')

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

  function _abApplySearch() {
    _abSearchQuery = (abSearchInput && abSearchInput.value ? abSearchInput.value : '').trim()
    _abRenderWorkspace()
  }
  if (abSearchInput) {
    abSearchInput.addEventListener('input', _abApplySearch)
    abSearchInput.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return
      e.preventDefault()
      _abApplySearch()
    })
  }
  if (abSearchBtn) abSearchBtn.addEventListener('click', _abApplySearch)
  if (abSearchResetBtn) {
    abSearchResetBtn.addEventListener('click', function () {
      _abSearchQuery = ''
      if (abSearchInput) abSearchInput.value = ''
      _abRenderWorkspace()
    })
  }

  _actionBoardRenderInFlight = false

  // Fetch data
  let data
  try {
    const params = new URLSearchParams()
    params.set('page_size', String(_abPageSize || 6))
    if (queryFrom) params.set('date_from', queryFrom)
    if (queryTo) params.set('date_to', queryTo)
    Object.keys(_abSectionPages).forEach(function (key) {
      var page = Number(_abSectionPages[key] || 1)
      if (page > 1 || page === 1) params.set(key + '_page', String(page))
    })
    const qs = params.toString() ? '?' + params.toString() : ''
    data = await _apiRequest(`/leads/action-board${qs}`, {
      headers: _apiAuthHeaders(),
      retries: 2,
      timeoutMs: 20000,
    })

    // Callback rows may not always include project/latest note fields depending on backend version.
    // Enrich missing fields from lead details so Action Board columns remain complete.
    const callbackRows = (data.today_callbacks || []).concat(data.overdue_callbacks || [])
    const needsEnrichment = []
    const seenLeadIds = {}
    callbackRows.forEach(function (r) {
      const lid = Number(r.lead_id || 0)
      if (!lid || seenLeadIds[lid]) return
      if (!r.project_name || typeof r.latest_note === 'undefined' || !r.lead_phone || !r.lead_status || !r.assigned_to_name) {
        needsEnrichment.push(lid)
      }
      seenLeadIds[lid] = true
    })

    if (needsEnrichment.length) {
      const leadPairs = await Promise.all(needsEnrichment.map(async function (lid) {
        try {
          const lj = await _apiRequest(`/leads/${lid}`, {
            headers: _apiAuthHeaders(),
            retries: 1,
            timeoutMs: 15000,
          })
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
        if (!r.lead_email) r.lead_email = lead.email || ''
        if (!r.lead_status) r.lead_status = lead.status || ''
        if (!r.lead_name) r.lead_name = lead.name || ('Lead #' + r.lead_id)
        if (!r.assigned_to_name) r.assigned_to_name = lead.assigned_to_name || lead.assigned_user_name || 'Unassigned'
      })
    }
  } catch (err) {
    if (!_guard()) return
    document.getElementById('abWorkspace').innerHTML = `
      <div style="text-align:center;padding:60px 20px;">
        <div style="font-size:36px;margin-bottom:12px;">⚠️</div>
        <p style="color:#64748b;">Failed to load action board${err && err.message ? ': ' + String(err.message) : ''}. <button class="button" onclick="renderActionBoard(_abDateFrom, _abDateTo)" style="font-size:13px;">Retry</button></p>
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
  const briefing = Number(s.overdue_count || 0) > 0
    ? `${Number(s.overdue_count || 0)} overdue callback${Number(s.overdue_count || 0) === 1 ? '' : 's'} require attention.`
    : 'No pending actions. Have a productive day.'
  const headerMetaEl = document.getElementById('abHeaderMeta')
  const headerDateEl = document.getElementById('abHeaderDate')
  if (headerMetaEl) headerMetaEl.textContent = `${greetingPrefix}, ${user.name} • ${briefing}`
  if (headerDateEl) headerDateEl.textContent = headerDateLabel

  // ── Helper: lead mini-card ───────────────────────────────────────────────
  function _leadCard(l, extra) {
    const priority = _abLeadPriority(l)
    const age = l.created_at ? _leadAge(new Date(l.created_at)) : ''
    const compact = _abViewMode === 'compact'
    const phone = l.phone || ''
    const alternatePhone = l.alternate_phone || ''
    const project = l.project_name || '-'
    const nextCallback = _abNextCallbackLabel(l)
    const latestNote = (l.latest_note || '').trim()
    const safePhone = escape(phone)
    const safeAlternatePhone = escape(alternatePhone)
    const callPhoneArg = JSON.stringify(phone)
    const callAlternatePhoneArg = JSON.stringify(alternatePhone)
    const callNameArg = JSON.stringify(l.name || 'Lead')
    const compactNameStyle = compact ? 'font-weight:700;font-size:12.5px;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;' : 'font-weight:700;font-size:13px;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
    const avatarStyle = compact ? 'width:30px;height:30px;border-radius:9px;background:#eef2ff;color:#4f46e5;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;flex-shrink:0;' : 'width:34px;height:34px;border-radius:10px;background:#eef2ff;color:#4f46e5;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;flex-shrink:0;'
    const callBtn = phone
      ? `<button onclick='_abStartCallFlow(${l.id}, ${callPhoneArg}, ${callNameArg}, ${callAlternatePhoneArg})' style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #dbeafe;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#1d4ed8;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-phone" style="margin-right:${compact ? '0' : '4px'};font-size:10px;"></i>${compact ? '' : 'Call'}</button>`
      : ''
    const statusControl = _abStatusControl(l.id, l.status)
    return `
      <div class="ab-lead-card ab-row-shell" data-lead-id="${l.id}" data-phone="${safePhone}" tabindex="0" style="border-left:4px solid ${priority.color};">
        <div class="ab-row-identity">
          <div style="${avatarStyle}">${escape((l.name||'?')[0]).toUpperCase()}</div>
          <div class="ab-row-identity-copy">
            <button onclick="_abOpenLead(${l.id})" style="${compactNameStyle}background:none;border:none;padding:0;cursor:pointer;color:#1e40af;text-decoration:underline;text-underline-offset:2px;text-decoration-color:rgba(30,64,175,.35);">${escape(l.name||'')}</button>
            <div class="ab-row-age">${escape(age || '1 Day')} • ${escape(priority.short)}</div>
            <div class="ab-row-phone"><strong style="color:#334155;">Phone:</strong> ${escape(phone || '—')}${alternatePhone ? ` <span style="color:#64748b;">· Alt ${safeAlternatePhone}</span>` : ''}</div>
          </div>
        </div>
        <div class="ab-row-context">
          <div class="ab-row-label">Project</div>
          <div class="ab-row-value">${escape(project)}</div>
          <div class="ab-row-label" style="margin-top:2px;">Latest Note</div>
          <div class="ab-row-note" title="${escape(latestNote || 'No notes')}">${escape(latestNote || 'No notes')}</div>
        </div>
        <div class="ab-row-callback">
          <div class="ab-row-label">Next Callback</div>
          <div class="ab-row-value">${escape(nextCallback)}</div>
        </div>
        <div class="ab-row-status-cell">${statusControl}</div>
        ${extra || ''}
        <div class="ab-row-actions">
          ${callBtn}
          <button onclick="_abOpenLead(${l.id})" style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#4f46e5;cursor:pointer;white-space:nowrap;">${compact ? '<i class="fa-solid fa-folder-open"></i>' : 'Open Lead'}</button>
          <button onclick="_abQuickNote(${l.id})" style="font-size:11px;font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#64748b;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-pen-to-square" style="margin-right:4px;font-size:10px;"></i>Note</button>
          <button onclick="_abCallCallback(${l.id})" style="font-size:11px;font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#0369a1;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-calendar-plus" style="margin-right:4px;font-size:10px;"></i>Callback</button>
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
    const alternatePhone = c.lead_alternate_phone || c.alternate_phone || ''
    const project = c.project_name || c.project || c.project_title || '-'
    const latestNote = (c.latest_note || '').trim()
    const safePhone = escape(phone)
    const safeAlternatePhone = escape(alternatePhone)
    const callPhoneArg = JSON.stringify(phone)
    const callAlternatePhoneArg = JSON.stringify(alternatePhone)
    const callNameArg = JSON.stringify(c.lead_name || 'Lead')
    const compactNameStyle = compact ? 'font-weight:700;font-size:12.5px;color:#0f172a;' : 'font-weight:600;font-size:13px;color:#0f172a;'
    const callBtn = phone
      ? `<button onclick='_abStartCallFlow(${c.lead_id}, ${callPhoneArg}, ${callNameArg}, ${callAlternatePhoneArg})' style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #dbeafe;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#1d4ed8;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-phone" style="margin-right:${compact ? '0' : '4px'};font-size:10px;"></i>${compact ? '' : 'Call'}</button>`
      : ''
    const timeStr = dt.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
    const statusText = (c.lead_status || '').replace(/_/g,' ') || 'callback'
    const statusControl = c.lead_id ? _abStatusControl(c.lead_id, c.lead_status) : ''
    return `
      <div class="ab-lead-card ab-row-shell" data-lead-id="${c.lead_id}" data-phone="${safePhone}" tabindex="0" style="background:${compact ? '#fff' : bg};border-left:4px solid ${col};border-color:${col}22;">
        <div class="ab-row-identity">
          <div style="width:${compact ? '28px' : '32px'};height:${compact ? '28px' : '32px'};border-radius:10px;background:${col}15;display:flex;align-items:center;justify-content:center;color:${col};font-size:${compact ? '12px' : '14px'};flex-shrink:0;"><i class="${faIcon}"></i></div>
          <div class="ab-row-identity-copy">
            <button onclick="_abOpenLead(${c.lead_id})" style="${compactNameStyle}background:none;border:none;padding:0;cursor:pointer;color:#1e40af;text-decoration:underline;text-underline-offset:2px;text-decoration-color:rgba(30,64,175,.35);">${escape(c.lead_name||'')}</button>
            <div class="ab-row-age">${escape((c.lead_created_at ? _leadAge(new Date(c.lead_created_at)) : '1 Day'))} • Callback</div>
            <div class="ab-row-phone"><strong style="color:#334155;">Phone:</strong> ${escape(phone || '—')}${alternatePhone ? ` <span style="color:#64748b;">· Alt ${safeAlternatePhone}</span>` : ''}</div>
          </div>
        </div>
        <div class="ab-row-context">
          <div class="ab-row-label">Project</div>
          <div class="ab-row-value">${escape(project)}</div>
          <div class="ab-row-label" style="margin-top:2px;">Latest Note</div>
          <div class="ab-row-note" title="${escape(latestNote || 'No notes')}">${escape(latestNote || 'No notes')}</div>
        </div>
        <div class="ab-row-callback">
          <div class="ab-row-label">Next Callback</div>
          <div class="ab-row-value">${escape(timeStr)}</div>
        </div>
        <div class="ab-row-status-cell">${statusControl}</div>
        <div class="ab-row-actions">
          ${callBtn}
          <button onclick="_abOpenLead(${c.lead_id})" style="font-size:${compact ? '10px' : '11px'};font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:${compact ? '4px 8px' : '5px 10px'};color:#4f46e5;cursor:pointer;white-space:nowrap;">${compact ? '<i class="fa-solid fa-folder-open"></i>' : 'Open Lead'}</button>
          <button onclick="_abQuickNote(${c.lead_id})" style="font-size:11px;font-weight:600;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#64748b;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-pen-to-square" style="margin-right:4px;font-size:10px;"></i>Note</button>
          <button onclick="markCallbackDone(${c.id}, ${c.lead_id})" style="font-size:11px;font-weight:600;background:#fff;border:1px solid #d1fae5;border-radius:6px;padding:5px 10px;color:#059669;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-check" style="margin-right:4px;font-size:10px;"></i>Done</button>
        </div>
      </div>`
  }

  // ── Build sections ───────────────────────────────────────────────────────
  const sectionData = [
    {
      key: 'today_callbacks',
      title: callbacksLabel,
      icon: '<i class="fa-solid fa-phone"></i>',
      rawItems: data.today_callbacks || [],
      renderItem: _callbackRow,
      emptyMsg: 'No callbacks scheduled for today.',
      accentColor: '#2563eb',
      paging: (data.pagination || {}).today_callbacks || null,
      count: s.today_callbacks_count || 0,
    },
    {
      key: 'overdue_callbacks',
      title: 'Overdue Callbacks',
      icon: '<i class="fa-solid fa-triangle-exclamation"></i>',
      rawItems: data.overdue_callbacks || [],
      renderItem: _callbackRow,
      emptyMsg: 'No overdue callbacks - great work!',
      accentColor: '#dc2626',
      paging: (data.pagination || {}).overdue_callbacks || null,
      count: s.overdue_count || 0,
    },
    {
      key: 'new_leads_today',
      title: newLeadsLabel,
      icon: '<i class="fa-solid fa-user-plus"></i>',
      rawItems: data.new_leads_today || [],
      renderItem: function (l) {
        const age = l.created_at ? _leadAge(new Date(l.created_at)) : ''
        return _leadCard(l, age ? `<span style="background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px;">${age}</span>` : '')
      },
      emptyMsg: 'No new leads assigned today.',
      accentColor: '#0891b2',
      paging: (data.pagination || {}).new_leads_today || null,
      count: s.new_leads_count || 0,
    },
    {
      key: 'follow_up',
      title: followUpLabel,
      icon: '<i class="fa-solid fa-rotate"></i>',
      rawItems: data.follow_up_leads || [],
      renderItem: _leadCard,
      emptyMsg: 'No leads in Follow Up or Callback Scheduled status.',
      accentColor: '#7c3aed',
      paging: (data.pagination || {}).follow_up || null,
      count: s.follow_up_count || 0,
    },
    {
      key: 'no_answer',
      title: noAnswerLabel,
      icon: '<i class="fa-solid fa-phone-slash"></i>',
      rawItems: data.no_answer_leads || [],
      renderItem: _leadCard,
      emptyMsg: 'No unanswered leads pending retry.',
      accentColor: '#ea580c',
      paging: (data.pagination || {}).no_answer || null,
      count: s.no_answer_count || 0,
    },
    {
      key: 'warm_leads',
      title: warmLeadsLabel,
      icon: '<i class="fa-solid fa-sun"></i>',
      rawItems: data.warm_leads || [],
      renderItem: _leadCard,
      emptyMsg: 'No warm leads at the moment.',
      accentColor: '#f59e0b',
      paging: (data.pagination || {}).warm_leads || null,
      count: s.warm_leads_count || 0,
    },
    {
      key: 'hot_leads',
      title: hotLeadsLabel,
      icon: '<i class="fa-solid fa-fire"></i>',
      rawItems: data.hot_leads || [],
      renderItem: _leadCard,
      emptyMsg: 'No hot leads at the moment.',
      accentColor: '#6d28d9',
      paging: (data.pagination || {}).hot_leads || null,
      count: s.hot_leads_count || 0,
    }
  ]

  _abCurrentSections = sectionData
  if (!_abCurrentSections.some(function (sec) { return sec.key === _abActiveSectionKey })) {
    _abActiveSectionKey = _abCurrentSections.length ? _abCurrentSections[0].key : 'today_callbacks'
  }
  _abLastRenderMs = Date.now()
  if (_guard()) _abRenderWorkspace()

  _abRefreshUpdatedLabels()
  _abUpdatedTimer = setInterval(_abRefreshUpdatedLabels, 60000)
}

function _abGetSearchFields(section, item) {
  if (!section || !item) return []
  if (section.key === 'today_callbacks' || section.key === 'overdue_callbacks') {
    return [item.lead_name || '', item.lead_phone || '', item.lead_email || item.email || '', item.project_name || '']
  }
  return [item.name || '', item.phone || '', item.email || '', item.project_name || '']
}

function _abFilterSectionItems(section) {
  var items = Array.isArray(section && section.rawItems) ? section.rawItems : []
  var q = (_abSearchQuery || '').toLowerCase().trim()
  if (!q) return items
  return items.filter(function (item) {
    return _abGetSearchFields(section, item).some(function (value) {
      return String(value || '').toLowerCase().includes(q)
    })
  })
}

function _abFormatActionDate(raw) {
  if (!raw) return '—'
  var dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).replace(',', '')
}

function _abNotePreview(note) {
  var text = String(note || '').replace(/\s+/g, ' ').trim()
  if (!text) return '—'
  return text.length > 30 ? (text.slice(0, 30).trimEnd() + '...') : text
}

function _abOpenNoteEditor(leadId) {
  if (typeof openLeadInlineNoteEditor === 'function') return openLeadInlineNoteEditor(leadId)
  return _abQuickNote(leadId)
}

function _abOpenCallbackScheduler(leadId) {
  if (typeof openLeadCallbackScheduler === 'function') return openLeadCallbackScheduler(leadId)
  return _abCallCallback(leadId)
}

function _abNormalizeActionRow(section, item) {
  var isCallback = section && (section.key === 'today_callbacks' || section.key === 'overdue_callbacks')
  var leadId = Number(isCallback ? item.lead_id : item.id)
  var status = String(isCallback ? (item.lead_status || '') : (item.status || '')).toLowerCase()
  var priority = _abLeadPriority({ status: status })
  var createdAt = isCallback ? item.lead_created_at : item.created_at
  var age = createdAt ? _leadAge(new Date(createdAt)) : '1 Day'
  var nextCallback = isCallback
    ? _abFormatActionDate(item.callback_datetime)
    : _abFormatActionDate(item.next_callback_datetime || item.next_callback_at || item.next_callback)
  return {
    leadId: leadId,
    name: isCallback ? (item.lead_name || ('Lead #' + leadId)) : (item.name || ('Lead #' + leadId)),
    age: age,
    priority: priority.short,
    phone: isCallback ? (item.lead_phone || item.phone || '') : (item.phone || ''),
    status: status,
    project: isCallback ? (item.project_name || item.project || item.project_title || '—') : (item.project_name || '—'),
    latestNote: isCallback ? (item.latest_note || '') : (item.latest_note || ''),
    nextCallback: nextCallback,
  }
}

function _abRenderActionRow(section, item) {
  var row = _abNormalizeActionRow(section, item)
  if (!row.leadId) return ''
  var callPhoneArg = JSON.stringify(row.phone || '')
  var callNameArg = JSON.stringify(row.name || 'Lead')
  var notePreview = _abNotePreview(row.latestNote)
  return `
    <tr class="ab-action-row ab-lead-card" data-lead-id="${row.leadId}" data-phone="${escape(row.phone || '')}" tabindex="0">
      <td>
        <div class="ab-action-name-cell">
          <button type="button" class="ab-action-name-btn" onclick="_abOpenLead(${row.leadId})">${escape(row.name)}</button>
          <div class="ab-action-name-meta">${escape(row.age)} • ${escape(row.priority)}</div>
        </div>
      </td>
      <td><span class="ab-cell-text">${escape(row.phone || '—')}</span></td>
      <td data-ab-no-open="1"><div class="ab-action-status" data-ab-no-open="1">${_abStatusControl(row.leadId, row.status)}</div></td>
      <td><span class="ab-cell-text" title="${escape(row.project)}">${escape(row.project)}</span></td>
      <td>
        <div class="ab-note-cell" title="${escape(row.latestNote || 'No notes')}">
          <span class="ab-note-preview">${escape(notePreview)}</span>
        </div>
      </td>
      <td>
        <div class="ab-callback-cell">
          <span class="ab-cell-text" title="${escape(row.nextCallback)}">${escape(row.nextCallback)}</span>
        </div>
      </td>
      <td>
        <div class="ab-action-buttons">
          ${row.phone ? `<button type="button" class="ab-row-action-btn" onclick='_abStartCallFlow(${row.leadId}, ${callPhoneArg}, ${callNameArg}, ${JSON.stringify(row.alternate_phone || row.lead_alternate_phone || '')})'><span class="ab-row-action-icon">📞</span><span class="ab-row-action-label">Call</span></button>` : ''}
          <button type="button" class="ab-row-action-btn" onclick="_abOpenNoteEditor(${row.leadId})"><span class="ab-row-action-icon">📝</span><span class="ab-row-action-label">Note</span></button>
          <button type="button" class="ab-row-action-btn" onclick="_abOpenCallbackScheduler(${row.leadId})"><span class="ab-row-action-icon">📅</span><span class="ab-row-action-label">Callback</span></button>
        </div>
      </td>
    </tr>`
}

function _abRenderWorkspace() {
  var workspace = document.getElementById('abWorkspace')
  if (!workspace || !workspace.isConnected) return
  if (!_abCurrentSections || !_abCurrentSections.length) {
    workspace.innerHTML = '<div class="message">No KPI data available.</div>'
    return
  }

  var active = _abCurrentSections.find(function (sec) { return sec.key === _abActiveSectionKey }) || _abCurrentSections[0]
  _abActiveSectionKey = active.key
  var isMobile = (window.innerWidth || 0) <= 768
  var filteredItems = _abFilterSectionItems(active)
  var renderedRows = filteredItems.map(function (item) { return _abRenderActionRow(active, item) }).filter(Boolean)
  var renderedCards = filteredItems.map(function (item) { return active.renderItem(item) }).filter(Boolean)
  var paging = active.paging || null
  var totalPages = paging && paging.page_size ? Math.max(1, Math.ceil((paging.total || 0) / paging.page_size)) : 1
  var recordCount = paging && typeof paging.total === 'number' ? paging.total : filteredItems.length
  var searchApplied = !!((_abSearchQuery || '').trim())
  var startIndex = paging && typeof paging.start === 'number' ? paging.start : (filteredItems.length ? 1 : 0)
  var endIndex = paging && typeof paging.end === 'number' ? paging.end : filteredItems.length
  var totalCount = paging && typeof paging.total === 'number' ? paging.total : filteredItems.length
  var searchMeta = searchApplied
    ? ('Showing ' + filteredItems.length + ' matching result' + (filteredItems.length === 1 ? '' : 's'))
    : ('Showing ' + startIndex + '-' + endIndex + ' of ' + totalCount)
  workspace.innerHTML = `
    <div class="ab-kpi-strip">
        ${_abCurrentSections.map(function (sec) {
          var isActive = sec.key === active.key
          return `
            <button type="button" class="ab-kpi-tab${isActive ? ' is-active' : ''}" data-section-key="${sec.key}" style="--ab-kpi-color:${sec.accentColor};">
              <span class="ab-kpi-count">${Number(sec.count || 0).toLocaleString()}</span>
              <span class="ab-kpi-copy">
                <span class="ab-kpi-title">${sec.title}</span>
              </span>
            </button>`
        }).join('')}
    </div>
    <section class="ab-active-panel">
        <div class="ab-active-panel-body" style="min-height:0;">
          <div class="ab-list-shell">
            <div class="ab-list-header">
              <div>
                <p class="ab-list-eyebrow">Action List</p>
                <h3 class="ab-list-title">${active.title}</h3>
              </div>
              <span class="ab-list-count">${Number(recordCount || 0).toLocaleString()} leads</span>
            </div>
            ${isMobile
              ? (renderedCards.length
                ? `<div class="ab-mobile-list">${renderedCards.join('')}</div>`
                : `<p class="ab-empty-state">${searchApplied ? 'No results match this search in the selected KPI list.' : active.emptyMsg}</p>`)
              : (renderedRows.length
                ? `<div class="ab-table-wrap">
                    <table class="ab-action-table">
                      <colgroup>
                        <col style="width:17%;" />
                        <col style="width:12%;" />
                        <col style="width:15%;" />
                        <col style="width:12%;" />
                        <col style="width:16%;" />
                        <col style="width:12%;" />
                        <col style="width:16%;" />
                      </colgroup>
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Phone</th>
                          <th>Status</th>
                          <th>Project</th>
                          <th>Latest Note</th>
                          <th>Next Callback</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>${renderedRows.join('')}</tbody>
                    </table>
                  </div>`
                : `<p class="ab-empty-state">${searchApplied ? 'No results match this search in the selected KPI list.' : active.emptyMsg}</p>`)}
          </div>
        </div>
        <div class="ab-utility-row">
          <div class="ab-utility-left">
            <span class="ab-panel-meta">${searchMeta || `Showing ${recordCount} records`}</span>
            <label class="ab-page-label" for="abPageSizeSelect">Page Size</label>
            <select id="abPageSizeSelect" class="ab-size-select ab-page-size-select">
              <option value="auto" ${_abPageSizeMode === 'auto' ? 'selected' : ''}>Auto (${_abRecommendedPageSize()})</option>
              ${[6, 12, 18].map(function (size) { return `<option value="${size}" ${_abPageSizeMode !== 'auto' && Number(_abPageSize || 6) === size ? 'selected' : ''}>${size}</option>` }).join('')}
            </select>
          </div>
          <div class="ab-utility-right">
            <div class="ab-panel-pager">
              <span class="ab-panel-page-state">Page ${paging && paging.page ? paging.page : 1} of ${totalPages}</span>
              <select id="abPageSelect" class="ab-page-select" data-section-key="${active.key}">
                ${Array.from({ length: totalPages }, function (_unused, idx) {
                  var pageNum = idx + 1
                  return `<option value="${pageNum}" ${paging && pageNum === paging.page ? 'selected' : ''}>${pageNum}</option>`
                }).join('')}
              </select>
              <button type="button" class="ab-page-btn" data-section-key="${active.key}" data-page-action="prev" ${paging && paging.has_prev ? '' : 'disabled'}>Prev</button>
              <button type="button" class="ab-page-btn" data-section-key="${active.key}" data-page-action="next" ${paging && paging.has_next ? '' : 'disabled'}>Next</button>
            </div>
            <button type="button" id="abRefreshBtn" class="dash-refresh-btn">↻ Refresh</button>
          </div>
        </div>
      </section>
  `

  _abWireKpiTabs(workspace)
  _abWirePagination(workspace)
  _abWireCardFocus(workspace)
  var sizeSel = workspace.querySelector('#abPageSizeSelect')
  if (sizeSel) {
    sizeSel.addEventListener('change', function () {
      if (sizeSel.value === 'auto') {
        _abPageSizeMode = 'auto'
        _abPageSize = _abRecommendedPageSize()
      } else {
        _abPageSizeMode = 'manual'
        _abPageSize = Math.max(6, parseInt(sizeSel.value, 10) || 6)
      }
      Object.keys(_abSectionPages).forEach(function (key) { _abSectionPages[key] = 1 })
      renderActionBoard(_abDateFrom, _abDateTo, _abRange)
    })
  }
  var refreshBtn = workspace.querySelector('#abRefreshBtn')
  if (refreshBtn) refreshBtn.addEventListener('click', function () { renderActionBoard(_abDateFrom, _abDateTo, _abRange) })
}

function _abStatusControl(leadId, currentStatus) {
  var id = Number(leadId || 0)
  if (!id) return ''
  var current = String(currentStatus || '').toLowerCase()
  var meta = _abStatusMeta[current] || { label: current.replace(/_/g, ' '), bg: '#f8fafc', color: '#334155', border: '#cbd5e1' }
  return `
    <span class="ab-status-chip" data-ab-no-open="1" style="padding:0 8px;border:1px solid ${meta.border};border-radius:999px;background:${meta.bg};">
      <select class="ab-inline-status-select" data-ab-no-open="1" data-lead-id="${id}" style="color:${meta.color};">
        ${_abStatusOptions.map(function (opt) {
          return `<option value="${opt.value}" ${opt.value === current ? 'selected' : ''}>${opt.label}</option>`
        }).join('')}
      </select>
    </span>`
}

function _abWireKpiTabs(root) {
  var tabs = root.querySelectorAll('.ab-kpi-tab')
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      var key = tab.getAttribute('data-section-key') || ''
      if (!key || key === _abActiveSectionKey) return
      _abActiveSectionKey = key
      _abRenderWorkspace()
    })
  })
}


// ── Quick Actions ─────────────────────────────────────────────────────────

function _abLeadPriority(l) {
  const st = (l && l.status ? String(l.status) : '').toLowerCase()
  if (st === 'site_visit_done' || st === 'negotiation') {
    return { color: '#dc2626', short: 'High', icon: '🔴', bg: '#fef2f2', text: '#b91c1c', border: '#fecaca' }
  }
  if (st === 'interested' || st === 'site_visit_planned') {
    return { color: '#ca8a04', short: 'Medium', icon: '🟡', bg: '#fefce8', text: '#a16207', border: '#fde68a' }
  }
  return { color: '#16a34a', short: 'Normal', icon: '🟢', bg: '#f0fdf4', text: '#166534', border: '#bbf7d0' }
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
    card.addEventListener('click', function (event) {
      card.focus()

      var target = event && event.target
      if (target && typeof target.closest === 'function') {
        var interactive = target.closest('button, a, input, select, textarea, label, [role="button"], [data-ab-no-open], .ab-action-status, .ab-status-chip, .ab-inline-status-select')
        if (interactive && interactive !== card) return
      }

      var leadId = Number(card.getAttribute('data-lead-id') || 0)
      if (leadId > 0) _abOpenLead(leadId)
    })
    card.addEventListener('keydown', function (event) {
      if (!event || (event.key !== 'Enter' && event.key !== ' ')) return
      var target = event.target
      if (target && typeof target.closest === 'function') {
        var interactive = target.closest('button, a, input, select, textarea, label, [role="button"], [data-ab-no-open], .ab-action-status, .ab-status-chip, .ab-inline-status-select')
        if (interactive && interactive !== card) return
      }
      event.preventDefault()
      var leadId = Number(card.getAttribute('data-lead-id') || 0)
      if (leadId > 0) _abOpenLead(leadId)
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

  var selects = root.querySelectorAll('.ab-page-select')
  selects.forEach(function (sel) {
    sel.addEventListener('change', function () {
      var key = sel.getAttribute('data-section-key') || ''
      if (!key || typeof _abSectionPages[key] === 'undefined') return
      var page = Number(sel.value || 1)
      _abSectionPages[key] = Math.max(1, page)
      renderActionBoard(_abDateFrom, _abDateTo, _abRange)
    })
  })

  var statusSelects = root.querySelectorAll('.ab-inline-status-select')
  statusSelects.forEach(function (sel) {
    ;['pointerdown', 'mousedown', 'touchstart', 'click'].forEach(function (evtName) {
      sel.addEventListener(evtName, function (e) {
        if (e && typeof e.stopPropagation === 'function') e.stopPropagation()
      })
    })
    sel.addEventListener('keydown', function (e) {
      if (e && typeof e.stopPropagation === 'function') e.stopPropagation()
    })
    sel.addEventListener('change', async function () {
      var id = Number(sel.getAttribute('data-lead-id') || 0)
      var toStatus = String(sel.value || '').trim()
      if (!id || !toStatus) return
      sel.disabled = true
      try {
        await _apiRequest(`/pipeline/leads/${id}/move`, {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ to_status: toStatus }),
          retries: 0,
          timeoutMs: 20000,
        })
        showToast('Lead status updated.', 'success')
        await _abRefreshPreservingState()
        if (await confirmDialog('Add Note?', 'Yes', '#4f46e5')) {
          _abQuickNote(id)
        }
      } catch (err) {
        showToast((err && err.message) || 'Failed to update status.', 'error')
      } finally {
        sel.disabled = false
      }
    })
  })
}

function _abRefreshUpdatedLabels() {
  var labels = document.querySelectorAll('#abWorkspace .ab-updated')
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

async function _abStartCallFlow(leadId, phone, leadName, alternatePhone) {
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

  _abOpenCallOutcomeModal(id, phone, leadName, alternatePhone || '')
}

function _abOpenCallOutcomeModal(leadId, phone, leadName, alternatePhone) {
  var id = Number(leadId)
  if (!Number.isFinite(id) || id <= 0) return

  var overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.setAttribute('data-call-modal', '1')
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:520px;width:100%;">
      <h3 class="sm-section-heading" style="margin-bottom:8px;">📞 Log Call Outcome</h3>
      <div style="font-size:13px;color:#64748b;margin-bottom:16px;line-height:1.5;">
        ${escape(leadName || 'Lead')} ${phone ? '· ' + escape(phone) : ''}${alternatePhone ? ' · Alt ' + escape(alternatePhone) : ''}
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
  const mins = Math.max(0, Math.floor((Date.now() - created.getTime()) / 60000))
  const hrs = Math.floor(mins / 60)
  const days = Math.max(1, Math.floor(hrs / 24) || (hrs > 0 ? 1 : 1))
  return `${days} Day${days === 1 ? '' : 's'}`
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
    await _abRefreshPreservingState()
    if (await confirmDialog('Update Lead Status?', 'Yes', '#4f46e5')) {
      _abOpenStatusModal(leadId)
    }
  } catch {
    showToast('Failed to save note.', 'error')
  }
}

function _abCallCallback(leadId) {
  if (typeof openCallbackModal === 'function') {
    openCallbackModal(leadId, { source: 'action_board' })
  } else {
    showToast('Callback scheduler is loading...', 'info')
  }
}
