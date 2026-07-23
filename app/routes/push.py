"""Push notification subscription endpoints (Phase M1).

Foundation only — no outbound delivery. The frontend posts a Web Push
subscription (or future FCM token) here; we persist it scoped to the
authenticated user + tenant for later delivery by a worker.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.push import NotificationEvent, PushSubscription

push_bp = Blueprint('push', __name__, url_prefix='/api/push')


@push_bp.route('/register', methods=['POST'])
@require_auth
def register_subscription():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    endpoint = (data.get('endpoint') or '').strip()
    if not endpoint:
        return jsonify({'error': 'endpoint is required'}), 400

    keys = data.get('keys') or {}
    p256dh = (keys.get('p256dh') if isinstance(keys, dict) else None) or None
    auth = (keys.get('auth') if isinstance(keys, dict) else None) or None
    platform = (data.get('platform') or '').strip().lower() or None
    user_agent = (data.get('user_agent') or '')[:400] or None

    existing = PushSubscription.query.filter_by(user_id=user.id, endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.platform = platform
        existing.user_agent = user_agent
        existing.tenant_id = user.tenant_id
        existing.is_active = True
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'subscription': existing.to_dict(), 'created': False}), 200

    sub = PushSubscription(
        user_id=user.id,
        tenant_id=user.tenant_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        platform=platform,
        user_agent=user_agent,
        is_active=True,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({'subscription': sub.to_dict(), 'created': True}), 201


@push_bp.route('/unregister', methods=['POST'])
@require_auth
def unregister_subscription():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    endpoint = (data.get('endpoint') or '').strip()
    if not endpoint:
        return jsonify({'error': 'endpoint is required'}), 400
    sub = PushSubscription.query.filter_by(user_id=user.id, endpoint=endpoint).first()
    if sub:
        sub.is_active = False
        sub.updated_at = datetime.utcnow()
        db.session.commit()
    return jsonify({'ok': True}), 200


@push_bp.route('/subscriptions', methods=['GET'])
@require_auth
def list_subscriptions():
    user = request.current_user
    rows = (
        PushSubscription.query
        .filter_by(user_id=user.id, is_active=True)
        .order_by(PushSubscription.updated_at.desc())
        .all()
    )
    return jsonify({'subscriptions': [r.to_dict() for r in rows]}), 200


@push_bp.route('/test-send', methods=['POST'])
@require_auth
def test_send():
    """Send a test push to all active subscriptions for the authenticated user.
    Body: { title?, body? }  — defaults to a test message.
    Useful for verifying iOS Web Push delivery end-to-end without waiting for a
    real event (callback / lead assignment).
    """
    from app.services.push_dispatcher import send_web_push, _vapid_configured
    user = request.current_user
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or 'Sociomonkey Test').strip()[:80]
    body  = (data.get('body')  or 'Push notifications are working!').strip()[:200]
    url   = (data.get('url')   or '/').strip()

    if not _vapid_configured():
        return jsonify({'error': 'VAPID keys not configured on server'}), 503

    subs = PushSubscription.query.filter_by(user_id=user.id, is_active=True).all()
    if not subs:
        return jsonify({'error': 'No active push subscriptions found. '
                        'Open the app on your device and grant notification permission first.'}), 404

    results = []
    for sub in subs:
        res = send_web_push(sub, title, body, url, tag='sm-test')
        results.append({
            'sub_id': sub.id,
            'platform': sub.platform,
            'ok': res.ok,
            'status_code': res.status_code,
            'action': res.action,
            'error': res.error if not res.ok else '',
        })
        if not res.ok and res.action == 'deactivate':
            sub.is_active = False
            db.session.commit()

    any_ok = any(r['ok'] for r in results)
    return jsonify({'ok': any_ok, 'results': results}), 200


@push_bp.route('/diagnostics', methods=['GET'])
@require_role('superadmin', 'platform_owner')
def delivery_diagnostics():
    """Tenant-scoped aggregate delivery health without message payloads or PII."""
    user = request.current_user
    event_rows = (
        db.session.query(NotificationEvent.status, db.func.count(NotificationEvent.id))
        .filter(NotificationEvent.tenant_id == user.tenant_id)
        .group_by(NotificationEvent.status)
        .all()
    )
    subscription_rows = (
        db.session.query(PushSubscription.is_active, db.func.count(PushSubscription.id))
        .filter(PushSubscription.tenant_id == user.tenant_id)
        .group_by(PushSubscription.is_active)
        .all()
    )
    oldest_queued = (
        db.session.query(db.func.min(NotificationEvent.created_at))
        .filter(
            NotificationEvent.tenant_id == user.tenant_id,
            NotificationEvent.status == 'queued',
        )
        .scalar()
    )
    return jsonify({
        'events': {str(status): int(count) for status, count in event_rows},
        'subscriptions': {
            'active' if active else 'inactive': int(count)
            for active, count in subscription_rows
        },
        'oldest_queued_at': oldest_queued.isoformat() if oldest_queued else None,
    }), 200


@push_bp.route('/events/<int:event_id>/retry', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def retry_delivery_event(event_id):
    """Requeue one failed/skipped tenant delivery without recreating it."""
    event = NotificationEvent.query.filter_by(
        id=event_id,
        tenant_id=request.current_user.tenant_id,
    ).first()
    if not event:
        return jsonify({'error': 'Delivery event not found'}), 404
    if event.status not in ('failed', 'skipped'):
        return jsonify({'error': 'Only failed or skipped events can be retried'}), 409

    event.status = 'queued'
    event.attempts = 0
    event.last_error = None
    event.scheduled_for = datetime.utcnow()
    event.claimed_at = None
    event.dead_lettered_at = None
    db.session.commit()
    return jsonify({'ok': True, 'event_id': event.id, 'status': event.status}), 200
