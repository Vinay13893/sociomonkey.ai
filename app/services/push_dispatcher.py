"""
Web Push delivery via pywebpush (RFC 8292 / VAPID).

Architecture
------------
`send_web_push(subscription, title, body, url, tag)` sends a single Web Push
message to one PushSubscription row.  It is called by the notification queue
processor and is the only place that does real network I/O for push.

Caller contract:
  - Pass a `PushSubscription` ORM row (must be active).
  - Returns a `PushResult` namedtuple: (ok: bool, status_code: int, error: str).
  - Never raises — all exceptions are caught and returned as failed results.

VAPID config (set env vars on Vercel before enabling delivery):
  VAPID_PUBLIC_KEY    — urlsafe-base64url EC P-256 uncompressed public key
  VAPID_PRIVATE_KEY   — urlsafe-base64url DER PKCS8 private key
  VAPID_CLAIMS_EMAIL  — mailto: URI for the iss/sub claim (RFC 8292 §2.4)

Retry policy (controlled by NotificationProcessor):
  Attempt 1  → immediate
  Attempt 2  → caller-side back-off (5 s)
  Attempt 3  → caller-side back-off (30 s)
  After 3 fails → subscription.is_active = False (endpoint expired/gone)

Web Push HTTP status semantics we handle:
  201/200  → success (delivered to push service)
  400      → bad request — malformed payload; mark failed, do NOT retry
  401      → VAPID auth failure — likely misconfigured keys; fail loud
  404/410  → subscription expired/removed; deactivate and mark skipped
  413      → payload too large; truncate and retry once
  429      → too many requests; back off (handled by caller)
  5xx      → push service transient error; retry up to PUSH_MAX_ATTEMPTS
"""
import json
import logging
from collections import namedtuple

from flask import current_app

logger = logging.getLogger(__name__)

# ── Result type ──────────────────────────────────────────────────────────────
PushResult = namedtuple('PushResult', ['ok', 'status_code', 'error', 'action'])
# action: 'ok' | 'retry' | 'deactivate' | 'fail'

_MAX_BODY_BYTES = 3800  # FCM / APNS cap is ~4 KB; leave room for JSON envelope


def _build_payload(title: str, body: str, url: str = '/', tag: str = None) -> bytes:
    """Build the JSON push payload Chrome/Safari expect."""
    payload = {
        'notification': {
            'title': title[:80],
            'body': (body or '')[:200],
            'icon': '/Assets/pwa/icon-192.png',
            'badge': '/Assets/pwa/icon-96.png',
            'tag': tag or 'sm-notification',
            'renotify': True,
            'data': {'url': url or '/'},
        }
    }
    raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    if len(raw) > _MAX_BODY_BYTES:
        payload['notification']['body'] = payload['notification']['body'][:80] + '\u2026'
        raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    return raw


def _vapid_configured() -> bool:
    pub  = current_app.config.get('VAPID_PUBLIC_KEY', '')
    priv = current_app.config.get('VAPID_PRIVATE_KEY', '')
    return bool(pub and priv)


def send_web_push(subscription, title: str, body: str,
                  url: str = '/', tag: str = None) -> 'PushResult':
    """
    Deliver a Web Push message to one subscription.

    Parameters
    ----------
    subscription : PushSubscription ORM row
    title        : notification title
    body         : notification body
    url          : deep-link URL opened when user taps the notification
    tag          : notification tag (deduplication key in the OS)

    Returns
    -------
    PushResult namedtuple
    """
    if not _vapid_configured():
        return PushResult(ok=False, status_code=0, error='VAPID keys not configured', action='fail')

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return PushResult(ok=False, status_code=0, error='pywebpush not installed', action='fail')

    endpoint  = subscription.endpoint
    p256dh    = subscription.p256dh
    auth_key  = subscription.auth

    if not endpoint or not p256dh or not auth_key:
        return PushResult(ok=False, status_code=0,
                          error='Subscription missing endpoint/keys — likely iOS-before-16.4',
                          action='deactivate')

    payload_bytes = _build_payload(title, body, url, tag)

    vapid_pub  = current_app.config['VAPID_PUBLIC_KEY']
    vapid_priv = current_app.config['VAPID_PRIVATE_KEY']
    vapid_email = current_app.config.get('VAPID_CLAIMS_EMAIL', 'mailto:push@sociomonkey.com')

    try:
        response = webpush(
            subscription_info={
                'endpoint': endpoint,
                'keys': {'p256dh': p256dh, 'auth': auth_key},
            },
            data=payload_bytes,
            vapid_private_key=vapid_priv,
            vapid_claims={'sub': vapid_email},
            content_encoding='aes128gcm',
            ttl=86400,        # 24 h — push service may hold if device offline
            timeout=4,
        )
        status = response.status_code if hasattr(response, 'status_code') else 201
        if status in (200, 201):
            return PushResult(ok=True, status_code=status, error='', action='ok')
        return _classify_failure(status, '')

    except Exception as exc:
        # pywebpush raises WebPushException on HTTP error; check status if available
        status = getattr(exc, 'response', None)
        if status is not None and hasattr(status, 'status_code'):
            code = status.status_code
            logger.warning('[PushDispatcher] HTTP %d for endpoint %.60s: %s', code, endpoint, exc)
            return _classify_failure(code, str(exc))
        logger.warning('[PushDispatcher] Network error for endpoint %.60s: %s', endpoint, exc)
        return PushResult(ok=False, status_code=0, error=str(exc)[:400], action='retry')


def _classify_failure(status_code: int, error: str) -> 'PushResult':
    """Map HTTP status codes to retry/deactivate/fail strategies."""
    if status_code in (404, 410):
        # Subscription gone — endpoint unregistered by browser or device
        return PushResult(ok=False, status_code=status_code,
                          error='Subscription expired', action='deactivate')
    if status_code == 400:
        return PushResult(ok=False, status_code=status_code,
                          error=error or 'Bad request', action='fail')
    if status_code == 401:
        return PushResult(ok=False, status_code=status_code,
                          error='VAPID auth failed — check VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY',
                          action='fail')
    if status_code == 413:
        return PushResult(ok=False, status_code=status_code,
                          error='Payload too large', action='fail')
    if status_code == 429:
        return PushResult(ok=False, status_code=status_code,
                          error='Rate limited by push service', action='retry')
    if status_code >= 500:
        return PushResult(ok=False, status_code=status_code,
                          error=f'Push service error {status_code}', action='retry')
    return PushResult(ok=False, status_code=status_code,
                      error=error or f'Unexpected status {status_code}', action='retry')
