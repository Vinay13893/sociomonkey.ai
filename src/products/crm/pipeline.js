// ── Pipeline lifecycle state ──────────────────────────────────────────────────────────
var _pipelineRenderId  = 0
var _pipelineAbortCtrl = null
var _pipelineCardState = {}
var _pipelineGlobalSearchQuery = ''
var _pipelineGlobalSearchTimer = null
var _pipelineDragState = null
var _pipelineMoveInFlight = {}

function _pipelineSupportsDragAndDrop() {
  // HTML5 DnD is desktop-first; on touch-only devices we keep click-only cards.
  if (window.matchMedia) return window.matchMedia('(pointer:fine)').matches
  return !('ontouchstart' in window)
}

async function renderPipeline() {
  var _loadStartMs = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now()
  _pipelineRenderId++
  var myId = _pipelineRenderId
  if (_pipelineAbortCtrl) { _pipelineAbortCtrl.abort(); _pipelineAbortCtrl = null }
  var ctrl = new AbortController()
  _pipelineAbortCtrl = ctrl
  var signal = ctrl.signal
  // Claim global route ownership — _guard() will fail immediately if user navigates away
  window._ACTIVE_ROUTE = 'pipeline'
  function _guard() {
    return myId === _pipelineRenderId
        && !signal.aborted
        && window._ACTIVE_ROUTE === 'pipeline'
  }

  await Promise.all([loadUsers(), loadProjects()])
  if (!_guard()) return  // navigated away during users/projects load

  // Re-fetch live content reference after await — pre-await ref may be detached
  var content = document.getElementById('content')
  if (!content || !content.isConnected) return

  const salesManagers = users.filter(u => u.role === 'sales_manager')

  content.innerHTML = `
    <div class="card">
      <div class="sm-page-header" style="margin-bottom:12px;">
        <h2 class="sm-page-title">Pipeline View</h2>
      </div>

      <!-- Pipeline Filters -->
      <div class="pipeline-filter-shell">
        <div class="pipeline-filter-row pipeline-filter-row-enterprise">
          <div class="pipeline-filter-field pipeline-filter-search">
          <label class="sm-label">LEAD SEARCH</label>
          <input id="pipelineSearchInput" class="dash-filter-ctl" type="text" placeholder="Search by name, mobile, email, or project" value="${escape(_pipelineGlobalSearchQuery)}" />
          </div>
          <button id="pipelineSearchBtn" class="dash-refresh-btn pipeline-filter-btn">Search</button>
          <button id="pipelineSearchResetBtn" class="sm-btn sm-btn-secondary pipeline-filter-btn">Reset</button>
          ${user.role === 'superadmin' ? `
          <div class="pipeline-filter-field pipeline-filter-manager">
            <label class="sm-label">SALES MANAGER</label>
            <select id="pipelineManagerFilter" class="dash-filter-ctl">
              <option value="">All Sales Managers</option>
              ${salesManagers.map(m => `<option value="${m.id}">${escape(m.name)}</option>`).join('')}
            </select>
          </div>` : ''}
          <div class="pipeline-filter-field pipeline-filter-project">
          <label class="sm-label">PROJECT</label>
          <select id="pipelineProjectFilter" class="dash-filter-ctl">
            <option value="">All Projects</option>
            ${projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')}
          </select>
          </div>
          <button onclick="clearPipelineFilters()" class="sm-btn sm-btn-secondary pipeline-filter-btn">Clear</button>
        </div>
      </div>

      <p style="color:#94a3b8;font-size:12px;margin:0 0 16px;">Click any card to view lead details. On mobile/tablet, use the status selector to move leads between stages.</p>
      <div id="pipelineContainer" class="pipeline-grid"></div>
    </div>
  `

  var res
  try {
    res = await fetch(`${API_BASE}/pipeline/stages`, {
      headers: _apiAuthHeaders(),
      signal: signal
    })
  } catch (err) {
    if (err && err.name === 'AbortError') return  // navigated away
    return
  }
  if (!_guard()) return  // navigated away during fetch

  var data
  try { data = await res.json() } catch (_e) { return }
  if (!_guard()) return  // navigated away during JSON parse

  window._pipelineData = data.pipeline || {}

  document.getElementById('pipelineManagerFilter')?.addEventListener('change', applyPipelineFilters)
  document.getElementById('pipelineProjectFilter')?.addEventListener('change', applyPipelineFilters)
  document.getElementById('pipelineSearchBtn')?.addEventListener('click', function() {
    const el = document.getElementById('pipelineSearchInput')
    _pipelineGlobalSearchQuery = (el && el.value ? el.value : '').trim()
    applyPipelineFilters()
  })
  document.getElementById('pipelineSearchResetBtn')?.addEventListener('click', function() {
    _pipelineGlobalSearchQuery = ''
    const el = document.getElementById('pipelineSearchInput')
    if (el) el.value = ''
    applyPipelineFilters()
  })
  document.getElementById('pipelineSearchInput')?.addEventListener('keydown', function(e) {
    if (e.key !== 'Enter') return
    e.preventDefault()
    _pipelineGlobalSearchQuery = (e.target.value || '').trim()
    applyPipelineFilters()
  })
  document.getElementById('pipelineSearchInput')?.addEventListener('input', function(e) {
    if (_pipelineGlobalSearchTimer) clearTimeout(_pipelineGlobalSearchTimer)
    _pipelineGlobalSearchTimer = setTimeout(function() {
      _pipelineGlobalSearchQuery = (e.target.value || '').trim()
      applyPipelineFilters()
    }, 120)
  })

  applyPipelineFilters()
  window._pipelinePerfLastLoadMs = Math.round(((typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now()) - _loadStartMs)
}

function _filterPipelineLeadsForStage(stage) {
  const managerId  = document.getElementById('pipelineManagerFilter')?.value || ''
  const projectId  = document.getElementById('pipelineProjectFilter')?.value || ''
  const pipeline   = window._pipelineData || {}

  let managerUserIds = null
  if (managerId) {
    managerUserIds = new Set(users.filter(u => String(u.manager_id) === managerId).map(u => u.id))
    managerUserIds.add(parseInt(managerId))
  }

  const stageData = pipeline[stage] || { count: 0, leads: [] }
  let filtered = stageData.leads
  if (managerUserIds) filtered = filtered.filter(l => l.assigned_to && managerUserIds.has(l.assigned_to))
  if (projectId) filtered = filtered.filter(l => String(l.project_id) === projectId)

  const globalQ = (_pipelineGlobalSearchQuery || '').toLowerCase().trim()
  if (globalQ) {
    filtered = filtered.filter(function(l) {
      return [l.name || '', l.phone || '', l.email || '', l.project_name || '']
        .some(v => String(v).toLowerCase().includes(globalQ))
    })
  }

  return filtered
}

function applyPipelineFilters() {
  // Guard: bail if pipeline is not the active page (navigated away or never rendered)
  var container = document.getElementById('pipelineContainer')
  if (!container || !container.isConnected) return
  const canDrag = _pipelineSupportsDragAndDrop()

  container.innerHTML = PIPELINE_STAGES.map(stage => {
    let filtered = _filterPipelineLeadsForStage(stage)

    if (!_pipelineCardState[stage]) {
      _pipelineCardState[stage] = { page: 1, pageSize: 3 }
    }
    const state = _pipelineCardState[stage]

    const totalCount = filtered.length
    const pageSize = 3
    const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))
    if (state.page > totalPages) state.page = totalPages
    if (state.page < 1) state.page = 1
    const start = (state.page - 1) * pageSize
    const pageItems = filtered.slice(start, start + pageSize)

    const color   = getStatusColor(stage)
    const safeStage = stage.replace(/'/g, "\\'")
    const fromN = totalCount === 0 ? 0 : (start + 1)
    const toN = Math.min(start + pageSize, totalCount)
    const prevDisabled = state.page <= 1 ? 'disabled' : ''
    const nextDisabled = state.page >= totalPages ? 'disabled' : ''
    return `
      <div class="pipeline-col">
        <div class="pipeline-col-header pipeline-stage-head" style="border-bottom:3px solid ${color};background:${color}18;">
          <div class="pipeline-stage-name" style="color:${color};">${PIPELINE_STAGE_LABELS[stage].toUpperCase()}</div>
          <div class="pipeline-stage-count">${totalCount}</div>
          <div class="pipeline-stage-sub">${totalCount === 1 ? 'Lead' : 'Leads'}</div>
        </div>
        <div style="padding:8px 10px;border-bottom:1px solid #e2e8f0;background:#f8fafc;display:flex;justify-content:space-between;align-items:center;gap:8px;">
          <span style="font-size:11px;color:#64748b;">${fromN}-${toN} of ${totalCount}</span>
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:11px;color:#64748b;">Per page</span>
            <select disabled style="border:1px solid #d1d5db;border-radius:6px;padding:3px 6px;font-size:11px;background:#f8fafc;color:#64748b;cursor:default;">
              <option value="3" selected>3</option>
            </select>
          </div>
        </div>
        <div class="pipeline-col-body" data-stage="${safeStage}" ondragover="handlePipelineDragOver(event, '${safeStage}')" ondragleave="handlePipelineDragLeave(event, '${safeStage}')" ondrop="handlePipelineDrop(event, '${safeStage}')">
          ${pageItems.map(lead => {
            const mgrName = (() => {
              const u = users.find(u => u.id === lead.assigned_to)
              if (!u) return null
              const mgr = users.find(m => m.id === u.manager_id)
              return mgr ? mgr.name : null
            })()
            const safeLeadStage = stage.replace(/'/g, "\\'")
            const pendingClass = _pipelineMoveInFlight[lead.id] ? ' pipeline-card-pending' : ''
            return `
            <div class="pipeline-card${pendingClass}" style="border-left:3px solid ${color};" onclick="viewLeadDetails(${lead.id})" draggable="${canDrag ? 'true' : 'false'}" ondragstart="handlePipelineDragStart(event, ${lead.id}, '${safeLeadStage}')" ondragend="handlePipelineDragEnd(event)">
              <div class="pipeline-card-topline">
                <span class="pipeline-card-name">${escape(lead.name)}</span>
                <span class="pipeline-card-status-chip" style="background:${color}1a;color:${color};border-color:${color}55;" onclick="event.stopPropagation()">
                  <select class="pipeline-card-status-select" data-lead-id="${lead.id}" data-current-stage="${stage}" onclick="event.stopPropagation()" style="color:${color};">
                    ${PIPELINE_STAGES.map(function (st) {
                      return `<option value="${st}" ${st === stage ? 'selected' : ''}>${PIPELINE_STAGE_LABELS[st]}</option>`
                    }).join('')}
                  </select>
                </span>
              </div>
              <div class="pipeline-card-meta">${escape(lead.phone || '-')}</div>
              <div class="pipeline-card-meta">${escape(lead.project_name || 'No Project')} · ${escape(mgrName || 'Unassigned')}</div>
              <div class="pipeline-card-actions" onclick="event.stopPropagation()">
                <button class="pipeline-card-action-btn" title="Call" onclick='_abStartCallFlow(${lead.id}, ${JSON.stringify(lead.phone || '')}, ${JSON.stringify(lead.name || 'Lead')}); event.stopPropagation();'>📞</button>
                <button class="pipeline-card-action-btn" title="Callback" onclick="openLeadCallbackScheduler(${lead.id}); event.stopPropagation();">📅</button>
                <button class="pipeline-card-action-btn" title="Notes" onclick="openLeadInlineNoteEditor(${lead.id}); event.stopPropagation();">📝</button>
                <button class="pipeline-card-action-btn" title="Open Lead" onclick="viewLeadDetails(${lead.id}); event.stopPropagation();">↗</button>
              </div>
            </div>`
          }).join('')}
          ${totalCount === 0 ? `<div class="pipeline-empty">No leads</div>` : ''}
          <div style="margin-top:auto;display:flex;justify-content:space-between;align-items:center;gap:8px;padding-top:6px;">
            <button ${prevDisabled} onclick="setPipelineCardPage('${safeStage}', ${state.page - 1})" style="border:1px solid #d1d5db;background:#fff;border-radius:6px;padding:3px 8px;font-size:11px;color:${state.page <= 1 ? '#cbd5e1' : '#374151'};cursor:${state.page <= 1 ? 'default' : 'pointer'};">Prev</button>
            <span style="font-size:11px;color:#64748b;">Page ${state.page}/${totalPages}</span>
            <button ${nextDisabled} onclick="setPipelineCardPage('${safeStage}', ${state.page + 1})" style="border:1px solid #d1d5db;background:#fff;border-radius:6px;padding:3px 8px;font-size:11px;color:${state.page >= totalPages ? '#cbd5e1' : '#374151'};cursor:${state.page >= totalPages ? 'default' : 'pointer'};">Next</button>
          </div>
        </div>
      </div>
    `
  }).join('')

  if (!canDrag) {
    var info = document.getElementById('pipelineDnDNotice')
    if (!info) {
      info = document.createElement('div')
      info.id = 'pipelineDnDNotice'
      info.style.cssText = 'margin-top:10px;font-size:11px;color:#94a3b8;'
      info.textContent = 'Drag-and-drop is optimized for desktop pointers. On tablet, use lead detail updates.'
      container.parentNode && container.parentNode.appendChild(info)
    }
  } else {
    var existing = document.getElementById('pipelineDnDNotice')
    if (existing) existing.remove()
  }

  var statusSelects = container.querySelectorAll('.pipeline-card-status-select')
  statusSelects.forEach(function (sel) {
    sel.addEventListener('change', async function (e) {
      var leadId = Number(sel.getAttribute('data-lead-id') || 0)
      var fromStage = String(sel.getAttribute('data-current-stage') || '').trim()
      var toStage = String(sel.value || '').trim()
      if (!leadId || !fromStage || !toStage || fromStage === toStage) return
      sel.disabled = true
      try {
        await _movePipelineLead(leadId, fromStage, toStage)
      } finally {
        sel.disabled = false
      }
      if (e && typeof e.stopPropagation === 'function') e.stopPropagation()
    })
    sel.addEventListener('click', function (e) {
      if (e && typeof e.stopPropagation === 'function') e.stopPropagation()
    })
  })
}

function setPipelineCardPage(stage, page) {
  if (!_pipelineCardState[stage]) _pipelineCardState[stage] = { page: 1, pageSize: 5 }
  _pipelineCardState[stage].page = Math.max(1, parseInt(page, 10) || 1)
  applyPipelineFilters()
}

function setPipelineCardPageSize(stage, pageSize) {
  if (!_pipelineCardState[stage]) _pipelineCardState[stage] = { page: 1, pageSize: 3 }
  _pipelineCardState[stage].pageSize = 3
  _pipelineCardState[stage].page = 1
  applyPipelineFilters()
}

function clearPipelineFilters() {
  const mf = document.getElementById('pipelineManagerFilter')
  const pf = document.getElementById('pipelineProjectFilter')
  const sf = document.getElementById('pipelineSearchInput')
  if (mf) mf.value = ''
  if (pf) pf.value = ''
  _pipelineGlobalSearchQuery = ''
  if (sf) sf.value = ''
  applyPipelineFilters()
}

function handlePipelineDragStart(event, leadId, fromStage) {
  if (!_pipelineSupportsDragAndDrop()) return
  if (_pipelineMoveInFlight[leadId]) {
    event.preventDefault()
    return
  }
  _pipelineDragState = { leadId: leadId, fromStage: fromStage }
  try {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', JSON.stringify(_pipelineDragState))
  } catch (_e) {}
  event.currentTarget.classList.add('pipeline-card-dragging')
}

function handlePipelineDragEnd(event) {
  if (event && event.currentTarget) event.currentTarget.classList.remove('pipeline-card-dragging')
  _pipelineDragState = null
  document.querySelectorAll('.pipeline-col-body.pipeline-drop-target').forEach(function(el) {
    el.classList.remove('pipeline-drop-target')
  })
}

function handlePipelineDragOver(event, toStage) {
  if (!_pipelineDragState || _pipelineDragState.fromStage === toStage) return
  event.preventDefault()
  event.currentTarget.classList.add('pipeline-drop-target')
}

function handlePipelineDragLeave(event, _toStage) {
  event.currentTarget.classList.remove('pipeline-drop-target')
}

async function handlePipelineDrop(event, toStage) {
  event.preventDefault()
  event.currentTarget.classList.remove('pipeline-drop-target')

  let payload = _pipelineDragState
  try {
    const raw = event.dataTransfer && event.dataTransfer.getData('text/plain')
    if (raw) payload = JSON.parse(raw)
  } catch (_e) {}
  if (!payload) return
  if (payload.fromStage === toStage) return
  await _movePipelineLead(payload.leadId, payload.fromStage, toStage)
}

function _findPipelineLead(stage, leadId) {
  const list = ((window._pipelineData || {})[stage] || {}).leads || []
  const index = list.findIndex(function(l) { return l.id === leadId })
  return { list: list, index: index }
}

async function _movePipelineLead(leadId, fromStage, toStage) {
  if (_pipelineMoveInFlight[leadId]) return
  _pipelineMoveInFlight[leadId] = true

  const fromRef = _findPipelineLead(fromStage, leadId)
  if (fromRef.index < 0) {
    delete _pipelineMoveInFlight[leadId]
    return
  }

  const lead = fromRef.list[fromRef.index]
  const originalStatus = lead.status
  fromRef.list.splice(fromRef.index, 1)
  lead.status = toStage
  const toRef = _findPipelineLead(toStage, leadId)
  toRef.list.unshift(lead)
  applyPipelineFilters()

  const moveStartMs = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now()
  try {
    const data = await _apiRequest(`/pipeline/leads/${leadId}/move`, {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ to_status: toStage }),
      retries: 0,
      timeoutMs: 12000,
    })

    const liveLead = data && data.lead ? data.lead : null
    if (liveLead && Array.isArray(leads)) {
      const idx = leads.findIndex(function(l) { return l.id === leadId })
      if (idx >= 0) {
        leads[idx].status = liveLead.status
        leads[idx].updated_at = liveLead.updated_at
      }
    }
    invalidateLeadsCache()
    window._pipelinePerfLastMoveMs = Math.round(((typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now()) - moveStartMs)
    showToast('Lead moved successfully.', 'success')
  } catch (err) {
    // Roll back optimistic move on any server error.
    const targetRef = _findPipelineLead(toStage, leadId)
    if (targetRef.index >= 0) targetRef.list.splice(targetRef.index, 1)
    lead.status = originalStatus
    const restoreRef = _findPipelineLead(fromStage, leadId)
    restoreRef.list.splice(Math.min(fromRef.index, restoreRef.list.length), 0, lead)
    applyPipelineFilters()
    showToast((err.payload && err.payload.error) || err.message || 'Failed to move lead.', 'error')
  } finally {
    delete _pipelineMoveInFlight[leadId]
    applyPipelineFilters()
  }
}

function openPipelineStage(stage, managerId = '', projectId = '') {
  const pipeline = window._pipelineData || {}
  const stageData = pipeline[stage] || { count: 0, leads: [] }
  const color = getStatusColor(stage)

  // Apply active filters from dropdowns (dropdown values take precedence over args)
  const activeMgr = document.getElementById('pipelineManagerFilter')?.value || managerId
  const activePrj = document.getElementById('pipelineProjectFilter')?.value || projectId

  let managerUserIds = null
  if (activeMgr) {
    managerUserIds = new Set(users.filter(u => String(u.manager_id) === activeMgr).map(u => u.id))
    managerUserIds.add(parseInt(activeMgr))
  }

  let leads = stageData.leads || []
  if (managerUserIds) leads = leads.filter(l => l.assigned_to && managerUserIds.has(l.assigned_to))
  if (activePrj)      leads = leads.filter(l => String(l.project_id) === activePrj)
  const globalQ = (_pipelineGlobalSearchQuery || '').toLowerCase().trim()
  if (globalQ) {
    leads = leads.filter(function(l) {
      return [l.name || '', l.phone || '', l.email || '', l.project_name || '']
        .some(v => String(v).toLowerCase().includes(globalQ))
    })
  }

  const leadsHtml = leads.length === 0
    ? `<div style="text-align:center;color:#94a3b8;padding:48px 0;font-size:14px;">No leads in this stage</div>`
    : leads.map(lead => {
        const assignedUser = users.find(u => u.id === lead.assigned_to)
        const mgrName = assignedUser ? users.find(m => m.id === assignedUser.manager_id)?.name : null
        return `
        <div class="pipeline-modal-row" onclick="closePipelineModal();viewLeadDetails(${lead.id})">
          <div class="pipeline-modal-avatar" style="background:${color}20;color:${color};">
            ${escape(lead.name.charAt(0).toUpperCase())}
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;color:#0f172a;font-size:14px;">${escape(lead.name)}</div>
            <div style="color:#64748b;font-size:12px;margin-top:2px;">${escape(lead.phone || '-')}${lead.email ? ' · ' + escape(lead.email) : ''}</div>
            ${lead.project_name ? `<div style="font-size:11px;color:#2563eb;margin-top:2px;">${escape(lead.project_name)}</div>` : ''}
          </div>
          <div style="text-align:right;flex-shrink:0;">
            <div style="font-size:12px;color:#475569;">${escape(lead.assigned_to_name || 'Unassigned')}</div>
            ${mgrName ? `<div style="font-size:11px;color:#7c3aed;margin-top:1px;">${escape(mgrName)}</div>` : ''}
            ${lead.budget_min || lead.budget_max ? `<div style="font-size:11px;color:#94a3b8;margin-top:2px;">${fmtBudget(lead.budget_min)} – ${fmtBudget(lead.budget_max)}</div>` : ''}
          </div>
        </div>`
      }).join('')

  const modal = document.createElement('div')
  modal.className = 'modal-overlay'
  modal.id = 'pipelineModal'
  modal.innerHTML = `
    <div class="modal-box" style="width:600px;padding:0;overflow:hidden;">
      <div style="background:${color}18;border-bottom:3px solid ${color};padding:20px 24px;display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div style="font-size:11px;font-weight:700;color:${color};letter-spacing:.8px;text-transform:uppercase;">Pipeline Stage</div>
          <div style="font-size:20px;font-weight:800;color:#0f172a;">${PIPELINE_STAGE_LABELS[stage]}</div>
          <div style="font-size:13px;color:#64748b;margin-top:2px;">${leads.length} lead${leads.length !== 1 ? 's' : ''}</div>
        </div>
        <button onclick="closePipelineModal()" class="modal-close" style="position:static;">✕</button>
      </div>
      <div style="max-height:480px;overflow-y:auto;">${leadsHtml}</div>
    </div>
  `
  modal.addEventListener('click', e => { if (e.target === modal) closePipelineModal() })
  document.body.appendChild(modal)
}

function closePipelineModal() {
  const m = document.getElementById('pipelineModal')
  if (m) m.remove()
}

