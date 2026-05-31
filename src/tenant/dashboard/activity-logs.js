// ============================================================================
// ACTIVITY LOGS
// ============================================================================

var _activityLogsRenderId = 0

async function renderActivityLogs() {
  var myId = ++_activityLogsRenderId
  const content = document.getElementById('content')
  if (!content) return
  content.innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <h2 style="margin:0;">Activity Logs</h2>
        <button class="button" onclick="downloadActivityLogs()" style="font-size:13px;padding:8px 16px;">⬇ Download Excel</button>
      </div>
      <div style="display:flex;gap:10px;margin:0 0 20px;">
        <select id="filterUser" class="select" style="width:200px;">
          <option value="">All Users</option>
        </select>
        <select id="filterAction" class="select" style="width:200px;">
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
        <select id="filterModule" class="select" style="width:200px;">
          <option value="">All Modules</option>
          <option value="auth">Auth</option>
          <option value="leads">Leads</option>
          <option value="projects">Projects</option>
          <option value="users">Users</option>
        </select>
        <select id="filterSortOrder" class="select" style="width:160px;">
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
        </select>
      </div>
      <div id="logsContainer"></div>
    </div>
  `
  
  await loadActivityLogs()
  await loadUsers()
  if (myId !== _activityLogsRenderId) return

  const userSelect = document.getElementById('filterUser')
  if (!userSelect) return
  userSelect.innerHTML = '<option value="">All Users</option>' +
    users.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
  
  document.getElementById('filterUser').addEventListener('change', filterAndRenderLogs)
  document.getElementById('filterAction').addEventListener('change', filterAndRenderLogs)
  document.getElementById('filterModule').addEventListener('change', filterAndRenderLogs)
  document.getElementById('filterSortOrder').addEventListener('change', async function () {
    await loadActivityLogs()
    filterAndRenderLogs()
  })
  
  filterAndRenderLogs()
}

async function downloadActivityLogs() {
  const userFilter   = document.getElementById('filterUser')?.value || ''
  const actionFilter = document.getElementById('filterAction')?.value || ''
  const moduleFilter = document.getElementById('filterModule')?.value || ''
  const params = new URLSearchParams()
  if (userFilter)   params.set('user_id', userFilter)
  if (actionFilter) params.set('action', actionFilter)
  if (moduleFilter) params.set('module', moduleFilter)
  const url = `${API_BASE}/reports/activity/download?${params.toString()}`
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
  const sort = document.getElementById('filterSortOrder')?.value || 'newest'
  const res = await fetch(`${API_BASE}/reports/activity-logs?limit=500&sort=${encodeURIComponent(sort)}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const data = await res.json()
  activityLogs = data.activity_logs || []
}

function filterAndRenderLogs() {
  const userFilter = document.getElementById('filterUser')?.value
  const actionFilter = document.getElementById('filterAction')?.value
  const moduleFilter = document.getElementById('filterModule')?.value
  
  let filtered = activityLogs
  if (userFilter) filtered = filtered.filter(l => l.user_id === parseInt(userFilter))
  if (actionFilter) filtered = filtered.filter(l => l.action === actionFilter)
  if (moduleFilter) filtered = filtered.filter(l => l.module === moduleFilter)
  
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
  if (filtered.length === 0) {
    container.innerHTML = '<div class="message">No activity logs found</div>'
    return
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
          ${filtered.slice(0, 100).map(l => `
            <tr>
              <td>${escape(l.user_name || 'Unknown')}</td>
              <td><span class="tag" style="background:#e0f2fe;color:#0369a1;">${escape(actionLabels[l.action] || l.action)}</span></td>
              <td>${escape(l.module)}</td>
              <td>${l.resource_id || '-'}</td>
              <td>${escape(changeSummary(l))}</td>
              <td>${new Date(l.created_at).toLocaleString()}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
}

// ============================================================================
