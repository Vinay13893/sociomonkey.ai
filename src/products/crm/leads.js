var _leadsSearchQuery = ''
var _leadsAdvancedOpen = false

function _leadsResolveTimeRange(rangeKey) {
  var now = new Date()
  var today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  var start = null
  var end = null
  var key = String(rangeKey || '').trim()

  if (key === 'today') {
    start = new Date(today)
    end = new Date(today)
  } else if (key === 'yesterday') {
    start = new Date(today)
    start.setDate(start.getDate() - 1)
    end = new Date(start)
  } else if (key === 'last_7_days') {
    start = new Date(today)
    start.setDate(start.getDate() - 6)
    end = new Date(today)
  } else if (key === 'last_30_days') {
    start = new Date(today)
    start.setDate(start.getDate() - 29)
    end = new Date(today)
  } else if (key === 'this_month') {
    start = new Date(now.getFullYear(), now.getMonth(), 1)
    end = new Date(today)
  } else if (key === 'last_month') {
    start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    end = new Date(now.getFullYear(), now.getMonth(), 0)
  } else if (key === 'year_to_date') {
    start = new Date(now.getFullYear(), 0, 1)
    end = new Date(today)
  }

  return { start, end }
}

function _leadsFmtDateInput(d) {
  return d.toISOString().split('T')[0]
}

function _leadsFmtRangeText(fromYmd, toYmd) {
  if (!fromYmd && !toYmd) return ''
  function fmt(v) {
    var dt = new Date(v + 'T00:00:00')
    if (Number.isNaN(dt.getTime())) return v
    return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  }
  if (fromYmd && toYmd) return fmt(fromYmd) + ' → ' + fmt(toYmd)
  if (fromYmd) return 'From ' + fmt(fromYmd)
  return 'Until ' + fmt(toYmd)
}

function _leadsUpdateRangeDisplay() {
  var display = document.getElementById('filterTimeRangeDisplay')
  if (!display) return
  var from = document.getElementById('filterDateFrom')?.value || ''
  var to = document.getElementById('filterDateTo')?.value || ''
  var text = _leadsFmtRangeText(from, to)
  display.textContent = text
  display.style.display = text ? 'block' : 'none'
}

function _leadsSetAdvancedFiltersVisibility(open) {
  _leadsAdvancedOpen = !!open
  var panel = document.getElementById('leadsAdvancedFilters')
  var toggle = document.getElementById('toggleLeadsAdvancedBtn')
  if (panel) panel.style.display = _leadsAdvancedOpen ? 'grid' : 'none'
  if (toggle) toggle.innerHTML = _leadsAdvancedOpen ? 'Advanced Filters ▲' : 'Advanced Filters ▼'
  try { sessionStorage.setItem('leads_advanced_open', _leadsAdvancedOpen ? '1' : '0') } catch (_) {}
}

async function renderLeads() {
  var myId = (window._leadsRenderId = (window._leadsRenderId || 0) + 1)
  const content = document.getElementById('content')
  if (!content) return
  try {
    _leadsAdvancedOpen = sessionStorage.getItem('leads_advanced_open') === '1'
  } catch (_) {
    _leadsAdvancedOpen = false
  }
  content.innerHTML = `
    <div class="card leads-workbench">
      <div class="sm-page-header leads-header-row">
        <div>
          <h2 class="sm-page-title">Leads <span id="leadsHeaderCount" class="leads-header-count">(0)</span></h2>
        </div>
        <div class="leads-page-actions">
          <button class="sm-btn sm-btn-primary leads-action-btn leads-action-btn-primary" id="newLeadBtn"><span class="leads-action-icon">＋</span><span>New Lead</span></button>
          <button class="sm-btn sm-btn-secondary leads-action-btn" id="bulkUpdateLeadsBtn"><span class="leads-action-icon">✎</span><span>Update Existing</span></button>
          ${user.role !== 'team_member' ? `<button class="sm-btn sm-btn-secondary leads-action-btn" id="importLeadsBtn"><span class="leads-action-icon">⤴</span><span>Import</span></button>` : ''}
          ${user.role === 'superadmin' ? `<button class="sm-btn sm-btn-secondary leads-action-btn" id="exportLeadsBtn"><span class="leads-action-icon">⤓</span><span>Export</span></button>` : ''}
        </div>
      </div>

      <div class="leads-command-shell">
        <div class="leads-search-row">
          <div class="dash-filter-group leads-search-main leads-priority-primary">
            <label class="dash-filter-label">Search</label>
            <div class="leads-search-inline">
              <input id="leadsSearchInput" class="dash-filter-ctl" type="text" placeholder="Search by name, phone, email, project" value="${escape(_leadsSearchQuery)}" />
              <button id="leadsSearchBtn" class="dash-refresh-btn">Search</button>
              <button id="leadsSearchResetBtn" class="sm-btn sm-btn-secondary leads-reset-btn">Reset</button>
            </div>
            <div class="leads-filter-aux-row">
              <div id="leadsQuickFilters" class="leads-quick-strip">
                <button class="sm-btn sm-btn-secondary leads-quick-chip" data-quick-status="">All</button>
                <button class="sm-btn sm-btn-secondary leads-quick-chip" data-quick-status="new">New</button>
                <button class="sm-btn sm-btn-secondary leads-quick-chip" data-quick-status="no_answer">No Answer</button>
                <button class="sm-btn sm-btn-secondary leads-quick-chip" data-quick-status="follow_up">Follow Up</button>
                <button class="sm-btn sm-btn-secondary leads-quick-chip" data-quick-status="callback_scheduled">Callback</button>
                <button class="sm-btn sm-btn-secondary leads-quick-chip" data-quick-status="interested">Interested</button>
                <button class="sm-btn sm-btn-secondary leads-quick-chip" data-quick-status="negotiation">Negotiation</button>
              </div>
              <div class="dash-filter-group" style="min-width:170px;">
                <label class="dash-filter-label">Quick Sort</label>
                <select id="quickSortOrder" class="dash-filter-ctl">
                  <option value="new_old">New → Old</option>
                  <option value="old_new">Old → New</option>
                </select>
              </div>
              <div class="leads-advanced-toggle-row leads-priority-secondary">
                <button type="button" id="toggleLeadsAdvancedBtn" class="sm-btn sm-btn-secondary leads-advanced-toggle-btn">Advanced Filters ▼</button>
              </div>
            </div>
          </div>
        </div>

        <div id="leadsAdvancedFilters" class="leads-advanced-filters" style="display:${_leadsAdvancedOpen ? 'grid' : 'none'};">
          <div class="dash-filter-group">
            <label class="dash-filter-label">Status</label>
            <select id="filterStatus" class="dash-filter-ctl">
              <option value="">All Statuses</option>
              <option value="new">New</option>
              <option value="no_answer">No Answer</option>
              <option value="follow_up">Follow Up</option>
              <option value="callback_scheduled">Callback Scheduled</option>
              <option value="interested">Interested</option>
              <option value="site_visit_planned">Site Visit Planned</option>
              <option value="site_visit_done">Site Visit Done</option>
              <option value="negotiation">Negotiation</option>
              <option value="booking_done">Closed</option>
              <option value="not_interested">Not Interested</option>
              <option value="lost">Lost</option>
              <option value="junk">Junk</option>
            </select>
          </div>
          <div class="dash-filter-group">
            <label class="dash-filter-label">Project</label>
            <select id="filterProject" class="dash-filter-ctl"><option value="">All Projects</option></select>
          </div>
          <div class="dash-filter-group">
            <label class="dash-filter-label">Manager</label>
            <select id="filterTeamMember" class="dash-filter-ctl">
              <option value="">All Members</option>
              <option value="unassigned">Unassigned</option>
            </select>
          </div>
          ${user.role === 'superadmin' ? `
          <div class="dash-filter-group">
            <label class="dash-filter-label">Sales Manager</label>
            <select id="filterSalesManager" class="dash-filter-ctl"><option value="">All Managers</option></select>
          </div>` : ''}
          <div class="dash-filter-group">
            <label class="dash-filter-label">Source</label>
            <select id="filterSource" class="dash-filter-ctl">
              <option value="">All Sources</option>
              <option value="Website">Website</option>
              <option value="Referral">Referral</option>
              <option value="Walk-in">Walk-in</option>
              <option value="Meta">Meta</option>
              <option value="Google">Google</option>
              <option value="Email Campaign">Email Campaign</option>
              <option value="Direct">Direct</option>
              <option value="Other">Other</option>
              <option value="G1">G1</option>
              <option value="G2">G2</option>
              <option value="G3">G3</option>
              <option value="TP">TP</option>
            </select>
          </div>
          <div class="dash-filter-group"><label class="dash-filter-label">Lead Created From</label><input type="date" id="filterDateFrom" class="dash-filter-ctl" /></div>
          <div class="dash-filter-group"><label class="dash-filter-label">Lead Created To</label><input type="date" id="filterDateTo" class="dash-filter-ctl" /></div>
          <div class="dash-filter-group"><label class="dash-filter-label">Status Updated From</label><input type="date" id="filterUpdatedFrom" class="dash-filter-ctl" /></div>
          <div class="dash-filter-group"><label class="dash-filter-label">Status Updated To</label><input type="date" id="filterUpdatedTo" class="dash-filter-ctl" /></div>
          <div class="dash-filter-group">
            <label class="dash-filter-label">Time Range</label>
            <select id="filterTimeRange" class="dash-filter-ctl">
              <option value="">All Time</option>
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="last_7_days">Last 7 Days</option>
              <option value="last_30_days">Last 30 Days</option>
              <option value="this_month">This Month</option>
              <option value="last_month">Last Month</option>
              <option value="year_to_date">Year to Date</option>
              <option value="custom">Custom</option>
            </select>
            <div id="filterTimeRangeDisplay" style="display:none;font-size:11px;color:#475569;margin-top:5px;font-weight:600;"></div>
          </div>
        </div>
      </div>

      <div id="leadsContainer"><div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:#9ca3af;font-size:14px;"><span style="animation:spin 1s linear infinite;display:inline-block;border:3px solid #e5e7eb;border-top-color:#6366f1;border-radius:50%;width:28px;height:28px;margin-right:12px;"></span>Loading leads…</div></div>
    </div>
  `

  document.getElementById('newLeadBtn').addEventListener('click', openLeadForm)
  document.getElementById('leadsSearchBtn').addEventListener('click', function() {
    const el = document.getElementById('leadsSearchInput')
    _leadsSearchQuery = (el && el.value ? el.value : '').trim()
    filterAndRenderLeads()
  })
  document.getElementById('leadsSearchResetBtn').addEventListener('click', function() {
    clearLeadsFilters()
  })
  document.getElementById('leadsSearchInput').addEventListener('keydown', function(e) {
    if (e.key !== 'Enter') return
    e.preventDefault()
    _leadsSearchQuery = (e.target.value || '').trim()
    filterAndRenderLeads()
  })
  document.getElementById('filterStatus').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterProject').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterSource').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterTeamMember').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterDateFrom').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterDateTo').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterUpdatedFrom').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterUpdatedTo').addEventListener('change', filterAndRenderLeads)
  document.getElementById('quickSortOrder').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterTimeRange').addEventListener('change', e => {
    var key = e.target.value
    if (key === 'custom') {
      _leadsUpdateRangeDisplay()
      return
    }
    if (!key) {
      document.getElementById('filterDateFrom').value = ''
      document.getElementById('filterDateTo').value = ''
      _leadsUpdateRangeDisplay()
      filterAndRenderLeads()
      return
    }
    var resolved = _leadsResolveTimeRange(key)
    document.getElementById('filterDateFrom').value = resolved.start ? _leadsFmtDateInput(resolved.start) : ''
    document.getElementById('filterDateTo').value = resolved.end ? _leadsFmtDateInput(resolved.end) : ''
    _leadsUpdateRangeDisplay()
    filterAndRenderLeads()
  })
  document.getElementById('filterDateFrom').addEventListener('change', _leadsUpdateRangeDisplay)
  document.getElementById('filterDateTo').addEventListener('change', _leadsUpdateRangeDisplay)
  if (user.role === 'superadmin') {
    const smFilter = document.getElementById('filterSalesManager')
    if (smFilter) smFilter.addEventListener('change', () => {
      updateTeamMemberDropdown(smFilter.value)
      filterAndRenderLeads()
    })
  }
  var advToggle = document.getElementById('toggleLeadsAdvancedBtn')
  if (advToggle) advToggle.addEventListener('click', function () {
    _leadsSetAdvancedFiltersVisibility(!_leadsAdvancedOpen)
  })
  document.querySelectorAll('.leads-quick-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      var statusVal = chip.getAttribute('data-quick-status') || ''
      var statusSel = document.getElementById('filterStatus')
      if (statusSel) statusSel.value = statusVal
      filterAndRenderLeads()
    })
  })
  _leadsSetAdvancedFiltersVisibility(_leadsAdvancedOpen)
  if (user.role !== 'team_member') {
    document.getElementById('importLeadsBtn').addEventListener('click', openImportModal)
  }
  if (user.role === 'superadmin') {
    document.getElementById('exportLeadsBtn').addEventListener('click', quickExportLeads)
  }
  document.getElementById('bulkUpdateLeadsBtn').addEventListener('click', openBulkUpdateModal)

  await Promise.all([loadProjects(), loadUsers(), loadLeads()])
  _leadsUpdateRangeDisplay()

  const projectSelect = document.getElementById('filterProject')
  if (projectSelect) {
    projectSelect.innerHTML = '<option value="">All Projects</option>' +
      projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')
  }

  const teamSelect = document.getElementById('filterTeamMember')
  if (teamSelect) {
    const teamMembers = users.filter(u => u.role === 'team_member')
    teamSelect.innerHTML = '<option value="">All Members</option><option value="unassigned">Unassigned</option>' +
      teamMembers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
  }

  const smSelect = document.getElementById('filterSalesManager')
  if (smSelect) {
    const salesManagers = users.filter(u => u.role === 'sales_manager')
    smSelect.innerHTML = '<option value="">All Sales Managers</option>' +
      salesManagers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
  }

  function updateTeamMemberDropdown(managerId) {
    const teamSelect = document.getElementById('filterTeamMember')
    if (!teamSelect) return
    const allMembers = users.filter(u => u.role === 'team_member')
    const filtered = managerId
      ? allMembers.filter(u => String(u.manager_id) === String(managerId))
      : allMembers
    const prevVal = teamSelect.value
    teamSelect.innerHTML = '<option value="">All Members</option><option value="unassigned">Unassigned</option>' +
      filtered.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
    // restore previous selection if still valid
    if (prevVal && filtered.some(u => String(u.id) === String(prevVal))) {
      teamSelect.value = prevVal
    }
  }

  await filterAndRenderLeads()
}

function openLeadInlineNoteEditor(leadId) {
  const lead = (leads || []).find(function (x) { return x.id === leadId }) || {}
  const existing = (lead.latest_note || '').trim()
  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:520px;width:95%;">
      <h3 class="sm-section-heading" style="margin-bottom:10px;">Update Latest Note</h3>
      <div style="font-size:12px;color:#64748b;margin-bottom:10px;">${escape(lead.name || ('Lead #' + leadId))}</div>
      <textarea id="leadInlineNoteText" class="select" rows="5" style="width:100%;resize:vertical;font-size:13px;" placeholder="Write note update...">${escape(existing)}</textarea>
      <div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end;">
        <button class="button secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="button" onclick="saveLeadInlineNote(${leadId})">Save Note</button>
      </div>
    </div>
  `
  document.body.appendChild(overlay)
  const input = overlay.querySelector('#leadInlineNoteText')
  if (input) input.focus()
}

async function saveLeadInlineNote(leadId) {
  const input = document.getElementById('leadInlineNoteText')
  const noteText = (input && input.value ? input.value : '').trim()
  if (!noteText) {
    showToast('Please enter a note.', 'warning')
    return
  }
  try {
    await _apiRequest(`/leads/${leadId}/notes`, {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ note: noteText }),
      retries: 0,
    })
    const overlay = document.querySelector('.modal-overlay')
    if (overlay) overlay.remove()
    await loadLeads(true)
    await filterAndRenderLeads(false)
    showToast('Note updated.', 'success')
    if (await confirmDialog('Update Lead Status?', 'Yes', '#4f46e5')) {
      const statusSelect = document.getElementById('newStatus')
      if (statusSelect) {
        statusSelect.scrollIntoView({ behavior: 'smooth', block: 'center' })
        statusSelect.focus()
      }
    }
  } catch (err) {
    showToast((err.payload && err.payload.error) || err.message || 'Failed to update note.', 'error')
  }
}

function clearLeadsFilters() {
  _leadsSearchQuery = ''
  const searchInput = document.getElementById('leadsSearchInput')
  if (searchInput) searchInput.value = ''
  ;['filterStatus','filterProject','filterSource','filterTeamMember','filterSalesManager',
   'filterDateFrom','filterDateTo','filterUpdatedFrom','filterUpdatedTo','filterTimeRange','quickSortOrder'].forEach(id => {
    const el = document.getElementById(id)
    if (el) el.value = ''
  })
  var quickSort = document.getElementById('quickSortOrder')
  if (quickSort) quickSort.value = 'new_old'
  _leadsUpdateRangeDisplay()

  // If Sales Manager filter was used, restore full member list so advanced
  // filters are visually and functionally reset.
  const teamSelect = document.getElementById('filterTeamMember')
  if (teamSelect && Array.isArray(users)) {
    const teamMembers = users.filter(function (u) { return u.role === 'team_member' })
    teamSelect.innerHTML = '<option value="">All Members</option><option value="unassigned">Unassigned</option>' +
      teamMembers.map(function (u) { return `<option value="${u.id}">${escape(u.name)}</option>` }).join('')
  }

  _leadsSyncQuickFilterChips('')
  leadsPage = 1
  filterAndRenderLeads()
}

function goToLeadsPage(page) {
  leadsPage = parseInt(page)
  filterAndRenderLeads(false)
}

function setLeadsPageSize(size) {
  leadsPageSize = parseInt(size)
  leadsPage = 1
  filterAndRenderLeads(false)
}

function _leadHealthMeta(status) {
  var s = String(status || '').toLowerCase()
  if (s === 'site_visit_done' || s === 'negotiation') return { dot: '🔴', label: 'Hot' }
  if (s === 'interested' || s === 'site_visit_planned') return { dot: '🟡', label: 'Warm' }
  return null
}

function _leadStatusMeta(status) {
  var s = String(status || '').toLowerCase()
  var map = {
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
  return map[s] || { label: s.replace(/_/g, ' ') || 'Unknown', bg: '#f8fafc', color: '#334155', border: '#cbd5e1' }
}

function _formatCallbackCell(datetimeValue) {
  if (!datetimeValue) return 'No Callback'
  var d = new Date(datetimeValue)
  if (Number.isNaN(d.getTime())) return 'No Callback'
  var now = new Date()
  var startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  var startTomorrow = new Date(startToday)
  startTomorrow.setDate(startTomorrow.getDate() + 1)
  var timeText = d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit' })
  if (d >= startToday && d < startTomorrow) return 'Today ' + timeText
  var startAfterTomorrow = new Date(startTomorrow)
  startAfterTomorrow.setDate(startAfterTomorrow.getDate() + 1)
  if (d >= startTomorrow && d < startAfterTomorrow) return 'Tomorrow ' + timeText
  return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: 'numeric', minute: '2-digit' })
}

function _leadAgeOldLabel(createdAt) {
  var dt = createdAt ? new Date(createdAt) : null
  if (!dt || Number.isNaN(dt.getTime())) return 'Today'
  var ageMs = Date.now() - dt.getTime()
  var days = Math.max(0, Math.floor(ageMs / 86400000))
  if (days <= 0) return 'Today'
  return days + ' Day' + (days === 1 ? '' : 's') + ' Old'
}

function _sourceBadgeLabel(source) {
  var src = String(source || '').trim()
  if (!src) return '—'
  var map = {
    google: 'Google',
    website: 'Website',
    referral: 'Referral',
    walkin: 'Walk-in',
    'walk-in': 'Walk-in',
    emailcampaign: 'Email',
    'email campaign': 'Email',
    direct: 'Direct',
    other: 'Other',
    g1: 'G1',
    g2: 'G2',
    g3: 'G3',
    tp: 'TP',
    meta: 'Meta',
  }
  var norm = src.toLowerCase().replace(/\s+/g, '')
  return map[norm] || src
}

function _leadsSyncQuickFilterChips(statusFilter) {
  var target = String(statusFilter || '')
  var chips = document.querySelectorAll('.leads-quick-chip')
  chips.forEach(function (chip) {
    var chipStatus = String(chip.getAttribute('data-quick-status') || '')
    chip.classList.toggle('is-active', chipStatus === target)
  })
}

var _filterRenderId = 0
async function filterAndRenderLeads(resetPage = true) {
  var myId = ++_filterRenderId
  if (resetPage) leadsPage = 1
  await loadLeads()
  if (myId !== _filterRenderId) return  // a newer filter call superseded this one

  let filtered = leads
  const statusFilter       = document.getElementById('filterStatus')?.value
  const projectFilter      = document.getElementById('filterProject')?.value
  const sourceFilter       = document.getElementById('filterSource')?.value
  const teamMemberFilter   = document.getElementById('filterTeamMember')?.value
  const salesManagerFilter = document.getElementById('filterSalesManager')?.value
  const dateFrom           = document.getElementById('filterDateFrom')?.value
  const dateTo             = document.getElementById('filterDateTo')?.value
  const updatedFrom        = document.getElementById('filterUpdatedFrom')?.value
  const updatedTo          = document.getElementById('filterUpdatedTo')?.value
  const sortOrder          = document.getElementById('quickSortOrder')?.value || 'new_old'

  if (statusFilter)   filtered = filtered.filter(l => l.status === statusFilter)
  if (projectFilter)  filtered = filtered.filter(l => l.project_id === parseInt(projectFilter))
  if (sourceFilter)   filtered = filtered.filter(l => l.source === sourceFilter)
  if (teamMemberFilter === 'unassigned') {
    filtered = filtered.filter(l => !l.assigned_to)
  } else if (teamMemberFilter) {
    filtered = filtered.filter(l => l.assigned_to === parseInt(teamMemberFilter))
  }
  if (salesManagerFilter) {
    filtered = filtered.filter(l => l.sales_manager_id === parseInt(salesManagerFilter))
  }
  if (dateFrom) {
    const from = new Date(dateFrom)
    filtered = filtered.filter(l => new Date(l.created_at) >= from)
  }
  if (dateTo) {
    const to = new Date(dateTo); to.setHours(23,59,59,999)
    filtered = filtered.filter(l => new Date(l.created_at) <= to)
  }
  if (updatedFrom) {
    const from = new Date(updatedFrom)
    filtered = filtered.filter(l => new Date(l.updated_at) >= from)
  }
  if (updatedTo) {
    const to = new Date(updatedTo); to.setHours(23,59,59,999)
    filtered = filtered.filter(l => new Date(l.updated_at) <= to)
  }

  _leadsSyncQuickFilterChips(statusFilter)

  const projectMap = {}
  projects.forEach(p => { projectMap[p.id] = p.name })

  function projectMapById(projectId) {
    return projectMap[projectId] || ''
  }

  if (_leadsSearchQuery) {
    const q = _leadsSearchQuery.toLowerCase()
    filtered = filtered.filter(l => {
      const projectName = projectMapById(l.project_id)
      return [
        l.name || '',
        l.phone || '',
        l.email || '',
        projectName || '',
      ].some(v => String(v).toLowerCase().includes(q))
    })
  }

  filtered = filtered.slice().sort((a, b) => {
    const aTs = new Date(a.created_at || 0).getTime()
    const bTs = new Date(b.created_at || 0).getTime()
    return sortOrder === 'old_new' ? aTs - bTs : bTs - aTs
  })

  const container = document.getElementById('leadsContainer')
  if (!container) return

  // Keep only selections that are still visible
  const filteredIds = new Set(filtered.map(l => l.id))
  for (const id of selectedLeads) { if (!filteredIds.has(id)) selectedLeads.delete(id) }

  if (filtered.length === 0) {
    container.innerHTML = '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;text-align:center;"><div style="font-size:36px;margin-bottom:12px;">📋</div><div style="font-size:16px;font-weight:600;color:#374151;margin-bottom:6px;">No leads found</div><div style="font-size:13px;color:#6b7280;">Try adjusting your filters or add a new lead.</div></div>'
    return
  }

  // Pagination
  const totalLeads = filtered.length
  const totalPages = leadsPageSize === 0 ? 1 : Math.ceil(totalLeads / leadsPageSize)
  if (leadsPage > totalPages) leadsPage = totalPages
  if (leadsPage < 1) leadsPage = 1
  const pageStart = leadsPageSize === 0 ? 0 : (leadsPage - 1) * leadsPageSize
  const pageEnd   = leadsPageSize === 0 ? totalLeads : pageStart + leadsPageSize
  const paginated  = filtered.slice(pageStart, pageEnd)
  const showFrom   = totalLeads === 0 ? 0 : pageStart + 1
  const showTo     = Math.min(pageEnd, totalLeads)

  // Page number buttons (show up to 7 around current page)
  const pageButtons = (() => {
    if (totalPages <= 1) return ''
    const nums = []
    const delta = 3
    for (let p = 1; p <= totalPages; p++) {
      if (p === 1 || p === totalPages || (p >= leadsPage - delta && p <= leadsPage + delta)) nums.push(p)
      else if (nums[nums.length-1] !== '…') nums.push('…')
    }
    return nums.map(p => p === '…'
      ? `<span style="padding:0 4px;color:#94a3b8;font-size:13px;">…</span>`
      : `<button onclick="goToLeadsPage(${p})" style="min-width:32px;height:32px;border:1px solid ${p===leadsPage?'#2563eb':'#e2e8f0'};border-radius:6px;background:${p===leadsPage?'#2563eb':'#fff'};color:${p===leadsPage?'#fff':'#374151'};font-size:13px;font-weight:${p===leadsPage?'700':'400'};cursor:${p===leadsPage?'default':'pointer'};">${p}</button>`
    ).join('')
  })()

  const paginationBar = `
    <div class="leads-pagination-bar">
      <div class="leads-pagination-summary">
        Showing <strong>${showFrom}–${showTo}</strong> of <strong>${totalLeads}</strong> leads
      </div>
      <div class="leads-pagination-controls">
        <button onclick="goToLeadsPage(${leadsPage-1})" ${leadsPage<=1?'disabled':''}
          class="leads-page-btn" style="color:${leadsPage<=1?'#cbd5e1':'#374151'};cursor:${leadsPage<=1?'default':'pointer'};">Prev</button>
        ${pageButtons}
        <button onclick="goToLeadsPage(${leadsPage+1})" ${leadsPage>=totalPages?'disabled':''}
          class="leads-page-btn" style="color:${leadsPage>=totalPages?'#cbd5e1':'#374151'};cursor:${leadsPage>=totalPages?'default':'pointer'};">Next</button>
      </div>
      <div class="leads-pagination-size">
        <span>Rows per page:</span>
        <select onchange="setLeadsPageSize(this.value)" class="leads-page-size-select">
          ${[10,12,25,50,100].map(n => `<option value="${n}" ${leadsPageSize===n?'selected':''}>${n}</option>`).join('')}
          <option value="0" ${leadsPageSize===0?'selected':''}>All</option>
        </select>
      </div>
    </div>`

  const canAssign = user.role === 'superadmin' || user.role === 'sales_manager' || user.role === 'platform_owner'
  const canAssignManager = user.role === 'superadmin' || user.role === 'platform_owner'
  const canDeleteLead = user.role === 'superadmin' || user.role === 'platform_owner'
  const assignableManagers = users.filter(u => {
    if (user.role === 'superadmin' || user.role === 'platform_owner') return u.role === 'sales_manager'
    return false
  })
  const assignableMembers = (user.role === 'superadmin' || user.role === 'platform_owner')
    ? users.filter(u => u.role === 'team_member')
    : user.role === 'sales_manager'
      ? [{ id: user.id, name: `${user.name} (me)` }, ...users.filter(u => u.manager_id === user.id)]
      : []

  const VALID_STATUSES_LIST = ['new','no_answer','follow_up','callback_scheduled','interested','site_visit_planned','site_visit_done','negotiation','booking_done','not_interested','lost','junk']
  const STATUS_OPTIONS = [
    { value: 'new', label: 'New' },
    { value: 'interested', label: 'Interested' },
    { value: 'site_visit_planned', label: 'Site Visit Planned' },
    { value: 'site_visit_done', label: 'Site Visit Done' },
    { value: 'negotiation', label: 'Negotiation' },
    { value: 'follow_up', label: 'Follow Up' },
    { value: 'callback_scheduled', label: 'Callback Scheduled' },
    { value: 'no_answer', label: 'No Answer' },
    { value: 'not_interested', label: 'Not Interested' },
    { value: 'booking_done', label: 'Closed' },
    { value: 'lost', label: 'Lost' },
    { value: 'junk', label: 'Junk' },
  ]
  const allChecked = paginated.length > 0 && paginated.every(l => selectedLeads.has(l.id))
  const buildStatusControl = function (lead) {
    var meta = _leadStatusMeta(lead.status)
    return `<span class="lead-status-chip" style="background:${meta.bg};border-color:${meta.border};"><select class="lead-inline-status" data-lead-id="${lead.id}" style="color:${meta.color};">${STATUS_OPTIONS.map(function (opt) { return `<option value="${opt.value}" ${String(lead.status || '') === opt.value ? 'selected' : ''}>${opt.label}</option>` }).join('')}</select></span>`
  }

  container.innerHTML = `
    <div id="bulkBar" class="bulk-bar" style="display:${selectedLeads.size > 0 ? 'flex' : 'none'};align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px;">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <span id="bulkCount" class="bulk-count">${selectedLeads.size} lead${selectedLeads.size !== 1 ? 's' : ''} selected</span>
        <button onclick="clearLeadSelection()" class="sm-btn sm-btn-secondary" style="height:30px;padding:0 10px;font-size:12px;">Clear</button>
        <button onclick="bulkExportSelectedLeads()" class="sm-btn sm-btn-secondary" style="height:30px;padding:0 10px;font-size:12px;">Export</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <select id="bulkStatusSelect" class="dash-filter-ctl" style="min-width:160px;">
          <option value="">Change Status</option>
          ${VALID_STATUSES_LIST.map(s => `<option value="${s}">${s.replace(/_/g,' ')}</option>`).join('')}
        </select>
        <button class="sm-btn sm-btn-secondary" onclick="bulkUpdateStatus()" style="height:34px;">Apply</button>
        ${canAssignManager && assignableManagers.length ? `<select id="bulkAssignManagerSelect" class="dash-filter-ctl" style="min-width:170px;"><option value="">Assign Manager</option><option value="unassign">Unassign</option>${assignableManagers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')}</select><button class="sm-btn sm-btn-secondary" onclick="bulkAssignLeads('bulkAssignManagerSelect')" style="height:34px;">Assign</button>` : ''}
        ${canAssign && assignableMembers.length ? `<select id="bulkAssignMemberSelect" class="dash-filter-ctl" style="min-width:170px;"><option value="">Assign Member</option><option value="unassign">Unassign</option>${assignableMembers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')}</select><button class="sm-btn sm-btn-secondary" onclick="bulkAssignLeads('bulkAssignMemberSelect')" style="height:34px;">Assign</button>` : ''}
        ${canDeleteLead ? `<button class="sm-btn sm-btn-secondary" onclick="bulkDeleteLeads()" style="height:34px;color:#b91c1c;border-color:#fecaca;">Delete</button>` : ''}
      </div>
    </div>
    <div class="leads-table-wrap">
      <table class="table leads-table">
        <colgroup>
          <col style="width:36px;">
          <col style="width:190px;">
          <col style="width:110px;">
          <col style="width:86px;">
          <col style="width:120px;">
          <col style="width:150px;">
          <col style="width:120px;">
          <col style="width:210px;">
          <col style="width:170px;">
        </colgroup>
        <thead>
          <tr>
            <th style="width:36px;"><input type="checkbox" id="selectAllLeads" ${allChecked ? 'checked' : ''} onchange="toggleSelectAllLeads(this.checked)" style="cursor:pointer;width:16px;height:16px;"></th>
            <th class="ta-center">Name</th>
            <th class="ta-center">Phone</th>
            <th class="ta-center">Source</th>
            <th class="ta-center">Project</th>
            <th class="ta-center">Status</th>
            <th class="ta-center">Manager</th>
            <th class="ta-center leads-note-col">Latest Note</th>
            <th class="ta-center leads-actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${paginated.map(l => `
            <tr class="${selectedLeads.has(l.id) ? 'lead-row-selected' : ''}">
              <td data-label="Select"><input type="checkbox" class="lead-checkbox" data-id="${l.id}" ${selectedLeads.has(l.id) ? 'checked' : ''} onchange="toggleSelectLead(${l.id}, this.checked)" style="cursor:pointer;width:16px;height:16px;"></td>
              <td class="ta-center" data-label="Name">
                <button class="lead-name-link" onclick="viewLeadDetails(${l.id})"
                  title="Open lead details"
                  style="background:none;border:none;padding:0;font-size:12px;font-weight:700;color:#1e40af;cursor:pointer;text-decoration:none;transition:color .15s;display:block;margin:0 auto;"
                  onmouseover="this.style.color='#1d4ed8';this.style.textDecorationColor='#1d4ed8'"
                  onmouseout="this.style.color='#1e40af';this.style.textDecorationColor='rgba(30,64,175,.35)'"
                  >${escape(l.name)}</button>
                <span class="leads-name-sub">${_leadAgeOldLabel(l.created_at)}</span>
              </td>
              <td class="ta-center" data-label="Phone">
                <button class="leads-phone-link" onclick='_abStartCallFlow(${l.id}, ${JSON.stringify(l.phone || '')}, ${JSON.stringify(l.name || 'Lead')})' title="Call lead">${escape(l.phone || '—')}</button>
              </td>
              <td class="ta-center" data-label="Source"><span class="leads-source-badge">${escape(_sourceBadgeLabel(l.source))}</span></td>
              <td class="ta-center" data-label="Project">${escape(projectMap[l.project_id] || '-')}</td>
              <td class="ta-center" data-label="Status">${buildStatusControl(l)}</td>
              <td class="ta-center" data-label="Manager"><span class="leads-cell-text leads-cell-text-center">${escape(l.sales_manager_name || '—')}</span></td>
              <td class="ta-center leads-note-col" data-label="Latest Note">
                <div class="leads-note-cell">
                  ${l.latest_note
                    ? `<span title="${escape(l.latest_note)}" class="leads-note-preview">${escape(l.latest_note)}</span>`
                    : `<span class="leads-note-preview leads-note-empty">—</span>`}
                  <button onclick="openLeadInlineNoteEditor(${l.id})" class="leads-icon-action" title="Edit latest note">✎</button>
                </div>
              </td>
              <td class="ta-center leads-actions-cell" data-label="Actions">
                <div class="leads-row-actions">
                  <button class="sm-btn sm-btn-secondary leads-row-action-btn leads-row-icon-btn" onclick='_abStartCallFlow(${l.id}, ${JSON.stringify(l.phone || '')}, ${JSON.stringify(l.name || 'Lead')})' title="Call"><span class="leads-row-action-icon">📞</span></button>
                  <button class="sm-btn sm-btn-secondary leads-row-action-btn leads-row-icon-btn" onclick="openLeadCallbackScheduler(${l.id})" title="Callback Scheduler"><span class="leads-row-action-icon">📅</span></button>
                  <button class="sm-btn sm-btn-secondary leads-row-action-btn leads-row-icon-btn" onclick="openLeadInlineNoteEditor(${l.id})" title="Notes"><span class="leads-row-action-icon">📝</span></button>
                  <button class="sm-btn sm-btn-secondary leads-actions-toggle leads-row-action-btn leads-row-icon-btn leads-more-btn" data-lead-id="${l.id}" title="More"><span class="leads-row-action-icon">⋮</span></button>
                  <div class="leads-actions-menu" id="leadActionsMenu-${l.id}" style="display:none;position:absolute;z-index:10;background:#fff;border:1px solid #e2e8f0;border-radius:8px;box-shadow:0 10px 24px rgba(15,23,42,.12);padding:4px;right:0;top:32px;">
                    <button class="leads-menu-item" onclick="viewLeadDetails(${l.id})">Open Lead</button>
                    <button class="leads-menu-item" onclick="viewLeadDetails(${l.id})">View Activity</button>
                    ${(user.role === 'superadmin' || user.role === 'sales_manager' || user.role === 'platform_owner') ? `<button class="leads-menu-item" onclick="openLeadAssignModal(${l.id})">Reassign Lead</button>` : ''}
                    ${canDeleteLead ? `<button class="leads-menu-item" style="color:#b91c1c;" onclick="deleteLead(${l.id}, '${escape(l.name)}')">Delete Lead</button>` : ''}
                  </div>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    ${paginationBar}
  `

  var countEl = document.getElementById('leadsHeaderCount')
  if (countEl) countEl.textContent = `(${totalLeads})`

  var statusSelects = container.querySelectorAll('.lead-inline-status')
  statusSelects.forEach(function (sel) {
    sel.addEventListener('change', async function () {
      var leadId = Number(sel.getAttribute('data-lead-id') || 0)
      var nextStatus = String(sel.value || '').trim()
      if (!leadId || !nextStatus) return
      sel.disabled = true
      try {
        await _apiRequest(`/pipeline/leads/${leadId}/move`, {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ to_status: nextStatus }),
          retries: 0,
          timeoutMs: 20000,
        })
        await loadLeads(true)
        await filterAndRenderLeads(false)
        showToast('Lead status updated.', 'success')
      } catch (err) {
        showToast((err && err.message) || 'Failed to update status.', 'error')
        sel.disabled = false
      }
    })
  })

  var actionToggles = container.querySelectorAll('.leads-actions-toggle')
  actionToggles.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation()
      var leadId = btn.getAttribute('data-lead-id')
      var menu = document.getElementById('leadActionsMenu-' + leadId)
      if (!menu) return
      var wasOpen = menu.style.display === 'block'
      container.querySelectorAll('.leads-actions-menu').forEach(function (m) { m.style.display = 'none' })
      if (!wasOpen) {
        menu.style.display = 'block'
      }
    })
  })

  document.addEventListener('click', window.__closeLeadMenusHandler || (window.__closeLeadMenusHandler = function () {
    var menus = document.querySelectorAll('.leads-actions-menu')
    menus.forEach(function (m) { m.style.display = 'none' })
  }))

  // Cascade: bulk Assign Sales Manager → filter Assign Team Member
  const bulkMgrSel = document.getElementById('bulkAssignManagerSelect')
  const bulkMemSel = document.getElementById('bulkAssignMemberSelect')
  if (bulkMgrSel && bulkMemSel) {
    const allBulkMembers = users.filter(u => u.role === 'team_member')
    bulkMgrSel.addEventListener('change', () => {
      const mid = bulkMgrSel.value
      const filtered = mid
        ? allBulkMembers.filter(u => String(u.manager_id) === String(mid))
        : allBulkMembers
      bulkMemSel.innerHTML = '<option value="">— Select member —</option>' +
        filtered.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
    })
  }
}

function toggleSelectLead(id, checked) {
  if (checked) selectedLeads.add(id)
  else selectedLeads.delete(id)
  renderBulkBar()
  // sync select-all checkbox
  const allBox = document.getElementById('selectAllLeads')
  if (allBox) {
    const all = document.querySelectorAll('.lead-checkbox')
    allBox.checked = all.length > 0 && [...all].every(c => c.checked)
    allBox.indeterminate = !allBox.checked && selectedLeads.size > 0
  }
  // highlight row
  const cb = document.querySelector(`.lead-checkbox[data-id="${id}"]`)
  if (cb) cb.closest('tr').classList.toggle('lead-row-selected', checked)
}

function toggleSelectAllLeads(checked) {
  document.querySelectorAll('.lead-checkbox').forEach(cb => {
    const id = parseInt(cb.dataset.id)
    cb.checked = checked
    if (checked) selectedLeads.add(id)
    else selectedLeads.delete(id)
    cb.closest('tr').classList.toggle('lead-row-selected', checked)
  })
  renderBulkBar()
}

function renderBulkBar() {
  const bar = document.getElementById('bulkBar')
  if (!bar) return
  bar.style.display = selectedLeads.size > 0 ? 'flex' : 'none'
  const countEl = document.getElementById('bulkCount')
  if (countEl) countEl.textContent = `${selectedLeads.size} lead${selectedLeads.size !== 1 ? 's' : ''} selected`
}

function clearLeadSelection() {
  selectedLeads.clear()
  filterAndRenderLeads()
}

async function bulkUpdateStatus() {
  const newStatus = document.getElementById('bulkStatusSelect')?.value
  if (!newStatus) { showToast('Please select a status to apply.', 'warning'); return }
  if (selectedLeads.size === 0) { showToast('No leads selected.', 'warning'); return }
  try {
    const data = await _apiRequest('/leads/bulk-status', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ lead_ids: [...selectedLeads], status: newStatus }),
      retries: 0,
    })
    selectedLeads.clear()
    await filterAndRenderLeads()
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#10b981;font-weight:600;">✅ ${data.updated} lead${data.updated !== 1 ? 's' : ''} updated to "${newStatus.replace(/_/g,' ')}"</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
}

async function bulkUpdateSource() {
  const newSource = document.getElementById('bulkSourceSelect')?.value
  if (!newSource) { showToast('Please select a source to apply.', 'warning'); return }
  if (selectedLeads.size === 0) { showToast('No leads selected.', 'warning'); return }
  try {
    const data = await _apiRequest('/leads/bulk-source', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ lead_ids: [...selectedLeads], source: newSource }),
      retries: 0,
    })
    selectedLeads.clear()
    await filterAndRenderLeads()
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#10b981;font-weight:600;">✅ ${data.updated} lead${data.updated !== 1 ? 's' : ''} source updated to "${data.source}"</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) { showToast('Error: ' + err.message, 'error') }
}

async function bulkAssignLeads(selectId = 'bulkAssignMemberSelect') {
  const assignTo = document.getElementById(selectId)?.value
  if (!assignTo) { showToast('Please select a person to assign to.', 'warning'); return }
  if (selectedLeads.size === 0) { showToast('No leads selected.', 'warning'); return }
  const assignType = selectId === 'bulkAssignManagerSelect' ? 'manager' : 'member'
  const isUnassign = assignTo === 'unassign'
  const btn = document.querySelector('#bulkBar .button')
  if (btn) { btn.disabled = true; btn.textContent = 'Assigning…' }
  try {
    const data = await _apiRequest('/leads/bulk-assign', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ lead_ids: [...selectedLeads], assigned_to: isUnassign ? null : parseInt(assignTo), assign_type: assignType }),
      retries: 0,
    })
    selectedLeads.clear()
    await filterAndRenderLeads()
    // flash success
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#10b981;font-weight:600;">✅ ${data.updated} lead${data.updated !== 1 ? 's' : ''} assigned to ${escape(data.assigned_to_name)}</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) {
    showToast((err.payload && err.payload.error) || err.message, 'error')
    if (btn) { btn.disabled = false; btn.textContent = 'Assign' }
  }
}

async function deleteLead(leadId, leadName) {
  if (!await confirmDialog('Delete lead &quot;' + escape(leadName) + '&quot;? This cannot be undone.', 'Delete')) return
  try {
    await _apiRequest(`/leads/${leadId}`, {
      method: 'DELETE',
      headers: _apiAuthHeaders(),
      retries: 0,
    })
    selectedLeads.delete(leadId)
    await loadLeads(true)
    filterAndRenderLeads()
  } catch (err) { showToast((err.payload && err.payload.error) || err.message || 'Error deleting lead.', 'error') }
}

async function bulkDeleteLeads() {
  if (selectedLeads.size === 0) { showToast('No leads selected.', 'warning'); return }
  if (!await confirmDialog('Delete ' + selectedLeads.size + ' selected lead' + (selectedLeads.size !== 1 ? 's' : '') + '? This cannot be undone.', 'Delete')) return
  try {
    const data = await _apiRequest('/leads/bulk-delete', {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ lead_ids: [...selectedLeads] }),
      retries: 0,
    })
    selectedLeads.clear()
    await loadLeads(true)
    filterAndRenderLeads()
    const bar = document.getElementById('bulkBar')
    if (bar) {
      bar.style.display = 'flex'
      bar.innerHTML = `<span style="color:#ef4444;font-weight:600;">🗑 ${data.deleted} lead${data.deleted !== 1 ? 's' : ''} deleted</span>`
      setTimeout(() => filterAndRenderLeads(), 1800)
    }
  } catch (err) { showToast('Error: ' + err.message, 'error') }
}

async function bulkExportSelectedLeads() {
  if (selectedLeads.size === 0) {
    showToast('No leads selected.', 'warning')
    return
  }
  var ids = Array.from(selectedLeads)
  var selected = (leads || []).filter(function (l) { return ids.includes(l.id) })
  if (!selected.length) {
    showToast('No selected leads available to export.', 'warning')
    return
  }
  var rows = selected.map(function (l) {
    return {
      Name: l.name || '',
      Phone: l.phone || '',
      Email: l.email || '',
      Source: l.source || '',
      Status: l.status || '',
      Project: l.project_name || '',
      AssignedTo: l.assigned_to_name || '',
      SalesManager: l.sales_manager_name || '',
      Created: l.created_at || '',
    }
  })
  var csvHeader = Object.keys(rows[0]).join(',')
  var csvBody = rows.map(function (r) {
    return Object.keys(r).map(function (k) {
      var v = String(r[k] == null ? '' : r[k]).replace(/"/g, '""')
      return '"' + v + '"'
    }).join(',')
  }).join('\n')
  var blob = new Blob([csvHeader + '\n' + csvBody], { type: 'text/csv;charset=utf-8;' })
  var url = window.URL.createObjectURL(blob)
  var a = document.createElement('a')
  a.href = url
  a.download = 'leads_selected_' + Date.now() + '.csv'
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}

async function openLeadAssignModal(leadId) {
  var id = Number(leadId || 0)
  if (!id) return
  var assignable = (user.role === 'superadmin' || user.role === 'platform_owner')
    ? users.filter(function (u) { return u.role === 'team_member' })
    : users.filter(function (u) { return u.role === 'team_member' && (u.manager_id === user.id || u.id === user.id) })
  if (!assignable.length) {
    showToast('No assignable team members available.', 'warning')
    return
  }

  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:420px;width:95%;">
      <h3 class="sm-section-heading" style="margin-bottom:10px;">Assign Lead</h3>
      <select id="singleAssignSelect" class="select" style="width:100%;font-size:13px;">
        <option value="">Select member</option>
        ${assignable.map(function (u) { return `<option value="${u.id}">${escape(u.name)}</option>` }).join('')}
      </select>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px;">
        <button class="button secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="button" id="singleAssignSaveBtn">Assign</button>
      </div>
    </div>`
  document.body.appendChild(overlay)
  overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove() })
  var btn = overlay.querySelector('#singleAssignSaveBtn')
  if (btn) btn.addEventListener('click', async function () {
    var sel = overlay.querySelector('#singleAssignSelect')
    var assignTo = Number(sel && sel.value)
    if (!assignTo) {
      showToast('Select a member first.', 'warning')
      return
    }
    try {
      await _apiRequest(`/leads/${id}/assign`, {
        method: 'POST',
        headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
        body: JSON.stringify({ assigned_to: assignTo }),
        retries: 0,
      })
      overlay.remove()
      await loadLeads(true)
      await filterAndRenderLeads(false)
      showToast('Lead assigned.', 'success')
    } catch (err) {
      showToast((err.payload && err.payload.error) || err.message || 'Failed to assign lead.', 'error')
    }
  })
}

async function openLeadCallbackScheduler(leadId) {
  var id = Number(leadId || 0)
  if (!id) return
  var callbackPayload = await _apiRequest(`/leads/${id}/callbacks`, {
    headers: _apiAuthHeaders(),
    retries: 0,
  }).catch(function () { return { callbacks: [] } })
  var pending = (callbackPayload.callbacks || []).find(function (c) { return c.status === 'pending' }) || null
  var defaultValue = ''
  if (pending && pending.callback_datetime) {
    var d = new Date(pending.callback_datetime)
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
    defaultValue = d.toISOString().slice(0, 16)
  }

  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:460px;width:95%;">
      <h3 class="sm-section-heading" style="margin-bottom:10px;">${pending ? 'Reschedule Callback' : 'Schedule Callback'}</h3>
      <label class="sm-label" style="display:block;margin-bottom:6px;">Date & Time</label>
      <input id="leadCallbackDateTime" type="datetime-local" class="input" value="${defaultValue}" style="width:100%;" />
      <label class="sm-label" style="display:block;margin:10px 0 6px;">Note</label>
      <textarea id="leadCallbackNote" class="textarea" rows="3" style="width:100%;">${escape((pending && pending.notes) || '')}</textarea>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px;">
        <button class="button secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="button" id="leadCallbackSaveBtn">${pending ? 'Save Changes' : 'Schedule'}</button>
      </div>
    </div>`
  document.body.appendChild(overlay)
  overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove() })

  var saveBtn = overlay.querySelector('#leadCallbackSaveBtn')
  if (saveBtn) saveBtn.addEventListener('click', async function () {
    var dtValue = (overlay.querySelector('#leadCallbackDateTime') || {}).value || ''
    if (!dtValue) {
      showToast('Please select callback date and time.', 'warning')
      return
    }
    var note = ((overlay.querySelector('#leadCallbackNote') || {}).value || '').trim()
    var payload = { callback_datetime: new Date(dtValue).toISOString(), notes: note }
    try {
      if (pending) {
        await _apiRequest(`/leads/callbacks/${pending.id}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify(payload),
          retries: 0,
        })
      } else {
        await _apiRequest(`/leads/${id}/callbacks`, {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify(payload),
          retries: 0,
        })
      }
      overlay.remove()
      await loadLeads(true)
      await filterAndRenderLeads(false)
      showToast('Callback saved.', 'success')
    } catch (err) {
      showToast((err.payload && err.payload.error) || err.message || 'Failed to save callback.', 'error')
    }
  })
}

// ── Import modal ─────────────────────────────────────────────────────────────
function openImportModal() {
  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.id = 'importModal'
  overlay.innerHTML = `
    <div class="modal-box">
      <button class="modal-close" id="closeImportModal">&times;</button>
      <h3>📤 Import Leads from Excel</h3>
      <form id="importModalForm">
        <div style="margin-bottom:14px;">
          <label style="display:block;font-weight:600;margin-bottom:6px;font-size:14px;">Select File (.xlsx, .xls, .csv)</label>
          <input type="file" id="importModalFile" accept=".xlsx,.xls,.csv" required
            style="display:block;width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px;" />
        </div>
        <div style="display:flex;gap:8px;">
          <button type="submit" class="button" style="flex:1;">📤 Upload & Import</button>
          <button type="button" class="button secondary" id="downloadTplBtn" style="flex:1;">⬇️ Download Template</button>
        </div>
      </form>
      <div id="importModalResult" style="margin-top:16px;"></div>
    </div>
  `
  document.body.appendChild(overlay)

  document.getElementById('closeImportModal').addEventListener('click', () => overlay.remove())
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove() })
  document.getElementById('downloadTplBtn').addEventListener('click', downloadExcelTemplate)
  document.getElementById('importModalForm').addEventListener('submit', async e => {
    e.preventDefault()
    const file = document.getElementById('importModalFile').files[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    const resultDiv = document.getElementById('importModalResult')
    resultDiv.innerHTML = '<div style="color:#64748b;font-size:14px;">Uploading…</div>'
    try {
      const res = await fetch(`${API_BASE}/leads/import/excel`, {
        method: 'POST', headers: _apiAuthHeaders(), body: formData
      })
      const data = await res.json()
      if (!res.ok) {
        resultDiv.innerHTML = `<div style="background:#fee2e2;padding:12px;border-radius:6px;color:#991b1b;">❌ ${escape(data.error || 'Upload failed')}</div>`
        return
      }
      window._importReportB64 = data.report_b64 || null
      const dlBtn = data.report_b64
        ? `<button onclick="downloadImportReport()" style="margin-top:10px;padding:8px 16px;background:#1e3a5f;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">📥 Download Report (.xlsx)</button>`
        : ''
      resultDiv.innerHTML = `
        <div style="background:#f0fdf4;border:1px solid #86efac;padding:14px;border-radius:8px;color:#166534;">
          <strong>✅ Import complete</strong><br>
          <span>Imported: ${data.success} &nbsp;|&nbsp; Failed: ${data.failed} &nbsp;|&nbsp; Total rows: ${data.total}</span>
          ${data.errors?.length ? `<div style="margin-top:8px;font-size:13px;">${data.errors.slice(0,5).map(e=>`Row ${e.row}: ${escape(e.error)}`).join('<br>')}</div>` : ''}
          ${dlBtn}
        </div>
      `
      await filterAndRenderLeads()
    } catch (err) {
      resultDiv.innerHTML = `<div style="background:#fee2e2;padding:12px;border-radius:6px;color:#991b1b;">❌ ${escape(err.message)}</div>`
    }
  })
}

// ── Quick export (uses active filters) ───────────────────────────────────────
async function quickExportLeads() {
  const status    = document.getElementById('filterStatus')?.value
  const projectId = document.getElementById('filterProject')?.value
  const params = []
  if (status)    params.push(`status=${encodeURIComponent(status)}`)
  if (projectId) params.push(`project_id=${encodeURIComponent(projectId)}`)
  const query = params.length ? '?' + params.join('&') : ''
  try {
    const res = await fetch(`${API_BASE}/leads/export/excel${query}`, {
      headers: _apiAuthHeaders()
    })
    if (!res.ok) { showToast('Export failed. Please try again.', 'error'); return }
    const blob = await res.blob()
    const url  = window.URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url
    a.download = `leads_export_${Date.now()}.xlsx`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (err) { showToast('Export error: ' + err.message, 'error') }
}


// ── Bulk Update modal ─────────────────────────────────────────────────────────
function openBulkUpdateModal() {
  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.id = 'bulkUpdateModal'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:780px;width:95%;">
      <button class="modal-close" id="closeBulkUpdateModal">&times;</button>
      <h3 class="sm-section-heading" style="margin-bottom:4px;">✏️ Update Existing Leads</h3>
      <p style="font-size:13px;color:#64748b;margin-bottom:18px;">
        Export your leads, edit the spreadsheet, then upload it back to apply bulk changes.
      </p>

      <!-- Step 1: Download + Upload -->
      <div id="buStep1">
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:14px;margin-bottom:18px;font-size:13px;color:#1e40af;">
          <strong>How it works:</strong><br>
          1. Download the update template (your current leads pre-filled)<br>
          2. Edit: name, status, source, project, budget, assignee, notes, callbacks<br>
          3. Upload the edited file — preview changes before they're saved<br>
          <em style="color:#64748b;">Phone and lead_id columns cannot be changed.</em>
        </div>
        <div style="display:flex;gap:10px;margin-bottom:20px;">
          <button id="buDownloadTplBtn" class="button secondary" style="flex:1;">
            ⬇️ Download Update Template
          </button>
        </div>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin-bottom:18px;">
        <label style="display:block;font-weight:600;margin-bottom:6px;font-size:14px;">
          Upload Edited File (.xlsx, .csv)
        </label>
        <input type="file" id="buFileInput" accept=".xlsx,.xls,.csv"
          style="display:block;width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px;margin-bottom:14px;" />
        <button id="buPreviewBtn" class="button" style="width:100%;">
          🔍 Preview Changes
        </button>
        <div id="buStep1Error" style="margin-top:10px;"></div>
      </div>

      <!-- Step 2: Preview table (hidden initially) -->
      <div id="buStep2" style="display:none;">
        <div id="buSummaryBar" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;"></div>
        <div id="buPreviewTable" style="max-height:380px;overflow-y:auto;margin-bottom:16px;"></div>
        <div style="display:flex;gap:10px;">
          <button id="buBackBtn" class="button secondary" style="flex:1;">← Back</button>
          <button id="buApplyBtn" class="button" style="flex:1;background:#16a34a;border-color:#16a34a;">
            ✅ Apply Changes
          </button>
        </div>
      </div>

      <!-- Step 3: Result (hidden initially) -->
      <div id="buStep3" style="display:none;"></div>
    </div>
  `
  document.body.appendChild(overlay)

  // State
  let previewToken   = null
  let previewExpires = null  // Date object

  // Close handlers
  document.getElementById('closeBulkUpdateModal').addEventListener('click', () => overlay.remove())
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove() })

  // Download template
  document.getElementById('buDownloadTplBtn').addEventListener('click', async () => {
    const btn = document.getElementById('buDownloadTplBtn')
    btn.textContent = '⏳ Generating…'
    btn.disabled = true
    try {
      const res = await fetch(`${API_BASE}/leads/export/update-template`, {
        headers: _apiAuthHeaders()
      })
      if (!res.ok) { showToast('Export failed. Please try again.', 'error'); return }
      const blob = await res.blob()
      const url  = window.URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `leads_update_template_${Date.now()}.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      showToast('Download error: ' + err.message, 'error')
    } finally {
      btn.textContent = '⬇️ Download Update Template'
      btn.disabled    = false
    }
  })

  // Preview changes
  document.getElementById('buPreviewBtn').addEventListener('click', async () => {
    const file = document.getElementById('buFileInput').files[0]
    if (!file) {
      document.getElementById('buStep1Error').innerHTML =
        '<div style="background:#fee2e2;padding:10px;border-radius:6px;color:#991b1b;font-size:13px;">Please select a file first.</div>'
      return
    }
    const btn = document.getElementById('buPreviewBtn')
    btn.textContent = '⏳ Analysing…'
    btn.disabled    = true
    document.getElementById('buStep1Error').innerHTML = ''

    const formData = new FormData()
    formData.append('file', file)
    try {
      const res  = await fetch(`${API_BASE}/leads/bulk-update/preview`, {
        method: 'POST', headers: _apiAuthHeaders(), body: formData
      })
      const data = await res.json()
      if (!res.ok) {
        document.getElementById('buStep1Error').innerHTML =
          `<div style="background:#fee2e2;padding:10px;border-radius:6px;color:#991b1b;font-size:13px;">❌ ${escape(data.error || 'Preview failed')}</div>`
        return
      }

      previewToken   = data.preview_token
      previewExpires = new Date(Date.now() + (data.expires_in_seconds || 600) * 1000)

      _renderBulkPreview(data.rows || [], data.summary || {})
      document.getElementById('buStep1').style.display = 'none'
      document.getElementById('buStep2').style.display = 'block'

    } catch (err) {
      document.getElementById('buStep1Error').innerHTML =
        `<div style="background:#fee2e2;padding:10px;border-radius:6px;color:#991b1b;font-size:13px;">❌ ${escape(err.message)}</div>`
    } finally {
      btn.textContent = '🔍 Preview Changes'
      btn.disabled    = false
    }
  })

  function _renderBulkPreview(rows, summary) {
    // Summary bar
    const bar = document.getElementById('buSummaryBar')
    const chips = [
      { label: 'Total',   count: summary.total,   bg: '#f1f5f9', color: '#1e293b' },
      { label: 'Valid',   count: summary.valid,   bg: '#dcfce7', color: '#166534' },
      { label: 'Invalid', count: summary.invalid, bg: '#fee2e2', color: '#991b1b' },
      { label: 'Skipped', count: summary.skipped, bg: '#fef9c3', color: '#92400e' },
    ]
    bar.innerHTML = chips.map(c =>
      `<div style="background:${c.bg};color:${c.color};padding:6px 14px;border-radius:20px;font-size:13px;font-weight:600;">
        ${c.label}: ${c.count}
      </div>`
    ).join('')

    // Preview table
    const tbl = document.getElementById('buPreviewTable')
    if (!rows.length) {
      tbl.innerHTML = '<div style="color:#64748b;font-size:14px;padding:12px;">No rows to preview.</div>'
      return
    }

    const html = rows.map(r => {
      const rowStyle = r.valid
        ? 'border-left:3px solid #22c55e;'
        : r.errors && r.errors.length
          ? 'border-left:3px solid #ef4444;'
          : 'border-left:3px solid #eab308;'

      const changesHtml = Object.entries(r.field_updates || {})
        .filter(([k]) => !k.startsWith('_'))
        .map(([k, v]) =>
          `<span style="font-size:12px;background:#eff6ff;color:#1e40af;padding:2px 6px;border-radius:4px;margin:2px;display:inline-block;">
            <strong>${k}</strong>: ${escape(String(v.old ?? ''))} → ${escape(String(v.new ?? ''))}
          </span>`
        ).join('')
      const noteHtml = r.note_text
        ? `<span style="font-size:12px;background:#ecfdf5;color:#065f46;padding:2px 6px;border-radius:4px;margin:2px;display:inline-block;">+ note</span>`
        : ''
      const cbHtml = r.callback_dt
        ? `<span style="font-size:12px;background:#f0fdf4;color:#065f46;padding:2px 6px;border-radius:4px;margin:2px;display:inline-block;">+ callback ${r.callback_dt.slice(0, 10)}</span>`
        : ''

      const errorsHtml = (r.errors || []).map(e =>
        `<div style="font-size:12px;color:#991b1b;">⚠ ${escape(e)}</div>`
      ).join('')
      const warningsHtml = (r.warnings || []).map(w =>
        `<div style="font-size:12px;color:#92400e;">⚡ ${escape(w)}</div>`
      ).join('')

      return `
        <div style="padding:10px 14px;border-bottom:1px solid #f1f5f9;${rowStyle}background:#fff;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span style="font-size:13px;font-weight:600;color:#1e293b;">
              Row ${r.row} — ${escape(r.lead_name || '(unknown)')}
              <span style="font-size:11px;color:#94a3b8;font-weight:400;"> #${r.lead_id || '?'} · ${escape(r.phone || '')}</span>
            </span>
            ${r.valid
              ? '<span style="font-size:11px;background:#dcfce7;color:#166534;padding:2px 8px;border-radius:10px;">✓ will update</span>'
              : r.errors && r.errors.length
                ? '<span style="font-size:11px;background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:10px;">✕ error</span>'
                : '<span style="font-size:11px;background:#fef9c3;color:#92400e;padding:2px 8px;border-radius:10px;">— skip</span>'
            }
          </div>
          <div>${changesHtml}${noteHtml}${cbHtml}</div>
          ${errorsHtml}${warningsHtml}
        </div>`
    }).join('')

    tbl.innerHTML = `<div style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">${html}</div>`
  }

  // Back to step 1
  document.getElementById('buBackBtn').addEventListener('click', () => {
    document.getElementById('buStep2').style.display = 'none'
    document.getElementById('buStep1').style.display = 'block'
    previewToken = null
  })

  // Apply changes
  document.getElementById('buApplyBtn').addEventListener('click', async () => {
    if (!previewToken) { showToast('Preview expired — please re-upload', 'error'); return }
    if (previewExpires && new Date() > previewExpires) {
      showToast('Preview expired — please re-upload the file', 'error')
      document.getElementById('buStep2').style.display = 'none'
      document.getElementById('buStep1').style.display = 'block'
      previewToken = null
      return
    }

    const btn = document.getElementById('buApplyBtn')
    btn.textContent = '⏳ Applying…'
    btn.disabled    = true

    try {
      const res  = await fetch(`${API_BASE}/leads/bulk-update/apply`, {
        method:  'POST',
        headers: { ..._apiAuthHeaders(), 'Content-Type': 'application/json' },
        body:    JSON.stringify({ preview_token: previewToken }),
      })
      const data = await res.json()
      if (!res.ok) {
        showToast(data.error || 'Apply failed. Please try again.', 'error')
        btn.textContent = '✅ Apply Changes'
        btn.disabled    = false
        return
      }

      // Store report for download
      window._bulkUpdateReportB64 = data.report_b64 || null

      const dlBtn = data.report_b64
        ? `<button onclick="downloadBulkUpdateReport()" style="margin-top:12px;padding:9px 18px;background:#1e3a5f;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">📥 Download Report (.xlsx)</button>`
        : ''

      document.getElementById('buStep2').style.display = 'none'
      const step3 = document.getElementById('buStep3')
      step3.style.display = 'block'
      step3.innerHTML = `
        <div style="background:#f0fdf4;border:1px solid #86efac;padding:18px;border-radius:8px;color:#166534;">
          <strong style="font-size:16px;">✅ Bulk update complete</strong><br><br>
          <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:14px;">
            <span><strong>${data.updated}</strong> leads updated</span>
            <span><strong>${data.failed}</strong> failed</span>
            <span><strong>${data.skipped}</strong> skipped</span>
            <span style="color:#475569;">of ${data.total} total rows</span>
          </div>
          ${dlBtn}
        </div>
        <button onclick="document.getElementById('bulkUpdateModal')?.remove();filterAndRenderLeads()"
          style="margin-top:14px;width:100%;padding:10px;background:#1e3a5f;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;">
          Close & Refresh Leads
        </button>
      `
      await filterAndRenderLeads()
    } catch (err) {
      showToast('Apply error: ' + err.message, 'error')
      btn.textContent = '✅ Apply Changes'
      btn.disabled    = false
    }
  })
}

function downloadBulkUpdateReport() {
  if (!window._bulkUpdateReportB64) return
  const binary = atob(window._bulkUpdateReportB64)
  const bytes  = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  const blob = new Blob([bytes], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = window.URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href     = url
  a.download = `bulk_update_report_${Date.now()}.xlsx`
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}


async function viewLeadDetails(leadId) {
  const resolvedLeadId = Number(leadId)
  if (!Number.isFinite(resolvedLeadId) || resolvedLeadId <= 0) {
    showToast('Invalid lead selected.', 'error')
    return
  }
  leadId = resolvedLeadId
  selectedLeadId = leadId
  const originRoute = (window._ACTIVE_ROUTE === 'lead_details')
    ? (window._LEAD_DETAIL_ORIGIN || 'leads')
    : (window._ACTIVE_ROUTE || 'leads')
  window._LEAD_DETAIL_ORIGIN = originRoute
  window._ACTIVE_ROUTE = 'lead_details'

  async function _safeGet(path, fallback) {
    try {
      const data = await _apiRequest(path, {
        headers: _apiAuthHeaders(),
        retries: 0,
        timeoutMs: 20000,
      })
      return data
    } catch (_) {
      return fallback
    }
  }

  let lead = leads.find(l => Number(l.id) === leadId)
  if (!lead) {
    const payload = await _safeGet(`/leads/${leadId}`, {})
    if (payload && payload.lead) lead = payload.lead
  }
  if (!lead) {
    showToast('Lead details not found.', 'error')
    return
  }

  const content = document.getElementById('content')
  if (!content) return

  // Optimistic skeleton while data loads
  content.innerHTML = `
    <div style="padding:32px 24px;max-width:1100px;margin:0 auto;">
      <div style="height:32px;background:#f1f5f9;border-radius:8px;width:200px;margin-bottom:24px;animation:pulse 1.5s ease-in-out infinite;"></div>
      <div style="height:120px;background:#f1f5f9;border-radius:12px;margin-bottom:20px;animation:pulse 1.5s ease-in-out infinite;"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
        <div style="height:280px;background:#f1f5f9;border-radius:12px;animation:pulse 1.5s ease-in-out infinite;"></div>
        <div style="height:280px;background:#f1f5f9;border-radius:12px;animation:pulse 1.5s ease-in-out infinite;"></div>
      </div>
    </div>
  `

  const preloadTasks = []
  if (!Array.isArray(projects) || projects.length === 0) preloadTasks.push(loadProjects())
  if (!Array.isArray(users) || users.length === 0) preloadTasks.push(loadUsers())
  if (preloadTasks.length) await Promise.all(preloadTasks)

  const detailBundle = await _safeGet(`/leads/${leadId}/detail-bundle`, null)
  let notes = []
  let statusHistory = []
  let assignmentHistory = []
  let callbacks = []
  let callActivities = []

  if (detailBundle && typeof detailBundle === 'object') {
    if (detailBundle.lead) lead = detailBundle.lead
    notes = detailBundle.notes || []
    statusHistory = detailBundle.status_history || []
    assignmentHistory = detailBundle.assignment_history || []
    callbacks = detailBundle.callbacks || []
    callActivities = detailBundle.call_activities || []
  } else {
    const dataResults = await Promise.all([
      _safeGet(`/leads/${leadId}/notes`, {}),
      _safeGet(`/leads/${leadId}/status-history`, {}),
      _safeGet(`/leads/${leadId}/assignment-history`, {}),
      _safeGet(`/leads/${leadId}/callbacks`, {}),
      _safeGet(`/leads/${leadId}/activity-timeline`, {}),
    ])

    notes = dataResults[0].notes || []
    statusHistory = dataResults[1].status_history || []
    assignmentHistory = dataResults[2].assignment_history || []
    callbacks = dataResults[3].callbacks || []
    callActivities = dataResults[4].call_activities || []
  }

  // Re-read lead only when local object is visibly incomplete.
  var L = lead
  if (!L.status || !L.updated_at || (!L.project_id && !L.project_name)) {
    const leadPayload = await _safeGet(`/leads/${leadId}`, {})
    if (leadPayload && leadPayload.lead) L = leadPayload.lead
  }

  const projectMap = {}
  projects.forEach(p => { projectMap[p.id] = p.name })

  const STATUS_COLORS = {
    new:'#1d4ed8', no_answer:'#ea580c', follow_up:'#7c3aed',
    callback_scheduled:'#4338ca', interested:'#16a34a',
    site_visit_planned:'#0891b2', site_visit_done:'#0d9488',
    negotiation:'#ca8a04', booking_done:'#059669',
    not_interested:'#64748b', lost:'#dc2626', junk:'#374151',
    // legacy aliases
    attempted:'#ea580c', connected:'#7c3aed',
  }
  const sc = STATUS_COLORS[L.status] || '#64748b'

  const fmtDate  = d => d ? new Date(d).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric'}) : '—'
  const fmtDT    = d => d ? new Date(d).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}) : '—'
  const statusLabel = s => {
    const labels = {
      new:'New', no_answer:'No Answer', follow_up:'Follow Up',
      callback_scheduled:'Callback Scheduled', interested:'Interested',
      site_visit_planned:'Site Visit Planned', site_visit_done:'Site Visit Done',
      negotiation:'Negotiation', booking_done:'Booking Done',
      not_interested:'Not Interested', lost:'Lost', junk:'Junk',
      // legacy
      attempted:'No Answer', connected:'Follow Up',
    }
    return labels[s] || (s || '').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())
  }
  const budgetStr = L.budget_min ? (fmtBudget(L.budget_min) + (L.budget_max ? ' – ' + fmtBudget(L.budget_max) : '')) : '—'

  // Build timeline items (notes + status changes merged)
  const timelineItems = [
    ...notes.map(n => ({ type:'note', ts: new Date(n.created_at), data: n })),
    ...statusHistory.map(h => ({ type:'status', ts: new Date(h.changed_at), data: h })),
    ...assignmentHistory.map(a => ({ type:'assign', ts: new Date(a.assigned_at), data: a })),
    ...callActivities.map(a => ({ type:'activity', ts: new Date(a.created_at), data: a })),
  ].sort((a,b) => b.ts - a.ts)

  const upcomingCallbacks = callbacks.filter(c => c.status === 'pending')
    .sort((a,b) => new Date(a.callback_datetime) - new Date(b.callback_datetime))

  const assignableManagers = users.filter(u => u.role === 'sales_manager')
  const allMembers         = users.filter(u => u.role === 'team_member')
  const backLabelMap = {
    action_board: 'Back to Action Board',
    pipeline: 'Back to Pipeline',
    recycle_queue: 'Back to Recycle Queue',
    dashboard: 'Back to Dashboard',
    leads: 'Back to Leads',
  }
  const backLabel = backLabelMap[originRoute] || 'Back to Leads'

  content.innerHTML = `
    <div style="max-width:1100px;margin:0 auto;padding:20px 16px 48px;">

      <!-- STICKY HEADER BAR -->
      <div style="position:sticky;top:0;z-index:20;background:#f8fafc;border-bottom:1px solid #e2e8f0;padding:12px 0 12px;margin:0 0 24px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <button id="backToLeads"
          style="display:flex;align-items:center;gap:6px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 14px;font-size:13px;font-weight:600;color:#475569;cursor:pointer;transition:all .15s;"
          onmouseover="this.style.borderColor='#94a3b8';this.style.color='#1e293b'"
          onmouseout="this.style.borderColor='#e2e8f0';this.style.color='#475569'">
          ← ${backLabel}
        </button>
        <div style="flex:1;min-width:0;">
          <h1 class="sm-section-heading" style="margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escape(L.name)}</h1>
        </div>
        <span style="background:${sc};color:#fff;padding:5px 14px;border-radius:20px;font-size:12px;font-weight:700;letter-spacing:.04em;white-space:nowrap;">${statusLabel(L.status)}</span>
        <button id="editLeadBtn"
          style="background:#1e3a5f;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;">
          ✏️ Edit Lead
        </button>
        <button id="scheduleCallbackBtn"
          style="background:#0369a1;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;">
          📞 Schedule Callback
        </button>
      </div>

      <!-- LEAD HERO CARD -->
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:24px 28px;margin-bottom:20px;box-shadow:0 2px 8px rgba(2,6,23,.06);display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start;">
        <!-- Avatar + basics -->
        <div style="display:flex;align-items:center;gap:20px;flex-shrink:0;">
          <div style="width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,${sc},${sc}99);display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:800;color:#fff;flex-shrink:0;box-shadow:0 4px 12px ${sc}44;">
            ${escape(L.name).charAt(0).toUpperCase()}
          </div>
          <div>
            <div style="font-size:22px;font-weight:800;color:#0f172a;">${escape(L.name)}</div>
            <div style="font-size:13px;color:#64748b;margin-top:2px;">${escape(L.phone || '—')} ${L.alternate_phone ? '· Alt ' + escape(L.alternate_phone) : ''} ${L.email ? '· ' + escape(L.email) : ''}</div>
          </div>
        </div>
        <!-- Meta chips -->
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;flex:1;justify-content:flex-end;">
          ${[
            { label:'Source',        val: L.source || '—',                          icon:'📌' },
            { label:'Project',       val: projectMap[L.project_id] || '—',          icon:'🏢' },
            { label:'Budget',        val: budgetStr,                                 icon:'💰' },
            { label:'Assigned To',   val: L.assigned_to_name || 'Unassigned',       icon:'👤' },
            { label:'Sales Manager', val: L.sales_manager_name || '—',              icon:'🧑‍💼' },
            { label:'Created',       val: fmtDate(L.created_at),                    icon:'📅' },
            { label:'Last Updated',  val: fmtDate(L.updated_at),                    icon:'🔄' },
          ].map(c => `
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:8px 14px;min-width:110px;">
              <div style="font-size:10px;font-weight:700;color:#94a3b8;letter-spacing:.06em;text-transform:uppercase;">${c.icon} ${c.label}</div>
              <div style="font-size:13px;font-weight:600;color:#1e293b;margin-top:3px;white-space:nowrap;">${c.val}</div>
            </div>
          `).join('')}
          <!-- Upcoming callbacks chip -->
          ${upcomingCallbacks.length ? `
            <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:8px 14px;min-width:110px;">
              <div style="font-size:10px;font-weight:700;color:#3b82f6;letter-spacing:.06em;text-transform:uppercase;">🔔 Next Callback</div>
              <div style="font-size:12px;font-weight:700;color:#1e40af;margin-top:3px;">${fmtDT(upcomingCallbacks[0].callback_datetime)}</div>
            </div>
          ` : ''}
        </div>
      </div>

      <!-- MAIN GRID -->
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:20px;">

        <!-- SECTION 1: Customer Info + Actions -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(2,6,23,.05);">
          <div style="padding:14px 20px;border-bottom:1px solid #f1f5f9;background:#f8fafc;">
            <h3 class="sm-card-heading">👤 Customer Information</h3>
          </div>
          <div style="padding:16px 20px;display:flex;flex-direction:column;gap:10px;">
            ${[
              ['Full Name',     escape(L.name)],
              ['Phone',         escape(L.phone || '—')],
              ['Alternate Phone', escape(L.alternate_phone || '—')],
              ['Email',         L.email ? `<a href="mailto:${escape(L.email)}" style="color:#2563eb;">${escape(L.email)}</a>` : '—'],
              ['City / Area',   escape((L.city) || '—')],
              ['Budget',        budgetStr],
              ['Project',       escape(projectMap[L.project_id] || '—')],
              ['Source',        escape(L.source || '—')],
            ].map(([k,v]) => `
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid #f8fafc;">
                <span style="font-size:12px;font-weight:600;color:#94a3b8;flex-shrink:0;">${k}</span>
                <span style="font-size:13px;color:#1e293b;text-align:right;">${v}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- SECTION 2: Lead Journey / Quick Actions -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(2,6,23,.05);">
          <div style="padding:14px 20px;border-bottom:1px solid #f1f5f9;background:#f8fafc;">
            <h3 class="sm-card-heading">📈 Lead Journey & Actions</h3>
          </div>
          <div style="padding:16px 20px;display:flex;flex-direction:column;gap:14px;">

            ${user.role !== 'team_member' ? `
            <div>
              <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:6px;">Update Status</label>
              <form id="updateStatusForm" style="display:flex;gap:8px;">
                <select id="newStatus" class="select" style="flex:1;font-size:13px;">
                  ${['new','no_answer','follow_up','callback_scheduled','interested','site_visit_planned','site_visit_done','negotiation','booking_done','not_interested','lost','junk'].map(s=>
                    `<option value="${s}" ${L.status===s?'selected':''}>${statusLabel(s)}</option>`).join('')}
                </select>
                <button type="submit" class="button" style="font-size:12px;padding:7px 14px;white-space:nowrap;">Update</button>
              </form>
            </div>
            <div>
              <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:6px;">Update Project</label>
              <form id="updateProjectForm" style="display:flex;gap:8px;">
                <select id="newProject" class="select" style="flex:1;font-size:13px;">
                  <option value="">— No Project —</option>
                  ${projects.map(p=>`<option value="${p.id}" ${L.project_id===p.id?'selected':''}>${escape(p.name)}</option>`).join('')}
                </select>
                <button type="submit" class="button" style="font-size:12px;padding:7px 14px;white-space:nowrap;">Update</button>
              </form>
            </div>
            <div>
              <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:6px;">Update Source</label>
              <form id="updateSourceForm" style="display:flex;gap:8px;">
                <select id="newSource" class="select" style="flex:1;font-size:13px;">
                  <option value="">— Select Source —</option>
                  ${['Website','Referral','Walk-in','Meta','Google','Email Campaign','Direct','Other','G1','G2','G3','TP'].map(s=>
                    `<option value="${s}" ${L.source===s?'selected':''}>${s}</option>`).join('')}
                </select>
                <button type="submit" class="button" style="font-size:12px;padding:7px 14px;white-space:nowrap;">Update</button>
              </form>
            </div>` : ''}

            ${user.role === 'sales_manager' || user.role === 'superadmin' ? `
            <div>
              <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:6px;">Assign Lead</label>
              <form id="assignForm" style="display:flex;flex-direction:column;gap:8px;">
                ${user.role === 'superadmin' ? `
                <select id="assignToManager" class="select" style="font-size:13px;">
                  <option value="">— Filter by Sales Manager —</option>
                  ${assignableManagers.map(u=>`<option value="${u.id}">${escape(u.name)}</option>`).join('')}
                </select>` : ''}
                <div style="display:flex;gap:8px;">
                  <select id="assignTo" class="select" style="flex:1;font-size:13px;"></select>
                  <button type="submit" class="button" style="font-size:12px;padding:7px 14px;white-space:nowrap;">Assign</button>
                </div>
              </form>
            </div>` : ''}

          </div>
        </div>

        <!-- SECTION 3: Callbacks -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(2,6,23,.05);">
          <div style="padding:14px 20px;border-bottom:1px solid #f1f5f9;background:#f8fafc;display:flex;justify-content:space-between;align-items:center;">
            <h3 class="sm-card-heading">📞 Scheduled Callbacks</h3>
            <button id="addCallbackInline"
              style="background:#0369a1;color:#fff;border:none;border-radius:7px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;">
              + Schedule
            </button>
          </div>
          <div id="callbacksPanel" style="padding:16px 20px;max-height:340px;overflow-y:auto;">
            ${callbacks.length === 0
              ? `<div style="text-align:center;padding:24px 0;color:#94a3b8;font-size:13px;">No callbacks scheduled.<br><span style="font-size:12px;">Use "+ Schedule" to add one.</span></div>`
              : callbacks.map(cb => {
                  const isPast    = new Date(cb.callback_datetime) < new Date()
                  const isDone    = cb.status === 'completed'
                  const isMissed  = cb.status === 'missed' || (isPast && cb.status === 'pending')
                  const dotColor  = isDone ? '#10b981' : isMissed ? '#ef4444' : '#0369a1'
                  const badgeBg   = isDone ? '#f0fdf4' : isMissed ? '#fef2f2' : '#eff6ff'
                  const badgeTxt  = isDone ? '#065f46' : isMissed ? '#991b1b' : '#1e40af'
                  const statusTxt = isDone ? 'Completed' : isMissed ? 'Missed' : 'Upcoming'
                  return `
                  <div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #f1f5f9;align-items:flex-start;">
                    <div style="width:10px;height:10px;border-radius:50%;background:${dotColor};flex-shrink:0;margin-top:4px;"></div>
                    <div style="flex:1;">
                      <div style="font-size:13px;font-weight:600;color:#0f172a;">${fmtDT(cb.callback_datetime)}</div>
                      ${cb.notes ? `<div style="font-size:12px;color:#64748b;margin-top:2px;">${escape(cb.notes)}</div>` : ''}
                      <div style="display:flex;gap:6px;align-items:center;margin-top:5px;">
                        <span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:12px;background:${badgeBg};color:${badgeTxt};">${statusTxt}</span>
                        ${!isDone && !isMissed ? `<button onclick="markCallbackDone(${cb.id},${leadId})" style="font-size:11px;padding:2px 8px;border:1px solid #86efac;border-radius:12px;background:#f0fdf4;color:#065f46;cursor:pointer;">✓ Done</button>` : ''}
                        <button onclick="deleteCallback(${cb.id},${leadId})" style="font-size:11px;padding:2px 8px;border:1px solid #fca5a5;border-radius:12px;background:#fef2f2;color:#991b1b;cursor:pointer;">Cancel</button>
                      </div>
                    </div>
                  </div>`
              }).join('')
            }
          </div>
        </div>

        <!-- SECTION 4: Status History -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(2,6,23,.05);">
          <div style="padding:14px 20px;border-bottom:1px solid #f1f5f9;background:#f8fafc;">
            <h3 class="sm-card-heading">🔄 Status History</h3>
          </div>
          <div style="padding:16px 20px;max-height:300px;overflow-y:auto;">
            ${statusHistory.length === 0
              ? `<div style="color:#94a3b8;font-size:13px;text-align:center;padding:20px 0;">No status changes yet.</div>`
              : statusHistory.map((h,i) => `
                <div style="display:flex;gap:12px;padding:8px 0;${i < statusHistory.length-1 ? 'border-bottom:1px solid #f8fafc;' : ''}">
                  <div style="width:8px;height:8px;border-radius:50%;background:${STATUS_COLORS[h.new_status]||'#94a3b8'};flex-shrink:0;margin-top:5px;"></div>
                  <div>
                    <div style="font-size:13px;font-weight:600;color:#1e293b;">
                      <span style="color:#94a3b8;">${statusLabel(h.old_status)}</span>
                      <span style="color:#cbd5e1;"> → </span>
                      <span style="color:${STATUS_COLORS[h.new_status]||'#64748b'};">${statusLabel(h.new_status)}</span>
                    </div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:2px;">${escape(h.changed_by_name||'Unknown')} · ${fmtDate(h.changed_at)}</div>
                  </div>
                </div>
              `).join('')}
          </div>
        </div>

        <!-- SECTION 5: Assignment History -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(2,6,23,.05);">
          <div style="padding:14px 20px;border-bottom:1px solid #f1f5f9;background:#f8fafc;">
            <h3 class="sm-card-heading">👥 Assignment History</h3>
          </div>
          <div style="padding:16px 20px;max-height:300px;overflow-y:auto;">
            ${assignmentHistory.length === 0
              ? `<div style="color:#94a3b8;font-size:13px;text-align:center;padding:20px 0;">No assignments yet.</div>`
              : assignmentHistory.map((a,i) => `
                <div style="display:flex;gap:12px;padding:8px 0;${i < assignmentHistory.length-1 ? 'border-bottom:1px solid #f8fafc;' : ''}">
                  <div style="width:8px;height:8px;border-radius:50%;background:#8b5cf6;flex-shrink:0;margin-top:5px;"></div>
                  <div>
                    <div style="font-size:13px;font-weight:600;color:#1e293b;">
                      <span style="color:#94a3b8;">${escape(a.assigned_from_name||'Unassigned')}</span>
                      <span style="color:#cbd5e1;"> → </span>
                      <span>${escape(a.assigned_to_name||'Unassigned')}</span>
                    </div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:2px;">${escape(a.assigned_by_name||'?')} · ${fmtDate(a.assigned_at)}</div>
                    ${a.reason ? `<div style="font-size:11px;color:#64748b;margin-top:2px;font-style:italic;">${escape(a.reason)}</div>` : ''}
                  </div>
                </div>
              `).join('')}
          </div>
        </div>

      </div><!-- end main grid -->

      <!-- TIMELINE SECTION (full width) -->
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(2,6,23,.05);margin-top:20px;">
        <div style="padding:14px 20px;border-bottom:1px solid #f1f5f9;background:#f8fafc;display:flex;justify-content:space-between;align-items:center;">
          <h3 class="sm-card-heading" style="margin-bottom:12px;">🕒 Notes & Activity Timeline</h3>
        </div>
        <div style="padding:10px 20px 0;color:#64748b;font-size:13px;line-height:1.5;">
          ${L.phone ? `<strong style="color:#334155;">Primary:</strong> ${escape(L.phone)}` : ''}${L.alternate_phone ? `${L.phone ? ' · ' : ''}<strong style="color:#334155;">Alternate:</strong> ${escape(L.alternate_phone)}` : ''}
        </div>
        <div style="padding:20px 28px;display:grid;grid-template-columns:1fr 340px;gap:28px;flex-wrap:wrap;" id="timelineGrid">

          <!-- Timeline -->
          <div style="position:relative;">
            <!-- Add note form -->
            <form id="addNoteForm" style="display:flex;gap:10px;margin-bottom:24px;align-items:flex-end;">
              <textarea id="noteText" class="input"
                style="flex:1;height:72px;resize:vertical;font-size:13px;border-radius:10px;"
                placeholder="Add a note, call log, or follow-up update…"></textarea>
              <button type="submit" class="button" style="padding:9px 18px;font-size:13px;white-space:nowrap;border-radius:10px;align-self:flex-end;">
                Add Note
              </button>
            </form>
            <!-- Timeline list -->
            <div style="border-left:2px solid #e2e8f0;padding-left:20px;display:flex;flex-direction:column;gap:0;">
              ${timelineItems.length === 0
                ? `<div style="color:#94a3b8;font-size:13px;padding:16px 0;">No activity yet.</div>`
                : timelineItems.map(item => {
                    if (item.type === 'note') {
                      const n = item.data
                      return `
                      <div style="position:relative;padding:0 0 20px;">
                        <div style="position:absolute;left:-25px;top:4px;width:10px;height:10px;border-radius:50%;background:#6366f1;border:2px solid #fff;box-shadow:0 0 0 2px #6366f1;"></div>
                        <div style="background:#fafafa;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;">
                          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                            <span style="font-size:12px;font-weight:700;color:#6366f1;">📝 Note</span>
                            <span style="font-size:11px;color:#94a3b8;">${escape(n.created_by_name||'?')} · ${fmtDT(n.created_at)}</span>
                          </div>
                          <p style="margin:0;font-size:13px;color:#1e293b;line-height:1.6;">${escape(n.note)}</p>
                        </div>
                      </div>`
                    }
                    if (item.type === 'status') {
                      const h = item.data
                      return `
                      <div style="position:relative;padding:0 0 20px;">
                        <div style="position:absolute;left:-25px;top:4px;width:10px;height:10px;border-radius:50%;background:${STATUS_COLORS[h.new_status]||'#94a3b8'};border:2px solid #fff;box-shadow:0 0 0 2px ${STATUS_COLORS[h.new_status]||'#94a3b8'};"></div>
                        <div style="background:#fafafa;border:1px solid #e2e8f0;border-radius:10px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;">
                          <span style="font-size:13px;color:#475569;">Status changed: <strong style="color:${STATUS_COLORS[h.new_status]||'#374151'};">${statusLabel(h.new_status)}</strong></span>
                          <span style="font-size:11px;color:#94a3b8;white-space:nowrap;">${escape(h.changed_by_name||'?')} · ${fmtDate(h.changed_at)}</span>
                        </div>
                      </div>`
                    }
                    if (item.type === 'assign') {
                      const a = item.data
                      return `
                      <div style="position:relative;padding:0 0 20px;">
                        <div style="position:absolute;left:-25px;top:4px;width:10px;height:10px;border-radius:50%;background:#8b5cf6;border:2px solid #fff;box-shadow:0 0 0 2px #8b5cf6;"></div>
                        <div style="background:#fafafa;border:1px solid #e2e8f0;border-radius:10px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;">
                          <span style="font-size:13px;color:#475569;">Assigned to <strong>${escape(a.assigned_to_name||'?')}</strong></span>
                          <span style="font-size:11px;color:#94a3b8;white-space:nowrap;">${fmtDate(a.assigned_at)}</span>
                        </div>
                      </div>`
                    }
                    if (item.type === 'activity') {
                      const a = item.data
                      const outcome = a.new_value && a.new_value.outcome_label ? a.new_value.outcome_label : (a.action || '').replace(/_/g, ' ')
                      const isAccidental = a.new_value && a.new_value.outcome === 'accidental_click'
                      const activityColor = isAccidental ? '#64748b' : '#0ea5e9'
                      return `
                      <div style="position:relative;padding:0 0 20px;">
                        <div style="position:absolute;left:-25px;top:4px;width:10px;height:10px;border-radius:50%;background:${activityColor};border:2px solid #fff;box-shadow:0 0 0 2px ${activityColor};"></div>
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;">
                          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;gap:10px;">
                            <span style="font-size:12px;font-weight:700;color:${activityColor};">📞 ${escape(outcome)}</span>
                            <span style="font-size:11px;color:#94a3b8;white-space:nowrap;">${escape(a.user_name || '?')} · ${fmtDT(a.created_at)}</span>
                          </div>
                          <p style="margin:0;font-size:13px;color:#1e293b;line-height:1.6;">${escape(a.description || 'Call activity logged.')}</p>
                        </div>
                      </div>`
                    }
                    return ''
                  }).join('')
              }
            </div>
          </div>

          <!-- Upcoming callbacks sidebar -->
          <div>
            <div style="font-size:12px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;margin-bottom:12px;">🔔 Upcoming Callbacks</div>
            ${upcomingCallbacks.length === 0
              ? `<div style="font-size:13px;color:#94a3b8;padding:16px 0;">None scheduled.</div>`
              : upcomingCallbacks.map(cb => `
                <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:12px 14px;margin-bottom:10px;">
                  <div style="font-size:13px;font-weight:700;color:#1e40af;">${fmtDT(cb.callback_datetime)}</div>
                  ${cb.notes ? `<div style="font-size:12px;color:#1e40af;opacity:.8;margin-top:3px;">${escape(cb.notes)}</div>` : ''}
                  <div style="font-size:11px;color:#64748b;margin-top:4px;">For: ${escape(cb.assigned_user_name||'—')}</div>
                </div>
              `).join('')}
          </div>

        </div>
      </div>

    </div>
  `

  // ── Event handlers ──────────────────────────────────────────────────────

  document.getElementById('backToLeads').addEventListener('click', function () {
    const origin = (window._LEAD_DETAIL_ORIGIN || 'leads')
    if (origin === 'action_board' && typeof renderActionBoard === 'function') {
      renderActionBoard(window._abDateFrom || '', window._abDateTo || '', window._abRange || 'today')
      return
    }
    if (origin === 'pipeline' && typeof renderPipeline === 'function') {
      renderPipeline()
      return
    }
    if (origin === 'recycle_queue' && typeof renderRecycleQueue === 'function') {
      renderRecycleQueue()
      return
    }
    if (origin === 'dashboard' && typeof renderDashboard === 'function') {
      renderDashboard()
      return
    }
    renderLeads()
  })

  document.getElementById('editLeadBtn').addEventListener('click', () => openLeadEditForm(L))

  document.getElementById('scheduleCallbackBtn').addEventListener('click', () => openCallbackModal(leadId, { leadPhone: L.phone || '', leadAlternatePhone: L.alternate_phone || '', leadName: L.name || 'Lead' }))
  document.getElementById('addCallbackInline').addEventListener('click', () => openCallbackModal(leadId, { leadPhone: L.phone || '', leadAlternatePhone: L.alternate_phone || '', leadName: L.name || 'Lead' }))

  // Update status
  const updateStatusForm = document.getElementById('updateStatusForm')
  if (updateStatusForm) {
    updateStatusForm.addEventListener('submit', async e => {
      e.preventDefault()
      const scrollY = window.scrollY || 0
      const newStatus = document.getElementById('newStatus').value
      try {
        await _apiRequest(`/leads/${leadId}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ status: newStatus }),
          retries: 0,
        })
        await loadLeads(true)
        viewLeadDetails(leadId)
        window.scrollTo(0, scrollY)
        if (await confirmDialog('Add Note?', 'Yes', '#4f46e5')) {
          const noteArea = document.getElementById('noteText')
          if (noteArea) {
            noteArea.scrollIntoView({ behavior: 'smooth', block: 'center' })
            noteArea.focus()
          }
        }
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }

  // Update project
  const updateProjectForm = document.getElementById('updateProjectForm')
  if (updateProjectForm) {
    updateProjectForm.addEventListener('submit', async e => {
      e.preventDefault()
      const scrollY = window.scrollY || 0
      const projectId = document.getElementById('newProject').value
      try {
        await _apiRequest(`/leads/${leadId}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ project_id: projectId ? parseInt(projectId) : null }),
          retries: 0,
        })
        await loadLeads(true)
        viewLeadDetails(leadId)
        window.scrollTo(0, scrollY)
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }

  // Update source
  const updateSourceForm = document.getElementById('updateSourceForm')
  if (updateSourceForm) {
    updateSourceForm.addEventListener('submit', async e => {
      e.preventDefault()
      const source = document.getElementById('newSource').value
      try {
        await _apiRequest(`/leads/${leadId}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ source }),
          retries: 0,
        })
        await loadLeads(true)
        viewLeadDetails(leadId)
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }

  // Add note
  const addNoteForm = document.getElementById('addNoteForm')
  if (addNoteForm) {
    addNoteForm.addEventListener('submit', async e => {
      e.preventDefault()
      const noteText = document.getElementById('noteText').value.trim()
      if (!noteText) return
      try {
        await _apiRequest(`/leads/${leadId}/notes`, {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ note: noteText }),
          retries: 0,
        })
        await loadLeads(true)
        viewLeadDetails(leadId)
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }

  // Assign lead
  const assignForm = document.getElementById('assignForm')
  if (assignForm) {
    const assignSelect = document.getElementById('assignTo')

    function updateAssignToOptions(managerId) {
      const allTM = users.filter(u => u.role === 'team_member')
      const filtered = managerId ? allTM.filter(u => String(u.manager_id) === String(managerId)) : allTM
      const selfOption = user.role === 'sales_manager'
        ? `<option value="${user.id}">${escape(user.name)} (me)</option>` : ''
      assignSelect.innerHTML = '<option value="">Select team member</option>' + selfOption +
        filtered.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
      if (L.assigned_to) assignSelect.value = L.assigned_to
    }

    const mgrFilterSel = document.getElementById('assignToManager')
    if (mgrFilterSel) {
      const preManagerId = users.find(u => u.id === L.assigned_to)?.manager_id || null
      if (preManagerId) mgrFilterSel.value = preManagerId
      mgrFilterSel.addEventListener('change', () => updateAssignToOptions(mgrFilterSel.value))
      updateAssignToOptions(preManagerId)
    } else {
      updateAssignToOptions(user.id)
    }

    assignForm.addEventListener('submit', async e => {
      e.preventDefault()
      const assignedTo = parseInt(document.getElementById('assignTo').value)
      try {
        await _apiRequest(`/leads/${leadId}/assign`, {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ assigned_to: assignedTo }),
          retries: 0,
        })
        await loadLeads(true)
        viewLeadDetails(leadId)
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }
}

window.viewLeadDetails = viewLeadDetails

// Global safety net: if lead detail rendering fails mid-flight, return the user
// to the previous screen instead of leaving a blank content area.
var _unsafeViewLeadDetails = viewLeadDetails
viewLeadDetails = async function (leadId) {
  try {
    return await _unsafeViewLeadDetails(leadId)
  } catch (err) {
    var origin = window._LEAD_DETAIL_ORIGIN || 'leads'
    window._ACTIVE_ROUTE = origin
    var content = document.getElementById('content')
    var isBlank = !content || !String(content.innerHTML || '').trim()

    if (isBlank) {
      if (origin === 'action_board' && typeof renderActionBoard === 'function') {
        await renderActionBoard(window._abDateFrom || '', window._abDateTo || '', window._abRange || 'today')
      } else if (typeof renderLeads === 'function') {
        await renderLeads()
      }
    }

    showToast((err && err.message) || 'Failed to open lead details.', 'error')
    return
  }
}
window.viewLeadDetails = viewLeadDetails

// ── Lead edit form ─────────────────────────────────────────────────────────
function openLeadEditForm(lead) {
  const overlay = document.createElement('div')
  const canEditPrimaryPhone = user && (user.role === 'superadmin' || user.role === 'platform_owner')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:520px;width:100%;">
      <button class="modal-close" id="closeEditLead">&times;</button>
      <h3 class="sm-section-heading" style="margin:0 0 20px;">✏️ Edit Lead</h3>
      <form id="editLeadForm" style="display:flex;flex-direction:column;gap:12px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Full Name *</label>
            <input class="input" id="editName" value="${escape(lead.name)}" required placeholder="Full name" style="font-size:13px;" />
          </div>
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Contact Number</label>
            <input class="input" id="editPhone" value="${escape(lead.phone||'')}" placeholder="Contact Number" style="font-size:13px;${canEditPrimaryPhone ? '' : 'background:#f8fafc;color:#64748b;'}" ${canEditPrimaryPhone ? '' : 'readonly'} />
            ${canEditPrimaryPhone ? '' : '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">Only admins can edit the contact number.</div>'}
          </div>
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Email</label>
            <input class="input" id="editEmail" type="email" value="${escape(lead.email||'')}" placeholder="Email" style="font-size:13px;" />
          </div>
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Alternate Number</label>
            <input class="input" id="editAlternatePhone" value="${escape(lead.alternate_phone||'')}" placeholder="Alternate Number" style="font-size:13px;" />
          </div>
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Source</label>
            <select class="select" id="editSource" style="font-size:13px;">
              <option value="">— Source —</option>
              ${['Website','Referral','Walk-in','Meta','Google','Email Campaign','Direct','Other','G1','G2','G3','TP'].map(s=>`<option value="${s}" ${lead.source===s?'selected':''}>${s}</option>`).join('')}
            </select>
          </div>
        </div>
        <div>
          <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Budget Range (₹ Cr)</label>
          <select class="select" id="editBudget" style="font-size:13px;">${budgetRangeOptions()}</select>
        </div>
        <div style="display:flex;gap:12px;margin-top:8px;">
          <button type="submit" class="button" style="flex:1;font-size:14px;padding:10px;">Save Changes</button>
          <button type="button" class="button secondary" id="cancelEditLead" style="flex:1;font-size:14px;padding:10px;">Cancel</button>
        </div>
      </form>
    </div>
  `
  document.body.appendChild(overlay)

  // Set budget
  const bSel = document.getElementById('editBudget')
  if (bSel && lead.budget_min) {
    const matchVal = `${lead.budget_min}|${lead.budget_max||lead.budget_min}`
    for (const opt of bSel.options) {
      if (opt.value === matchVal || opt.value.startsWith(String(lead.budget_min)+'|')) {
        opt.selected = true; break
      }
    }
  }

  const close = () => overlay.remove()
  document.getElementById('closeEditLead').addEventListener('click', close)
  document.getElementById('cancelEditLead').addEventListener('click', close)
  overlay.addEventListener('click', e => { if (e.target === overlay) close() })

  document.getElementById('editLeadForm').addEventListener('submit', async e => {
    e.preventDefault()
    const bp = (document.getElementById('editBudget').value || '').split('|')
    try {
      await _apiRequest(`/leads/${lead.id}`, {
        method: 'PUT',
        headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
        body: JSON.stringify({
          name:       document.getElementById('editName').value.trim(),
            phone:      canEditPrimaryPhone ? document.getElementById('editPhone').value.trim() : (lead.phone || ''),
            alternate_phone: document.getElementById('editAlternatePhone').value.trim(),
          email:      document.getElementById('editEmail').value.trim(),
          source:     document.getElementById('editSource').value,
          budget_min: Number(bp[0]) || null,
          budget_max: Number(bp[1]) || null,
        }),
        retries: 0,
      })
      close()
      await loadLeads(true)
      viewLeadDetails(lead.id)
      showToast('Lead updated.', 'success')
    } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
  })
}

async function openLeadForm() {
  const content = document.getElementById('content')
  await loadProjects()
  
  const projectOptions = projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')
  
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>New Lead</h2>
      <form id="leadForm">
        <input class="input" id="leadName" placeholder="Full Name" required />
        <input class="input" id="leadPhone" placeholder="Phone Number" />
        <input class="input" id="leadAlternatePhone" placeholder="Alternate Number" />
        <input class="input" id="leadEmail" placeholder="Email Address" />
        <select class="select" id="leadSource">
          <option value="">Select Source</option>
          <option value="Website">Website</option>
          <option value="Referral">Referral</option>
          <option value="Walk-in">Walk-in</option>
          <option value="Meta">Meta</option>
          <option value="Google">Google</option>
          <option value="Email Campaign">Email Campaign</option>
          <option value="Direct">Direct</option>
          <option value="Other">Other</option>
          <option value="G1">G1</option>
          <option value="G2">G2</option>
          <option value="G3">G3</option>
          <option value="TP">TP</option>
        </select>
        
        <label style="font-size:13px;color:#64748b;margin-bottom:4px;display:block;">Budget Range (₹ Cr)</label>
        <select class="select" id="leadBudget">
          ${budgetRangeOptions()}
        </select>
        
        <select class="select" id="leadProject">
          <option value="">Select a project</option>
          ${projectOptions}
        </select>
        
        <select class="select" id="leadStatus">
          <option value="new">New</option>
          <option value="attempted">Attempted</option>
          <option value="connected">Connected</option>
          <option value="interested">Interested</option>
          <option value="follow_up">Follow Up</option>
          <option value="site_visit_planned">Site Visit Planned</option>
          <option value="site_visit_done">Site Visit Done</option>
          <option value="negotiation">Negotiation</option>
          <option value="booking_done">Booking Done</option>
          <option value="not_interested">Not Interested</option>
          <option value="lost">Lost</option>
          <option value="junk">Junk</option>
        </select>
        
        <div id="dupWarn"></div>
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">Save Lead</button>
          <button type="button" class="button secondary" id="cancelLead">Cancel</button>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('leadForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('leadName').value
    const phone = document.getElementById('leadPhone').value
    const alternate_phone = document.getElementById('leadAlternatePhone').value.trim()
    const email = document.getElementById('leadEmail').value
    const source = document.getElementById('leadSource').value
    const leadBudgetParts = (document.getElementById('leadBudget').value || '').split('|')
    const budget_min = Number(leadBudgetParts[0]) || null
    const budget_max = Number(leadBudgetParts[1]) || null
    const project_id = Number(document.getElementById('leadProject').value) || null
    const status = document.getElementById('leadStatus').value
    
    const submitLead = async (force = false) => {
      try {
        await _apiRequest('/leads', {
          method: 'POST',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ name, phone, alternate_phone, email, source, budget_min, budget_max, project_id, status, ...(force && { force: true }) }),
          retries: 0,
        })
        renderLeads()
      } catch (err) {
      if (err.status === 409) {
        const ex = err.payload && err.payload.existing_lead
        document.getElementById('dupWarn').innerHTML = `
          <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:12px 14px;margin-top:12px;">
            <div style="font-size:13px;font-weight:600;color:#92400e;">⚠ Duplicate phone number</div>
            <div style="font-size:12px;color:#78350f;margin-top:4px;">
              Lead <strong>${escape(ex.name)}</strong> (ID #${ex.id}, status: <em>${ex.status.replace(/_/g,' ')}</em>) already has this phone number.
            </div>
            <div style="display:flex;gap:8px;margin-top:10px;">
              <button type="button" class="button" onclick="viewLeadDetails(${ex.id})" style="font-size:12px;padding:6px 14px;">View Existing</button>
              ${user && user.role === 'superadmin' ? '<button type="button" id="forceCreate" class="button secondary" style="font-size:12px;padding:6px 14px;">Create Anyway</button>' : ''}
            </div>
          </div>`
        document.getElementById('forceCreate') && document.getElementById('forceCreate').addEventListener('click', () => submitLead(true))
        return
      }
      showToast((err.payload && err.payload.error) || 'Error saving lead. Please try again.', 'error')
      } // end catch
    }
    await submitLead()
  })
  
  document.getElementById('cancelLead').addEventListener('click', renderLeads)
}

// ── Callback modal ─────────────────────────────────────────────────────────
function openCallbackModal(leadId, options) {
  const modalOptions = options || {}
  const isRequiredFromCall = !!modalOptions.requireSchedule
  const leadPhone = modalOptions.leadPhone || ''
  const leadAlternatePhone = modalOptions.leadAlternatePhone || ''
  const leadName = modalOptions.leadName || ''
  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:480px;width:100%;">
      ${isRequiredFromCall ? '' : '<button class="modal-close" id="closeCallbackModal">&times;</button>'}
      <h3 class="sm-section-heading" style="margin:0 0 20px;">📞 Schedule Callback</h3>
      ${(leadName || leadPhone || leadAlternatePhone) ? `<div style="margin:-8px 0 10px;font-size:13px;color:#475569;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;line-height:1.45;">${leadName ? `<strong style="display:block;margin-bottom:2px;">${escape(leadName)}</strong>` : ''}${leadPhone ? `Primary: ${escape(leadPhone)}` : ''}${leadAlternatePhone ? `${leadPhone ? '<br/>' : ''}Alternate: ${escape(leadAlternatePhone)}` : ''}</div>` : ''}
      ${isRequiredFromCall ? `<div style="margin:-8px 0 10px;font-size:12px;color:#92400e;background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:10px 12px;">Select a callback date and time to complete the call outcome.</div>` : ''}
      <form id="callbackForm" style="display:flex;flex-direction:column;gap:14px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Date *</label>
            <input class="input" id="cbDate" type="date" required style="font-size:13px;" />
          </div>
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Time *</label>
            <input class="input" id="cbTime" type="time" required style="font-size:13px;" />
          </div>
        </div>
        <div>
          <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Note (optional)</label>
          <textarea class="input" id="cbNote" rows="2" placeholder="What is this callback about?" style="font-size:13px;resize:vertical;"></textarea>
        </div>
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:10px 14px;font-size:12px;color:#1e40af;">
          🔔 Reminders will be sent <strong>10 minutes before</strong> and <strong>at the time</strong> of the callback to the assigned team member and their manager.
        </div>
        <div style="display:flex;gap:10px;margin-top:4px;">
          <button type="submit" class="button" style="flex:1;font-size:14px;padding:10px;">Save Callback</button>
          ${isRequiredFromCall ? '' : '<button type="button" class="button secondary" id="cancelCallback" style="flex:1;font-size:14px;padding:10px;">Cancel</button>'}
        </div>
      </form>
    </div>
  `
  document.body.appendChild(overlay)

  // Default to tomorrow at 10:00 for regular scheduling, but require explicit selection
  // when the modal is opened from a call outcome flow.
  if (!isRequiredFromCall) {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    document.getElementById('cbDate').value = tomorrow.toISOString().split('T')[0]
    document.getElementById('cbTime').value = '10:00'
  }

  const close = () => overlay.remove()
  const closeBtn = document.getElementById('closeCallbackModal')
  const cancelBtn = document.getElementById('cancelCallback')
  if (closeBtn) closeBtn.addEventListener('click', close)
  if (cancelBtn) cancelBtn.addEventListener('click', close)
  overlay.addEventListener('click', e => {
    if (e.target === overlay && !isRequiredFromCall) close()
  })

  document.getElementById('callbackForm').addEventListener('submit', async e => {
    e.preventDefault()
    const cbDate = document.getElementById('cbDate').value
    const cbTime = document.getElementById('cbTime').value
    if (!cbDate || !cbTime) {
      showToast('Please select callback date and time.', 'warning')
      return
    }
    const dt = cbDate + 'T' + cbTime + ':00'
    const notes = document.getElementById('cbNote').value.trim()
    try {
      await _apiRequest(`/leads/${leadId}/callbacks`, {
        method: 'POST',
        headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
        body: JSON.stringify({ callback_datetime: dt, notes }),
        retries: 0,
      })
      close()
      await loadLeads(true)
      if (typeof window.viewLeadDetails === 'function') {
        try {
          await window.viewLeadDetails(leadId)
        } catch (_) {
          if (typeof renderActionBoard === 'function' && window._ACTIVE_ROUTE === 'action_board') {
            renderActionBoard(window._abDateFrom || '', window._abDateTo || '', window._abRange || 'today')
          }
        }
      }
      if (typeof modalOptions.onSaved === 'function') modalOptions.onSaved()
      showToast('Callback scheduled.', 'success')
    } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
  })
}

async function markCallbackDone(callbackId, leadId) {
  const closureNote = await openCallbackClosureModal('complete')
  if (!closureNote) return

  try {
    await _apiRequest(`/leads/callbacks/${callbackId}/complete`, {
      method: 'POST',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ closure_note: closureNote }),
      retries: 0,
    })
    await loadLeads(true)
    viewLeadDetails(leadId)
    showToast('Callback marked as completed.', 'success')
  } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
}

async function deleteCallback(callbackId, leadId) {
  if (!await confirmDialog('Close this callback as cancelled?', 'Cancel Callback')) return
  const closureNote = await openCallbackClosureModal('cancel')
  if (!closureNote) return

  try {
    await _apiRequest(`/leads/callbacks/${callbackId}`, {
      method: 'DELETE',
      headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
      body: JSON.stringify({ closure_note: closureNote }),
      retries: 0,
    })
    await loadLeads(true)
    viewLeadDetails(leadId)
    showToast('Callback cancelled.', 'success')
  } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
}

function openCallbackClosureModal(mode) {
  const isCancel = mode === 'cancel'
  const title = isCancel ? 'Cancel Callback' : 'Complete Callback'
  const hint = isCancel
    ? 'Add a cancellation note before closing this callback.'
    : 'Add a closure note before marking this callback as done.'
  const placeholder = isCancel
    ? 'Why was this callback cancelled?'
    : 'What happened on this callback?'

  return new Promise(resolve => {
    const overlay = document.createElement('div')
    overlay.className = 'modal-overlay'
    overlay.innerHTML = `
      <div class="modal-box" style="max-width:520px;width:100%;">
        <button class="modal-close" id="closeCallbackClosureModal">&times;</button>
        <h3 class="sm-section-heading" style="margin:0 0 12px;">${title}</h3>
        <div style="margin:0 0 12px;font-size:12px;color:#334155;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;">${hint}</div>
        <form id="callbackClosureForm" style="display:flex;flex-direction:column;gap:12px;">
          <div>
            <label style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:5px;">Closure Note *</label>
            <textarea class="input" id="callbackClosureNote" rows="4" maxlength="1000" placeholder="${placeholder}" required style="font-size:13px;resize:vertical;"></textarea>
          </div>
          <div style="display:flex;gap:10px;">
            <button type="submit" class="button" style="flex:1;font-size:14px;padding:10px;">Save & Continue</button>
            <button type="button" class="button secondary" id="cancelCallbackClosureModal" style="flex:1;font-size:14px;padding:10px;">Cancel</button>
          </div>
        </form>
      </div>
    `

    let settled = false
    const finish = note => {
      if (settled) return
      settled = true
      overlay.remove()
      resolve(note)
    }

    document.body.appendChild(overlay)
    const noteInput = document.getElementById('callbackClosureNote')
    if (noteInput) noteInput.focus()

    const closeBtn = document.getElementById('closeCallbackClosureModal')
    const cancelBtn = document.getElementById('cancelCallbackClosureModal')
    const form = document.getElementById('callbackClosureForm')

    if (closeBtn) closeBtn.addEventListener('click', () => finish(null))
    if (cancelBtn) cancelBtn.addEventListener('click', () => finish(null))

    overlay.addEventListener('click', e => {
      if (e.target === overlay) finish(null)
    })

    form.addEventListener('submit', e => {
      e.preventDefault()
      const note = (noteInput && noteInput.value ? noteInput.value : '').trim()
      if (!note) {
        showToast('Closure note is required.', 'warning')
        return
      }
      finish(note)
    })
  })
}

