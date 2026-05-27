// EXPORT LEADS
// ============================================================================

async function renderExportLeads() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card">
      <h2>ðŸ“¥ Export Leads to Excel</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
        <div>
          <h3>Export Options</h3>
          <form id="exportForm">
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">Filter by Status (optional)</label>
              <select id="exportStatus" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;">
                <option value="">All Status</option>
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
            
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">Filter by Project (optional)</label>
              <select id="exportProject" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;">
                <option value="">All Projects</option>
                ${projects.map(p => `<option value="${p.id}">${escape(p.name)}</option>`).join('')}
              </select>
            </div>
            
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">From Date (optional)</label>
              <input type="date" id="exportDateFrom" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;" />
            </div>
            
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">To Date (optional)</label>
              <input type="date" id="exportDateTo" style="display:block;width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;" />
            </div>
            
            <button type="submit" class="button" style="width:100%;">ðŸ“¥ Export to Excel</button>
          </form>
        </div>
        
        <div>
          <h3>Export Information</h3>
          <ul style="list-style:none;padding:0;color:#475569;">
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Format:</strong>
              <div style="font-size:12px;color:#94a3b8;">Microsoft Excel (.xlsx)</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Included Columns:</strong>
              <div style="font-size:12px;color:#94a3b8;">ID, Name, Phone, Email, Source, Status, Project, Assigned To, Budget Min/Max, Created Date, Created By</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Summary Sheet:</strong>
              <div style="font-size:12px;color:#94a3b8;">Automatic status breakdown included</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>Filtering:</strong>
              <div style="font-size:12px;color:#94a3b8;">Role-based (you only see your visible leads)</div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  `
  
  await loadProjects()
  
  document.getElementById('exportForm').addEventListener('submit', handleExportLeads)
}

async function handleExportLeads(e) {
  e.preventDefault()
  
  const status = document.getElementById('exportStatus')?.value
  const projectId = document.getElementById('exportProject')?.value
  const dateFrom = document.getElementById('exportDateFrom')?.value
  const dateTo = document.getElementById('exportDateTo')?.value
  
  let query = '/leads/export/excel?'
  const params = []
  
  if (status) params.push(`status=${status}`)
  if (projectId) params.push(`project_id=${projectId}`)
  if (dateFrom) params.push(`date_from=${dateFrom}`)
  if (dateTo) params.push(`date_to=${dateTo}`)
  
  query += params.join('&')
  
  try {
    const res = await fetch(`${API_BASE}${query}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (!res.ok) {
      showToast('Export failed. Please try again.', 'error')
      return
    }
    
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `leads_export_${new Date().getTime()}.xlsx`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    showToast('Export successful!', 'success')
  } catch (err) {
    showToast('Error exporting: ' + err.message, 'error')
  }
}

