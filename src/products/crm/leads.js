async function renderLeads() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
        <h2 style="margin:0;">Leads</h2>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          ${user.role !== 'team_member' ? `<button class="button secondary" id="importLeadsBtn" style="font-size:13px;padding:8px 14px;">📤 Import Excel</button>` : ''}
          ${user.role === 'superadmin' ? `<button class="button secondary" id="exportLeadsBtn" style="font-size:13px;padding:8px 14px;">📥 Export Excel</button>` : ''}
          <button class="button" id="newLeadBtn">+ New Lead</button>
        </div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin-bottom:18px;">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:12px;flex-wrap:wrap;">
          <span style="font-size:13px;font-weight:600;color:#475569;letter-spacing:0.04em;">🔍 FILTERS</span>
          <span id="leadsActiveDateBadge" style="display:none;font-size:11px;font-weight:600;padding:2px 9px;border-radius:20px;background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;"></span>
          <button onclick="clearLeadsFilters()" id="clearFiltersBtn" style="margin-left:auto;font-size:11px;padding:3px 10px;border:1px solid #cbd5e1;border-radius:20px;background:#fff;color:#64748b;cursor:pointer;font-weight:500;">✕ Clear all</button>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px;">
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">STATUS</label>
            <select id="filterStatus" class="select" style="font-size:13px;">
              <option value="">All Statuses</option>
              <option value="new">New</option>
              <option value="attempted">Attempted</option>
              <option value="connected">Connected</option>
              <option value="interested">Interested</option>
              <option value="site_visit_planned">Site Visit Planned</option>
              <option value="site_visit_done">Site Visit Done</option>
              <option value="negotiation">Negotiation</option>
              <option value="booking_done">Booking Done</option>
              <option value="lost">Lost</option>
              <option value="junk">Junk</option>
            </select>
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">PROJECT</label>
            <select id="filterProject" class="select" style="font-size:13px;">
              <option value="">All Projects</option>
            </select>
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">SOURCE</label>
            <select id="filterSource" class="select" style="font-size:13px;">
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
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">TEAM MEMBER</label>
            <select id="filterTeamMember" class="select" style="font-size:13px;">
              <option value="">All Members</option>
              <option value="unassigned">Unassigned</option>
            </select>
          </div>
          ${user.role === 'superadmin' ? `
          <div style="display:flex;flex-direction:column;gap:4px;min-width:150px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">SALES MANAGER</label>
            <select id="filterSalesManager" class="select" style="font-size:13px;">
              <option value="">All Managers</option>
            </select>
          </div>` : ''}
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;border-top:1px solid #e2e8f0;padding-top:10px;margin-top:2px;">
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">📅 LEAD CREATED FROM</label>
            <input type="date" id="filterDateFrom" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">LEAD CREATED TO</label>
            <input type="date" id="filterDateTo" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">🔄 STATUS UPDATED FROM</label>
            <input type="date" id="filterUpdatedFrom" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:130px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">STATUS UPDATED TO</label>
            <input type="date" id="filterUpdatedTo" class="input" style="font-size:13px;padding:7px 10px;" />
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;min-width:120px;flex:1;">
            <label style="font-size:11px;font-weight:600;color:#64748b;letter-spacing:0.05em;">QUICK MONTH</label>
            <select id="filterMonth" class="select" style="font-size:13px;">
              <option value="">All Months</option>
              ${Array.from({length:12},(_,i)=>`<option value="${i}">${new Date(2000,i,1).toLocaleString('default',{month:'long'})}</option>`).join('')}
            </select>
          </div>
        </div>
      </div>
      <div id="leadsContainer"><div style="display:flex;align-items:center;justify-content:center;padding:60px 20px;color:#9ca3af;font-size:14px;"><span style="animation:spin 1s linear infinite;display:inline-block;border:3px solid #e5e7eb;border-top-color:#6366f1;border-radius:50%;width:28px;height:28px;margin-right:12px;"></span>Loading leads…</div></div>
    </div>
  `

  document.getElementById('newLeadBtn').addEventListener('click', openLeadForm)
  document.getElementById('filterStatus').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterProject').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterSource').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterTeamMember').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterDateFrom').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterDateTo').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterUpdatedFrom').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterUpdatedTo').addEventListener('change', filterAndRenderLeads)
  document.getElementById('filterMonth').addEventListener('change', e => {
    const month = e.target.value
    if (month !== '') {
      const now = new Date()
      const year = now.getFullYear()
      const from = new Date(year, parseInt(month), 1)
      const to = new Date(year, parseInt(month) + 1, 0)
      document.getElementById('filterDateFrom').value = from.toISOString().split('T')[0]
      document.getElementById('filterDateTo').value = to.toISOString().split('T')[0]
    } else {
      document.getElementById('filterDateFrom').value = ''
      document.getElementById('filterDateTo').value = ''
    }
    filterAndRenderLeads()
  })
  if (user.role === 'superadmin') {
    const smFilter = document.getElementById('filterSalesManager')
    if (smFilter) smFilter.addEventListener('change', () => {
      updateTeamMemberDropdown(smFilter.value)
      filterAndRenderLeads()
    })
  }
  if (user.role !== 'team_member') {
    document.getElementById('importLeadsBtn').addEventListener('click', openImportModal)
  }
  if (user.role === 'superadmin') {
    document.getElementById('exportLeadsBtn').addEventListener('click', quickExportLeads)
  }

  await Promise.all([loadProjects(), loadUsers(), loadLeads()])

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

function clearLeadsFilters() {
  ['filterStatus','filterProject','filterSource','filterTeamMember','filterSalesManager',
   'filterDateFrom','filterDateTo','filterUpdatedFrom','filterUpdatedTo','filterMonth'].forEach(id => {
    const el = document.getElementById(id)
    if (el) el.value = ''
  })
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

async function filterAndRenderLeads(resetPage = true) {
  if (resetPage) leadsPage = 1
  await loadLeads()

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
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;padding:14px 4px 4px;border-top:1px solid #e2e8f0;margin-top:4px;">
      <div style="font-size:13px;color:#64748b;">
        Showing <strong>${showFrom}–${showTo}</strong> of <strong>${totalLeads}</strong> leads
      </div>
      <div style="display:flex;align-items:center;gap:4px;">
        <button onclick="goToLeadsPage(${leadsPage-1})" ${leadsPage<=1?'disabled':''}
          style="padding:4px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:${leadsPage<=1?'#cbd5e1':'#374151'};font-size:13px;cursor:${leadsPage<=1?'default':'pointer'};">← Prev</button>
        ${pageButtons}
        <button onclick="goToLeadsPage(${leadsPage+1})" ${leadsPage>=totalPages?'disabled':''}
          style="padding:4px 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:${leadsPage>=totalPages?'#cbd5e1':'#374151'};font-size:13px;cursor:${leadsPage>=totalPages?'default':'pointer'};">Next →</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:13px;color:#64748b;">Per page:</span>
        <select onchange="setLeadsPageSize(this.value)" style="border:1px solid #e2e8f0;border-radius:6px;padding:4px 8px;font-size:13px;color:#374151;background:#fff;cursor:pointer;">
          ${[25,50,100,200].map(n => `<option value="${n}" ${leadsPageSize===n?'selected':''}>${n}</option>`).join('')}
          <option value="0" ${leadsPageSize===0?'selected':''}>All</option>
        </select>
      </div>
    </div>`

  const projectMap = {}
  projects.forEach(p => { projectMap[p.id] = p.name })

  const canAssign = user.role === 'superadmin' || user.role === 'sales_manager'
  const canAssignManager = user.role === 'superadmin'
  const assignableManagers = users.filter(u => {
    if (user.role === 'superadmin') return u.role === 'sales_manager'
    return false
  })
  const assignableMembers = user.role === 'superadmin'
    ? users.filter(u => u.role === 'team_member')
    : user.role === 'sales_manager'
      ? [{ id: user.id, name: `${user.name} (me)` }, ...users.filter(u => u.manager_id === user.id)]
      : []

  const VALID_STATUSES_LIST = ['new','attempted','connected','interested','site_visit_planned','site_visit_done','negotiation','booking_done','lost','junk']
  const allChecked = paginated.length > 0 && paginated.every(l => selectedLeads.has(l.id))

  container.innerHTML = `
    <div id="bulkBar" style="display:${selectedLeads.size > 0 ? 'flex' : 'none'};align-items:stretch;gap:0;background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:0;margin-bottom:18px;overflow:hidden;">
      <!-- Identity section -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:6px;padding:12px 16px;background:#e0f2fe;flex-shrink:0;">
        <span style="font-size:12px;font-weight:700;color:#0369a1;letter-spacing:0.06em;white-space:nowrap;">⚡ BULK ACTIONS</span>
        <span id="bulkCount" style="font-size:12px;font-weight:600;color:#0284c7;white-space:nowrap;">${selectedLeads.size} lead${selectedLeads.size !== 1 ? 's' : ''} selected</span>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button onclick="clearLeadSelection()" style="font-size:11px;padding:3px 10px;border:1px solid #7dd3fc;border-radius:20px;background:#fff;color:#0369a1;cursor:pointer;font-weight:500;white-space:nowrap;">✕ Clear</button>
          ${user.role === 'superadmin' ? `<button onclick="bulkDeleteLeads()" style="font-size:11px;padding:3px 10px;border:1px solid #fca5a5;border-radius:20px;background:#fff;color:#ef4444;cursor:pointer;font-weight:500;white-space:nowrap;">🗑 Delete</button>` : ''}
        </div>
      </div>
      <!-- Change Status -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Change Status</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkStatusSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select status —</option>
            ${VALID_STATUSES_LIST.map(s => `<option value="${s}">${s.replace(/_/g,' ')}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkUpdateStatus()" style="padding:6px 14px;font-size:12px;background:#0369a1;white-space:nowrap;flex-shrink:0;">Update</button>
        </div>
      </div>
      <!-- Change Source -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Change Source</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkSourceSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select source —</option>
            ${['Website','Referral','Walk-in','Meta','Google','Email Campaign','Direct','Other','G1','G2','G3','TP'].map(s => `<option value="${s}">${s}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkUpdateSource()" style="padding:6px 14px;font-size:12px;background:#0369a1;white-space:nowrap;flex-shrink:0;">Update</button>
        </div>
      </div>
      ${canAssignManager ? `
      <!-- Assign Manager -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Assign Sales Manager</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkAssignManagerSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select manager —</option>
            <option value="unassign">⊘ Unassign Manager</option>
            ${assignableManagers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkAssignLeads('bulkAssignManagerSelect')" style="padding:6px 14px;font-size:12px;white-space:nowrap;flex-shrink:0;">Assign</button>
        </div>
      </div>
      ` : ''}
      ${canAssign && assignableMembers.length ? `
      <!-- Assign Team Member -->
      <div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:12px 16px;flex:1;min-width:180px;border-left:1px solid #bae6fd;">
        <label style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;">Assign Team Member</label>
        <div style="display:flex;gap:6px;align-items:center;">
          <select id="bulkAssignMemberSelect" class="select" style="flex:1;font-size:12px;padding:6px 8px;">
            <option value="">— Select member —</option>
            <option value="unassign">⊘ Unassign Member</option>
            ${assignableMembers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')}
          </select>
          <button class="button" onclick="bulkAssignLeads('bulkAssignMemberSelect')" style="padding:6px 14px;font-size:12px;white-space:nowrap;flex-shrink:0;">Assign</button>
        </div>
      </div>
      ` : ''}
    </div>
    <div style="overflow-x:auto;">
      <table class="table">
        <thead>
          <tr>
            <th style="width:36px;"><input type="checkbox" id="selectAllLeads" ${allChecked ? 'checked' : ''} onchange="toggleSelectAllLeads(this.checked)" style="cursor:pointer;width:16px;height:16px;"></th>
            <th>Name</th>
            <th>Phone</th>
            <th>Source</th>
            <th>Status</th>
            <th>Project</th>
            <th>Assigned To</th>
            <th>Sales Manager</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${paginated.map(l => `
            <tr class="${selectedLeads.has(l.id) ? 'lead-row-selected' : ''}">
              <td><input type="checkbox" class="lead-checkbox" data-id="${l.id}" ${selectedLeads.has(l.id) ? 'checked' : ''} onchange="toggleSelectLead(${l.id}, this.checked)" style="cursor:pointer;width:16px;height:16px;"></td>
              <td><strong>${escape(l.name)}</strong></td>
              <td>${escape(l.phone || '-')}</td>
              <td>${escape(l.source || '-')}</td>
              <td><span class="tag" style="background:${getStatusColor(l.status)};color:#fff;">${escape(l.status)}</span></td>
              <td>${escape(projectMap[l.project_id] || '-')}</td>
              <td>${escape(l.assigned_to_name || 'Unassigned')}</td>
              <td>${escape(l.sales_manager_name || '-')}</td>
              <td>${new Date(l.created_at).toLocaleDateString()}</td>
              <td>
                <button class="button secondary" onclick="viewLeadDetails(${l.id})" style="font-size:12px;padding:6px 10px;">View</button>
                ${user.role === 'superadmin' ? `<button class="button" onclick="deleteLead(${l.id}, '${escape(l.name)}')" style="font-size:12px;padding:6px 10px;background:#ef4444;margin-left:4px;">Delete</button>` : ''}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    ${paginationBar}
  `

  // Update active date badge in filter bar
  const badge = document.getElementById('leadsActiveDateBadge')
  if (badge) {
    const df = document.getElementById('filterDateFrom')?.value
    const dt = document.getElementById('filterDateTo')?.value
    const uf = document.getElementById('filterUpdatedFrom')?.value
    const ut = document.getElementById('filterUpdatedTo')?.value
    const fmtB = d => new Date(d).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})
    const parts = []
    if (df || dt) parts.push('Created: ' + (df && dt ? `${fmtB(df)} → ${fmtB(dt)}` : df ? `From ${fmtB(df)}` : `Until ${fmtB(dt)}`))
    if (uf || ut) parts.push('Updated: ' + (uf && ut ? `${fmtB(uf)} → ${fmtB(ut)}` : uf ? `From ${fmtB(uf)}` : `Until ${fmtB(ut)}`))
    if (parts.length) { badge.textContent = '📅 ' + parts.join(' · '); badge.style.display = 'inline' }
    else badge.style.display = 'none'
  }

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
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: formData
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
      headers: { Authorization: `Bearer ${token}` }
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


async function viewLeadDetails(leadId) {
  selectedLeadId = leadId
  const lead = leads.find(l => l.id === leadId)
  if (!lead) return
  
  const content = document.getElementById('content')
  
  // Load lead details, notes, and status history
  await loadProjects()
  const [notesRes, historyRes, assignmentRes] = await Promise.all([
    fetch(`${API_BASE}/leads/${leadId}/notes`, { headers: { Authorization: `Bearer ${token}` } }),
    fetch(`${API_BASE}/leads/${leadId}/status-history`, { headers: { Authorization: `Bearer ${token}` } }),
    fetch(`${API_BASE}/leads/${leadId}/assignment-history`, { headers: { Authorization: `Bearer ${token}` } })
  ])
  
  const notesData = await notesRes.json()
  const historyData = await historyRes.json()
  const assignmentData = await assignmentRes.json()
  
  const notes = notesData.notes || []
  const statusHistory = historyData.status_history || []
  const assignmentHistory = assignmentData.assignment_history || []
  
  content.innerHTML = `
    <div class="card" style="max-width:900px;">
      <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:20px;">
        <div>
          <h2>${escape(lead.name)}</h2>
          <p style="color:#64748b;margin:0;">Status: <span class="tag" style="background:${getStatusColor(lead.status)};color:#fff;">${escape(lead.status)}</span></p>
        </div>
        <button class="button secondary" id="closeLead" style="padding:8px 16px;">← Back</button>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
        <div>
          <h3>Lead Information</h3>
          <table class="table" style="margin-top:10px;">
            <tr><td><strong>Phone</strong></td><td>${escape(lead.phone || '-')}</td></tr>
            <tr><td><strong>Email</strong></td><td>${escape(lead.email || '-')}</td></tr>
            <tr><td><strong>Source</strong></td><td>${escape(lead.source || '-')}</td></tr>
            <tr><td><strong>Budget</strong></td><td>${lead.budget_min ? fmtBudget(lead.budget_min) + ' – ' + fmtBudget(lead.budget_max) : '-'}</td></tr>
            <tr><td><strong>Assigned To</strong></td><td>${escape(lead.assigned_to_name || 'Unassigned')}</td></tr>
            <tr><td><strong>Created</strong></td><td>${new Date(lead.created_at).toLocaleDateString()}</td></tr>
          </table>
          
          ${user.role !== 'team_member' ? `
            <div style="margin-top:20px;">
              <h3>Update Status</h3>
              <form id="updateStatusForm" style="display:flex;gap:10px;">
                <select id="newStatus" class="select" style="flex:1;">
                  <option value="new">New</option>
                  <option value="attempted">Attempted</option>
                  <option value="connected">Connected</option>
                  <option value="interested">Interested</option>
                  <option value="site_visit_planned">Site Visit Planned</option>
                  <option value="site_visit_done">Site Visit Done</option>
                  <option value="negotiation">Negotiation</option>
                  <option value="booking_done">Booking Done</option>
                  <option value="lost">Lost</option>
                  <option value="junk">Junk</option>
                </select>
                <button type="submit" class="button">Update</button>
              </form>
            </div>
            <div style="margin-top:16px;">
              <h3>Update Project</h3>
              <form id="updateProjectForm" style="display:flex;gap:10px;">
                <select id="newProject" class="select" style="flex:1;">
                  <option value="">— No Project —</option>
                  ${projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')}
                </select>
                <button type="submit" class="button">Update</button>
              </form>
            </div>
            <div style="margin-top:16px;">
              <h3>Update Source</h3>
              <form id="updateSourceForm" style="display:flex;gap:10px;">
                <select id="newSource" class="select" style="flex:1;">
                  <option value="">— Select Source —</option>
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
                <button type="submit" class="button">Update</button>
              </form>
            </div>
          ` : ''}
          
          ${user.role === 'sales_manager' || user.role === 'superadmin' ? `
            <div style="margin-top:20px;">
              <h3>Assign Lead</h3>
              <form id="assignForm" style="display:flex;flex-direction:column;gap:8px;">
                ${user.role === 'superadmin' ? `<select id="assignToManager" class="select" style="font-size:13px;"><option value="">— Filter by Sales Manager —</option></select>` : ''}
                <div style="display:flex;gap:10px;">
                  <select id="assignTo" class="select" style="flex:1;"></select>
                  <button type="submit" class="button">Assign</button>
                </div>
              </form>
            </div>
          ` : ''}
        </div>
        
        <div>
          <h3>Notes</h3>
          <div id="notesContainer" style="border:1px solid #e2e8f0;border-radius:8px;padding:10px;height:200px;overflow-y:auto;margin-bottom:10px;background:#f8fafc;">
            ${notes.length === 0 ? '<div style="color:#94a3b8;">No notes yet</div>' : notes.map(n => `
              <div style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:13px;">
                <div style="font-weight:bold;color:#0f172a;margin-bottom:2px;">${escape(n.created_by_name || 'Unknown')}</div>
                <div>${escape(n.note)}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:4px;">${new Date(n.created_at).toLocaleDateString()}</div>
              </div>
            `).join('')}
          </div>
          
          <form id="addNoteForm" style="display:flex;gap:8px;">
            <textarea id="noteText" class="input" style="flex:1;height:60px;" placeholder="Add a note..."></textarea>
            <button type="submit" class="button" style="align-self:flex-end;">Add</button>
          </form>
        </div>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
        <div>
          <h3>Status History</h3>
          <div style="border:1px solid #e2e8f0;border-radius:8px;padding:10px;max-height:250px;overflow-y:auto;">
            ${statusHistory.length === 0 ? '<div style="color:#94a3b8;font-size:13px;">No status changes yet</div>' : statusHistory.map(h => `
              <div style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:12px;">
                <div style="font-weight:bold;color:#0f172a;">${escape(h.old_status)} → ${escape(h.new_status)}</div>
                <div style="color:#64748b;font-size:11px;">${escape(h.changed_by_name || 'Unknown')} on ${new Date(h.changed_at).toLocaleDateString()}</div>
              </div>
            `).join('')}
          </div>
        </div>
        
        <div>
          <h3>Assignment History</h3>
          <div style="border:1px solid #e2e8f0;border-radius:8px;padding:10px;max-height:250px;overflow-y:auto;">
            ${assignmentHistory.length === 0 ? '<div style="color:#94a3b8;font-size:13px;">No assignments yet</div>' : assignmentHistory.map(a => `
              <div style="padding:8px;border-bottom:1px solid #e2e8f0;font-size:12px;">
                <div style="font-weight:bold;color:#0f172a;">${escape(a.assigned_from_name || 'Unassigned')} → ${escape(a.assigned_to_name)}</div>
                <div style="color:#64748b;font-size:11px;">${escape(a.assigned_by_name || 'Unknown')} on ${new Date(a.assigned_at).toLocaleDateString()}</div>
                ${a.reason ? `<div style="color:#64748b;font-size:11px;margin-top:4px;">Reason: ${escape(a.reason)}</div>` : ''}
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    </div>
  `
  
  document.getElementById('closeLead').addEventListener('click', renderLeads)
  
  // Set current values in dropdowns
  const newStatusSelect = document.getElementById('newStatus')
  if (newStatusSelect) newStatusSelect.value = lead.status

  const newProjectSelect = document.getElementById('newProject')
  if (newProjectSelect && lead.project_id) newProjectSelect.value = lead.project_id

  const newSourceSelect = document.getElementById('newSource')
  if (newSourceSelect && lead.source) newSourceSelect.value = lead.source

  // Update status handler
  if (document.getElementById('updateStatusForm')) {
    document.getElementById('updateStatusForm').addEventListener('submit', async e => {
      e.preventDefault()
      const newStatus = document.getElementById('newStatus').value
      try {
        await _apiRequest(`/leads/${leadId}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ status: newStatus }),
          retries: 0,
        })
        await loadLeads(true); viewLeadDetails(leadId)
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }

  // Update project handler
  if (document.getElementById('updateProjectForm')) {
    document.getElementById('updateProjectForm').addEventListener('submit', async e => {
      e.preventDefault()
      const projectId = document.getElementById('newProject').value
      try {
        await _apiRequest(`/leads/${leadId}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ project_id: projectId ? parseInt(projectId) : null }),
          retries: 0,
        })
        await loadLeads(true); viewLeadDetails(leadId)
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }

  // Update source handler
  if (document.getElementById('updateSourceForm')) {
    document.getElementById('updateSourceForm').addEventListener('submit', async e => {
      e.preventDefault()
      const source = document.getElementById('newSource').value
      try {
        await _apiRequest(`/leads/${leadId}`, {
          method: 'PUT',
          headers: { ..._apiAuthHeaders(), ..._apiJsonHeaders() },
          body: JSON.stringify({ source }),
          retries: 0,
        })
        await loadLeads(true); viewLeadDetails(leadId)
      } catch (err) { showToast((err.payload && err.payload.error) || err.message, 'error') }
    })
  }
  
  // Add note handler
  if (document.getElementById('addNoteForm')) {
    document.getElementById('addNoteForm').addEventListener('submit', async e => {
      e.preventDefault()
      const noteText = document.getElementById('noteText').value
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
  
  // Assign lead handler
  if (document.getElementById('assignForm')) {
    const assignSelect = document.getElementById('assignTo')
    await loadUsers()

    function updateAssignToOptions(managerId) {
      const allTM = users.filter(u => u.role === 'team_member')
      const filtered = managerId ? allTM.filter(u => String(u.manager_id) === String(managerId)) : allTM
      // If current user is a sales_manager, also include themselves in the list
      const selfOption = (user.role === 'sales_manager')
        ? `<option value="${user.id}">${escape(user.name)} (me)</option>` : ''
      assignSelect.innerHTML = '<option value="">Select team member</option>' + selfOption +
        filtered.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
      if (lead.assigned_to) assignSelect.value = lead.assigned_to
    }

    const mgrFilterSel = document.getElementById('assignToManager')
    if (mgrFilterSel) {
      const managers = users.filter(u => u.role === 'sales_manager')
      mgrFilterSel.innerHTML = '<option value="">— Filter by Sales Manager —</option>' +
        managers.map(u => `<option value="${u.id}">${escape(u.name)}</option>`).join('')
      // Pre-select manager based on currently assigned team member's manager
      const assignedUser = users.find(u => u.id === lead.assigned_to)
      const preManagerId = assignedUser?.manager_id || null
      if (preManagerId) mgrFilterSel.value = preManagerId
      mgrFilterSel.addEventListener('change', () => updateAssignToOptions(mgrFilterSel.value))
      updateAssignToOptions(preManagerId)
    } else {
      // sales_manager: show only own team
      updateAssignToOptions(user.id)
    }

    document.getElementById('assignForm').addEventListener('submit', async e => {
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
          <option value="site_visit_planned">Site Visit Planned</option>
          <option value="site_visit_done">Site Visit Done</option>
          <option value="negotiation">Negotiation</option>
          <option value="booking_done">Booking Done</option>
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
          body: JSON.stringify({ name, phone, email, source, budget_min, budget_max, project_id, status, ...(force && { force: true }) }),
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

