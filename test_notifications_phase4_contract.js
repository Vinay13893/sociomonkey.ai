const fs = require('fs')
const path = require('path')

const source = fs.readFileSync(path.join(__dirname, 'src', 'shared', 'ui', 'notifications.js'), 'utf8')

function assertIncludes(text, label) {
  if (!source.includes(text)) throw new Error(label + ' missing')
}

function assertNotIncludes(text, label) {
  if (source.includes(text)) throw new Error(label + ' should not be present')
}

assertIncludes('mode=history&unread_only=1&limit=', 'initial bounded history load')
assertIncludes('after_id=', 'delta polling cursor')
assertIncludes('document.visibilityState', 'hidden tab visibility handling')
assertIncludes('BroadcastChannel', 'broadcast channel coordination')
assertIncludes('localStorage.setItem(key, JSON.stringify', 'localStorage leader lease')
assertIncludes('_NOTIF_LEASE_MS', 'leader lease duration')
assertIncludes('_notifInFlight', 'request coalescing')
assertIncludes('_notifBackoffMs', 'retry backoff')
assertIncludes('_notifReleaseLeadership()', 'leadership release')
assertIncludes('_notifContextKey()', 'tenant/user scoped coordination')
assertIncludes("_notifBroadcast({ type: 'sync'", 'peer sync broadcast')
assertIncludes("_notifBroadcast({ type: 'mark-read'", 'peer mark-read broadcast')
assertIncludes('/leads/notifications/mark-read', 'mark read endpoint')
assertNotIncludes('setInterval(_pollNotifications, 60000)', 'old per-tab polling')
assertNotIncludes('_notifData = data.notifications || []', 'full-list replacement polling')

console.log('test_notifications_phase4_contract: ok')
