// EXCEL IMPORT
// ============================================================================

async function renderExcelUpload() {
  const content = document.getElementById('content')
  if (!content) return
  content.innerHTML = `
    <div class="card">
      <h2 class="sm-page-title" style="margin-bottom:20px;">📤 Bulk Import Leads from Excel</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
        <div>
          <h3 class="sm-section-heading" style="margin-bottom:16px;">Import File</h3>
          <form id="uploadForm">
            <div style="margin-bottom:15px;">
              <label style="display:block;font-weight:600;margin-bottom:8px;">Select Excel File (.xlsx, .xls, .csv)</label>
              <input type="file" id="excelFile" accept=".xlsx,.xls,.csv" required style="display:block;margin-bottom:10px;padding:10px;border:1px solid #cbd5e1;border-radius:6px;width:100%;box-sizing:border-box;" />
              <small style="color:#64748b;">Maximum file size: 5MB</small>
            </div>
            <button type="submit" class="sm-btn sm-btn-primary" style="width:100%;margin-bottom:10px;">📤 Upload File</button>
            <button type="button" class="sm-btn sm-btn-secondary" id="downloadTemplate" style="width:100%;">⬇️ Download Template</button>
          </form>
        </div>
        
        <div>
          <h3 class="sm-section-heading" style="margin-bottom:16px;">Required Columns</h3>
          <ul style="list-style:none;padding:0;color:#475569;">
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>name</strong>
              <div style="font-size:12px;color:#94a3b8;">Lead name (REQUIRED)</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>phone</strong>
              <div style="font-size:12px;color:#94a3b8;">Contact number</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>email</strong>
              <div style="font-size:12px;color:#94a3b8;">Email address</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>source</strong>
              <div style="font-size:12px;color:#94a3b8;">Lead source (e.g., Website)</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>status</strong>
              <div style="font-size:12px;color:#94a3b8;">new, attempted, connected, interested, site_visit_planned, site_visit_done, negotiation, booking_done, lost, junk</div>
            </li>
            <li style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
              <strong>assigned_to_email</strong>
              <div style="font-size:12px;color:#94a3b8;">Email of team member</div>
            </li>
          </ul>
        </div>
      </div>
      
      <div id="importResult" style="margin-top:30px;"></div>
    </div>
  `
  
  document.getElementById('uploadForm').addEventListener('submit', handleExcelUpload)
  document.getElementById('downloadTemplate').addEventListener('click', downloadExcelTemplate)
}

async function handleExcelUpload(e) {
  e.preventDefault()
  const fileInput = document.getElementById('excelFile')
  const file = fileInput.files[0]
  
  if (!file) {
    showToast('Please select a file', 'warning')
    return
  }
  
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    const res = await fetch(`${API_BASE}/leads/import/excel`, {
      method: 'POST',
      headers: _apiAuthHeaders(),
      body: formData
    })
    
    const data = await res.json()
    
    if (!res.ok) {
      showImportResult({
        success: 0,
        failed: 0,
        total: 0,
        errors: [{ row: 1, error: data.error || 'Upload failed' }],
        imported_leads: []
      }, false)
      return
    }
    
    showImportResult(data, res.ok)
    if (res.ok) {
      fileInput.value = ''
      await loadLeads(true) // Refresh leads (force bypass cache after import)
    }
  } catch (err) {
    showImportResult({
      success: 0,
      failed: 0,
      total: 0,
      errors: [{ row: 1, error: err.message }],
      imported_leads: []
    }, false)
  }
}

function showImportResult(data, success) {
  const resultDiv = document.getElementById('importResult')
  
  if (!success) {
    resultDiv.innerHTML = `
      <div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:6px;padding:16px;color:#7f1d1d;">
        <h3 class="sm-section-heading" style="margin-bottom:10px;">❌ Import Failed</h3>
        <p>${data.errors[0]?.error || 'An error occurred'}</p>
      </div>
    `
    return
  }
  
  const downloadBtn = data.report_b64
    ? `<button onclick="downloadImportReport()" style="margin-top:16px;padding:10px 20px;background:#1e3a5f;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;">📥 Download Import Report (.xlsx)</button>`
    : ''

  // Store b64 for the download handler
  window._importReportB64 = data.report_b64 || null

  let resultHtml = `
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:16px;color:#166534;">
      <h3 class="sm-section-heading" style="margin-bottom:10px;">✅ Import Complete</h3>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px;">
        <div style="padding:12px;background:#dcfce7;border-radius:4px;">
          <div style="font-size:12px;color:#6b7280;">Successfully Imported</div>
          <div style="font-size:24px;font-weight:bold;color:#16a34a;">${data.success}</div>
        </div>
        <div style="padding:12px;background:#fee2e2;border-radius:4px;">
          <div style="font-size:12px;color:#6b7280;">Failed</div>
          <div style="font-size:24px;font-weight:bold;color:#dc2626;">${data.failed}</div>
        </div>
        <div style="padding:12px;background:#dbeafe;border-radius:4px;">
          <div style="font-size:12px;color:#6b7280;">Total Rows</div>
          <div style="font-size:24px;font-weight:bold;color:#2563eb;">${data.total}</div>
        </div>
      </div>
  `
  
  if (data.errors && data.errors.length > 0) {
    resultHtml += `
      <h4 style="margin:20px 0 10px 0;color:#991b1b;">Errors (${data.errors.length}):</h4>
      <div style="max-height:300px;overflow-y:auto;background:#fff;border:1px solid #fca5a5;border-radius:4px;padding:12px;">
        <ul style="margin:0;padding-left:20px;">
          ${data.errors.map(err => `<li style="margin:5px 0;font-size:13px;"><strong>Row ${err.row}:</strong> ${escape(err.error)}</li>`).join('')}
        </ul>
      </div>
    `
  }

  resultHtml += downloadBtn
  resultHtml += '</div>'
  resultDiv.innerHTML = resultHtml
}

function downloadImportReport() {
  if (!window._importReportB64) return
  const byteChars = atob(window._importReportB64)
  const byteNums = new Array(byteChars.length)
  for (let i = 0; i < byteChars.length; i++) byteNums[i] = byteChars.charCodeAt(i)
  const blob = new Blob([new Uint8Array(byteNums)], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `import_report_${new Date().toISOString().slice(0,10)}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

async function downloadExcelTemplate() {
  try {
    const res = await fetch(`${API_BASE}/leads/import/template`, {
      headers: _apiAuthHeaders()
    })
    
    if (!res.ok) {
      showToast('Failed to download template', 'error')
      return
    }
    
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'lead_import_template.xlsx'
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (err) {
    showToast('Error downloading template: ' + err.message, 'error')
  }
}

