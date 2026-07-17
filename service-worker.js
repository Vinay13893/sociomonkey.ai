// Sociomonkey PWA service worker
// Responsibilities (Phase M1):
//   1. Make the app installable (presence of an SW + manifest is required).
//   2. Handle background push notifications via FCM (foundation only).
//   3. Route notification clicks back into the SPA at the correct deep link.
// NO offline caching strategy yet — kept minimal to avoid serving stale bundles.

const SW_VERSION = 'sm-sw-v1-2026.06.02-navfix1'

self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

// Web Push handler — supports both flat and nested (notification.*) payload shapes.
// Backend sends: { notification: { title, body, icon, badge, tag, renotify, data: { url } } }
// Flat shape fallback: { title, body, url }
self.addEventListener('push', (event) => {
  let raw = {}
  try { raw = event.data ? event.data.json() : {} } catch (e) {
    raw = { title: 'Sociomonkey', body: event.data ? event.data.text() : '' }
  }

  // Support nested notification object (sent by push_dispatcher._build_payload)
  const n = raw.notification || {}
  const d = n.data || raw.data || {}

  const title = n.title || raw.title || 'Sociomonkey'
  const body  = n.body  || raw.body  || ''
  // Deep link: nested data.url > flat data.url > flat url > fallback
  const url   = d.url   || raw.url   || '/'
  const tag   = n.tag   || raw.tag   || 'sm-notification'

  const options = {
    body: body,
    icon: n.icon  || '/Assets/pwa/icon-192.png',
    badge: n.badge || '/Assets/pwa/icon-96.png',
    data: { url: url },
    tag: tag,
    renotify: true,
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

// Click on notification -> focus existing tab and send navigation message, or open new tab
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const targetUrl = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil((async () => {
    const allClients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    for (const client of allClients) {
      try {
        const clientUrl = new URL(client.url)
        if (clientUrl.origin === self.location.origin) {
          await client.focus()
          // postMessage is more reliable than client.navigate() which can fail silently
          client.postMessage({ type: 'SW_NAVIGATE', url: targetUrl })
          return
        }
      } catch (_) {}
    }
    // No existing tab — open a new window at the deep link
    await self.clients.openWindow(targetUrl)
  })())
})
