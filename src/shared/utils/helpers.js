// ============================================================================
// SHARED UTILITY FUNCTIONS
// ============================================================================

function getRoleDisplay(role) {
  const roles = {
    'superadmin': '🔐 Super Admin',
    'sales_manager': '💼 Sales Manager',
    'team_member': '👤 Team Member',
    'platform_owner': '🌐 Platform Owner',
  }
  return roles[role] || role
}

function getStatusColor(status) {
  const colors = {
    'new': '#3b82f6',
    'attempted': '#f59e0b',
    'connected': '#10b981',
    'interested': '#8b5cf6',
    'site_visit_planned': '#f97316',
    'site_visit_done': '#06b6d4',
    'negotiation': '#ec4899',
    'booking_done': '#22c55e',
    'lost': '#ef4444',
    'junk': '#6b7280'
  }
  return colors[status] || '#6b7280'
}


function fmtBudget(val) {
  if (!val) return '?'
  if (val >= 10000000) return '₹' + (val / 10000000).toFixed(1) + ' Cr'
  if (val >= 100000) return '₹' + (val / 100000).toFixed(1) + ' L'
  return '₹' + val
}

function budgetRangeOptions(selMin, selMax) {
  let opts = '<option value="">Select Budget Range</option>'
  for (let i = 0.5; i < 10; i = Math.round((i + 0.5) * 10) / 10) {
    const lo = i
    const hi = Math.round((i + 0.5) * 10) / 10
    const min = Math.round(lo * 1e7)
    const max = Math.round(hi * 1e7)
    const label = `₹${lo} Cr – ₹${hi} Cr`
    const sel = (selMin === min && selMax === max) ? ' selected' : ''
    opts += `<option value="${min}|${max}"${sel}>${label}</option>`
  }
  return opts
}


function escape(text) {
  return String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

// ── Confirm Dialog ─────────────────────────────────────────────────────────
function confirmDialog(message, confirmLabel, confirmColor) {
  return new Promise(function (resolve) {
    var overlay = document.createElement('div')
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:11000;display:flex;align-items:center;justify-content:center;'
    overlay.innerHTML =
      '<div style="background:#fff;border-radius:14px;padding:24px 28px;max-width:400px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.25);">' +
        '<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.55;">' + message + '</p>' +
        '<div style="display:flex;gap:10px;justify-content:flex-end;">' +
          '<button id="_cdCancel" style="padding:8px 18px;border-radius:8px;border:1px solid #d1d5db;background:#fff;color:#374151;font-size:13px;cursor:pointer;">Cancel</button>' +
          '<button id="_cdConfirm" style="padding:8px 18px;border-radius:8px;border:none;background:' + (confirmColor || '#ef4444') + ';color:#fff;font-size:13px;font-weight:600;cursor:pointer;">' + (confirmLabel || 'Confirm') + '</button>' +
        '</div>' +
      '</div>'
    document.body.appendChild(overlay)
    function cleanup(ok) { document.body.removeChild(overlay); resolve(ok) }
    overlay.querySelector('#_cdConfirm').addEventListener('click', function () { cleanup(true) })
    overlay.querySelector('#_cdCancel').addEventListener('click', function () { cleanup(false) })
    overlay.addEventListener('click', function (e) { if (e.target === overlay) cleanup(false) })
    function onKey(e) { if (e.key === 'Escape') { document.removeEventListener('keydown', onKey); cleanup(false) } }
    document.addEventListener('keydown', onKey)
  })
}

// ── Toast Notifications ────────────────────────────────────────────────────
var _toastTimer = null
var _toastQueue = []
var _toastBusy  = false

function showToast(msg, type, duration) {
  _toastQueue.push({ msg: String(msg || ''), type: type || 'info', duration: typeof duration === 'number' ? duration : 3500 })
  if (!_toastBusy) _nextToast()
}

function _nextToast() {
  if (!_toastQueue.length) { _toastBusy = false; return }
  _toastBusy = true
  var item = _toastQueue.shift()
  var palette = {
    success: { bg: '#ecfdf5', border: '#10b981', text: '#065f46', icon: '✓' },
    error:   { bg: '#fef2f2', border: '#ef4444', text: '#991b1b', icon: '✕' },
    warning: { bg: '#fffbeb', border: '#f59e0b', text: '#92400e', icon: '!' },
    info:    { bg: '#eff6ff', border: '#3b82f6', text: '#1e40af', icon: 'i' },
  }
  var c = palette[item.type] || palette.info
  var wrap = document.getElementById('_toastWrap')
  if (!wrap) {
    wrap = document.createElement('div')
    wrap.id = '_toastWrap'
    wrap.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:10000;max-width:360px;min-width:240px;display:flex;flex-direction:column;gap:8px;pointer-events:none;'
    document.body.appendChild(wrap)
    var ks = document.createElement('style')
    ks.textContent = '@keyframes _tIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}@keyframes _loaderBar{0%{left:-50%;width:40%}60%{left:40%;width:40%}100%{left:110%;width:40%}}@keyframes spin{to{transform:rotate(360deg)}}'
    document.head.appendChild(ks)
  }
  var box = document.createElement('div')
  box.style.cssText = 'display:flex;align-items:flex-start;gap:10px;padding:12px 16px;border-radius:10px;border-left:4px solid ' + c.border + ';background:' + c.bg + ';box-shadow:0 4px 16px rgba(0,0,0,.14);pointer-events:auto;animation:_tIn .18s ease;'
  box.innerHTML = '<span style="flex-shrink:0;width:20px;height:20px;border-radius:50%;background:' + c.border + ';color:#fff;font-size:11px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;">' + c.icon + '</span>' +
    '<span style="font-size:13px;color:' + c.text + ';line-height:1.45;flex:1;">' + item.msg + '</span>'
  wrap.appendChild(box)
  if (_toastTimer) clearTimeout(_toastTimer)
  _toastTimer = setTimeout(function () {
    if (box.parentNode) box.parentNode.removeChild(box)
    setTimeout(_nextToast, 80)
  }, item.duration)
}

// ── Top Progress Bar ───────────────────────────────────────────────────────
function showLoader() {
  var el = document.getElementById('_topLoader')
  if (!el) {
    el = document.createElement('div')
    el.id = '_topLoader'
    el.style.cssText = 'position:fixed;top:0;left:-50%;right:0;z-index:9999;height:3px;width:40%;background:linear-gradient(90deg,#3b82f6 0%,#10b981 100%);animation:_loaderBar 1s linear infinite;'
    document.body.appendChild(el)
  }
  el.style.display = 'block'
}

function hideLoader() {
  var el = document.getElementById('_topLoader')
  if (el) el.style.display = 'none'
}
