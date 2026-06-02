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

// ── Tab: Stale ────────────────────────────────────────────────────────────────
var _arStaleDays = 5
var _arStaleStatus = ''
var _arStalePage = 1
var _arStalePageSize = 25
var _arStaleTotal = 0
var _arStaleLeads = []
var _arStaleAssignable = []
var _arStaleSelectedLeads = new Set()

// ── Tab: Workload ─────────────────────────────────────────────────────────────
var _arWorkloadMembers = []
var _arWorkloadAssignable = []

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
    var qs = `?page=${_arUnassignedPage}&per_page=${_arUnassignedPageSize}`
    var data = await _apiRequest(`/leads/assign-reassign/unassigned${qs}`, { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 15000 })
    _arUnassignedLeads = data.leads || []
    _arUnassignedTotal = data.total || 0
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

  var leadCards = leads.length === 0
    ? `<div style="text-align:center;padding:40px;color:#9ca3af;"><div style="font-size:32px;margin-bottom:8px;">📭</div><p>No unassigned leads found.</p></div>`
    : leads.map(function (l, i) {
      var sc = (typeof STATUS_COLORS !== 'undefined' ? STATUS_COLORS : {})[l.status] || { bg: '#f1f5f9', color: '#475569', label: l.status || 'new' }
      var serial = (_arUnassignedPage - 1) * _arUnassignedPageSize + i + 1
      var createdDate = l.created_at ? new Date(l.created_at).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' }) : '—'
      var initial = escape((l.name || '?')[0].toUpperCase())
      return `
        <div id="arURow_${l.id}" style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:${_arSelectedLeads.has(l.id) ? '#eff6ff' : '#fff'};border:1px solid #e2e8f0;border-radius:10px;transition:background .15s;">
          <input type="checkbox" id="arUChk_${l.id}" onchange="_arUToggle(${l.id})" ${_arSelectedLeads.has(l.id) ? 'checked' : ''} style="width:16px;height:16px;cursor:pointer;flex-shrink:0;" />
          <span style="font-size:11px;font-weight:700;color:#94a3b8;min-width:22px;text-align:right;flex-shrink:0;">${serial}</span>
          <div style="width:38px;height:38px;border-radius:50%;background:#6366f1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;flex-shrink:0;">${initial}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;color:#0f172a;">${escape(l.name || '')}</div>
            <div style="font-size:11px;color:#64748b;">${l.phone || '—'} · ${escape(l.project_name || l.project || '—')} · Added: ${createdDate}</div>
          </div>
          <span style="background:${sc.bg};color:${sc.color};font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;flex-shrink:0;">${sc.label || (l.status || 'new').replace(/_/g, ' ')}</span>
          <button onclick="viewLeadDetails(${l.id})" style="font-size:11px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#6366f1;cursor:pointer;font-weight:600;white-space:nowrap;flex-shrink:0;">Open</button>
        </div>`
    }).join('')

  tabContent.innerHTML = `
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
      <div style="display:flex;gap:6px;">
        <button onclick="_arUnassignedPrev()" ${_arUnassignedPage <= 1 ? 'disabled' : ''} style="font-size:12px;padding:4px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:${_arUnassignedPage <= 1 ? '#cbd5e1' : '#334155'};cursor:${_arUnassignedPage <= 1 ? 'default' : 'pointer'};">Prev</button>
        <button onclick="_arUnassignedNext()" ${_arUnassignedPage >= totalPages ? 'disabled' : ''} style="font-size:12px;padding:4px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:${_arUnassignedPage >= totalPages ? '#cbd5e1' : '#334155'};cursor:${_arUnassignedPage >= totalPages ? 'default' : 'pointer'};">Next</button>
      </div>
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
    var data = await _apiRequest('/leads/assign-reassign/unassigned?per_page=1000&page=1', {
      headers: _apiAuthHeaders(), retries: 1, timeoutMs: 20000,
    })
    ;(data.leads || []).forEach(function (l) {
      _arSelectedLeads.add(l.id)
      var chk = document.getElementById('arUChk_' + l.id)
      if (chk) chk.checked = true
      var row = document.getElementById('arURow_' + l.id)
      if (row) row.style.background = '#eff6ff'
    })
    _arUpdateAssignBtn()
    showToast(`${_arSelectedLeads.size} leads selected across all pages.`, 'success')
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
    var data = await _apiRequest('/leads/assign-reassign/unassigned?per_page=500', { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 20000 })
    var allLeads = data.leads || []
    var assignable = data.assignable_users || []
    if (allLeads.length === 0) { showToast('No unassigned leads.', 'info'); return }
    if (assignable.length === 0) { showToast('No assignable users.', 'warning'); return }

    // Distribute round-robin
    var batches = {}
    assignable.forEach(function (u) { batches[u.id] = [] })
    allLeads.forEach(function (l, i) {
      var u = assignable[i % assignable.length]
      batches[u.id].push(l.id)
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
    var qs = `?days=${_arStaleDays}&page=${_arStalePage}&per_page=${_arStalePageSize}${_arStaleStatus ? '&status=' + encodeURIComponent(_arStaleStatus) : ''}`
    var data = await _apiRequest(`/leads/assign-reassign/stale${qs}`, { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 15000 })
    _arStaleLeads = data.leads || []
    _arStaleTotal = data.total || 0
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
      var lastUpdated = l.updated_at ? new Date(l.updated_at).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' }) : '—'
      var initial = escape((l.name || '?')[0].toUpperCase())
      return `
        <div id="arSRow_${l.id}" style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:${_arStaleSelectedLeads.has(l.id) ? '#eff6ff' : '#fff'};border:1px solid #e2e8f0;border-radius:10px;transition:background .15s;">
          <input type="checkbox" id="arSChk_${l.id}" onchange="_arSToggle(${l.id})" ${_arStaleSelectedLeads.has(l.id) ? 'checked' : ''} style="width:16px;height:16px;cursor:pointer;flex-shrink:0;" />
          <span style="font-size:11px;font-weight:700;color:#94a3b8;min-width:22px;text-align:right;flex-shrink:0;">${serial}</span>
          <div style="width:38px;height:38px;border-radius:50%;background:#0891b2;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;flex-shrink:0;">${initial}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;color:#0f172a;">${escape(l.name || '')}</div>
            <div style="font-size:11px;color:#64748b;">${l.phone || '—'} · ${escape(l.project_name || l.project || '—')} · Last updated: ${lastUpdated}</div>
            ${l.assigned_to_name || l.assigned_user_name ? `<div style="font-size:11px;color:#94a3b8;margin-top:1px;">Currently: ${escape(l.assigned_to_name || l.assigned_user_name)}</div>` : ''}
          </div>
          <span style="background:${sc.bg};color:${sc.color};font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;flex-shrink:0;">${sc.label || (l.status || 'new').replace(/_/g, ' ')}</span>
          <button onclick="viewLeadDetails(${l.id})" style="font-size:11px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#6366f1;cursor:pointer;font-weight:600;white-space:nowrap;flex-shrink:0;">Open</button>
        </div>`
    }).join('')

  tabContent.innerHTML = `
    <div style="display:flex;gap:10px;align-items:flex-end;margin-bottom:14px;flex-wrap:wrap;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;">
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Not Updated In</div>
        <select id="arStaleDays" class="dash-filter-ctl" style="width:auto;">
          ${[1,2,3,5,7,10,14,15,21,30,45,60,90].map(function(d) { return `<option value="${d}" ${_arStaleDays === d ? 'selected' : ''}>${d} day${d>1?'s':''}</option>` }).join('')}
        </select>
      </div>
      <div>
        <div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;">Status</div>
        <select id="arStaleStatus" class="dash-filter-ctl" style="width:auto;">${statusOptions}</select>
      </div>
      <button onclick="_arStaleDays=Number(document.getElementById('arStaleDays').value);_arStaleStatus=document.getElementById('arStaleStatus').value;_arStalePage=1;_arLoadStale()" class="button secondary" style="height:36px;font-size:13px;">Apply</button>
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
      <div style="display:flex;gap:6px;">
        <button onclick="_arStalePrev()" ${_arStalePage <= 1 ? 'disabled' : ''} style="font-size:12px;padding:4px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:${_arStalePage <= 1 ? '#cbd5e1' : '#334155'};cursor:${_arStalePage <= 1 ? 'default' : 'pointer'};">Prev</button>
        <button onclick="_arStaleNext()" ${_arStalePage >= totalPages ? 'disabled' : ''} style="font-size:12px;padding:4px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:${_arStalePage >= totalPages ? '#cbd5e1' : '#334155'};cursor:${_arStalePage >= totalPages ? 'default' : 'pointer'};">Next</button>
      </div>
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
    var qs = `/leads/assign-reassign/stale?days=${_arStaleDays}&per_page=1000&page=1${_arStaleStatus ? '&status=' + encodeURIComponent(_arStaleStatus) : ''}`
    var data = await _apiRequest(qs, { headers: _apiAuthHeaders(), retries: 1, timeoutMs: 20000 })
    ;(data.leads || []).forEach(function (l) {
      _arStaleSelectedLeads.add(l.id)
      var chk = document.getElementById('arSChk_' + l.id)
      if (chk) chk.checked = true
      var row = document.getElementById('arSRow_' + l.id)
      if (row) row.style.background = '#eff6ff'
    })
    _arUpdateStaleAssignBtn()
    showToast(`${_arStaleSelectedLeads.size} leads selected across all pages.`, 'success')
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
        <div style="display:flex;gap:16px;margin-bottom:10px;">
          <div style="text-align:center;">
            <div style="font-size:22px;font-weight:800;color:#1e3a5f;">${m.active_leads || 0}</div>
            <div style="font-size:11px;color:#64748b;">Active</div>
          </div>
          <div style="text-align:center;">
            <div style="font-size:22px;font-weight:800;color:#475569;">${m.total_leads || 0}</div>
            <div style="font-size:11px;color:#64748b;">Total</div>
          </div>
        </div>
        <div style="background:#f1f5f9;border-radius:4px;height:6px;margin-bottom:12px;">
          <div style="background:${barColor};height:6px;border-radius:4px;width:${barPct}%;transition:width 0.4s;"></div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          <select id="arMoveStatus_${m.id}" class="dash-filter-ctl" style="font-size:12px;width:100%;">
            <option value="">Any Active Status</option>
            <option value="new">New</option>
            <option value="no_answer">No Answer</option>
            <option value="follow_up">Follow Up</option>
            <option value="callback_scheduled">Callback Scheduled</option>
            <option value="interested">Interested</option>
            <option value="site_visit_planned">Site Visit Planned</option>
            <option value="site_visit_done">Site Visit Done</option>
            <option value="negotiation">Negotiation</option>
            <option value="not_interested">Not Interested</option>
            <option value="booking_done">Booking Done</option>
            <option value="lost">Lost</option>
            <option value="junk">Junk</option>
          </select>
          <div style="display:flex;gap:6px;align-items:center;">
            <select id="arMoveTo_${m.id}" class="dash-filter-ctl" style="font-size:12px;flex:1;min-width:80px;">
              <option value="">Move to...</option>
              ${cardAssignableOptions}
            </select>
            <input id="arMoveCount_${m.id}" type="number" min="1" max="500" value="10" class="dash-filter-ctl" style="width:54px;font-size:12px;">
          </div>
          <button onclick="_arMoveLeads(${m.id})" class="button secondary" style="font-size:12px;padding:7px;width:100%;">Move</button>
        </div>
      </div>`
  }).join('')

  tabContent.innerHTML = `
    <div style="margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;">
      <p style="font-size:13px;color:#475569;margin:0;">Move leads from one member to another. Use the status filter to target a specific stage.</p>
      <button onclick="_arLoadWorkload()" class="button secondary" style="font-size:12px;padding:5px 14px;"><i class="fa-solid fa-rotate"></i> Refresh</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(240px, 1fr));gap:14px;">${cards}</div>
  `
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
