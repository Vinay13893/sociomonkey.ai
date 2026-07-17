(function () {
  if (window.smAttributionTracker) return

  var STORAGE_KEY = 'sm_attribution_v1'
  var TRACKING_KEYS = ['gclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']

  function _readStored() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY) || localStorage.getItem(STORAGE_KEY)
      if (!raw) return {}
      var data = JSON.parse(raw)
      return data && typeof data === 'object' ? data : {}
    } catch (_e) {
      return {}
    }
  }

  function _writeStored(data) {
    var payload = JSON.stringify(data || {})
    try { sessionStorage.setItem(STORAGE_KEY, payload) } catch (_e1) {}
    try { localStorage.setItem(STORAGE_KEY, payload) } catch (_e2) {}
  }

  function _parseUrl(url) {
    var out = {}
    var loc = null
    try {
      loc = new URL(url || window.location.href)
    } catch (_e) {
      return out
    }

    var params = loc.searchParams
    TRACKING_KEYS.forEach(function (k) {
      var v = (params.get(k) || '').trim()
      if (v) out[k] = v
    })

    out.landing_page_url = String(loc.href || '')
    out.captured_at = new Date().toISOString()
    return out
  }

  function captureFromLocation() {
    var prev = _readStored()
    var curr = _parseUrl(window.location.href)
    var merged = Object.assign({}, prev)

    TRACKING_KEYS.forEach(function (k) {
      if (curr[k]) merged[k] = curr[k]
    })

    if (curr.landing_page_url) merged.landing_page_url = curr.landing_page_url
    if (curr.captured_at) merged.captured_at = curr.captured_at

    _writeStored(merged)
    return merged
  }

  function getSnapshot() {
    return Object.assign({}, _readStored())
  }

  function enrichPayload(payload) {
    var base = payload && typeof payload === 'object' ? Object.assign({}, payload) : {}
    var snap = _readStored()
    TRACKING_KEYS.forEach(function (k) {
      if (!base[k] && snap[k]) base[k] = snap[k]
    })
    if (!base.landing_page_url && snap.landing_page_url) base.landing_page_url = snap.landing_page_url
    return base
  }

  function clear() {
    try { sessionStorage.removeItem(STORAGE_KEY) } catch (_e1) {}
    try { localStorage.removeItem(STORAGE_KEY) } catch (_e2) {}
  }

  window.smAttributionTracker = {
    keys: TRACKING_KEYS.slice(),
    captureFromLocation: captureFromLocation,
    getSnapshot: getSnapshot,
    enrichPayload: enrichPayload,
    clear: clear,
  }

  // Capture once on load so all forms can reuse this snapshot.
  try { captureFromLocation() } catch (_e) {}
})()
