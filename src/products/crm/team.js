// ============================================================================
// TEAM MANAGEMENT
// ============================================================================

var _teamRenderId = 0

async function renderTeamManagement() {
  var myId = ++_teamRenderId
  const content = document.getElementById('content')
  if (!content) return
  content.innerHTML = `
    <div class="card">
      <div class="header" style="margin-bottom:20px;">
        <h2>Team Management</h2>
        <button class="button" id="newUserBtn">+ Add Team Member</button>
      </div>
      <div id="teamContainer"></div>
    </div>
  `
  
  document.getElementById('newUserBtn').addEventListener('click', openUserForm)
  
  await loadUsers()
  if (myId !== _teamRenderId) return

  const container = document.getElementById('teamContainer')
  if (!container) return

  const TABLE_HEADERS_BASE = `<thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead>`
  const TABLE_HEADERS_TEAM = `<thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Sales Manager</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead>`

  function userRow(u, showManager) {
    const managerName = showManager
      ? (users.find(m => m.id === u.manager_id)?.name || '<span style="color:#94a3b8;">Unassigned</span>')
      : null
    return `<tr>
      <td><strong>${escape(u.name)}</strong></td>
      <td>${escape(u.email)}</td>
      <td>${escape(u.phone || '-')}</td>
      ${showManager ? `<td><span style="font-size:12px;font-weight:500;color:#0369a1;">${managerName}</span></td>` : ''}
      <td>${u.is_active ? '<span class="tag" style="background:#dcfce7;color:#166534;">Active</span>' : '<span class="tag" style="background:#fee2e2;color:#991b1b;">Inactive</span>'}</td>
      <td>${u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}</td>
      <td>
        <button class="button secondary edit-user-btn" data-id="${u.id}" style="font-size:12px;padding:6px 10px;">Edit</button>
        <button class="button del-user-btn" data-id="${u.id}" data-name="${escape(u.name)}" style="font-size:12px;padding:6px 10px;background:#ef4444;border-color:#ef4444;margin-left:4px;">Delete</button>
      </td>
    </tr>`
  }

  function sectionHTML(title, color, textColor, bgColor, members, showManager) {
    if (members.length === 0) return ''
    const headers = showManager ? TABLE_HEADERS_TEAM : TABLE_HEADERS_BASE
    return `
      <div style="margin-bottom:28px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
          <span style="font-size:14px;font-weight:700;color:${textColor};">${title}</span>
          <span style="font-size:12px;font-weight:600;background:${bgColor};color:${textColor};padding:2px 10px;border-radius:20px;">${members.length}</span>
          <div style="flex:1;height:1px;background:${color};opacity:0.3;"></div>
        </div>
        <div style="overflow-x:auto;">
          <table class="table">
            ${headers}
            <tbody>${members.map(u => userRow(u, showManager)).join('')}</tbody>
          </table>
        </div>
      </div>
    `
  }

  if (user.role === 'sales_manager') {
    const myTeam = users.filter(u => u.manager_id === user.id)
    if (myTeam.length === 0) {
      container.innerHTML = '<div class="message">No team members assigned to you yet.</div>'
      return
    }
    container.innerHTML = sectionHTML('Team Members', '#6366f1', '#4338ca', '#ede9fe', myTeam, false)
  } else {
    // superadmin: split into sections by role
    const superAdmins  = users.filter(u => u.role === 'superadmin')
    const salesManagers = users.filter(u => u.role === 'sales_manager')
    const teamMembers   = users.filter(u => u.role === 'team_member')
    if (superAdmins.length === 0 && salesManagers.length === 0 && teamMembers.length === 0) {
      container.innerHTML = '<div class="message">No team members found.</div>'
      return
    }
    container.innerHTML =
      sectionHTML('Super Admins',   '#94a3b8', '#475569', '#f1f5f9', superAdmins,  false) +
      sectionHTML('Sales Managers', '#0ea5e9', '#0369a1', '#e0f2fe', salesManagers, false) +
      sectionHTML('Team Members',   '#6366f1', '#4338ca', '#ede9fe', teamMembers,  true)
  }
  
  // Add click handlers for edit buttons
  document.querySelectorAll('.edit-user-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const userId = parseInt(e.target.getAttribute('data-id'))
      const editUser = users.find(u => u.id === userId)
      if (editUser) openEditUserForm(editUser)
    })
  })

  document.querySelectorAll('.del-user-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!await confirmDialog('Delete team member &quot;' + escape(btn.dataset.name) + '&quot;? This cannot be undone.', 'Delete')) return
      const res = await fetch(`${API_BASE}/users/${btn.dataset.id}`, {
        method: 'DELETE',
        headers: _apiAuthHeaders()
      })
      if (res.ok) {
        await loadUsers()
        renderTeamManagement()
      } else {
        const err = await res.json().catch(() => ({}))
        showToast(err.error || 'Error deleting user', 'error')
      }
    })
  })
}

async function openEditUserForm(editUser) {
  const content = document.getElementById('content')
  if (!content) return

  let salesManagerOptions = ''
  if (user.role === 'superadmin') {
    const managers = users.filter(u => u.role === 'sales_manager')
    salesManagerOptions = '<option value="">Unassigned</option>' + managers.map(m => 
      `<option value="${m.id}" ${editUser.manager_id === m.id ? 'selected' : ''}>${escape(m.name)}</option>`
    ).join('')
  }
  
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>Edit ${editUser.role === 'sales_manager' ? 'Sales Manager' : editUser.role === 'superadmin' ? 'Super Admin' : 'Team Member'}</h2>
      <form id="userForm">
        <input class="input" id="userName" placeholder="Full Name" value="${escape(editUser.name)}" required />
        <input class="input" id="userEmail" placeholder="Email Address" type="email" value="${escape(editUser.email)}" required />
        <input class="input" id="userPhone" placeholder="Phone Number" value="${escape(editUser.phone || '')}" />
        
        ${user.role === 'superadmin' ? `
          <select class="select" id="userRole" required>
            <option value="team_member" ${editUser.role === 'team_member' ? 'selected' : ''}>Team Member</option>
            <option value="sales_manager" ${editUser.role === 'sales_manager' ? 'selected' : ''}>Sales Manager</option>
            <option value="superadmin" ${editUser.role === 'superadmin' ? 'selected' : ''}>Super Admin</option>
          </select>
        ` : '<input type="hidden" id="userRole" value="' + editUser.role + '" />'}
        
        ${user.role === 'superadmin' && editUser.role === 'team_member' ? `
          <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">Sales Manager</label>
          <select class="select" id="userManager">
            ${salesManagerOptions}
          </select>
        ` : '<input type="hidden" id="userManager" value="' + (editUser.manager_id || '') + '" />'}
        
        <label style="display:flex;align-items:center;gap:8px;margin:10px 0;font-weight:500;">
          <input type="checkbox" id="isActive" ${editUser.is_active ? 'checked' : ''} />
          Active User
        </label>
        
        ${user.role === 'superadmin' ? `
          <div style="border-top:1px solid #e2e8f0;padding-top:16px;margin-top:16px;">
            <label style="display:block;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">Change Password (Optional)</label>
            <input class="input" id="userPassword" placeholder="New Password" type="password" />
            <p style="font-size:12px;color:#94a3b8;margin-top:6px;">Leave blank to keep current password unchanged</p>
          </div>
        ` : ''}
        
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">Save Changes</button>
          <button type="button" class="button secondary" id="cancelUser">Cancel</button>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('userForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('userName').value
    const email = document.getElementById('userEmail').value
    const phone = document.getElementById('userPhone').value
    const role = document.getElementById('userRole').value
    const isActive = document.getElementById('isActive').checked
    const managerId = document.getElementById('userManager')?.value || ''
    const password = user.role === 'superadmin' ? (document.getElementById('userPassword')?.value || '') : ''
    
    const body = { name, email, phone, role, is_active: isActive }
    if (user.role === 'superadmin' && editUser.role === 'team_member' && managerId) {
      body.manager_id = parseInt(managerId)
    }
    if (user.role === 'superadmin' && editUser.role === 'team_member' && !managerId) {
      body.manager_id = null
    }
    if (password) body.password = password
    
    const res = await fetch(`${API_BASE}/users/${editUser.id}`, {
      method: 'PUT',
      headers: Object.assign({ 'Content-Type': 'application/json' }, _apiAuthHeaders()),
      body: JSON.stringify(body)
    })
    if (res.ok) {
      await loadUsers()
      renderTeamManagement()
    } else {
      showToast('Error updating user', 'error')
    }
  })
  
  document.getElementById('cancelUser').addEventListener('click', renderTeamManagement)
}

async function openUserForm() {
  const content = document.getElementById('content')
  if (!content) return
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>Add Team Member</h2>
      <form id="userForm">
        <input class="input" id="userName" placeholder="Full Name" required />
        <input class="input" id="userEmail" placeholder="Email Address" type="email" required />
        <input class="input" id="userPhone" placeholder="Phone Number" />
        
        ${user.role === 'superadmin' ? `
          <select class="select" id="userRole">
            <option value="team_member">Team Member</option>
            <option value="sales_manager">Sales Manager</option>
            <option value="superadmin">Super Admin</option>
          </select>
        ` : '<input type="hidden" id="userRole" value="team_member" />'}
        
        <input class="input" id="userPassword" placeholder="Temporary Password" type="password" value="TeamMember@123" />
        
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">Create User</button>
          <button type="button" class="button secondary" id="cancelUser">Cancel</button>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('userForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('userName').value
    const email = document.getElementById('userEmail').value
    const phone = document.getElementById('userPhone').value
    const role = document.getElementById('userRole').value
    const password = document.getElementById('userPassword').value
    
    const res = await fetch(`${API_BASE}/users`, {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, _apiAuthHeaders()),
      body: JSON.stringify({ name, email, phone, role, password })
    })
    if (res.ok) renderTeamManagement()
  })
  
  document.getElementById('cancelUser').addEventListener('click', renderTeamManagement)
}

