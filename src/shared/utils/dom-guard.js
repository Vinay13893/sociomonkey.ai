// ── dom-guard.js: Centralized safe DOM mutation helpers ──────────────────────
// Loaded once (after helpers.js), available globally for all CRM/tenant modules.
// Prevents null-pointer crashes when the user navigates away during async renders.

/**
 * safeMutate(elOrId, html)
 * Safely sets el.innerHTML.
 * - Accepts a DOM element or an ID string.
 * - Returns true on success, false if the element is missing or detached.
 */
function safeMutate(elOrId, html) {
  var el = typeof elOrId === 'string' ? document.getElementById(elOrId) : elOrId
  if (!el || !el.isConnected) return false
  try { el.innerHTML = html; return true }
  catch (e) { console.error('[safeMutate] error writing to', elOrId, e); return false }
}

/**
 * _safeEl(elOrId)
 * Returns the live element if it is connected to the document, null otherwise.
 */
function _safeEl(elOrId) {
  var el = typeof elOrId === 'string' ? document.getElementById(elOrId) : elOrId
  return (el && el.isConnected) ? el : null
}
