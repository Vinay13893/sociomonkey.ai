// ============================================================================
// LEAD RECYCLE QUEUE — Auto-Reshuffle Engine
// Managers can view stale leads and reshuffle them to fresh team members
// ============================================================================

var _recycleRenderId = 0
var _recycleRenderInFlight = false
var _recycleSelected = new Set()
var _rqSearchQuery = ''
var _rqPage = 1
var _rqPageSize = 25
var _rqLastLoadTotal = 0
var _rqStrategyHelpText = {
  intelligent: 'Best default. Avoids recently assigned users and rotates safely to reduce repeat follow-ups.',
  round_robin: 'Strict turn-by-turn distribution. Best when you want even assignment count regardless of workload.',
  least_loaded: 'Sends leads to users with fewer active leads first. Best when team workload is uneven.',
}

function _rqRenderShell(target, showHeader) {
  if (!target) return
  _recycleSelected = new Set()
  var _headerHTML = (showHeader !== false) ? `
      <div class="sm-page-header" style="margin-bottom:20px;">
        <div>
          <h2 class="sm-page-title">♻️ Lead Recycle Queue</h2>
          <p class="sm-small sm-text-muted" style="margin:4px 0 0;">Reshuffle stale leads to fresh team members, excluding previous assignees.</p>
        </div>
      </div>` : ''

  target.innerHTML = `
    <div style="max-width:1200px;margin:0 auto;padding:${showHeader !== false ? '20px 16px' : '0'} 60px;" id="recycleRoot">
      ${_headerHTML}
      <!-- Filters -->
      <div class="rq-filter-shell">
        <div class="rq-filter-row">
        <div class="rq-filter-field">
          <label class="sm-label" style="display:block;margin-bottom:5px;">STALE WINDOW</label>
          <select id="rqStaleMode" class="dash-filter-ctl">
            <option value="today">Today</option>
            <option value="yesterday" selected>Yesterday</option>
            <option value="custom">Custom Date Range</option>
          </select>
        </div>
        <div class="rq-filter-field">
          <label class="sm-label" style="display:block;margin-bottom:5px;">STATUS</label>
          <select id="rqStatus" class="dash-filter-ctl">
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="no_answer">No Answer</option>
            <option value="follow_up">Follow Up</option>
            <option value="callback_scheduled">Callback Scheduled</option>
            <option value="interested">Interested</option>
            <option value="site_visit_planned">Site Visit Planned</option>
            <option value="site_visit_done">Site Visit Done</option>
            <option value="negotiation">Negotiation</option>
            <option value="booking_done">Booking Done</option>
            <option value="not_interested">Not Interested</option>
            <option value="lost">Lost</option>
            <option value="junk">Junk</option>
          </select>
        </div>
        <div class="rq-filter-field" id="rqDateRangeAnchor"></div>
        <div class="rq-filter-field rq-filter-search">
          <label class="sm-label" style="display:block;">SEARCH</label>
          <input id="rqSearch" class="dash-filter-ctl" type="text" placeholder="Name, mobile, project, assigned user" value="${escape(_rqSearchQuery)}" />
        </div>
        <button onclick="_rqLoad()" class="button rq-filter-btn">Load Queue</button>
        </div>
        <div id="rqDateRangeRow" style="display:none;align-items:center;gap:10px;margin-top:10px;padding-top:10px;border-top:1px solid #e2e8f0;">
          <input id="rqDateFrom" type="hidden" />
          <input id="rqDateTo" type="hidden" />
          <button onclick="_rqLoad()" class="button secondary" style="height:34px;font-size:12px;padding:0 14px;white-space:nowrap;">Apply</button>
        </div>
      </div>

      <!-- Bulk action bar -->
      <div id="rqBulkBar" style="display:none;background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:12px 16px;margin-bottom:14px;">
        <div class="rq-bulk-main-row">
          <span id="rqSelCount" class="rq-bulk-count">0 selected</span>
          <div class="rq-bulk-strategy">
            <label class="sm-label" style="margin-right:6px;white-space:nowrap;">STRATEGY</label>
            <select id="rqStrategy" class="select" style="font-size:12px;">
              <option value="intelligent" selected>Intelligent (Cooldown)</option>
              <option value="round_robin">Round Robin</option>
              <option value="least_loaded">Least Loaded</option>
            </select>
          </div>
          <div class="rq-bulk-reason-wrap">
            <input id="rqReason" type="text" class="select" placeholder="Reason (optional)" style="font-size:12px;" />
          </div>
          <div class="rq-bulk-actions">
            <button onclick="_rqReshuffle()" class="button" style="font-size:13px;background:#0369a1;">♻️ Reshuffle Selected</button>
            <button onclick="_rqClearSelection()" style="background:none;border:1px solid #bae6fd;border-radius:6px;padding:6px 12px;color:#0369a1;cursor:pointer;font-size:12px;">✕ Clear</button>
          </div>
        </div>
        <div class="rq-bulk-help-row">
          <span class="rq-bulk-help-label">How this strategy works:</span>
          <span id="rqStrategyHelp" class="rq-bulk-help-text"></span>
        </div>
      </div>

      <!-- Lead list -->
      <div id="rqLeadList" style="display:flex;flex-direction:column;gap:10px;">
        <div style="text-align:center;padding:60px 20px;color:#9ca3af;">
          <div style="font-size:36px;margin-bottom:8px;">♻️</div>
          <p style="font-size:14px;">Click "Load Queue" to fetch stale leads.</p>
        </div>
      </div>
    </div>
  `

  // Wire change events
  const staleModeSel = document.getElementById('rqStaleMode')
  const dateFromInput = document.getElementById('rqDateFrom')
  const dateToInput = document.getElementById('rqDateTo')
  if (staleModeSel) {
    staleModeSel.addEventListener('change', function () {
      if (staleModeSel.value !== 'custom') _rqLoad()
    })
  }
  if (dateFromInput) dateFromInput.addEventListener('change', _rqLoad)
  if (dateToInput) dateToInput.addEventListener('change', _rqLoad)
  const statusEl = document.getElementById('rqStatus')
  if (statusEl) statusEl.addEventListener('change', _rqLoad)
  const strategySel = document.getElementById('rqStrategy')
  if (strategySel) {
    strategySel.addEventListener('change', _rqUpdateStrategyHelp)
  }
  _rqUpdateStrategyHelp()
  const searchInput = document.getElementById('rqSearch')
  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key !== 'Enter') return
      e.preventDefault()
      _rqApplySearch()
    })
  }

  // Auto-load
  _rqLoad()
}


async function renderRecycleQueue() {
  if (_recycleRenderInFlight) return
  _recycleRenderInFlight = true
  _recycleRenderId++
  window._ACTIVE_ROUTE = 'recycle_queue'
  const content = document.getElementById('content')
  if (!content) { _recycleRenderInFlight = false; return }
  _rqRenderShell(content, true)
  _recycleRenderInFlight = false
}

// ── Load recycle queue ────────────────────────────────────────────────────

async function _rqLoad() {
  const staleMode  = document.getElementById('rqStaleMode')?.value  || 'yesterday'
  const dateFrom   = document.getElementById('rqDateFrom')?.value || ''
  const dateTo     = document.getElementById('rqDateTo')?.value || ''
  const statusVal  = document.getElementById('rqStatus')?.value     || ''
  const searchVal  = (document.getElementById('rqSearch')?.value || _rqSearchQuery || '').trim()
  const listEl     = document.getElementById('rqLeadList')
  if (!listEl) return

  listEl.innerHTML = `<div style="text-align:center;padding:40px;color:#9ca3af;"><span style="animation:spin 1s linear infinite;display:inline-block;border:3px solid #e5e7eb;border-top-color:#6366f1;border-radius:50%;width:24px;height:24px;"></span></div>`
  _recycleSelected = new Set()
  _rqUpdateBulkBar()

  let data
  try {
    const params = new URLSearchParams()
    params.set('stale_mode', staleMode)
    if (staleMode === 'custom') {
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
    }
    if (statusVal) params.set('status', statusVal)
    if (searchVal) params.set('q', searchVal)
    params.set('page', String(_rqPage))
    params.set('page_size', String(_rqPageSize))

    const url = `${API_BASE}/leads/recycle-queue?${params.toString()}`
    const res = await fetch(url, { headers: _apiAuthHeaders() })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data = await res.json()
  } catch (err) {
    listEl.innerHTML = `<div style="text-align:center;padding:40px;color:#ef4444;">Failed to load recycle queue.</div>`
    return
  }

  const leads = data.leads || []
  const total = data.total || 0
  const page = data.page || _rqPage
  const totalPages = data.total_pages || 1
  _rqLastLoadTotal = total
  if (!leads.length) {
    listEl.innerHTML = `<div style="text-align:center;padding:60px 20px;color:#9ca3af;"><div style="font-size:36px;margin-bottom:8px;">✅</div><p>No stale leads found for the selected criteria.</p></div>`
    return
  }

  listEl.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:0 4px;margin-bottom:8px;">
      <span style="font-size:13px;font-weight:600;color:#475569;">Showing ${leads.length} of ${total} stale lead${total !== 1 ? 's' : ''}</span>
      <div style="display:flex;gap:8px;align-items:center;">
        <button onclick="_rqSelectAll()" style="font-size:12px;color:#6366f1;background:none;border:1px solid #c7d2fe;border-radius:6px;padding:4px 10px;cursor:pointer;">Select Page (${leads.length})</button>
        ${total > leads.length ? `<button onclick="_rqSelectAllPages()" id="rqSelectAllPagesBtn" style="font-size:12px;color:#059669;background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:4px 10px;cursor:pointer;font-weight:600;">Select All ${total} Leads</button>` : ''}
      </div>
    </div>
    ${leads.map((l, i) => _rqLeadRow(l, (_rqPage - 1) * _rqPageSize + i + 1)).join('')}
    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:12px 4px 0;margin-top:8px;border-top:1px solid #e2e8f0;">
      <span style="font-size:12px;color:#64748b;">Page ${page} of ${totalPages}</span>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:12px;color:#64748b;">Page size</span>
        <select onchange="_rqSetPageSize(this.value)" style="border:1px solid #cbd5e1;border-radius:6px;padding:3px 7px;font-size:12px;">
          ${[10,25,50,100].map(function(n){ return `<option value="${n}" ${_rqPageSize===n?'selected':''}>${n}</option>` }).join('')}
        </select>
      </div>
      <div style="display:flex;align-items:center;gap:6px;">
        <button onclick="_rqSetPage(${page - 1})" ${page <= 1 ? 'disabled' : ''} style="font-size:12px;padding:4px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:${page <= 1 ? '#cbd5e1' : '#334155'};cursor:${page <= 1 ? 'default' : 'pointer'};">Prev</button>
        <button onclick="_rqSetPage(${page + 1})" ${page >= totalPages ? 'disabled' : ''} style="font-size:12px;padding:4px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:${page >= totalPages ? '#cbd5e1' : '#334155'};cursor:${page >= totalPages ? 'default' : 'pointer'};">Next</button>
      </div>
    </div>
  `
}

function _rqApplySearch() {
  _rqSearchQuery = (document.getElementById('rqSearch')?.value || '').trim()
  _rqPage = 1
  _rqLoad()
}

function _rqSetPage(page) {
  _rqPage = Math.max(1, parseInt(page, 10) || 1)
  _rqLoad()
}

function _rqSetPageSize(size) {
  _rqPageSize = Math.max(1, parseInt(size, 10) || 25)
  _rqPage = 1
  _rqLoad()
}

// ── Lead row ──────────────────────────────────────────────────────────────

function _rqLeadRow(l, serialNum) {
  const sc = (typeof STATUS_COLORS !== 'undefined' ? STATUS_COLORS : {})[l.status] || { bg: '#f1f5f9', color: '#475569', label: l.status }
  const staleDate = l.updated_at ? new Date(l.updated_at).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' }) : '—'
  const prevCount = (l.previous_assignee_ids || []).length

  return `
    <div id="rqRow_${l.id}" style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;transition:background .15s;">
      <input type="checkbox" id="rqChk_${l.id}" onchange="_rqToggle(${l.id})" style="width:16px;height:16px;cursor:pointer;flex-shrink:0;" />
      <span style="font-size:11px;font-weight:700;color:#94a3b8;min-width:22px;text-align:right;flex-shrink:0;">${serialNum}</span>
      <div style="width:38px;height:38px;border-radius:50%;background:#6366f1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;flex-shrink:0;">
        ${escape((l.name||'?')[0]).toUpperCase()}
      </div>
      <div style="flex:1;min-width:0;">
        <div style="font-weight:600;font-size:13px;color:#0f172a;">${escape(l.name||'')}</div>
        <div style="font-size:11px;color:#64748b;">${l.phone||'—'} · ${l.source||'—'} · Last updated: ${staleDate}</div>
        ${l.assigned_to_name ? `<div style="font-size:11px;color:#94a3b8;margin-top:1px;">Currently: ${escape(l.assigned_to_name)}</div>` : ''}
      </div>
      <span style="background:${sc.bg};color:${sc.color};font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;flex-shrink:0;">${sc.label}</span>
      ${prevCount > 0 ? `<span style="background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;flex-shrink:0;" title="Previous assignees that will be excluded">🚫 ${prevCount} prev</span>` : ''}
      <button onclick="viewLeadDetails(${l.id})" style="font-size:11px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:5px 10px;color:#6366f1;cursor:pointer;font-weight:600;white-space:nowrap;flex-shrink:0;">Open</button>
      ${(l.phone || l.alternate_phone) ? `<button onclick='openWhatsAppModal(${l.id}, ${JSON.stringify(l.phone || '')}, ${JSON.stringify(l.alternate_phone || '')}, ${JSON.stringify(l.name || 'Lead')}, ${l.project_id || 'null'})' style="font-size:11px;background:#fff;border:1px solid #bbf7d0;border-radius:6px;padding:5px 10px;color:#15803d;cursor:pointer;font-weight:600;white-space:nowrap;flex-shrink:0;">💬 WA</button>` : ''}
    </div>`
}

// ── Selection helpers ─────────────────────────────────────────────────────

function _rqToggle(leadId) {
  const chk = document.getElementById(`rqChk_${leadId}`)
  const row = document.getElementById(`rqRow_${leadId}`)
  if (!chk) return
  if (chk.checked) {
    _recycleSelected.add(leadId)
    if (row) row.style.background = '#eff6ff'
  } else {
    _recycleSelected.delete(leadId)
    if (row) row.style.background = '#fff'
  }
  _rqUpdateBulkBar()
}

function _rqSelectAll() {
  document.querySelectorAll('[id^="rqChk_"]').forEach(chk => {
    const id = parseInt(chk.id.replace('rqChk_', ''), 10)
    chk.checked = true
    _recycleSelected.add(id)
    const row = document.getElementById(`rqRow_${id}`)
    if (row) row.style.background = '#eff6ff'
  })
  _rqUpdateBulkBar()
}

async function _rqSelectAllPages() {
  const btn = document.getElementById('rqSelectAllPagesBtn')
  if (btn) { btn.textContent = '⏳ Loading...'; btn.disabled = true }

  const staleMode = document.getElementById('rqStaleMode')?.value || 'yesterday'
  const dateFrom = document.getElementById('rqDateFrom')?.value || ''
  const dateTo = document.getElementById('rqDateTo')?.value || ''
  const statusVal = document.getElementById('rqStatus')?.value || ''
  const searchVal = (document.getElementById('rqSearch')?.value || '').trim()

  try {
    const params = new URLSearchParams()
    params.set('stale_mode', staleMode)
    if (staleMode === 'custom') {
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
    }
    if (statusVal) params.set('status', statusVal)
    if (searchVal) params.set('q', searchVal)
    params.set('page', '1')
    params.set('page_size', String(Math.min(_rqLastLoadTotal || 1000, 1000)))

    const url = `${API_BASE}/leads/recycle-queue?${params.toString()}`
    const res = await fetch(url, { headers: _apiAuthHeaders() })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()

    ;(data.leads || []).forEach(l => {
      _recycleSelected.add(l.id)
      const chk = document.getElementById(`rqChk_${l.id}`)
      if (chk) chk.checked = true
      const row = document.getElementById(`rqRow_${l.id}`)
      if (row) row.style.background = '#eff6ff'
    })
    _rqUpdateBulkBar()
    showToast(`${_recycleSelected.size} leads selected across all pages.`, 'success')
    if (btn) { btn.textContent = `✓ All ${_recycleSelected.size} Selected`; btn.disabled = true }
  } catch (err) {
    showToast('Failed to select all leads.', 'error')
    if (btn) { btn.textContent = `Select All ${_rqLastLoadTotal} Leads`; btn.disabled = false }
  }
}

function _rqClearSelection() {
  document.querySelectorAll('[id^="rqChk_"]').forEach(chk => {
    chk.checked = false
    const id = parseInt(chk.id.replace('rqChk_', ''), 10)
    const row = document.getElementById(`rqRow_${id}`)
    if (row) row.style.background = '#fff'
  })
  _recycleSelected = new Set()
  _rqUpdateBulkBar()
}

function _rqUpdateBulkBar() {
  const bar     = document.getElementById('rqBulkBar')
  const cntEl   = document.getElementById('rqSelCount')
  if (!bar) return
  const n = _recycleSelected.size
  bar.style.display = n > 0 ? 'block' : 'none'
  if (cntEl) cntEl.textContent = `${n} lead${n !== 1 ? 's' : ''} selected`
}

function _rqUpdateStrategyHelp() {
  const strategy = document.getElementById('rqStrategy')?.value || 'intelligent'
  const helpEl = document.getElementById('rqStrategyHelp')
  if (!helpEl) return
  helpEl.textContent = _rqStrategyHelpText[strategy] || _rqStrategyHelpText.intelligent
}

// ── Reshuffle ─────────────────────────────────────────────────────────────

async function _rqReshuffle() {
  if (!_recycleSelected.size) return
  const strategy = document.getElementById('rqStrategy')?.value || 'round_robin'
  const reason   = (document.getElementById('rqReason')?.value || '').trim() || 'Recycled via Recycle Queue'

  const btn = document.querySelector('#rqBulkBar button.button')
  if (btn) { btn.textContent = '⏳ Reshuffling...'; btn.disabled = true }

  // Split into batches of 50 so each batch runs synchronously on the server
  const BATCH = 50
  const allIds = [..._recycleSelected]
  const batches = []
  for (let i = 0; i < allIds.length; i += BATCH) batches.push(allIds.slice(i, i + BATCH))

  let totalReshuffled = 0
  const allAssignments = []

  for (let b = 0; b < batches.length; b++) {
    if (btn) btn.textContent = `⏳ Batch ${b + 1}/${batches.length}…`
    try {
      const res = await fetch(`${API_BASE}/leads/reshuffle`, {
        method: 'POST',
        headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
        body: JSON.stringify({ lead_ids: batches[b], strategy, reason }),
      })
      if (!res.ok) {
        const errData = await res.json()
        showToast(errData.error || 'Reshuffle failed.', 'error')
        if (btn) { btn.textContent = '♻️ Reshuffle Selected'; btn.disabled = false }
        return
      }
      let data = await res.json()
      // If queued (large batch), call process endpoint
      if (data.status === 'queued' && data.job && data.job.id) {
        const processRes = await fetch(`${API_BASE}/leads/reshuffle/jobs/${data.job.id}/process`, {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({}),
        })
        if (!processRes.ok) {
          showToast(`Batch ${b + 1} processing failed. Please try again.`, 'error')
          if (btn) { btn.textContent = '♻️ Reshuffle Selected'; btn.disabled = false }
          return
        }
        data = await processRes.json()
      }
      totalReshuffled += (data.reshuffled || 0)
      allAssignments.push(...(data.assignments || []))
    } catch {
      showToast('Network error during reshuffle.', 'error')
      if (btn) { btn.textContent = '♻️ Reshuffle Selected'; btn.disabled = false }
      return
    }
  }

  if (btn) { btn.textContent = '♻️ Reshuffle Selected'; btn.disabled = false }
  // Show results modal
  _rqShowResults({ reshuffled: totalReshuffled, assignments: allAssignments })
  _rqClearSelection()
  // Reload the queue after a short delay
  setTimeout(_rqLoad, 800)
}

function _rqShowResults(data) {
  const n    = data.reshuffled || 0
  const rows = (data.assignments || []).map(a => `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:#f8fafc;border-radius:6px;font-size:13px;">
      <span style="font-weight:600;flex:1;">${escape(a.lead_name||'')}</span>
      <span style="color:#64748b;">${escape(a.from_user_name||'Unassigned')}</span>
      <span style="color:#94a3b8;">→</span>
      <span style="color:#059669;font-weight:700;">${escape(a.to_user_name||'')}</span>
    </div>`).join('')

  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:540px;width:100%;max-height:80vh;overflow:auto;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
        <h3 style="margin:0;font-size:16px;font-weight:700;">♻️ Reshuffle Complete</h3>
        <button onclick="this.closest('.modal-overlay').remove()" style="background:none;border:none;font-size:18px;cursor:pointer;color:#94a3b8;">✕</button>
      </div>
      <p style="margin:0 0 14px;font-size:14px;color:#059669;font-weight:600;">${n} lead${n !== 1 ? 's' : ''} successfully reshuffled.</p>
      <div style="display:flex;flex-direction:column;gap:6px;max-height:320px;overflow-y:auto;">
        <div style="display:flex;gap:8px;padding:6px 10px;font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;">
          <span style="flex:1;">Lead</span><span>From</span><span style="width:16px;"></span><span>To</span>
        </div>
        ${rows || '<p style="color:#9ca3af;text-align:center;">No assignments were made.</p>'}
      </div>
      <button class="button" onclick="this.closest('.modal-overlay').remove()" style="margin-top:16px;width:100%;">Close</button>
    </div>`
  document.body.appendChild(overlay)
}
