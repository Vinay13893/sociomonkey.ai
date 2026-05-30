// ── Pipeline lifecycle state ──────────────────────────────────────────────────────────
var _pipelineRenderId  = 0
var _pipelineAbortCtrl = null

async function renderPipeline() {
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
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin-bottom:16px;display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
        ${user.role === 'superadmin' ? `
        <div style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1;">
          <label class="sm-label">SALES MANAGER</label>
          <select id="pipelineManagerFilter" class="select" style="font-size:13px;">
            <option value="">All Sales Managers</option>
            ${salesManagers.map(m => `<option value="${m.id}">${escape(m.name)}</option>`).join('')}
          </select>
        </div>` : ''}
        <div style="display:flex;flex-direction:column;gap:4px;min-width:160px;flex:1;">
          <label class="sm-label">PROJECT</label>
          <select id="pipelineProjectFilter" class="select" style="font-size:13px;">
            <option value="">All Projects</option>
            ${projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')}
          </select>
        </div>
        <div style="display:flex;align-items:flex-end;">
          <button onclick="clearPipelineFilters()" class="sm-btn sm-btn-secondary">✕ Clear</button>
        </div>
      </div>

      <p style="color:#94a3b8;font-size:12px;margin:0 0 16px;">Click any status header to view all leads in that stage</p>
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

  applyPipelineFilters()
}

function applyPipelineFilters() {
  // Guard: bail if pipeline is not the active page (navigated away or never rendered)
  var container = document.getElementById('pipelineContainer')
  if (!container || !container.isConnected) return

  const managerId  = document.getElementById('pipelineManagerFilter')?.value || ''
  const projectId  = document.getElementById('pipelineProjectFilter')?.value || ''
  const pipeline   = window._pipelineData || {}

  // Build the set of user IDs under this manager (including manager themselves)
  let managerUserIds = null
  if (managerId) {
    managerUserIds = new Set(users.filter(u => String(u.manager_id) === managerId).map(u => u.id))
    managerUserIds.add(parseInt(managerId))
  }

  container.innerHTML = PIPELINE_STAGES.map(stage => {
    const stageData = pipeline[stage] || { count: 0, leads: [] }
    let filtered = stageData.leads
    if (managerUserIds) filtered = filtered.filter(l => l.assigned_to && managerUserIds.has(l.assigned_to))
    if (projectId)      filtered = filtered.filter(l => String(l.project_id) === projectId)

    const color   = getStatusColor(stage)
    const preview = filtered.slice(0, 5)
    const more    = filtered.length - preview.length
    const safeM   = managerId.replace(/'/g,"\'")
    const safeP   = projectId.replace(/'/g,"\'")
    return `
      <div class="pipeline-col">
        <div class="pipeline-col-header" style="border-bottom:3px solid ${color};background:${color}18;"
             onclick="openPipelineStage('${stage}','${safeM}','${safeP}')">
          <div style="font-size:11px;font-weight:700;color:${color};letter-spacing:.6px;">${PIPELINE_STAGE_LABELS[stage].toUpperCase()}</div>
          <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1.1;">${filtered.length}</div>
        </div>
        <div class="pipeline-col-body">
          ${preview.map(lead => {
            const mgrName = (() => {
              const u = users.find(u => u.id === lead.assigned_to)
              if (!u) return null
              const mgr = users.find(m => m.id === u.manager_id)
              return mgr ? mgr.name : null
            })()
            return `
            <div class="pipeline-card" style="border-left:3px solid ${color};" onclick="viewLeadDetails(${lead.id})">
              <div style="font-weight:600;font-size:12px;color:#0f172a;">${escape(lead.name)}</div>
              <div style="font-size:11px;color:#64748b;margin-top:2px;">${escape(lead.phone || '-')}</div>
              <div style="font-size:11px;color:#94a3b8;margin-top:3px;">${escape(lead.assigned_to_name || 'Unassigned')}${mgrName ? ` <span style="color:#2563eb;">· ${escape(mgrName)}</span>` : ''}</div>
            </div>`
          }).join('')}
          ${more > 0 ? `<div class="pipeline-more" onclick="openPipelineStage('${stage}','${safeM}','${safeP}')">+${more} more</div>` : ''}
          ${filtered.length === 0 ? `<div class="pipeline-empty">No leads</div>` : ''}
        </div>
      </div>
    `
  }).join('')
}

function clearPipelineFilters() {
  const mf = document.getElementById('pipelineManagerFilter')
  const pf = document.getElementById('pipelineProjectFilter')
  if (mf) mf.value = ''
  if (pf) pf.value = ''
  applyPipelineFilters()
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

