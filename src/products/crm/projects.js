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
  const isCompact = (window.innerWidth || 0) <= 1180

  if (isCompact) {
    container.innerHTML = `
      <div class="projects-grid">
        ${projects.map(p => `
          <article class="project-card">
            <div class="project-card-title">${escape(p.name)}</div>
            <div class="project-card-meta"><strong>Manager:</strong> ${escape(p.created_by_name || '-')}</div>
            <div class="project-card-meta"><strong>Type:</strong> ${escape(p.project_type || '-')}</div>
            <div class="project-card-meta"><strong>Lead Count:</strong> ${Number(p.lead_count || 0)}</div>
            <div class="project-card-meta"><strong>Status:</strong> <span class="tag" style="background:#e0f2fe;color:#075985;">Active</span></div>
            <div class="project-card-actions">
              <button class="button secondary" data-open-id="${p.id}" style="font-size:12px;padding:8px 12px;">Open</button>
              <button class="button secondary" data-assets-id="${p.id}" data-assets-name="${escape(p.name)}" style="font-size:12px;padding:8px 12px;">Assets</button>
              ${user && user.role === 'superadmin' ? `<button class="button secondary" data-id="${p.id}" style="font-size:12px;padding:8px 12px;">Edit</button><button class="button" data-del-id="${p.id}" data-del-name="${escape(p.name)}" style="font-size:12px;padding:8px 12px;background:#ef4444;border-color:#ef4444;">Delete</button>` : ''}
            </div>
          </article>
        `).join('')}
      </div>
    `
  } else {
  
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
            <th>Assets</th>
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
              <td>
                <button class="button secondary" data-assets-id="${p.id}" data-assets-name="${escape(p.name)}" style="font-size:12px;padding:6px 10px;">Assets</button>
              </td>
              ${user && user.role === 'superadmin' ? '<td><button class="button secondary" data-id="' + p.id + '" style="font-size:12px;padding:6px 10px;">Edit</button><button class="button" data-del-id="' + p.id + '" data-del-name="' + escape(p.name) + '" style="font-size:12px;padding:6px 10px;background:#ef4444;border-color:#ef4444;margin-left:4px;">Delete</button></td>' : ''}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
  }

  container.querySelectorAll('button[data-open-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      var p = projects.find(x => x.id === Number(btn.dataset.openId))
      if (!p) return
      showToast('Open project details coming in next update.', 'info')
    })
  })

  container.querySelectorAll('button[data-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = projects.find(x => x.id === Number(btn.dataset.id))
      if (p) openProjectForm(p)
    })
  })

  container.querySelectorAll('button[data-assets-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      openProjectAssetsModal(Number(btn.dataset.assetsId), btn.dataset.assetsName || 'Project')
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

async function openProjectAssetsModal(projectId, projectName) {
  const overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  overlay.id = 'projectAssetsModal'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:920px;width:96%;max-height:88vh;overflow:auto;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h3 class="sm-section-heading" style="margin:0;">Project Assets · ${escape(projectName || '')}</h3>
        <button class="button secondary" onclick="document.getElementById('projectAssetsModal')?.remove()" style="padding:6px 10px;font-size:12px;">Close</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px;">
        <input type="file" id="projectAssetFile" class="input" style="max-width:420px;" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.xlsx,.xls,.doc,.docx,.zip" />
        <button class="button" onclick="uploadProjectAsset(${projectId})" style="font-size:13px;">Upload Asset</button>
      </div>
      <div style="font-size:12px;color:#64748b;margin-bottom:10px;">Supported: PDF, Images, Excel, Word, ZIP</div>
      <div id="projectAssetsList" style="min-height:120px;"></div>
    </div>
  `
  document.body.appendChild(overlay)
  await loadProjectAssets(projectId)
}

async function loadProjectAssets(projectId) {
  const listEl = document.getElementById('projectAssetsList')
  if (!listEl) return
  listEl.innerHTML = '<div class="message">Loading assets…</div>'
  try {
    const data = await _apiRequest(`/projects/${projectId}/assets`, {
      headers: _apiAuthHeaders(),
      retries: 0,
    })
    const assets = data.assets || []
    if (!assets.length) {
      listEl.innerHTML = '<div class="message">No assets uploaded yet.</div>'
      return
    }
    listEl.innerHTML = `
      <div style="overflow-x:auto;">
        <table class="table" style="margin-top:0;">
          <thead>
            <tr>
              <th>File Name</th>
              <th>Uploaded By</th>
              <th>Upload Date</th>
              <th>View</th>
              <th>Download</th>
            </tr>
          </thead>
          <tbody>
            ${assets.map(a => `
              <tr>
                <td>${escape(a.file_name || '-')}</td>
                <td>${escape(a.uploaded_by_name || '-')}</td>
                <td>${a.uploaded_at ? new Date(a.uploaded_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}) : '-'}</td>
                <td><button class="button secondary" onclick="viewProjectAsset(${projectId}, ${a.id})" style="font-size:12px;padding:4px 8px;">View</button></td>
                <td><button class="button" onclick="downloadProjectAsset(${projectId}, ${a.id})" style="font-size:12px;padding:4px 8px;">Download</button></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `
  } catch (err) {
    listEl.innerHTML = `<div class="message error">${escape((err.payload && err.payload.error) || err.message || 'Failed to load assets.')}</div>`
  }
}

async function uploadProjectAsset(projectId) {
  const fileInput = document.getElementById('projectAssetFile')
  const file = fileInput && fileInput.files ? fileInput.files[0] : null
  if (!file) {
    showToast('Select a file first.', 'warning')
    return
  }

  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/assets`, {
      method: 'POST',
      headers: _apiAuthHeaders(),
      body: formData,
    })
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}))
      throw new Error(payload.error || `Upload failed (${res.status})`)
    }
    showToast('Asset uploaded.', 'success')
    if (fileInput) fileInput.value = ''
    await loadProjectAssets(projectId)
  } catch (err) {
    showToast(err.message || 'Upload failed.', 'error')
  }
}

async function viewProjectAsset(projectId, assetId) {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/assets/${assetId}/view`, {
      headers: _apiAuthHeaders(),
    })
    if (!res.ok) throw new Error(`Unable to open file (${res.status})`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (err) {
    showToast(err.message || 'Unable to open file.', 'error')
  }
}

async function downloadProjectAsset(projectId, assetId) {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/assets/${assetId}/download`, {
      headers: _apiAuthHeaders(),
    })
    if (!res.ok) throw new Error(`Unable to download file (${res.status})`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'asset'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 30000)
  } catch (err) {
    showToast(err.message || 'Unable to download file.', 'error')
  }
}

