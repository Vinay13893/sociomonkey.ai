// ============================================================================
// ASSIGN / REASSIGN — Lead Distribution Manager
// 4 tabs: Unassigned | Stale Leads | Workload | Recycle Queue
// Access: superadmin (full edit), sales_manager (read + assign within team)
// ============================================================================

var _arRenderId = 0
var _arRenderInFlight = false
var _arActiveTab = 'unassigned'
var _arSelectedLeads = new Set()

// ── Tab: Unassigned ──────────────────────────────────────────────────────────
var _arUnassignedPage = 1
var _arUnassignedPageSize = 25
var _arUnassignedTotal = 0
var _arUnassignedLeads = []
var _arUnassignedAssignable = []
var _arUnassignedSource = ''
var _arUnassignedProject = ''
var _arUnassignedSearch = ''
var _arUnassignedSort = 'received_desc'
var _arUnassignedSources = []
var _arUnassignedProjects = []

// ── Tab: Stale ────────────────────────────────────────────────────────────────
var _arStaleDays = 5
var _arStaleStatus = ''
var _arStalePage = 1
var _arStalePageSize = 25
var _arStaleTotal = 0
var _arStaleLeads = []
var _arStaleAssignable = []
var _arStaleSelectedLeads = new Set()
var _arStaleSource = ''
var _arStaleProject = ''
var _arStaleSearch = ''
var _arStaleSort = 'stale_desc'
var _arStaleSources = []
var _arStaleProjects = []

// ── Tab: Workload ─────────────────────────────────────────────────────────────
var _arWorkloadMembers = []
var _arWorkloadAssignable = []
var _arWorkloadSelectedFrom = null
var _arWorkloadPreview = null
var _arWorkloadPage = 1
var _arWorkloadPageSize = 10
var _arWorkloadSelectedLeads = new Set()
var _arWorkloadFilterState = {}
var AR_LEAD_STATUSES = [
  'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
  'site_visit_planned', 'site_visit_done', 'negotiation', 'booking_done',
  'not_interested', 'lost', 'junk'
]

function _arLeadAgeLabel(l) {
  var days = Number(l && (l.received_age_days != null ? l.received_age_days : l.age_days))
  var hours = Number(l && l.received_age_hours)
  if (Number.isFinite(days) && days > 0) return days + 'd old'
  if (Number.isFinite(hours) && hours > 0) return hours + 'h old'
  return 'new today'
}

function _arWhenLabel(raw) {
  if (!raw) return '-'
  var dt = new Date(raw)
  if (Number.isNaN(dt.getTime())) return '-'
  return dt.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).replace(',', '')
}

function _arMetaChip(label, value) {
  if (!value) return ''
  return `<span style="display:inline-flex;align-items:center;max-width:180px;min-height:24px;padding:4px 8px;border-radius:8px;background:#f8fafc;border:1px solid #e2e8f0;color:#475569;font-size:11px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${escape(String(value))}">${escape(label)}: ${escape(String(value))}</span>`
}

function _arOptionHtml(options, selected, valueKey, labelKey, placeholder) {
  var html = `<option value="">${escape(placeholder)}</option>`
  ;(options || []).forEach(function (opt) {
    var value = String(opt[valueKey] == null ? '' : opt[valueKey])
    var label = String(opt[labelKey] == null ? value : opt[labelKey])
    html += `<option value="${escape(value)}" ${String(selected || '') === value ? 'selected' : ''}>${escape(label)}</option>`
  })
  return html
}

function _arSimpleOptions(values, selected, placeholder) {
  var html = `<option value="">${escape(placeholder)}</option>`
  ;(values || []).forEach(function (value) {
    var label = String(value || '').replace(/_/g, ' ')
    html += `<option value="${escape(value)}" ${String(selected || '') === String(value) ? 'selected' : ''}>${escape(label)}</option>`
  })
  return html
}

function _arBuildUnassignedParams(extra) {
  var params = new URLSearchParams()
  params.set('page', String(_arUnassignedPage))
  params.set('per_page', String(_arUnassignedPageSize))
  if (_arUnassignedSource) params.set('source', _arUnassignedSource)
  if (_arUnassignedProject) params.set('project_id', _arUnassignedProject)
  if (_arUnassignedSearch) params.set('search', _arUnassignedSearch)
  if (_arUnassignedSort) params.set('sort', _arUnassignedSort)
  Object.keys(extra || {}).forEach(function (key) { params.set(key, String(extra[key])) })
  return params
}

function _arBuildStaleParams(extra) {
  var params = new URLSearchParams()
  params.set('days', String(_arStaleDays))
  params.set('page', String(_arStalePage))
  params.set('per_page', String(_arStalePageSize))
  if (_arStaleStatus) params.set('status', _arStaleStatus)
  if (_arStaleSource) params.set('source', _arStaleSource)
  if (_arStaleProject) params.set('project_id', _arStaleProject)
  if (_arStaleSearch) params.set('search', _arStaleSearch)
  if (_arStaleSort) params.set('sort', _arStaleSort)
  Object.keys(extra || {}).forEach(function (key) { params.set(key, String(extra[key])) })
  return params
}

function _arPagerHtml(prefix, page, total, pageSize) {
  var totalPages = Math.max(1, Math.ceil((total || 0) / (pageSize || 25)))
  var current = Math.min(Math.max(1, page || 1), totalPages)
  var start = Math.max(1, current - 2)
  var end = Math.min(totalPages, start + 4)
  start = Math.max(1, end - 4)
  var buttons = []
  for (var p = start; p <= end; p++) {
    buttons.push(`<button onclick="${prefix}SetPage(${p})" style="min-width:30px;font-size:12px;padding:4px 8px;border:1px solid ${p === current ? '#0f766e' : '#cbd5e1'};border-radius:6px;background:${p === current ? '#0f766e' : '#fff'};color:${p === current ? '#fff' : '#334155'};cursor:pointer;font-weight:700;">${p}</button>`)
  }
  return `
    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">
      <button onclick="${prefix}SetPage(1)" ${current <= 1 ? 'disabled' : ''} class="ar-page-btn">First</button>
      <button onclick="${prefix}SetPage(${current - 1})" ${current <= 1 ? 'disabled' : ''} class="ar-page-btn">Prev</button>
      ${buttons.join('')}
      <button onclick="${prefix}SetPage(${current + 1})" ${current >= totalPages ? 'disabled' : ''} class="ar-page-btn">Next</button>
      <button onclick="${prefix}SetPage(${totalPages})" ${current >= totalPages ? 'disabled' : ''} class="ar-page-btn">Last</button>
    </div>`
}

// ── Tab: Recycle Queue (embedded) ────────────────────────────────────────────
// Delegates to _rqRenderShell() from recycle-queue.js

// ── Global helpers called from inline onclick attrs ───────────────────────────

function _arUToggle(leadId) {
  var chk = document.getElementById('arUChk_' + leadId)
  var row = document.getElementById('arURow_' + leadId)
  if (!chk) return
  if (chk.checked) { _arSelectedLeads.add(leadId); if (row) row.style.background = '#eff6ff' }
  else { _arSelectedLeads.delete(leadId); if (row) row.style.background = '#fff' }
  _arUpdateAssignBtn()
}

function _arSToggle(leadId) {
  var chk = document.getElementById('arSChk_' + leadId)
  var row = document.getElementById('arSRow_' + leadId)
  if (!chk) return
  if (chk.checked) { _arStaleSelectedLeads.add(leadId); if (row) row.style.background = '#eff6ff' }
  else { _arStaleSelectedLeads.delete(leadId); if (row) row.style.background = '#fff' }
  _arUpdateStaleAssignBtn()
}

function _arUSelectAll(checked) {
  document.querySelectorAll('[id^="arUChk_"]').forEach(function(chk) {
    var id = parseInt(chk.id.replace('arUChk_', ''), 10)
    chk.checked = checked
    var row = document.getElementById('arURow_' + id)
    if (checked) { _arSelectedLeads.add(id); if (row) row.style.background = '#eff6ff' }
    else { _arSelectedLeads.delete(id); if (row) row.style.background = '#fff' }
  })
  _arUpdateAssignBtn()
}

function _arSSelectAll(checked) {
  document.querySelectorAll('[id^="arSChk_"]').forEach(function(chk) {
    var id = parseInt(chk.id.replace('arSChk_', ''), 10)
    chk.checked = checked
    var row = document.getElementById('arSRow_' + id)
    if (checked) { _arStaleSelectedLeads.add(id); if (row) row.style.background = '#eff6ff' }
    else { _arStaleSelectedLeads.delete(id); if (row) row.style.background = '#fff' }
  })
  _arUpdateStaleAssignBtn()
}

function _arUnassignedPrev() { if (_arUnassignedPage > 1) { _arUnassignedPage--; _arLoadUnassigned() } }
function _arUnassignedNext() { var tp = Math.ceil(_arUnassignedTotal / _arUnassignedPageSize); if (_arUnassignedPage < tp) { _arUnassignedPage++; _arLoadUnassigned() } }
function _arUnassignedSetPageSize(s) { _arUnassignedPageSize = parseInt(s, 10) || 25; _arUnassignedPage = 1; _arLoadUnassigned() }
function _arStalePrev() { if (_arStalePage > 1) { _arStalePage--; _arLoadStale() } }
function _arStaleNext() { var tp = Math.ceil(_arStaleTotal / _arStalePageSize); if (_arStalePage < tp) { _arStalePage++; _arLoadStale() } }
function _arStaleSetPageSize(s) { _arStalePageSize = parseInt(s, 10) || 25; _arStalePage = 1; _arLoadStale() }

function _arUnassignedSetPage(page) {
  var totalPages = Math.max(1, Math.ceil(_arUnassignedTotal / _arUnassignedPageSize))
  _arUnassignedPage = Math.min(Math.max(1, parseInt(page, 10) || 1), totalPages)
  _arLoadUnassigned()
}

function _arStaleSetPage(page) {
  var totalPages = Math.max(1, Math.ceil(_arStaleTotal / _arStalePageSize))
  _arStalePage = Math.min(Math.max(1, parseInt(page, 10) || 1), totalPages)
  _arLoadStale()
}

function _arApplyUnassignedFilters() {
  _arUnassignedSource = document.getElementById('arUnassignedSource')?.value || ''
  _arUnassignedProject = document.getElementById('arUnassignedProject')?.value || ''
  _arUnassignedSearch = (document.getElementById('arUnassignedSearch')?.value || '').trim()
  _arUnassignedSort = document.getElementById('arUnassignedSort')?.value || 'received_desc'
  _arUnassignedPage = 1
  _arLoadUnassigned()
}

function _arResetUnassignedFilters() {
  _arUnassignedSource = ''
  _arUnassignedProject = ''
  _arUnassignedSearch = ''
  _arUnassignedSort = 'received_desc'
  _arUnassignedPage = 1
  _arLoadUnassigned()
}

function _arApplyStaleFilters() {
  _arStaleDays = Number(document.getElementById('arStaleDays')?.value || _arStaleDays)
  _arStaleStatus = document.getElementById('arStaleStatus')?.value || ''
  _arStaleSource = document.getElementById('arStaleSource')?.value || ''
  _arStaleProject = document.getElementById('arStaleProject')?.value || ''
  _arStaleSearch = (document.getElementById('arStaleSearch')?.value || '').trim()
  _arStaleSort = document.getElementById('arStaleSort')?.value || 'stale_desc'
  _arStalePage = 1
  _arLoadStale()
}

function _arResetStaleFilters() {
  _arStaleDays = 5
  _arStaleStatus = ''
  _arStaleSource = ''
  _arStaleProject = ''
  _arStaleSearch = ''
  _arStaleSort = 'stale_desc'
  _arStalePage = 1
  _arLoadStale()
}

async function renderAssignReassign(initialTab) {
  if (_arRenderInFlight) return
  _arRenderInFlight = true
  _arRenderId++
  var myId = _arRenderId
  window._ACTIVE_ROUTE = 'assign_reassign'

  if (initialTab) _arActiveTab = initialTab === 'recycle_queue' ? 'recycle' : initialTab

  function _guard() {
    return myId === _arRenderId && window._ACTIVE_ROUTE === 'assign_reassign'
  }

  const content = document.getElementById('content')
  if (!content) { _arRenderInFlight = false; return }

  content.innerHTML = `
    <div style="max-width:1200px;margin:0 auto;padding:20px 16px 60px;" id="arRoot">
      <div class="sm-page-header" style="margin-bottom:16px;">
        <div>
          <h2 class="sm-page-title">📋 Allocation</h2>
          <p class="sm-small sm-text-muted" style="margin:4px 0 0;">Distribute and rebalance leads across your team.</p>
        </div>
      </div>

      <div class="ar-tabs" style="display:flex;gap:0;border-bottom:2px solid #e2e8f0;margin-bottom:20px;">
        <button class="ar-tab-btn ${_arActiveTab === 'unassigned' ? 'ar-tab-active' : ''}" data-tab="unassigned" style="padding:10px 20px;border:none;background:none;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid ${_arActiveTab === 'unassigned' ? '#2563eb' : 'transparent'};color:${_arActiveTab === 'unassigned' ? '#2563eb' : '#64748b'};margin-bottom:-2px;">Unassigned</button>
        <button class="ar-tab-btn ${_arActiveTab === 'stale' ? 'ar-tab-active' : ''}" data-tab="stale" style="padding:10px 20px;border:none;background:none;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid ${_arActiveTab === 'stale' ? '#2563eb' : 'transparent'};color:${_arActiveTab === 'stale' ? '#2563eb' : '#64748b'};margin-bottom:-2px;">Stale Leads</button>
        <button class="ar-tab-btn ${_arActiveTab === 'workload' ? 'ar-tab-active' : ''}" data-tab="workload" style="padding:10px 20px;border:none;background:none;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid ${_arActiveTab === 'workload' ? '#2563eb' : 'transparent'};color:${_arActiveTab === 'workload' ? '#2563eb' : '#64748b'};margin-bottom:-2px;">Workload</button>
        <button class="ar-tab-btn ${_arActiveTab === 'recycle' ? 'ar-tab-active' : ''}" data-tab="recycle" style="padding:10px 20px;border:none;background:none;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid ${_arActiveTab === 'recycle' ? '#2563eb' : 'transparent'};color:${_arActiveTab === 'recycle' ? '#2563eb' : '#64748b'};margin-bottom:-2px;">♻️ Recycle Queue</button>
      </div>

      <div id="arTabContent" style="min-height:300px;">
        <div style="text-align:center;padding:60px;color:#64748b;">Loading...</div>
      </div>
    </div>`

  // Tab switching
  document.querySelectorAll('.ar-tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!_guard()) return
      _arActiveTab = btn.dataset.tab
      // Update tab styles
      document.querySelectorAll('.ar-tab-btn').forEach(function (b) {
        var active = b.dataset.tab === _arActiveTab
        b.style.borderBottomColor = active ? '#2563eb' : 'transparent'
        b.style.color = active ? '#2563eb' : '#64748b'
      })
      _arLoadTab()
    })
  })

  _arRenderInFlight = false
  if (!_guard()) return
  await _arLoadTab()
}

async function _arLoadTab() {
  window._ACTIVE_ROUTE = 'assign_reassign'
  var tabContent = document.getElementById('arTabContent')
  if (!tabContent) return

  if (_arActiveTab === 'recycle') {
    _rqRenderShell(tabContent, false)
    return
  }

  if (_arActiveTab === 'unassigned') return _arLoadUnassigned()
  if (_arActiveTab === 'stale') return _arLoadStale()
  if (_arActiveTab === 'workload') return _arLoadWorkload()
}

// ── UNASSIGNED TAB ───────────────────────────────────────────────────────────

async function _arLoadUnassigned() {
  var tabContent = document.getElementById('arTabContent')
  if (!tabContent) return
  tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#64748b;"><i class="fa-solid fa-spinner fa-spin"></i> Loading unassigned leads...</div>`

  try {
    var qs = `?${_arBuildUnassignedParams().toString()}`
    var data = await _apiRequest(`/leads/assign-reassign/unassigned${qs}`, { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 15000 })
    _arUnassignedLeads = data.leads || []
    _arUnassignedTotal = data.total || 0
    _arUnassignedPage = data.page || _arUnassignedPage
    _arUnassignedSources = (data.filters && data.filters.sources) || []
    _arUnassignedProjects = (data.filters && data.filters.projects) || []
    _arUnassignedAssignable = data.assignable_users || []
    _arSelectedLeads = new Set()
    _arRenderUnassigned()
  } catch (err) {
    if (tabContent) tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#ef4444;">Failed to load: ${escape(err && err.message || 'Unknown error')}</div>`
  }
}

function _arRenderUnassigned() {
  var tabContent = document.getElementById('arTabContent')
  if (!tabContent) return
  var leads = _arUnassignedLeads
  var total = _arUnassignedTotal
  var assignable = _arUnassignedAssignable
  var totalPages = Math.max(1, Math.ceil(total / _arUnassignedPageSize))

  var memberOptions = assignable.map(function (u) {
    return `<option value="${u.id}">${escape(u.name)} (${u.role.replace(/_/g, ' ')})</option>`
  }).join('')
  var sourceOptions = _arOptionHtml(_arUnassignedSources, _arUnassignedSource, 'value', 'label', 'All Sources')
  var projectOptions = _arOptionHtml(_arUnassignedProjects, _arUnassignedProject, 'id', 'name', 'All Projects')

  var leadCards = leads.length === 0
    ? `<div style="text-align:center;padding:40px;color:#9ca3af;"><div style="font-size:32px;margin-bottom:8px;">📭</div><p>No unassigned leads found.</p></div>`
    : leads.map(function (l, i) {
      var sc = (typeof STATUS_COLORS !== 'undefined' ? STATUS_COLORS : {})[l.status] || { bg: '#f1f5f9', color: '#475569', label: l.status || 'new' }
      var serial = (_arUnassignedPage - 1) * _arUnassignedPageSize + i + 1
      var createdDate = _arWhenLabel(l.received_at || l.created_at)
      var initial = escape((l.name || '?')[0].toUpperCase())
      return `
        <div id="arURow_${l.id}" class="ar-lead-row" style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:${_arSelectedLeads.has(l.id) ? '#eff6ff' : '#fff'};border:1px solid #e2e8f0;border-radius:10px;transition:background .15s;">
          <input type="checkbox" id="arUChk_${l.id}" onchange="_arUToggle(${l.id})" ${_arSelectedLeads.has(l.id) ? 'checked' : ''} style="width:16px;height:16px;cursor:pointer;flex-shrink:0;" />
          <span style="font-size:11px;font-weight:700;color:#94a3b8;min-width:22px;text-align:right;flex-shrink:0;">${serial}</span>
          <div style="width:38px;height:38px;border-radius:50%;background:#6366f1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;flex-shrink:0;">${initial}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;color:#0f172a;">${escape(l.name || '')}</div>
            <div style="font-size:11px;color:#64748b;">${l.phone || '-'} | Received ${createdDate} | ${escape(_arLeadAgeLabel(l))}</div>
            <div class="ar-row-meta" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;">
              ${_arMetaChip('Project', l.project_name || l.project)}
              ${_arMetaChip('Source', l.source)}
            </div>
          </div>
          <span style="background:${sc.bg};color:${sc.color};font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;flex-shrink:0;">${sc.label || (l.status || 'new').replace(/_/g, ' ')}</span>
          <button onclick="viewLeadDetails(${l.id})" style="font-size:11px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#6366f1;cursor:pointer;font-weight:600;white-space:nowrap;flex-shrink:0;">Open</button>
        </div>`
    }).join('')

  tabContent.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:12px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;">
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Source</div>
        <select id="arUnassignedSource" class="dash-filter-ctl">${sourceOptions}</select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Project</div>
        <select id="arUnassignedProject" class="dash-filter-ctl">${projectOptions}</select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Sort</div>
        <select id="arUnassignedSort" class="dash-filter-ctl">
          <option value="received_desc" ${_arUnassignedSort === 'received_desc' ? 'selected' : ''}>Newest received first</option>
          <option value="received_asc" ${_arUnassignedSort === 'received_asc' ? 'selected' : ''}>Oldest received first</option>
        </select>
      </div>
      <div style="min-width:180px;">
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Search</div>
        <input id="arUnassignedSearch" class="dash-filter-ctl" value="${escape(_arUnassignedSearch)}" placeholder="Name, phone, project" onkeydown="if(event.key==='Enter'){event.preventDefault();_arApplyUnassignedFilters()}" />
      </div>
      <div style="display:flex;align-items:flex-end;gap:8px;">
        <button onclick="_arApplyUnassignedFilters()" class="button secondary" style="height:36px;font-size:13px;">Apply</button>
        <button onclick="_arResetUnassignedFilters()" style="height:36px;font-size:13px;border:1px solid #cbd5e1;border-radius:7px;background:#fff;color:#334155;padding:0 12px;font-weight:700;cursor:pointer;">Reset</button>
      </div>
    </div>

    <div style="display:flex;gap:10px;align-items:flex-end;margin-bottom:14px;flex-wrap:wrap;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;">
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Assign To</div>
        <select id="arUnassignedTarget" class="dash-filter-ctl" style="max-width:240px;">
          <option value="">— Select Member —</option>
          ${memberOptions}
        </select>
      </div>
      <button onclick="_arBulkAssignUnassigned()" class="button" id="arAssignBtn" style="height:36px;font-size:13px;">Assign Selected (${_arSelectedLeads.size})</button>
      <button onclick="_arDistributeUnassigned()" class="button secondary" style="height:36px;font-size:13px;">⚖️ Distribute Equally</button>
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;padding:0 2px;margin-bottom:10px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <label style="font-size:13px;font-weight:600;color:#475569;display:flex;align-items:center;gap:8px;cursor:pointer;">
          <input type="checkbox" onchange="_arUSelectAll(this.checked)" id="arSelectAllUnassigned"> Select Page (${leads.length})
        </label>
        ${total > leads.length ? `<button onclick="_arUSelectAllPages()" id="arUSelectAllPagesBtn" style="font-size:12px;color:#059669;background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:4px 10px;cursor:pointer;font-weight:600;">Select All ${total} Leads</button>` : ''}
      </div>
      <span style="font-size:12px;color:#94a3b8;">${total} unassigned total</span>
    </div>

    <div style="display:flex;flex-direction:column;gap:8px;">
      ${leadCards}
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 4px 0;margin-top:12px;border-top:1px solid #e2e8f0;flex-wrap:wrap;gap:8px;">
      <span style="font-size:12px;color:#64748b;">Page ${_arUnassignedPage} of ${totalPages}</span>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:12px;color:#64748b;">Page size</span>
        <select onchange="_arUnassignedSetPageSize(this.value)" style="border:1px solid #cbd5e1;border-radius:6px;padding:3px 7px;font-size:12px;">
          ${[10, 25, 50].map(function(n) { return `<option value="${n}" ${_arUnassignedPageSize === n ? 'selected' : ''}>${n}</option>` }).join('')}
        </select>
      </div>
      ${_arPagerHtml('_arUnassigned', _arUnassignedPage, total, _arUnassignedPageSize)}
    </div>
  `
}

function _arUpdateAssignBtn() {
  var btn = document.getElementById('arAssignBtn')
  if (btn) btn.textContent = `Assign Selected (${_arSelectedLeads.size})`
}

async function _arUSelectAllPages() {
  var btn = document.getElementById('arUSelectAllPagesBtn')
  if (btn) { btn.textContent = '⏳ Loading...'; btn.disabled = true }
  try {
    var data = await _apiRequest('/leads/assign-reassign/unassigned?' + _arBuildUnassignedParams({ ids_only: 1, limit: 10000 }).toString(), {
      headers: _apiAuthHeaders(), retries: 1, timeoutMs: 20000,
    })
    ;(data.lead_ids || []).forEach(function (id) {
      _arSelectedLeads.add(id)
      var chk = document.getElementById('arUChk_' + id)
      if (chk) chk.checked = true
      var row = document.getElementById('arURow_' + id)
      if (row) row.style.background = '#eff6ff'
    })
    _arUpdateAssignBtn()
    var limited = data.limited ? ` First ${_arSelectedLeads.size} selected.` : ''
    showToast(`${_arSelectedLeads.size} leads selected across all pages.${limited}`, data.limited ? 'warning' : 'success')
    if (btn) { btn.textContent = `✓ All ${_arSelectedLeads.size} Selected`; btn.disabled = true }
  } catch (err) {
    showToast('Failed to select all leads.', 'error')
    if (btn) { btn.textContent = `Select All ${_arUnassignedTotal} Leads`; btn.disabled = false }
  }
}

async function _arBulkAssignUnassigned() {
  var target = document.getElementById('arUnassignedTarget')
  var targetId = target && target.value ? Number(target.value) : null
  if (!targetId) { showToast('Please select a member to assign to.', 'warning'); return }
  if (_arSelectedLeads.size === 0) { showToast('Please select at least one lead.', 'warning'); return }
  try {
    var result = await _apiRequest('/leads/assign-reassign/bulk-assign', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ lead_ids: Array.from(_arSelectedLeads), target_user_id: targetId }),
      retries: 0,
    })
    showToast(`Assigned ${result.assigned} lead${result.assigned !== 1 ? 's' : ''} successfully.`, 'success')
    _arUnassignedPage = 1
    _arLoadUnassigned()
  } catch (err) {
    showToast('Assignment failed: ' + (err && err.message || 'Unknown error'), 'error')
  }
}

async function _arDistributeUnassigned() {
  if (!confirm('Equally distribute ALL unassigned leads among team members?')) return
  try {
    // Fetch all unassigned lead IDs
    var data = await _apiRequest('/leads/assign-reassign/unassigned?' + _arBuildUnassignedParams({ ids_only: 1, limit: 10000 }).toString(), { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 20000 })
    var allLeadIds = data.lead_ids || []
    var assignable = data.assignable_users || []
    if (allLeadIds.length === 0) { showToast('No unassigned leads.', 'info'); return }
    if (assignable.length === 0) { showToast('No assignable users.', 'warning'); return }
    if (data.limited) {
      showToast(`Only the first ${allLeadIds.length} leads can be distributed at once.`, 'warning')
    }

    // Distribute round-robin
    var batches = {}
    assignable.forEach(function (u) { batches[u.id] = [] })
    allLeadIds.forEach(function (id, i) {
      var u = assignable[i % assignable.length]
      batches[u.id].push(id)
    })

    var totalAssigned = 0
    for (var uid in batches) {
      if (batches[uid].length === 0) continue
      var res = await _apiRequest('/leads/assign-reassign/bulk-assign', {
        method: 'POST',
        headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
        body: JSON.stringify({ lead_ids: batches[uid], target_user_id: Number(uid), reason: 'Equal distribution' }),
        retries: 0,
      })
      totalAssigned += (res.assigned || 0)
    }
    showToast(`Distributed ${totalAssigned} leads equally.`, 'success')
    _arUnassignedPage = 1
    _arLoadUnassigned()
  } catch (err) {
    showToast('Distribution failed: ' + (err && err.message || 'Unknown error'), 'error')
  }
}

// ── STALE LEADS TAB ──────────────────────────────────────────────────────────

async function _arLoadStale() {
  var tabContent = document.getElementById('arTabContent')
  if (!tabContent) return
  tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#64748b;"><i class="fa-solid fa-spinner fa-spin"></i> Loading stale leads...</div>`

  try {
    var qs = `?${_arBuildStaleParams().toString()}`
    var data = await _apiRequest(`/leads/assign-reassign/stale${qs}`, { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 15000 })
    _arStaleLeads = data.leads || []
    _arStaleTotal = data.total || 0
    _arStalePage = data.page || _arStalePage
    _arStaleSources = (data.filters && data.filters.sources) || []
    _arStaleProjects = (data.filters && data.filters.projects) || []
    _arStaleAssignable = data.assignable_users || []
    _arStaleSelectedLeads = new Set()
    _arRenderStale()
  } catch (err) {
    if (tabContent) tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#ef4444;">Failed to load: ${escape(err && err.message || 'Unknown error')}</div>`
  }
}

function _arRenderStale() {
  var tabContent = document.getElementById('arTabContent')
  if (!tabContent) return
  var leads = _arStaleLeads
  var total = _arStaleTotal
  var assignable = _arStaleAssignable
  var totalPages = Math.max(1, Math.ceil(total / _arStalePageSize))

  var memberOptions = assignable.map(function (u) {
    return `<option value="${u.id}">${escape(u.name)}</option>`
  }).join('')
  var sourceOptions = _arOptionHtml(_arStaleSources, _arStaleSource, 'value', 'label', 'All Sources')
  var projectOptions = _arOptionHtml(_arStaleProjects, _arStaleProject, 'id', 'name', 'All Projects')

  var statusOptions = [
    '', 'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
    'site_visit_planned', 'site_visit_done', 'negotiation', 'booking_done',
    'not_interested', 'lost', 'junk',
  ].map(function (s) {
    return `<option value="${s}" ${_arStaleStatus === s ? 'selected' : ''}>${s ? s.replace(/_/g, ' ') : 'All Statuses'}</option>`
  }).join('')

  var leadCards = leads.length === 0
    ? `<div style="text-align:center;padding:40px 20px;color:#9ca3af;">
        <div style="font-size:32px;margin-bottom:10px;">🕐</div>
        <p style="margin:0 0 6px;font-size:14px;color:#475569;font-weight:600;">No stale leads found for "Not updated in ${_arStaleDays} day${_arStaleDays !== 1 ? 's' : ''}".</p>
        <p style="margin:0;font-size:12px;color:#94a3b8;">A lead is stale when it has not been updated for ${_arStaleDays}+ consecutive days.<br>Try selecting fewer days (e.g. 3 or 5) to see recently untouched leads.</p>
      </div>`
    : leads.map(function (l, i) {
      var sc = (typeof STATUS_COLORS !== 'undefined' ? STATUS_COLORS : {})[l.status] || { bg: '#f1f5f9', color: '#475569', label: l.status || 'new' }
      var serial = (_arStalePage - 1) * _arStalePageSize + i + 1
      var lastUpdated = _arWhenLabel(l.last_action_at || l.updated_at)
      var initial = escape((l.name || '?')[0].toUpperCase())
      return `
        <div id="arSRow_${l.id}" class="ar-lead-row" style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:${_arStaleSelectedLeads.has(l.id) ? '#eff6ff' : '#fff'};border:1px solid #e2e8f0;border-radius:10px;transition:background .15s;">
          <input type="checkbox" id="arSChk_${l.id}" onchange="_arSToggle(${l.id})" ${_arStaleSelectedLeads.has(l.id) ? 'checked' : ''} style="width:16px;height:16px;cursor:pointer;flex-shrink:0;" />
          <span style="font-size:11px;font-weight:700;color:#94a3b8;min-width:22px;text-align:right;flex-shrink:0;">${serial}</span>
          <div style="width:38px;height:38px;border-radius:50%;background:#0891b2;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;flex-shrink:0;">${initial}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;color:#0f172a;">${escape(l.name || '')}</div>
            <div style="font-size:11px;color:#64748b;">${l.phone || '-'} | ${escape(l.stale_reason || 'Not recently updated')} | Last action ${lastUpdated}</div>
            <div class="ar-row-meta" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;">
              ${_arMetaChip('Owner', l.assigned_to_name || l.assigned_user_name)}
              ${_arMetaChip('Project', l.project_name || l.project)}
              ${_arMetaChip('Source', l.source)}
            </div>
            ${l.assigned_to_name || l.assigned_user_name ? `<div style="font-size:11px;color:#94a3b8;margin-top:1px;">Currently: ${escape(l.assigned_to_name || l.assigned_user_name)}</div>` : ''}
          </div>
          <span style="background:${sc.bg};color:${sc.color};font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;flex-shrink:0;">${sc.label || (l.status || 'new').replace(/_/g, ' ')}</span>
          <button onclick="viewLeadDetails(${l.id})" style="font-size:11px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#6366f1;cursor:pointer;font-weight:600;white-space:nowrap;flex-shrink:0;">Open</button>
        </div>`
    }).join('')

  tabContent.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px;margin-bottom:12px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;">
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Not Updated In</div>
        <select id="arStaleDays" class="dash-filter-ctl">
          ${[1,2,3,5,7,10,14,15,21,30,45,60,90].map(function(d) { return `<option value="${d}" ${_arStaleDays === d ? 'selected' : ''}>${d} day${d>1?'s':''}</option>` }).join('')}
        </select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Status</div>
        <select id="arStaleStatus" class="dash-filter-ctl">${statusOptions}</select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Source</div>
        <select id="arStaleSource" class="dash-filter-ctl">${sourceOptions}</select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Project</div>
        <select id="arStaleProject" class="dash-filter-ctl">${projectOptions}</select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Sort</div>
        <select id="arStaleSort" class="dash-filter-ctl">
          <option value="stale_desc" ${_arStaleSort === 'stale_desc' ? 'selected' : ''}>Most stale first</option>
          <option value="stale_asc" ${_arStaleSort === 'stale_asc' ? 'selected' : ''}>Least stale first</option>
        </select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Search</div>
        <input id="arStaleSearch" class="dash-filter-ctl" value="${escape(_arStaleSearch)}" placeholder="Name, phone, project" onkeydown="if(event.key==='Enter'){event.preventDefault();_arApplyStaleFilters()}" />
      </div>
      <div style="display:flex;align-items:flex-end;gap:8px;">
        <button onclick="_arApplyStaleFilters()" class="button secondary" style="height:36px;font-size:13px;">Apply</button>
        <button onclick="_arResetStaleFilters()" style="height:36px;font-size:13px;border:1px solid #cbd5e1;border-radius:7px;background:#fff;color:#334155;padding:0 12px;font-weight:700;cursor:pointer;">Reset</button>
      </div>
    </div>

    <div style="display:flex;gap:10px;align-items:flex-end;margin-bottom:14px;flex-wrap:wrap;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;">
      <div style="margin-left:auto;">
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Reassign To</div>
        <select id="arStaleTarget" class="dash-filter-ctl" style="max-width:200px;">
          <option value="">— Select Member —</option>
          ${memberOptions}
        </select>
      </div>
      <button onclick="_arBulkAssignStale()" class="button" id="arStaleAssignBtn" style="height:36px;font-size:13px;">Reassign Selected (${_arStaleSelectedLeads.size})</button>
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;padding:0 2px;margin-bottom:10px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <label style="font-size:13px;font-weight:600;color:#475569;display:flex;align-items:center;gap:8px;cursor:pointer;">
          <input type="checkbox" onchange="_arSSelectAll(this.checked)" id="arSelectAllStale"> Select Page (${leads.length})
        </label>
        ${total > leads.length ? `<button onclick="_arSSelectAllPages()" id="arSSelectAllPagesBtn" style="font-size:12px;color:#059669;background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:4px 10px;cursor:pointer;font-weight:600;">Select All ${total} Leads</button>` : ''}
      </div>
      <span style="font-size:12px;color:#94a3b8;">${total} stale total</span>
    </div>

    <div style="display:flex;flex-direction:column;gap:8px;">
      ${leadCards}
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 4px 0;margin-top:12px;border-top:1px solid #e2e8f0;flex-wrap:wrap;gap:8px;">
      <span style="font-size:12px;color:#64748b;">Page ${_arStalePage} of ${totalPages}</span>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:12px;color:#64748b;">Page size</span>
        <select onchange="_arStaleSetPageSize(this.value)" style="border:1px solid #cbd5e1;border-radius:6px;padding:3px 7px;font-size:12px;">
          ${[10, 25, 50].map(function(n) { return `<option value="${n}" ${_arStalePageSize === n ? 'selected' : ''}>${n}</option>` }).join('')}
        </select>
      </div>
      ${_arPagerHtml('_arStale', _arStalePage, total, _arStalePageSize)}
    </div>
  `
}

function _arUpdateStaleAssignBtn() {
  var btn = document.getElementById('arStaleAssignBtn')
  if (btn) btn.textContent = `Reassign Selected (${_arStaleSelectedLeads.size})`
}

async function _arSSelectAllPages() {
  var btn = document.getElementById('arSSelectAllPagesBtn')
  if (btn) { btn.textContent = '⏳ Loading...'; btn.disabled = true }
  try {
    var qs = `/leads/assign-reassign/stale?${_arBuildStaleParams({ ids_only: 1, limit: 10000 }).toString()}`
    var data = await _apiRequest(qs, { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 20000 })
    ;(data.lead_ids || []).forEach(function (id) {
      _arStaleSelectedLeads.add(id)
      var chk = document.getElementById('arSChk_' + id)
      if (chk) chk.checked = true
      var row = document.getElementById('arSRow_' + id)
      if (row) row.style.background = '#eff6ff'
    })
    _arUpdateStaleAssignBtn()
    var limited = data.limited ? ` First ${_arStaleSelectedLeads.size} selected.` : ''
    showToast(`${_arStaleSelectedLeads.size} leads selected across all pages.${limited}`, data.limited ? 'warning' : 'success')
    if (btn) { btn.textContent = `✓ All ${_arStaleSelectedLeads.size} Selected`; btn.disabled = true }
  } catch (err) {
    showToast('Failed to select all leads.', 'error')
    if (btn) { btn.textContent = `Select All ${_arStaleTotal} Leads`; btn.disabled = false }
  }
}

async function _arBulkAssignStale() {
  var target = document.getElementById('arStaleTarget')
  var targetId = target && target.value ? Number(target.value) : null
  if (!targetId) { showToast('Please select a member to reassign to.', 'warning'); return }
  if (_arStaleSelectedLeads.size === 0) { showToast('Please select at least one lead.', 'warning'); return }
  try {
    var result = await _apiRequest('/leads/assign-reassign/bulk-assign', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ lead_ids: Array.from(_arStaleSelectedLeads), target_user_id: targetId, reason: 'Stale lead reassignment' }),
      retries: 0,
    })
    showToast(`Reassigned ${result.assigned} lead${result.assigned !== 1 ? 's' : ''} successfully.`, 'success')
    _arStalePage = 1
    _arLoadStale()
  } catch (err) {
    showToast('Reassignment failed: ' + (err && err.message || 'Unknown error'), 'error')
  }
}

// ── WORKLOAD TAB ─────────────────────────────────────────────────────────────

async function _arLoadWorkload() {
  var tabContent = document.getElementById('arTabContent')
  if (!tabContent) return
  tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#64748b;"><i class="fa-solid fa-spinner fa-spin"></i> Loading workload data...</div>`

  try {
    var data = await _apiRequest('/leads/assign-reassign/workload', { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 15000 })
    _arWorkloadMembers = data.members || []
    _arWorkloadAssignable = data.assignable_users || []
    _arRenderWorkload()
  } catch (err) {
    if (tabContent) tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#ef4444;">Failed to load: ${escape(err && err.message || 'Unknown error')}</div>`
  }
}

function _arRenderWorkload() {
  var tabContent = document.getElementById('arTabContent')
  if (!tabContent) return
  var members = _arWorkloadMembers
  var assignable = _arWorkloadAssignable

  if (members.length === 0) {
    tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#64748b;">No team members found.</div>`
    return
  }

  var maxActive = Math.max.apply(null, members.map(function (m) { return m.active_leads || 0 })) || 1

  var cards = members.map(function (m) {
    var barPct = Math.round(((m.active_leads || 0) / maxActive) * 100)
    var barColor = barPct > 75 ? '#ef4444' : barPct > 50 ? '#f59e0b' : '#22c55e'
    var cardAssignableOptions = assignable
      .filter(function (u) { return u.id !== m.id })
      .map(function (u) { return `<option value="${u.id}">${escape(u.name)}</option>` })
      .join('')
    return `
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 18px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
          <div>
            <div style="font-weight:700;font-size:14px;color:#0f172a;">${escape(m.name)}</div>
            <div style="font-size:11px;color:#64748b;">${(m.role || '').replace(/_/g, ' ')}</div>
          </div>
          ${m.overdue_callbacks > 0 ? `<span style="background:#fef2f2;color:#dc2626;font-size:11px;font-weight:700;padding:3px 8px;border-radius:6px;">⚠️ ${m.overdue_callbacks} overdue</span>` : ''}
        </div>
        <div class="ar-workload-metrics" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:10px;">
          ${[
            ['Assigned', m.assigned || m.total_leads || 0, '#1e3a5f'],
            ['Untouched', m.untouched || 0, '#d97706'],
            ['Callbacks', m.callbacks || 0, '#2563eb'],
            ['Overdue', m.overdue_callbacks || 0, '#dc2626'],
            ['Stale', m.stale || 0, '#7c2d12'],
            ['Follow ups', m.follow_ups || 0, '#7c3aed'],
          ].map(function(metric) {
            return `<div style="border:1px solid #e2e8f0;border-radius:9px;padding:8px;background:#f8fafc;">
              <div style="font-size:18px;font-weight:800;color:${metric[2]};line-height:1;">${metric[1]}</div>
              <div style="font-size:10px;color:#64748b;font-weight:700;margin-top:3px;">${metric[0]}</div>
            </div>`
          }).join('')}
        </div>
        <div style="background:#f1f5f9;border-radius:4px;height:6px;margin-bottom:12px;">
          <div style="background:${barColor};height:6px;border-radius:4px;width:${barPct}%;transition:width 0.4s;"></div>
        </div>
        <button onclick="_arSelectWorkloadMember(${m.id})" class="button secondary" style="font-size:12px;padding:8px;width:100%;">Manage workload</button>
      </div>`
  }).join('')

  tabContent.innerHTML = `
    <div style="margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;">
      <p style="font-size:13px;color:#475569;margin:0;">Move leads from one member to another. Use the status filter to target a specific stage.</p>
      <button onclick="_arLoadWorkload()" class="button secondary" style="font-size:12px;padding:5px 14px;"><i class="fa-solid fa-rotate"></i> Refresh</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(240px, 1fr));gap:14px;">${cards}</div>
    <div id="arWorkloadPanel" style="margin-top:16px;"></div>
  `
  if (_arWorkloadSelectedFrom) _arRenderWorkloadPanel()
}

async function _arMoveLeads(fromUserId) {
  var toEl = document.getElementById('arMoveTo_' + fromUserId)
  var countEl = document.getElementById('arMoveCount_' + fromUserId)
  var statusEl = document.getElementById('arMoveStatus_' + fromUserId)
  var toId = toEl && toEl.value ? Number(toEl.value) : null
  var count = countEl ? Math.max(1, Math.min(500, Number(countEl.value) || 10)) : 10
  var statusFilter = statusEl ? statusEl.value : ''

  if (!toId) { showToast('Please select a destination member.', 'warning'); return }
  if (toId === fromUserId) { showToast('Cannot move leads to the same person.', 'warning'); return }

  var fromName = ''
  var toName = ''
  _arWorkloadMembers.forEach(function (m) { if (m.id === fromUserId) fromName = m.name })
  _arWorkloadAssignable.forEach(function (u) { if (u.id === toId) toName = u.name })

  var statusLabel = statusFilter ? ` "${statusFilter.replace(/_/g, ' ')}"` : ''
  if (!confirm(`Move ${count}${statusLabel} lead${count !== 1 ? 's' : ''} from ${fromName} to ${toName}?`)) return

  try {
    var result = await _apiRequest('/leads/assign-reassign/workload-move', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ from_user_id: fromUserId, to_user_id: toId, count: count, status_filter: statusFilter }),
      retries: 0,
    })
    showToast(`Moved ${result.moved} lead${result.moved !== 1 ? 's' : ''}${statusLabel}.`, 'success')
    _arLoadWorkload()
  } catch (err) {
    showToast('Move failed: ' + (err && err.message || 'Unknown error'), 'error')
  }
}

function _arSelectWorkloadMember(userId) {
  _arWorkloadSelectedFrom = userId
  _arWorkloadPage = 1
  _arWorkloadSelectedLeads = new Set()
  _arWorkloadFilterState = {}
  _arRenderWorkloadPanel()
  _arLoadWorkloadPreview()
}

function _arWorkloadReadFilters() {
  var state = {}
  ;['status','project_id','source','callback_state','lead_age','last_updated','sort'].forEach(function (id) {
    var el = document.getElementById('arW_' + id)
    if (el && el.value) state[id] = el.value
  })
  var search = (document.getElementById('arW_search')?.value || '').trim()
  if (search) state.search = search
  state.untouched_only = document.getElementById('arW_untouched')?.checked ? '1' : ''
  state.stale_only = document.getElementById('arW_stale')?.checked ? '1' : ''
  var dest = document.getElementById('arW_to_user_id')?.value || ''
  if (dest) state.to_user_id = dest
  return state
}

function _arWorkloadParams(extra, refreshState) {
  if (refreshState) _arWorkloadFilterState = _arWorkloadReadFilters()
  var state = _arWorkloadFilterState || {}
  var params = new URLSearchParams()
  params.set('from_user_id', String(_arWorkloadSelectedFrom || ''))
  params.set('page', String(_arWorkloadPage))
  params.set('per_page', String(_arWorkloadPageSize))
  ;['status','project_id','source','callback_state','lead_age','last_updated','sort','search','to_user_id'].forEach(function (id) {
    if (state[id]) params.set(id, state[id])
  })
  if (state.untouched_only) params.set('untouched_only', '1')
  if (state.stale_only) params.set('stale_only', '1')
  Object.keys(extra || {}).forEach(function(k){ params.set(k, String(extra[k])) })
  return params
}

function _arRenderWorkloadPanel() {
  var panel = document.getElementById('arWorkloadPanel')
  if (!panel || !_arWorkloadSelectedFrom) return
  var from = _arWorkloadMembers.find(function(m){ return Number(m.id) === Number(_arWorkloadSelectedFrom) }) || {}
  var state = _arWorkloadFilterState || {}
  var filterMeta = (_arWorkloadPreview && _arWorkloadPreview.filters) || {}
  var statuses = filterMeta.statuses || AR_LEAD_STATUSES
  var sourceOptions = _arOptionHtml(filterMeta.sources || [], state.source || '', 'value', 'label', 'All Sources')
  var projectOptions = _arOptionHtml(filterMeta.projects || [], state.project_id || '', 'id', 'name', 'All Projects')
  var destOptions = _arWorkloadAssignable.filter(function(u){ return Number(u.id) !== Number(_arWorkloadSelectedFrom) }).map(function(u){ return `<option value="${u.id}" ${String(state.to_user_id || '') === String(u.id) ? 'selected' : ''}>${escape(u.name)}</option>` }).join('')
  var rows = (_arWorkloadPreview && _arWorkloadPreview.leads) || []
  var counters = _arWorkloadPreview ? `
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin:10px 0;">
      ${[['Matching', _arWorkloadPreview.matching], ['Eligible', _arWorkloadPreview.eligible], ['Excluded', _arWorkloadPreview.excluded]].map(function(x){ return `<div style="border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#f8fafc;"><div style="font-size:18px;font-weight:800;color:#0f172a;">${x[1] || 0}</div><div style="font-size:10px;font-weight:800;color:#64748b;text-transform:uppercase;">${x[0]}</div></div>` }).join('')}
    </div>` : ''
  panel.innerHTML = `
    <div style="background:#fff;border:1px solid #dbeafe;border-radius:12px;padding:14px 16px;box-shadow:0 4px 14px rgba(15,23,42,.06);">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:10px;">
        <div><div style="font-weight:800;color:#0f172a;">Manage workload: ${escape(from.name || '')}</div><div style="font-size:12px;color:#64748b;">Filter, preview and move a precise cohort.</div></div>
        <button onclick="_arWorkloadSelectedFrom=null;_arWorkloadPreview=null;_arRenderWorkload()" class="ar-page-btn">Close</button>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px;">
        <select id="arW_status" class="dash-filter-ctl">${_arSimpleOptions(statuses, state.status || '', 'Active statuses')}</select>
        <select id="arW_project_id" class="dash-filter-ctl">${projectOptions}</select>
        <select id="arW_source" class="dash-filter-ctl">${sourceOptions}</select>
        <select id="arW_callback_state" class="dash-filter-ctl"><option value="">Any Callback</option><option value="none" ${state.callback_state === 'none' ? 'selected' : ''}>None</option><option value="pending" ${state.callback_state === 'pending' ? 'selected' : ''}>Pending</option><option value="today" ${state.callback_state === 'today' ? 'selected' : ''}>Today</option><option value="overdue" ${state.callback_state === 'overdue' ? 'selected' : ''}>Overdue</option><option value="future" ${state.callback_state === 'future' ? 'selected' : ''}>Future</option></select>
        <select id="arW_lead_age" class="dash-filter-ctl"><option value="">Any Age</option><option value="0_3" ${state.lead_age === '0_3' ? 'selected' : ''}>0-3 days</option><option value="4_7" ${state.lead_age === '4_7' ? 'selected' : ''}>4-7 days</option><option value="8_15" ${state.lead_age === '8_15' ? 'selected' : ''}>8-15 days</option><option value="16_30" ${state.lead_age === '16_30' ? 'selected' : ''}>16-30 days</option><option value="31_plus" ${state.lead_age === '31_plus' ? 'selected' : ''}>31+ days</option></select>
        <select id="arW_last_updated" class="dash-filter-ctl"><option value="">Any Last Updated</option><option value="today" ${state.last_updated === 'today' ? 'selected' : ''}>Today</option><option value="1_plus" ${state.last_updated === '1_plus' ? 'selected' : ''}>1+ day ago</option><option value="3_plus" ${state.last_updated === '3_plus' ? 'selected' : ''}>3+ days ago</option><option value="7_plus" ${state.last_updated === '7_plus' ? 'selected' : ''}>7+ days ago</option><option value="15_plus" ${state.last_updated === '15_plus' ? 'selected' : ''}>15+ days ago</option><option value="30_plus" ${state.last_updated === '30_plus' ? 'selected' : ''}>30+ days ago</option></select>
        <select id="arW_sort" class="dash-filter-ctl"><option value="oldest_received" ${state.sort === 'oldest_received' || !state.sort ? 'selected' : ''}>Oldest received</option><option value="newest_received" ${state.sort === 'newest_received' ? 'selected' : ''}>Newest received</option><option value="least_recently_updated" ${state.sort === 'least_recently_updated' ? 'selected' : ''}>Least recently updated</option><option value="most_recently_updated" ${state.sort === 'most_recently_updated' ? 'selected' : ''}>Most recently updated</option><option value="oldest_callback" ${state.sort === 'oldest_callback' ? 'selected' : ''}>Oldest callback</option></select>
        <input id="arW_search" class="dash-filter-ctl" placeholder="Search name, phone, project" value="${escape(state.search || '')}" />
      </div>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:10px;">
        <label style="font-size:12px;color:#475569;"><input id="arW_untouched" type="checkbox" ${state.untouched_only ? 'checked' : ''}> Untouched only</label>
        <label style="font-size:12px;color:#475569;"><input id="arW_stale" type="checkbox" ${state.stale_only ? 'checked' : ''}> Stale only</label>
        <button onclick="_arWorkloadPage=1;_arWorkloadSelectedLeads=new Set();_arLoadWorkloadPreview(true)" class="button secondary" style="height:34px;font-size:12px;">Apply filters</button>
      </div>
      ${counters}
      <div style="overflow:auto;border:1px solid #e2e8f0;border-radius:10px;">
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
          <thead style="background:#f8fafc;"><tr><th style="padding:8px;"><input type="checkbox" onchange="_arWSelectPage(this.checked)"></th><th>Lead</th><th>Status</th><th>Project</th><th>Source</th><th>Age</th><th>Last update</th><th>Callback</th><th>Owner</th></tr></thead>
          <tbody>${rows.length ? rows.map(function(l){ return `<tr style="border-top:1px solid #e2e8f0;"><td style="padding:8px;text-align:center;"><input id="arWChk_${l.id}" type="checkbox" onchange="_arWToggle(${l.id})"></td><td style="padding:8px;font-weight:700;color:#1d4ed8;">${escape(l.name || '')}</td><td>${escape(l.status || '')}</td><td>${escape(l.project_name || '-')}</td><td>${escape(l.source || '-')}</td><td>${escape(_arLeadAgeLabel(l))}</td><td>${escape(_arWhenLabel(l.last_action_at || l.updated_at))}</td><td>${escape(l.callback_state || 'none')}</td><td>${escape(l.assigned_user_name || '-')}</td></tr>` }).join('') : `<tr><td colspan="9" style="padding:18px;text-align:center;color:#94a3b8;">No eligible leads match these filters.</td></tr>`}</tbody>
        </table>
      </div>
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px;">
        <div><select id="arW_to_user_id" class="dash-filter-ctl" style="min-width:180px;"><option value="">Move to...</option>${destOptions}</select></div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <input id="arW_count" type="number" min="1" max="500" value="1" class="dash-filter-ctl" style="width:80px;">
          <button onclick="_arExecuteWorkloadMove('selected')" class="button secondary" style="font-size:12px;">Move Selected (${_arWorkloadSelectedLeads.size})</button>
          <button onclick="_arExecuteWorkloadMove('current_page')" class="button secondary" style="font-size:12px;">Move Page</button>
          <button onclick="_arExecuteWorkloadMove('first_n')" class="button secondary" style="font-size:12px;">First N</button>
          <button onclick="_arExecuteWorkloadMove('random_n')" class="button secondary" style="font-size:12px;">Random N</button>
        </div>
      </div>
      <div style="margin-top:10px;">${_arPagerHtml('_arWorkload', _arWorkloadPage, (_arWorkloadPreview && _arWorkloadPreview.eligible) || 0, _arWorkloadPageSize)}</div>
    </div>`
}

async function _arLoadWorkloadPreview(refreshState) {
  if (!_arWorkloadSelectedFrom) return
  var data = await _apiRequest('/leads/assign-reassign/workload-preview?' + _arWorkloadParams({}, refreshState).toString(), { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 15000 })
  _arWorkloadPreview = data
  _arWorkloadPage = data.page || _arWorkloadPage
  _arRenderWorkloadPanel()
}

function _arWorkloadSetPage(page) {
  var total = (_arWorkloadPreview && _arWorkloadPreview.eligible) || 0
  var totalPages = Math.max(1, Math.ceil(total / _arWorkloadPageSize))
  _arWorkloadPage = Math.min(Math.max(1, parseInt(page, 10) || 1), totalPages)
  _arLoadWorkloadPreview()
}

function _arWToggle(id) {
  var chk = document.getElementById('arWChk_' + id)
  if (chk && chk.checked) _arWorkloadSelectedLeads.add(id)
  else _arWorkloadSelectedLeads.delete(id)
}

function _arWSelectPage(checked) {
  ;((_arWorkloadPreview && _arWorkloadPreview.leads) || []).forEach(function(l){
    var chk = document.getElementById('arWChk_' + l.id)
    if (chk) chk.checked = checked
    if (checked) _arWorkloadSelectedLeads.add(l.id)
    else _arWorkloadSelectedLeads.delete(l.id)
  })
  _arRenderWorkloadPanel()
}

async function _arExecuteWorkloadMove(mode) {
  var toId = document.getElementById('arW_to_user_id')?.value || ''
  if (!toId) { showToast('Select a destination user.', 'warning'); return }
  var count = Math.max(1, Math.min(500, Number(document.getElementById('arW_count')?.value || 1)))
  if (mode === 'selected' && !_arWorkloadSelectedLeads.size) { showToast('Select at least one preview row.', 'warning'); return }
  var label = mode === 'selected' ? _arWorkloadSelectedLeads.size : mode === 'current_page' ? ((_arWorkloadPreview && _arWorkloadPreview.leads || []).length) : count
  if (!confirm(`Move ${label} lead${label !== 1 ? 's' : ''}?`)) return
  var body = Object.fromEntries(_arWorkloadParams({}, true).entries())
  body.from_user_id = _arWorkloadSelectedFrom
  body.to_user_id = Number(toId)
  body.selection_mode = mode
  body.count = count
  body.lead_ids = Array.from(_arWorkloadSelectedLeads)
  var result = await _apiRequest('/leads/assign-reassign/workload-move', {
    method: 'POST',
    headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
    body: JSON.stringify(body),
    retries: 0,
  })
  showToast(`Moved ${result.moved || 0} lead${result.moved === 1 ? '' : 's'}.`, 'success')
  _arWorkloadSelectedLeads = new Set()
  await _arLoadWorkload()
}
