// ============================================================================
// PROJECTS
// ============================================================================

var _projectsRenderId = 0

async function renderProjects() {
  var myId = ++_projectsRenderId
  const content = document.getElementById('content')
  if (!content) return
  content.innerHTML = `
    <div class="card">
      <div class="header">
        <h2>Projects</h2>
        ${user && user.role === 'superadmin' ? '<button class="sm-btn sm-btn-primary" id="newProjectBtn">+ New Project</button>' : ''}
      </div>
      <div id="projectsContainer"></div>
    </div>
  `
  
  const newProjBtn = document.getElementById('newProjectBtn')
  if (newProjBtn) newProjBtn.addEventListener('click', openProjectForm)
  
  await loadProjects()
  if (myId !== _projectsRenderId) return

  const container = document.getElementById('projectsContainer')
  if (!container) return
  if (projects.length === 0) {
    container.innerHTML = '<div class="message">No projects found</div>'
    return
  }
  
  container.innerHTML = `
    <div style="overflow-x:auto;">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Location</th>
            <th>Developer</th>
            <th>Type</th>
            <th>Budget Range</th>
            <th>Created By</th>
            ${user && user.role === 'superadmin' ? '<th>Actions</th>' : ''}
          </tr>
        </thead>
        <tbody>
          ${projects.map(p => `
            <tr>
              <td><strong>${escape(p.name)}</strong></td>
              <td>${escape(p.location || '-')}</td>
              <td>${escape(p.developer || '-')}</td>
              <td>${escape(p.project_type || '-')}</td>
              <td>${p.budget_min ? fmtBudget(p.budget_min) + ' – ' + fmtBudget(p.budget_max) : '-'}</td>
              <td>${escape(p.created_by_name || '-')}</td>
              ${user && user.role === 'superadmin' ? '<td><button class="button secondary" data-id="' + p.id + '" style="font-size:12px;padding:6px 10px;">Edit</button><button class="button" data-del-id="' + p.id + '" data-del-name="' + escape(p.name) + '" style="font-size:12px;padding:6px 10px;background:#ef4444;border-color:#ef4444;margin-left:4px;">Delete</button></td>' : ''}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `

  container.querySelectorAll('button[data-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = projects.find(x => x.id === Number(btn.dataset.id))
      if (p) openProjectForm(p)
    })
  })

  container.querySelectorAll('button[data-del-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!await confirmDialog('Delete project &quot;' + escape(btn.dataset.delName) + '&quot;? This cannot be undone.', 'Delete')) return
      const res = await fetch(`${API_BASE}/projects/${btn.dataset.delId}`, {
        method: 'DELETE',
        headers: _apiAuthHeaders()
      })
      if (res.ok) renderProjects()
      else showToast('Error deleting project', 'error')
    })
  })
}

async function openProjectForm(project = null) {
  const isEdit = project !== null
  const content = document.getElementById('content')
  if (!content) return
  const budgetVal = (project && project.budget_min && project.budget_max)
    ? `${project.budget_min}|${project.budget_max}` : ''
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2 class="sm-section-heading" style="margin-bottom:20px;">${isEdit ? 'Edit Project' : 'New Project'}</h2>
      <form id="projectForm">
        <input class="input" id="projName" placeholder="Project Name" required value="${isEdit ? escape(project.name) : ''}" />
        <input class="input" id="projLocation" placeholder="Location" value="${isEdit ? escape(project.location || '') : ''}" />
        <input class="input" id="projDeveloper" placeholder="Developer Name" value="${isEdit ? escape(project.developer || '') : ''}" />
        <input class="input" id="projType" placeholder="Project Type" value="${isEdit ? escape(project.project_type || '') : ''}" />
        <textarea class="input" id="projDescription" placeholder="Description" style="height:80px;">${isEdit ? escape(project.description || '') : ''}</textarea>
        
        <label style="font-size:13px;color:#64748b;margin-bottom:4px;display:block;">Budget Range (₹ Cr)</label>
        <select class="select" id="projBudget">
          ${budgetRangeOptions(project ? project.budget_min : null, project ? project.budget_max : null)}
        </select>
        
        <div style="display:flex;gap:10px;margin-top:20px;">
          <button type="submit" class="button">${isEdit ? 'Update Project' : 'Save Project'}</button>
          <button type="button" class="button secondary" id="cancelProject">Cancel</button>
        </div>
      </form>
    </div>
  `

  // Pre-select dropdown for existing project if value matches an option
  if (budgetVal) {
    const sel = document.getElementById('projBudget')
    const opt = Array.from(sel.options).find(o => o.value === budgetVal)
    if (opt) opt.selected = true
  }
  
  document.getElementById('projectForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = document.getElementById('projName').value
    const location = document.getElementById('projLocation').value
    const developer = document.getElementById('projDeveloper').value
    const project_type = document.getElementById('projType').value
    const description = document.getElementById('projDescription').value
    const budgetParts = (document.getElementById('projBudget').value || '').split('|')
    const budget_min = Number(budgetParts[0]) || null
    const budget_max = Number(budgetParts[1]) || null
    
    const url = isEdit ? `${API_BASE}/projects/${project.id}` : `${API_BASE}/projects`
    const method = isEdit ? 'PUT' : 'POST'
    const res = await fetch(url, {
      method,
      headers: Object.assign({ 'Content-Type': 'application/json' }, _apiAuthHeaders()),
      body: JSON.stringify({ name, location, developer, project_type, description, budget_min, budget_max })
    })
    if (res.ok) renderProjects()
  })
  
  document.getElementById('cancelProject').addEventListener('click', renderProjects)
}

