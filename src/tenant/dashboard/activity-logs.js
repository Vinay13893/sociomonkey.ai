// ============================================================================
// ACTIVITY LOGS
// ============================================================================

var _activityLogsRenderId = 0
var _activityLogsPage = 1
var _activityLogsPerPage = 25
var _activityLogsTotal = 0

async function renderActivityLogs() {
  var myId = ++_activityLogsRenderId
  const content = document.getElementById('content')
  if (!content) return

  const isManager  = user && user.role === 'sales_manager'
  const isMember   = user && user.role === 'team_member'
  const pageTitle  = isMember ? 'My Activity' : 'Activity Logs'
  const showUserFilter = !isMember

  content.innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <h2 style="margin:0;">${pageTitle}</h2>
        <button class="button" onclick="downloadActivityLogs()" style="font-size:13px;padding:8px 16px;">⬇ Download Excel</button>
      </div>
      <style>
        .activity-filter-bar{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin:0 0 20px;}
        .activity-filter-bar .select{height:38px;}
        .activity-date-anchor{flex:0 1 240px;min-width:210px;max-width:260px;}
        .activity-date-anchor .smdr-shell{min-width:0;width:100%;}
        .activity-pagination{display:flex;gap:8px;align-items:center;justify-content:space-between;margin-top:10px;font-size:12px;flex-wrap:wrap;background:rgba(255,255,255,.94);border:1px solid #e2e8f0;border-radius:12px;padding:8px 10px;}
        .activity-pagination-left,.activity-pagination-right{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
        .activity-page-btn{border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:7px 10px;font-size:12px;font-weight:700;cursor:pointer;}
        .activity-page-btn.primary{background:#0f766e;color:#fff;border-color:#0f766e;}
        .activity-page-btn:disabled{opacity:.55;cursor:not-allowed;}
      </style>
      <div class="activity-filter-bar">
        ${showUserFilter ? `<select id="filterUser" class="select" style="width:180px;"><option value="">All Users</option></select>` : ''}
        <select id="filterAction" class="select" style="width:180px;">
          <option value="">All Actions</option>
          <option value="login">Login</option>
          <option value="logout">Logout</option>
          <option value="create_lead">Create Lead</option>
          <option value="update_lead">Update Lead</option>
          <option value="bulk_update_lead">Bulk Update Lead</option>
          <option value="bulk_status_update">Bulk Status Update</option>
          <option value="import_lead">Import Lead</option>
          <option value="assign_lead">Assign Lead</option>
          <option value="assign_manager">Assign Manager</option>
          <option value="add_note">Add Note</option>
          <option value="create_callback">Create Callback</option>
          <option value="update_callback">Update Callback</option>
          <option value="complete_callback">Complete Callback</option>
          <option value="call_initiated">Call Initiated</option>
          <option value="call_answered">Call Answered</option>
          <option value="call_unanswered">Call Unanswered</option>
          <option value="call_busy">Call Busy</option>
          <option value="call_hangup">Call Hangup</option>
          <option value="call_duration_update">Call Duration Update</option>
          <option value="create_project">Create Project</option>
        </select>
        <select id="filterModule" class="select" style="width:180px;">
          <option value="">All Modules</option>
          <option value="auth">Auth</option>
          <option value="leads">Leads</option>
          <option value="projects">Projects</option>
          <option value="users">Users</option>
        </select>
        <select id="filterSortOrder" class="select" style="width:150px;">
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
        </select>
        <div class="dash-filter-group activity-date-anchor">
          <input type="hidden" id="activityDateFrom" />
          <input type="hidden" id="activityDateTo" />
        </div>
      </div>
      <div id="logsContainer"></div>
    </div>
  `

  await loadActivityLogs()

  if (showUserFilter) {
    await loadUsers()
    if (myId !== _activityLogsRenderId) return
    const userSelect = document.getElementById('filterUser')
    if (userSelect) {
      // Sales managers only see their own team in the dropdown
      const visibleUsers = isManager
        ? users.filter(u => u.id === user.id || u.manager_id === user.id)
        : users
      userSelect.innerHTML = '<option value="">All Users</option>' +
        visibleUsers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
      userSelect.addEventListener('change', reloadActivityLogsFromFirstPage)
    }
  } else {
    if (myId !== _activityLogsRenderId) return
  }

  document.getElementById('filterAction').addEventListener('change', reloadActivityLogsFromFirstPage)
  document.getElementById('filterModule').addEventListener('change', reloadActivityLogsFromFirstPage)
  document.getElementById('filterSortOrder').addEventListener('change', async function () {
    await reloadActivityLogsFromFirstPage()
  })
  
  filterAndRenderLogs()
}

async function reloadActivityLogsFromFirstPage() {
  _activityLogsPage = 1
  await loadActivityLogs()
  filterAndRenderLogs()
}

async function downloadActivityLogs() {
  const userFilter   = document.getElementById('filterUser')?.value || ''
  const actionFilter = document.getElementById('filterAction')?.value || ''
  const moduleFilter = document.getElementById('filterModule')?.value || ''
  const dateFrom = document.getElementById('activityDateFrom')?.value || ''
  const dateTo = document.getElementById('activityDateTo')?.value || ''
  const params = new URLSearchParams()
  if (userFilter)   params.set('user_id', userFilter)
  if (actionFilter) params.set('action', actionFilter)
  if (moduleFilter) params.set('module', moduleFilter)
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const url = `${API_BASE}/reports/activity-logs/download?${params.toString()}`
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) { showToast('Failed to download', 'error'); return }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `activity_logs_${new Date().toISOString().slice(0,10)}.xlsx`
  a.click()
  URL.revokeObjectURL(a.href)
}

async function loadActivityLogs() {
  const userFilter   = document.getElementById('filterUser')?.value || ''
  const actionFilter = document.getElementById('filterAction')?.value || ''
  const moduleFilter = document.getElementById('filterModule')?.value || ''
  const sort = document.getElementById('filterSortOrder')?.value || 'newest'
  const dateFrom = document.getElementById('activityDateFrom')?.value || ''
  const dateTo = document.getElementById('activityDateTo')?.value || ''
  const params = new URLSearchParams()
  params.set('page', String(_activityLogsPage || 1))
  params.set('per_page', String(_activityLogsPerPage || 25))
  params.set('sort', sort)
  if (userFilter) params.set('user_id', userFilter)
  if (actionFilter) params.set('action', actionFilter)
  if (moduleFilter) params.set('module', moduleFilter)
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const res = await fetch(`${API_BASE}/reports/activity-logs?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  activityLogs = data.activity_logs || []
  _activityLogsTotal = Number(data.total || activityLogs.length || 0)
  _activityLogsPage = Number(data.page || _activityLogsPage || 1)
  _activityLogsPerPage = Number(data.per_page || _activityLogsPerPage || 25)
}

async function refreshActivityLogsDateRange() {
  await reloadActivityLogsFromFirstPage()
}

function filterAndRenderLogs() {
  let filtered = activityLogs
  
  const actionLabels = {
    create_lead: 'Create Lead',
    update_lead: 'Update Lead',
    bulk_update_lead: 'Bulk Update Lead',
    bulk_status_update: 'Bulk Status Update',
    import_lead: 'Import Lead',
    assign_lead: 'Assign Lead',
    assign_manager: 'Assign Manager',
    add_note: 'Add Note',
    create_callback: 'Create Callback',
    update_callback: 'Reschedule Callback',
    complete_callback: 'Complete Callback',
    call_initiated: 'Call Initiated',
    call_answered: 'Call Answered',
    call_unanswered: 'Call Unanswered',
    call_busy: 'Call Busy',
    call_hangup: 'Call Ended',
    call_duration_update: 'Call Duration Updated',
  }

  function changeSummary(log) {
    if (!log) return '-'
    var base = log.description || '-'
    var oldValue = log.old_value || {}
    var newValue = log.new_value || {}
    var details = []

    if (Object.prototype.hasOwnProperty.call(newValue, 'status')) {
      var oldStatus = oldValue.status || '—'
      var newStatus = newValue.status || '—'
      details.push(`Status: ${oldStatus} -> ${newStatus}`)
    }
    if (Object.prototype.hasOwnProperty.call(newValue, 'phone')) {
      var oldPhone = oldValue.phone || '—'
      var newPhone = newValue.phone || '—'
      details.push(`Phone: ${oldPhone} -> ${newPhone}`)
    }

    if (!details.length) return base
    return `${base} (${details.join(' | ')})`
  }
  
  const container = document.getElementById('logsContainer')
  const totalPages = Math.max(1, Math.ceil((_activityLogsTotal || 0) / (_activityLogsPerPage || 25)))
  const startIdx = (_activityLogsPage - 1) * _activityLogsPerPage + 1

  if (filtered.length === 0) {
    container.innerHTML = '<div class="message">No activity logs found</div>'
    return
  }

  let pagerButtons = ''
  const fromPage = Math.max(1, _activityLogsPage - 2)
  const toPage = Math.min(totalPages, fromPage + 4)
  for (let p = fromPage; p <= toPage; p += 1) {
    pagerButtons += `<button class="activity-page-btn ${p === _activityLogsPage ? 'primary' : ''}" data-activity-page="${p}">${p}</button>`
  }
  
  container.innerHTML = `
    <div style="overflow-x:auto;">
      <table class="table">
        <thead>
          <tr>
            <th>User</th>
            <th>Action</th>
            <th>Module</th>
            <th>Resource ID</th>
            <th>Description</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(l => `
            <tr>
              <td>${escape(l.user_name || 'Unknown')}</td>
              <td><span class="tag" style="background:#e0f2fe;color:#0369a1;">${escape(actionLabels[l.action] || l.action)}</span></td>
              <td>${escape(l.module)}</td>
              <td>${l.resource_id || '-'}</td>
              <td>${escape(changeSummary(l))}</td>
              <td style="white-space:nowrap;">${_fmtIST(l.created_at)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    <div class="activity-pagination">
      <div class="activity-pagination-left">
        <button class="activity-page-btn" data-activity-page="${Math.max(1, _activityLogsPage - 1)}" ${_activityLogsPage <= 1 ? 'disabled' : ''}>Prev</button>
        ${pagerButtons}
        <button class="activity-page-btn" data-activity-page="${Math.min(totalPages, _activityLogsPage + 1)}" ${_activityLogsPage >= totalPages ? 'disabled' : ''}>Next</button>
      </div>
      <div class="activity-pagination-right">
        <span class="muted">Showing ${filtered.length ? startIdx : 0} - ${filtered.length ? startIdx + filtered.length - 1 : 0} of ${_activityLogsTotal} activities</span>
        <label class="muted" for="activityLogsPerPage" style="margin:0">Rows</label>
        <select id="activityLogsPerPage" class="select" style="width:auto;height:34px;">
          <option value="25" ${_activityLogsPerPage === 25 ? 'selected' : ''}>25</option>
          <option value="50" ${_activityLogsPerPage === 50 ? 'selected' : ''}>50</option>
          <option value="100" ${_activityLogsPerPage === 100 ? 'selected' : ''}>100</option>
        </select>
      </div>
    </div>
  `

  container.querySelectorAll('[data-activity-page]').forEach(btn => {
    btn.addEventListener('click', async function () {
      if (btn.disabled) return
      _activityLogsPage = Number(btn.getAttribute('data-activity-page') || 1)
      await loadActivityLogs()
      filterAndRenderLogs()
    })
  })
  const perPageSelect = document.getElementById('activityLogsPerPage')
  if (perPageSelect) {
    perPageSelect.addEventListener('change', async function () {
      _activityLogsPerPage = Number(perPageSelect.value || 25)
      _activityLogsPage = 1
      await loadActivityLogs()
      filterAndRenderLogs()
    })
  }
}

// ============================================================================
