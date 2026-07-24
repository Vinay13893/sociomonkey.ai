"""Push subscription and notification-operations endpoints.

The frontend registers Web Push subscriptions here; we persist them for
delivery and expose tenant-scoped
operational health and controls.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.middleware import require_auth, require_capability, require_role
from app.models.base import db
from app.models.push import NotificationEvent, PushSubscription
from app.utils.correlation import request_correlation_id

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
        existing.failure_count = 0
        existing.deactivated_at = None
        existing.deactivation_reason = None
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
        sub.deactivated_at = datetime.utcnow()
        sub.deactivation_reason = 'user_unregistered'
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
    from app.services.notification_operations import queue_health

    user = request.current_user
    health = queue_health(user.tenant_id)
    return jsonify({
        'events': health['queue']['counts'],
        'subscriptions': health['subscriptions'],
        'oldest_queued_at': health['queue']['oldest_pending_at'],
        'health': health,
    }), 200


@push_bp.route('/events/<int:event_id>/retry', methods=['POST'])
@require_capability('notifications.retry', 'TENANT')
def retry_delivery_event(event_id):
    """Requeue one failed/skipped tenant delivery without recreating it."""
    from app.services.notification_operations import replay_event

    user = request.current_user
    event = NotificationEvent.query.filter(
        NotificationEvent.id == event_id,
        NotificationEvent.tenant_id == user.tenant_id,
    ).first()
    if not event:
        return jsonify({'error': 'Delivery event not found'}), 404
    if event.status not in ('failed', 'skipped'):
        return jsonify({'error': 'Only failed or skipped events can be retried'}), 409
    result = replay_event(
        event,
        request.current_user,
        request_correlation_id(request),
    )
    return jsonify({
        'ok': True,
        'event_id': event.id,
        'status': event.status,
        'event': result,
    }), 200


@push_bp.route('/operations/summary', methods=['GET'])
@require_capability('notifications.view', 'TENANT')
def notification_operations_summary():
    from app.services.notification_operations import queue_health

    return jsonify({
        'health': queue_health(request.current_user.tenant_id),
    }), 200


@push_bp.route('/operations/events', methods=['GET'])
@require_capability('notifications.view', 'TENANT')
def notification_operations_events():
    from app.services.notification_operations import list_events

    try:
        result = list_events(request.current_user.tenant_id, request.args)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid event filter or pagination value'}), 400
    return jsonify(result), 200


@push_bp.route('/operations/events/<int:event_id>', methods=['GET'])
@require_capability('notifications.view', 'TENANT')
def notification_operations_event_detail(event_id):
    from app.services.notification_operations import event_detail

    result = event_detail(request.current_user.tenant_id, event_id)
    if not result:
        return jsonify({'error': 'Delivery event not found'}), 404
    return jsonify({'event': result}), 200


@push_bp.route('/operations/events/<int:event_id>/replay', methods=['POST'])
@require_capability('notifications.retry', 'TENANT')
def notification_operations_event_replay(event_id):
    from app.services.notification_operations import replay_event

    event = NotificationEvent.query.filter_by(
        id=event_id,
        tenant_id=request.current_user.tenant_id,
    ).first()
    if not event:
        return jsonify({'error': 'Delivery event not found'}), 404
    try:
        result = replay_event(
            event,
            request.current_user,
            request_correlation_id(request),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 409
    return jsonify({'ok': True, 'event': result}), 200


@push_bp.route('/operations/events/archive-completed', methods=['POST'])
@require_capability('notifications.manage', 'TENANT')
def notification_operations_archive_completed():
    from app.services.notification_operations import archive_completed

    data = request.get_json(silent=True) or {}
    try:
        result = archive_completed(
            request.current_user.tenant_id,
            request.current_user,
            older_than_days=data.get('older_than_days', 30),
            limit=data.get('limit', 500),
            requested_correlation_id=request_correlation_id(request),
        )
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid archive boundary'}), 400
    return jsonify({'ok': True, **result}), 200
