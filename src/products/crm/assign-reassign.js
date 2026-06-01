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
var _arUnassignedTotal = 0
var _arUnassignedLeads = []
var _arUnassignedAssignable = []

// ── Tab: Stale ────────────────────────────────────────────────────────────────
var _arStaleDays = 5
var _arStaleStatus = ''
var _arStalePage = 1
var _arStaleTotal = 0
var _arStaleLeads = []
var _arStaleAssignable = []
var _arStaleSelectedLeads = new Set()

// ── Tab: Workload ─────────────────────────────────────────────────────────────
var _arWorkloadMembers = []
var _arWorkloadAssignable = []

// ── Tab: Recycle Queue (embedded) ────────────────────────────────────────────
// Delegates to renderRecycleQueue() — just switches route key

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
          <h2 class="sm-page-title">🔀 Assign / Reassign</h2>
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
    // Hand off to existing recycle queue renderer but keep our root
    tabContent.innerHTML = `<div id="content"></div>`
    // Swap content ref temporarily — trick: renderRecycleQueue writes to #content
    var savedRoot = document.getElementById('content')
    // Actually just inline the recycle queue content directly in tabContent
    tabContent.id = 'content'
    window._ACTIVE_ROUTE = 'recycle_queue'
    await renderRecycleQueue()
    // Restore our tab content id
    var newContent = document.getElementById('content')
    if (newContent) newContent.id = 'arTabContent'
    window._ACTIVE_ROUTE = 'assign_reassign'
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
    var qs = `?page=${_arUnassignedPage}&per_page=25`
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
  var perPage = 25
  var totalPages = Math.ceil(total / perPage)

  var memberOptions = assignable.map(function (u) {
    return `<option value="${u.id}">${escape(u.name)} (${u.role.replace('_', ' ')})</option>`
  }).join('')

  var rows = leads.length === 0
    ? `<tr><td colspan="6" style="text-align:center;padding:24px;color:#64748b;">No unassigned leads found.</td></tr>`
    : leads.map(function (l) {
      return `<tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:8px 10px;"><input type="checkbox" class="ar-lead-cb" data-id="${l.id}" ${_arSelectedLeads.has(l.id) ? 'checked' : ''}></td>
        <td style="padding:8px 10px;font-weight:600;font-size:13px;">${escape(l.name || '—')}</td>
        <td style="padding:8px 10px;font-size:12px;color:#475569;">${escape(l.phone || '—')}</td>
        <td style="padding:8px 10px;font-size:12px;color:#475569;">${escape(l.project_name || l.project || '—')}</td>
        <td style="padding:8px 10px;font-size:12px;"><span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:6px;">${escape((l.status || 'new').replace(/_/g, ' '))}</span></td>
        <td style="padding:8px 10px;font-size:11px;color:#94a3b8;">${l.created_at ? new Date(l.created_at).toLocaleDateString('en-IN') : '—'}</td>
      </tr>`
    }).join('')

  tabContent.innerHTML = `
    <div style="display:flex;gap:12px;align-items:flex-end;margin-bottom:16px;flex-wrap:wrap;">
      <div style="flex:1;min-width:180px;">
        <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:4px;">ASSIGN TO</div>
        <select id="arUnassignedTarget" class="dash-filter-ctl" style="width:100%;max-width:260px;">
          <option value="">— Select Member —</option>
          ${memberOptions}
        </select>
      </div>
      <button onclick="_arBulkAssignUnassigned()" class="button" style="height:36px;font-size:13px;">Assign Selected (${_arSelectedLeads.size})</button>
      <button onclick="_arDistributeUnassigned()" class="button secondary" style="height:36px;font-size:13px;">⚖️ Equally Distribute All</button>
    </div>

    <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#f8fafc;border-bottom:1px solid #e2e8f0;">
        <label style="font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px;cursor:pointer;">
          <input type="checkbox" id="arSelectAllUnassigned"> Select All (${leads.length})
        </label>
        <span style="font-size:12px;color:#64748b;">${total} total unassigned</span>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="background:#f8fafc;">
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;width:40px;"></th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Name</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Phone</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Project</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Status</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Created</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>

    ${totalPages > 1 ? `
    <div style="display:flex;gap:8px;justify-content:center;margin-top:14px;">
      ${_arUnassignedPage > 1 ? `<button onclick="_arUnassignedPage--;_arLoadUnassigned()" class="button secondary" style="font-size:12px;padding:5px 14px;">← Prev</button>` : ''}
      <span style="padding:6px 12px;font-size:13px;color:#475569;">Page ${_arUnassignedPage} / ${totalPages}</span>
      ${_arUnassignedPage < totalPages ? `<button onclick="_arUnassignedPage++;_arLoadUnassigned()" class="button secondary" style="font-size:12px;padding:5px 14px;">Next →</button>` : ''}
    </div>` : ''}
  `

  // Bind checkboxes
  tabContent.querySelectorAll('.ar-lead-cb').forEach(function (cb) {
    cb.addEventListener('change', function () {
      var id = Number(cb.dataset.id)
      if (cb.checked) _arSelectedLeads.add(id)
      else _arSelectedLeads.delete(id)
      _arUpdateAssignBtn()
    })
  })
  var selectAll = document.getElementById('arSelectAllUnassigned')
  if (selectAll) {
    selectAll.addEventListener('change', function () {
      tabContent.querySelectorAll('.ar-lead-cb').forEach(function (cb) {
        cb.checked = selectAll.checked
        var id = Number(cb.dataset.id)
        if (selectAll.checked) _arSelectedLeads.add(id)
        else _arSelectedLeads.delete(id)
      })
      _arUpdateAssignBtn()
    })
  }
}

function _arUpdateAssignBtn() {
  var btn = document.querySelector('[onclick="_arBulkAssignUnassigned()"]')
  if (btn) btn.textContent = `Assign Selected (${_arSelectedLeads.size})`
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
    var qs = `?days=${_arStaleDays}&page=${_arStalePage}&per_page=25${_arStaleStatus ? '&status=' + encodeURIComponent(_arStaleStatus) : ''}`
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
  var perPage = 25
  var totalPages = Math.ceil(total / perPage)

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

  var rows = leads.length === 0
    ? `<tr><td colspan="7" style="text-align:center;padding:24px;color:#64748b;">No stale leads found.</td></tr>`
    : leads.map(function (l) {
      var lastUpdated = l.updated_at ? new Date(l.updated_at).toLocaleDateString('en-IN') : '—'
      return `<tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:8px 10px;"><input type="checkbox" class="ar-stale-cb" data-id="${l.id}" ${_arStaleSelectedLeads.has(l.id) ? 'checked' : ''}></td>
        <td style="padding:8px 10px;font-weight:600;font-size:13px;">${escape(l.name || '—')}</td>
        <td style="padding:8px 10px;font-size:12px;color:#475569;">${escape(l.phone || '—')}</td>
        <td style="padding:8px 10px;font-size:12px;color:#475569;">${escape(l.project_name || l.project || '—')}</td>
        <td style="padding:8px 10px;font-size:12px;"><span style="background:#f1f5f9;color:#475569;padding:2px 8px;border-radius:6px;">${escape((l.status || 'new').replace(/_/g, ' '))}</span></td>
        <td style="padding:8px 10px;font-size:12px;color:#475569;">${escape(l.assigned_to_name || l.assigned_user_name || 'Unassigned')}</td>
        <td style="padding:8px 10px;font-size:11px;color:#94a3b8;">${lastUpdated}</td>
      </tr>`
    }).join('')

  tabContent.innerHTML = `
    <div style="display:flex;gap:12px;align-items:flex-end;margin-bottom:16px;flex-wrap:wrap;">
      <div>
        <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:4px;">STALE SINCE</div>
        <select id="arStaleDays" class="dash-filter-ctl" style="width:auto;">
          ${[1,2,3,4,5,7,10,14,15].map(function(d) { return `<option value="${d}" ${_arStaleDays === d ? 'selected' : ''}>${d} day${d>1?'s':''}</option>` }).join('')}
        </select>
      </div>
      <div>
        <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:4px;">STATUS</div>
        <select id="arStaleStatus" class="dash-filter-ctl" style="width:auto;">${statusOptions}</select>
      </div>
      <button onclick="_arStaleDays=Number(document.getElementById('arStaleDays').value);_arStaleStatus=document.getElementById('arStaleStatus').value;_arStalePage=1;_arLoadStale()" class="button secondary" style="height:36px;font-size:13px;">Apply</button>
      <div style="flex:1;min-width:180px;margin-left:auto;">
        <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:4px;">REASSIGN TO</div>
        <select id="arStaleTarget" class="dash-filter-ctl" style="width:100%;max-width:220px;">
          <option value="">— Select Member —</option>
          ${memberOptions}
        </select>
      </div>
      <button onclick="_arBulkAssignStale()" class="button" style="height:36px;font-size:13px;">Reassign Selected (${_arStaleSelectedLeads.size})</button>
    </div>

    <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#f8fafc;border-bottom:1px solid #e2e8f0;">
        <label style="font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px;cursor:pointer;">
          <input type="checkbox" id="arSelectAllStale"> Select All (${leads.length})
        </label>
        <span style="font-size:12px;color:#64748b;">${total} stale leads found</span>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="background:#f8fafc;">
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;width:40px;"></th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Name</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Phone</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Project</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Status</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Assigned To</th>
          <th style="padding:8px 10px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">Last Updated</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>

    ${totalPages > 1 ? `
    <div style="display:flex;gap:8px;justify-content:center;margin-top:14px;">
      ${_arStalePage > 1 ? `<button onclick="_arStalePage--;_arLoadStale()" class="button secondary" style="font-size:12px;padding:5px 14px;">← Prev</button>` : ''}
      <span style="padding:6px 12px;font-size:13px;color:#475569;">Page ${_arStalePage} / ${totalPages}</span>
      ${_arStalePage < totalPages ? `<button onclick="_arStalePage++;_arLoadStale()" class="button secondary" style="font-size:12px;padding:5px 14px;">Next →</button>` : ''}
    </div>` : ''}
  `

  tabContent.querySelectorAll('.ar-stale-cb').forEach(function (cb) {
    cb.addEventListener('change', function () {
      var id = Number(cb.dataset.id)
      if (cb.checked) _arStaleSelectedLeads.add(id)
      else _arStaleSelectedLeads.delete(id)
      _arUpdateStaleAssignBtn()
    })
  })
  var selectAll = document.getElementById('arSelectAllStale')
  if (selectAll) {
    selectAll.addEventListener('change', function () {
      tabContent.querySelectorAll('.ar-stale-cb').forEach(function (cb) {
        cb.checked = selectAll.checked
        var id = Number(cb.dataset.id)
        if (selectAll.checked) _arStaleSelectedLeads.add(id)
        else _arStaleSelectedLeads.delete(id)
      })
      _arUpdateStaleAssignBtn()
    })
  }
}

function _arUpdateStaleAssignBtn() {
  var btn = document.querySelector('[onclick="_arBulkAssignStale()"]')
  if (btn) btn.textContent = `Reassign Selected (${_arStaleSelectedLeads.size})`
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

  var assignableOptions = assignable.map(function (u) {
    return `<option value="${u.id}">${escape(u.name)}</option>`
  }).join('')

  if (members.length === 0) {
    tabContent.innerHTML = `<div style="text-align:center;padding:40px;color:#64748b;">No team members found.</div>`
    return
  }

  var maxActive = Math.max.apply(null, members.map(function (m) { return m.active_leads || 0 })) || 1

  var cards = members.map(function (m) {
    var barPct = Math.round(((m.active_leads || 0) / maxActive) * 100)
    var barColor = barPct > 75 ? '#ef4444' : barPct > 50 ? '#f59e0b' : '#22c55e'
    return `
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 18px;min-width:220px;flex:1;">
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
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <select id="arMoveTo_${m.id}" class="dash-filter-ctl" style="font-size:12px;flex:1;min-width:120px;">
            <option value="">Move to...</option>
            ${assignableOptions}
          </select>
          <input id="arMoveCount_${m.id}" type="number" min="1" max="100" value="10" class="dash-filter-ctl" style="width:60px;font-size:12px;">
          <button onclick="_arMoveLeads(${m.id})" class="button secondary" style="font-size:12px;padding:5px 10px;">Move</button>
        </div>
      </div>`
  }).join('')

  tabContent.innerHTML = `
    <div style="margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;">
      <p style="font-size:13px;color:#475569;margin:0;">Move active leads from one member to another. Leads in Lost/Junk/Booking Done are excluded.</p>
      <button onclick="_arLoadWorkload()" class="button secondary" style="font-size:12px;padding:5px 14px;"><i class="fa-solid fa-rotate"></i> Refresh</button>
    </div>
    <div style="display:flex;gap:14px;flex-wrap:wrap;">${cards}</div>
  `
}

async function _arMoveLeads(fromUserId) {
  var toEl = document.getElementById('arMoveTo_' + fromUserId)
  var countEl = document.getElementById('arMoveCount_' + fromUserId)
  var toId = toEl && toEl.value ? Number(toEl.value) : null
  var count = countEl ? Math.max(1, Math.min(100, Number(countEl.value) || 10)) : 10

  if (!toId) { showToast('Please select a destination member.', 'warning'); return }
  if (toId === fromUserId) { showToast('Cannot move leads to the same person.', 'warning'); return }

  var fromName = ''
  var toName = ''
  _arWorkloadMembers.forEach(function (m) { if (m.id === fromUserId) fromName = m.name })
  _arWorkloadAssignable.forEach(function (u) { if (u.id === toId) toName = u.name })

  if (!confirm(`Move ${count} lead${count !== 1 ? 's' : ''} from ${fromName} to ${toName}?`)) return

  try {
    var result = await _apiRequest('/leads/assign-reassign/workload-move', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ from_user_id: fromUserId, to_user_id: toId, count: count }),
      retries: 0,
    })
    showToast(`Moved ${result.moved} lead${result.moved !== 1 ? 's' : ''}.`, 'success')
    _arLoadWorkload()
  } catch (err) {
    showToast('Move failed: ' + (err && err.message || 'Unknown error'), 'error')
  }
}
