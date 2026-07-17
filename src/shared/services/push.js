// ============================================================================
// PUSH NOTIFICATIONS — Delivery-ready (Phase M1)
// ----------------------------------------------------------------------------
// Responsibilities:
//   - Register the service worker
//   - Detect notification capability per device
//   - Expose pushRequestPermission() for opt-in UI (not auto-prompted)
//   - Fetch VAPID public key from /api/public/push-config (no hardcoded key)
//   - Subscribe to Web Push and POST subscription to /api/push/register
// ============================================================================

var _swRegistration = null
var _pushRegistering = false
var _pushVapidKey = null  // cached after first fetch

// Handle SW_NAVIGATE messages posted from the service worker on notification click.
// This is more reliable than client.navigate() which can fail silently on some browsers.
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('message', function (event) {
    if (event.data && event.data.type === 'SW_NAVIGATE') {
      var url = event.data.url
      if (!url) return
      try {
        history.pushState({}, '', url)
        if (typeof dispatch === 'function') dispatch()
      } catch (_) {}
    }
  })
}

function pushIsSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

function pushPermissionState() {
  if (!('Notification' in window)) return 'unsupported'
  return Notification.permission // 'default' | 'granted' | 'denied'
}

async function pushRegisterServiceWorker() {
  if (!('serviceWorker' in navigator)) return null
  if (_swRegistration) return _swRegistration
  try {
    _swRegistration = await navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
    return _swRegistration
  } catch (err) {
    console.warn('[push] SW registration failed:', err)
    return null
  }
}

function _urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const arr = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i)
  return arr
}

async function _pushGetVapidKey() {
  // Return cached key first
  if (_pushVapidKey) return _pushVapidKey
  // Fallback to inline global (injected by index.html or server)
  if (typeof window !== 'undefined' && window.PUSH_VAPID_KEY) {
    _pushVapidKey = window.PUSH_VAPID_KEY
    return _pushVapidKey
  }
  try {
    var resp = await fetch(API_BASE + '/public/push-config')
    if (resp.ok) {
      var data = await resp.json()
      if (data.enabled && data.vapid_public_key) {
        _pushVapidKey = data.vapid_public_key
        return _pushVapidKey
      }
    }
  } catch (err) {
    console.warn('[push] Failed to fetch VAPID public key:', err)
  }
  return null
}

async function pushRequestPermission() {
  if (!pushIsSupported()) return { ok: false, reason: 'unsupported' }
  if (_pushRegistering) return { ok: false, reason: 'in_progress' }
  _pushRegistering = true
  try {
    const reg = await pushRegisterServiceWorker()
    if (!reg) return { ok: false, reason: 'sw_failed' }

    const perm = await Notification.requestPermission()
    if (perm !== 'granted') return { ok: false, reason: 'denied' }

    const vapidKey = await _pushGetVapidKey()
    let subscription = await reg.pushManager.getSubscription()
    if (!subscription && vapidKey) {
      subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: _urlBase64ToUint8Array(vapidKey),
      })
    }

    if (!subscription) {
      // Permission granted but VAPID not yet deployed — user is opted in,
      // we will subscribe them on next app open once VAPID keys are live.
      return { ok: true, reason: 'permission_only', subscription: null }
    }

    await _pushPostSubscription(subscription)
    return { ok: true, reason: 'subscribed', subscription: subscription }
  } catch (err) {
    console.warn('[push] permission/subscribe failed:', err)
    return { ok: false, reason: 'error', error: String(err && err.message || err) }
  } finally {
    _pushRegistering = false
  }
}

async function _pushPostSubscription(subscription) {
  if (typeof token === 'undefined' || !token) return
  const payload = {
    endpoint: subscription.endpoint,
    keys: subscription.toJSON().keys || null,
    platform: _pushDetectPlatform(),
    user_agent: navigator.userAgent,
  }
  try {
    await fetch(API_BASE + '/push/register', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch (err) {
    console.warn('[push] register POST failed:', err)
  }
}

function _pushDetectPlatform() {
  const ua = navigator.userAgent || ''
  if (/iPhone|iPad|iPod/i.test(ua)) return 'ios'
  if (/Android/i.test(ua)) return 'android'
  return 'web'
}

// Auto-register the service worker (no permission prompt) so PWA install
// criteria are met. Permission is only requested via pushRequestPermission().
if (typeof window !== 'undefined') {
  window.addEventListener('load', function () {
    if ('serviceWorker' in navigator) {
      pushRegisterServiceWorker()
    }

    // If the user already granted permission (i.e. they accepted the prompt
    // in a previous session), silently refresh their subscription so the
    // backend always has a current endpoint.  This handles:
    //   - iOS reinstall (new endpoint issued by APNs)
    //   - subscription expiry / rotation
    //   - first open after login on a previously-permitted device
    //
    // We do NOT auto-prompt here — requesting permission outside a user
    // gesture is silently ignored on iOS Safari and blocked on Chrome.
    // The prompt is triggered only from pushRequestPermission() which is
    // called explicitly after password or OTP login success.
    try {
      var hasSession = !!(localStorage.getItem('lms_token') || sessionStorage.getItem('lms_token'))
      if (hasSession && pushIsSupported() && Notification.permission === 'granted') {
        // Quietly re-subscribe and re-POST so backend endpoint stays fresh.
        pushEnsureSubscription().catch(function () {})
      }
    } catch (_e) {}
  })
}

// Silently ensure subscription is current without requesting new permission.
// Safe to call at any time when permission is already granted.
async function pushEnsureSubscription() {
  if (!pushIsSupported()) return
  if (Notification.permission !== 'granted') return
  try {
    var reg = await pushRegisterServiceWorker()
    if (!reg) return
    var vapidKey = await _pushGetVapidKey()
    var subscription = await reg.pushManager.getSubscription()
    if (!subscription && vapidKey) {
      subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: _urlBase64ToUint8Array(vapidKey),
      })
    }
    if (subscription) {
      await _pushPostSubscription(subscription)
    }
  } catch (err) {
    console.warn('[push] ensureSubscription failed:', err)
  }
}

