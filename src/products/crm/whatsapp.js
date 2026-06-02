// whatsapp.js — WhatsApp modal, template library, asset sharing, activity logging
// Loaded globally; called from leads.js, action-board.js, pipeline.js, recycle-queue.js

/* eslint-disable no-unused-vars */

var _waTemplatesCache = null
var _waTemplatesCacheTid = null

const WA_ASSET_TYPE_LABELS = {
  brochure: 'Brochure',
  price_list: 'Price List',
  floor_plan: 'Floor Plan',
  payment_plan: 'Payment Plan',
  location_map: 'Location Map',
  gallery_pdf: 'Gallery PDF',
  custom_pdf: 'Custom PDF',
}

const WA_ASSET_TYPES = Object.keys(WA_ASSET_TYPE_LABELS)

// ── Helpers ────────────────────────────────────────────────────────────────

function _waClean(num) {
  // Remove all non-digit chars, normalise to full international number (no leading 0, no +)
  const digits = (num || '').replace(/\D/g, '')
  if (!digits) return ''
  // 10-digit Indian mobile: prefix 91
  if (digits.length === 10) return '91' + digits
  // 11-digit with leading 0 (Indian trunk: 0XXXXXXXXXX): strip 0, prefix 91
  if (digits.length === 11 && digits[0] === '0') return '91' + digits.slice(1)
  return digits
}

function _waBuildMessage(template, lead) {
  if (!template) return ''
  let msg = template.body_text || ''
  const vars = {
    lead_name: lead.name || '',
    agent_name: (window._currentUser && window._currentUser.name) || '',
    company_name: (window._tenantConfig && window._tenantConfig.brand_name) || 'us',
    project_name: lead.project_name || '',
    location: '',
    budget_min: lead.budget_min ? String(lead.budget_min) : '',
    budget_max: lead.budget_max ? String(lead.budget_max) : '',
  }
  Object.keys(vars).forEach(k => {
    msg = msg.replace(new RegExp('{{' + k + '}}', 'g'), vars[k])
  })
  return msg
}

async function _waFetchTemplates() {
  try {
    const data = await _apiRequest('/whatsapp/templates', { headers: _apiAuthHeaders(), retries: 0 })
    _waTemplatesCache = data.templates || []
  } catch (_) {
    _waTemplatesCache = []
  }
  return _waTemplatesCache
}

async function _waFetchProjectAssets(projectId) {
  if (!projectId) return []
  try {
    const data = await _apiRequest(`/projects/${projectId}/assets`, { headers: _apiAuthHeaders(), retries: 0 })
    return data.assets || []
  } catch (_) {
    return []
  }
}

async function _waLogActivity(leadId, payload) {
  try {
    await _apiRequest('/whatsapp/log', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, _apiAuthHeaders()),
      body: JSON.stringify({ lead_id: leadId, ...payload }),
      retries: 0,
    })
  } catch (_) {
    // Silent — logging failure must not block the WA launch
  }
}

// ── Main entry point: open the WhatsApp modal ─────────────────────────────

async function openWhatsAppModal(leadId, phone, alternatePhone, leadName, projectId) {
  const existingModal = document.getElementById('waModal')
  if (existingModal) existingModal.remove()

  const waNumber = _waClean(alternatePhone || phone || '')
  const displayPhone = phone || ''
  const displayAlt = alternatePhone || ''

  // Load templates + assets in parallel
  const [templates, assets] = await Promise.all([
    _waFetchTemplates(),
    _waFetchProjectAssets(projectId || null),
  ])

  const overlay = document.createElement('div')
  overlay.id = 'waModal'
  overlay.className = 'modal-overlay'
  overlay.style.cssText = 'z-index:9999;'

  const templateOptions = templates.length
    ? templates.map(t => `<option value="${t.id}" data-body="${escape(t.body_text || '')}" data-name="${escape(t.name || '')}">${escape(t.name)}</option>`).join('')
    : '<option value="">— No templates yet —</option>'

  const hasAssets = assets.length > 0
  const assetRows = hasAssets
    ? assets.map(a => {
        const typeLabel = WA_ASSET_TYPE_LABELS[a.asset_type] || a.asset_type || 'File'
        const sizekb = a.file_size ? Math.ceil(a.file_size / 1024) + ' KB' : ''
        return `
          <label style="display:flex;align-items:center;gap:8px;padding:6px 8px;border:1px solid #e2e8f0;border-radius:6px;cursor:pointer;margin-bottom:4px;font-size:12px;">
            <input type="checkbox" class="wa-asset-chk" value="${a.id}" data-name="${escape(a.file_name || '')}" style="width:14px;height:14px;cursor:pointer;" />
            <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escape(a.file_name || '')}">${escape(a.file_name || '')}</span>
            <span style="background:#f1f5f9;color:#64748b;font-size:10px;font-weight:600;padding:2px 6px;border-radius:10px;flex-shrink:0;">${escape(typeLabel)}</span>
            ${sizekb ? `<span style="color:#94a3b8;font-size:10px;flex-shrink:0;">${escape(sizekb)}</span>` : ''}
          </label>`
      }).join('')
    : '<div style="color:#94a3b8;font-size:12px;padding:6px 0;">No assets available for this project.</div>'

  overlay.innerHTML = `
    <div class="modal-box" style="max-width:560px;width:96%;max-height:90vh;overflow:auto;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3 class="sm-section-heading" style="margin:0;display:flex;align-items:center;gap:8px;">
          <span style="background:#25d366;color:#fff;border-radius:8px;padding:4px 8px;font-size:13px;">WhatsApp</span>
          <span style="font-size:15px;">${escape(leadName || 'Lead')}</span>
        </h3>
        <button onclick="document.getElementById('waModal')?.remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:#64748b;padding:4px;">×</button>
      </div>

      <!-- Phone selection -->
      <div style="margin-bottom:14px;">
        <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:6px;">Send to</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          ${displayPhone ? `<label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;">
            <input type="radio" name="waPhone" value="${escape(displayPhone)}" data-type="primary" checked style="cursor:pointer;" />
            <span>Primary: ${escape(displayPhone)}</span>
          </label>` : ''}
          ${displayAlt ? `<label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;">
            <input type="radio" name="waPhone" value="${escape(displayAlt)}" data-type="alternate" style="cursor:pointer;" />
            <span>Alternate: ${escape(displayAlt)}</span>
          </label>` : ''}
          ${!displayPhone && !displayAlt ? '<span style="color:#ef4444;font-size:13px;">No phone number available.</span>' : ''}
        </div>
      </div>

      <!-- Template selection -->
      <div style="margin-bottom:14px;">
        <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:6px;">Message Template</div>
        <select id="waTemplateSelect" class="select" style="margin-bottom:8px;font-size:13px;">
          <option value="">— Select a template (optional) —</option>
          ${templateOptions}
        </select>
        <textarea id="waMessageText" class="input" placeholder="Type your message here or select a template above…" style="height:120px;font-size:13px;resize:vertical;"></textarea>
      </div>

      <!-- Asset selection -->
      ${hasAssets ? `
      <div style="margin-bottom:14px;">
        <div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:6px;">Share Documents</div>
        <div id="waAssetList" style="max-height:160px;overflow-y:auto;">
          ${assetRows}
        </div>
        <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Selected documents will be noted in the activity log. Attach them manually in WhatsApp.</div>
      </div>` : ''}

      <!-- Actions -->
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
        <button id="waLaunchBtn" class="button" style="background:#25d366;border:none;font-size:13px;flex:1;min-width:140px;" ${!displayPhone && !displayAlt ? 'disabled' : ''}>
          Open WhatsApp
        </button>
        <button onclick="document.getElementById('waModal')?.remove()" class="button secondary" style="font-size:13px;">Cancel</button>
      </div>
    </div>
  `

  document.body.appendChild(overlay)

  // Template select → populate message
  const templateSel = document.getElementById('waTemplateSelect')
  const msgArea = document.getElementById('waMessageText')
  if (templateSel) {
    templateSel.addEventListener('change', () => {
      const opt = templateSel.options[templateSel.selectedIndex]
      if (!opt || !opt.value) { if (msgArea) msgArea.value = ''; return }
      const tmpl = templates.find(t => String(t.id) === String(opt.value))
      if (tmpl && msgArea) {
        const leadObj = { name: leadName }
        msgArea.value = _waBuildMessage(tmpl, leadObj)
      }
    })
  }

  // Launch button
  const launchBtn = document.getElementById('waLaunchBtn')
  if (launchBtn) {
    launchBtn.addEventListener('click', async () => {
      const phoneRadio = overlay.querySelector('input[name="waPhone"]:checked')
      const selectedPhone = phoneRadio ? phoneRadio.value : (displayPhone || displayAlt || '')
      const phoneType = phoneRadio ? (phoneRadio.dataset.type || 'primary') : 'primary'
      const cleanNum = _waClean(selectedPhone)
      const msgText = (msgArea ? msgArea.value : '').trim()

      // Collect selected assets
      const selectedAssets = []
      overlay.querySelectorAll('.wa-asset-chk:checked').forEach(chk => {
        selectedAssets.push(Number(chk.value))
      })

      const templateSel = document.getElementById('waTemplateSelect')
      const templateId = templateSel && templateSel.value ? Number(templateSel.value) : null
      const templateName = templateId
        ? (templates.find(t => t.id === templateId) || {}).name || null
        : null

      // Log activity first (non-blocking)
      _waLogActivity(leadId, {
        template_id: templateId,
        template_name: templateName,
        phone_used: selectedPhone,
        phone_type: phoneType,
        documents_shared: selectedAssets,
        message_preview: msgText.slice(0, 500),
      })

      // Mobile: open native WhatsApp app via wa.me
      // Desktop: open/reuse a named WhatsApp Web tab
      if (cleanNum) {
        const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
        const waUrl = isMobile
          ? `https://wa.me/${cleanNum}` + (msgText ? `?text=${encodeURIComponent(msgText)}` : '')
          : `https://web.whatsapp.com/send?phone=${cleanNum}` + (msgText ? `&text=${encodeURIComponent(msgText)}` : '')
        isMobile ? window.open(waUrl, '_blank', 'noopener') : window.open(waUrl, 'sm_whatsapp_tab')
      } else {
        showToast('No valid phone number to open WhatsApp.', 'warning')
        return
      }

      document.getElementById('waModal')?.remove()
    })
  }
}

// ── Admin: Template Library ────────────────────────────────────────────────

async function openWaTemplateLibrary() {
  const existingModal = document.getElementById('waTemplateLibraryModal')
  if (existingModal) existingModal.remove()

  const overlay = document.createElement('div')
  overlay.id = 'waTemplateLibraryModal'
  overlay.className = 'modal-overlay'
  overlay.style.cssText = 'z-index:9998;'
  overlay.innerHTML = `
    <div class="modal-box" style="max-width:820px;width:96%;max-height:92vh;overflow:auto;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3 class="sm-section-heading" style="margin:0;">WhatsApp Template Library</h3>
        <div style="display:flex;gap:8px;">
          <button class="button" onclick="_waOpenNewTemplateForm()" style="font-size:12px;padding:7px 12px;">+ New Template</button>
          <button onclick="document.getElementById('waTemplateLibraryModal')?.remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:#64748b;padding:4px;">×</button>
        </div>
      </div>
      <div id="waTemplateLibraryList"><div class="message">Loading…</div></div>
    </div>
  `
  document.body.appendChild(overlay)
  await _waLoadTemplateLibrary()
}

async function _waLoadTemplateLibrary() {
  const listEl = document.getElementById('waTemplateLibraryList')
  if (!listEl) return
  listEl.innerHTML = '<div class="message">Loading…</div>'
  try {
    const data = await _apiRequest('/whatsapp/templates/all', { headers: _apiAuthHeaders(), retries: 0 })
    const templates = data.templates || []
    _waTemplatesCache = templates.filter(t => t.is_active)

    if (!templates.length) {
      listEl.innerHTML = '<div class="message">No templates yet. Click "+ New Template" to add one.</div>'
      return
    }
    listEl.innerHTML = `
      <table class="table" style="margin-top:0;">
        <thead><tr>
          <th>#</th>
          <th>Name</th>
          <th>Category</th>
          <th>Status</th>
          <th style="min-width:220px;">Preview</th>
          <th>Actions</th>
        </tr></thead>
        <tbody>
          ${templates.map((t, i) => `
            <tr style="${t.is_active ? '' : 'opacity:0.5;'}">
              <td style="color:#94a3b8;font-size:11px;text-align:center;">${t.sort_order}</td>
              <td style="font-weight:600;font-size:13px;">${escape(t.name)}</td>
              <td><span style="background:#f1f5f9;color:#475569;font-size:11px;font-weight:600;padding:2px 7px;border-radius:10px;">${escape(t.category)}</span></td>
              <td><span style="background:${t.is_active ? '#dcfce7' : '#fee2e2'};color:${t.is_active ? '#166534' : '#991b1b'};font-size:11px;font-weight:700;padding:2px 7px;border-radius:10px;">${t.is_active ? 'Active' : 'Inactive'}</span></td>
              <td style="font-size:11px;color:#64748b;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escape(t.body_text || '')}">${escape((t.body_text || '').slice(0, 80))}${(t.body_text || '').length > 80 ? '…' : ''}</td>
              <td>
                <div style="display:flex;gap:4px;">
                  <button class="button secondary" onclick="_waOpenEditTemplateForm(${t.id})" style="font-size:11px;padding:4px 8px;">Edit</button>
                  ${t.is_active ? `<button class="button" onclick="_waDeleteTemplate(${t.id})" style="font-size:11px;padding:4px 8px;background:#fee2e2;color:#991b1b;border-color:#fca5a5;">Delete</button>` : ''}
                </div>
              </td>
            </tr>`).join('')}
        </tbody>
      </table>`
  } catch (err) {
    listEl.innerHTML = `<div class="message error">${escape((err.payload && err.payload.error) || err.message || 'Failed to load templates.')}</div>`
  }
}

function _waOpenNewTemplateForm() {
  _waOpenTemplateForm(null)
}

async function _waOpenEditTemplateForm(templateId) {
  try {
    const data = await _apiRequest('/whatsapp/templates/all', { headers: _apiAuthHeaders(), retries: 0 })
    const tmpl = (data.templates || []).find(t => t.id === templateId)
    if (tmpl) _waOpenTemplateForm(tmpl)
  } catch (_) {
    showToast('Unable to load template.', 'error')
  }
}

function _waOpenTemplateForm(template) {
  const existingForm = document.getElementById('waTemplateFormModal')
  if (existingForm) existingForm.remove()

  const isEdit = !!template
  const overlay = document.createElement('div')
  overlay.id = 'waTemplateFormModal'
  overlay.className = 'modal-overlay'
  overlay.style.cssText = 'z-index:10000;'

  const categoryOptions = [
    'greeting', 'property_intro', 'follow_up', 'site_visit_invite',
    'price_offer', 'payment_plan', 'booking_confirmation',
    'callback_reminder', 'document_share', 'general',
  ].map(c => `<option value="${c}" ${isEdit && template.category === c ? 'selected' : ''}>${c.replace(/_/g, ' ')}</option>`).join('')

  overlay.innerHTML = `
    <div class="modal-box" style="max-width:560px;width:96%;max-height:90vh;overflow:auto;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3 class="sm-section-heading" style="margin:0;">${isEdit ? 'Edit Template' : 'New Template'}</h3>
        <button onclick="document.getElementById('waTemplateFormModal')?.remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:#64748b;padding:4px;">×</button>
      </div>
      <form id="waTemplateForm">
        <div style="margin-bottom:10px;">
          <label style="font-size:12px;font-weight:600;color:#475569;display:block;margin-bottom:4px;">Template Name</label>
          <input class="input" id="waTplName" placeholder="e.g. Initial Greeting" value="${isEdit ? escape(template.name || '') : ''}" required />
        </div>
        <div style="margin-bottom:10px;">
          <label style="font-size:12px;font-weight:600;color:#475569;display:block;margin-bottom:4px;">Category</label>
          <select class="select" id="waTplCategory">${categoryOptions}</select>
        </div>
        <div style="margin-bottom:10px;">
          <label style="font-size:12px;font-weight:600;color:#475569;display:block;margin-bottom:4px;">Sort Order</label>
          <input class="input" id="waTplSort" type="number" min="1" max="999" value="${isEdit ? (template.sort_order || 99) : 99}" style="width:100px;" />
        </div>
        <div style="margin-bottom:10px;">
          <label style="font-size:12px;font-weight:600;color:#475569;display:block;margin-bottom:4px;">
            Message Body
            <span style="font-weight:400;color:#94a3b8;margin-left:6px;">Use {{lead_name}}, {{agent_name}}, {{project_name}}, {{company_name}}, {{budget_min}}, {{budget_max}} as variables</span>
          </label>
          <textarea class="input" id="waTplBody" placeholder="Hi {{lead_name}}, …" style="height:160px;resize:vertical;font-size:13px;">${isEdit ? escape(template.body_text || '') : ''}</textarea>
        </div>
        ${isEdit ? `
        <div style="margin-bottom:14px;">
          <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">
            <input type="checkbox" id="waTplActive" ${template.is_active ? 'checked' : ''} style="width:15px;height:15px;cursor:pointer;" />
            Active (visible in WA modal)
          </label>
        </div>` : ''}
        <div style="display:flex;gap:8px;margin-top:4px;">
          <button type="submit" class="button" style="flex:1;font-size:13px;">${isEdit ? 'Save Changes' : 'Create Template'}</button>
          <button type="button" onclick="document.getElementById('waTemplateFormModal')?.remove()" class="button secondary" style="font-size:13px;">Cancel</button>
        </div>
      </form>
    </div>
  `
  document.body.appendChild(overlay)

  document.getElementById('waTemplateForm').addEventListener('submit', async e => {
    e.preventDefault()
    const name = (document.getElementById('waTplName').value || '').trim()
    const category = document.getElementById('waTplCategory').value
    const sort_order = parseInt(document.getElementById('waTplSort').value, 10) || 99
    const body_text = (document.getElementById('waTplBody').value || '').trim()
    const is_active = isEdit ? document.getElementById('waTplActive').checked : true

    if (!name || !body_text) {
      showToast('Name and message body are required.', 'warning')
      return
    }

    const payload = { name, category, body_text, sort_order, is_active }
    const url = isEdit ? `/whatsapp/templates/${template.id}` : '/whatsapp/templates'
    const method = isEdit ? 'PUT' : 'POST'

    try {
      await _apiRequest(url, {
        method,
        headers: Object.assign({ 'Content-Type': 'application/json' }, _apiAuthHeaders()),
        body: JSON.stringify(payload),
        retries: 0,
      })
      showToast(isEdit ? 'Template updated.' : 'Template created.', 'success')
      document.getElementById('waTemplateFormModal')?.remove()
      _waTemplatesCache = null  // invalidate cache
      await _waLoadTemplateLibrary()
    } catch (err) {
      showToast((err.payload && err.payload.error) || 'Save failed.', 'error')
    }
  })
}

async function _waDeleteTemplate(templateId) {
  if (!await confirmDialog('Deactivate this template? It will no longer appear in the WhatsApp modal.', 'Deactivate')) return
  try {
    await _apiRequest(`/whatsapp/templates/${templateId}`, {
      method: 'DELETE',
      headers: _apiAuthHeaders(),
      retries: 0,
    })
    showToast('Template deactivated.', 'success')
    _waTemplatesCache = null
    await _waLoadTemplateLibrary()
  } catch (err) {
    showToast((err.payload && err.payload.error) || 'Delete failed.', 'error')
  }
}
