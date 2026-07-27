"""Phase 13r: Meta lead source health check.

A dead Meta OAuth token previously failed silently - webhooks kept
arriving but every lead failed enrichment, and nobody found out until
someone happened to check the Lead Sources page days later. This check
detects an invalid token and alerts tenant admins (in-app + push),
re-alerting about once/day while broken and clearing on recovery.
"""

from unittest.mock import patch


def _bootstrap(app):
    from app.models.base import db
    from app.models.ingestion import LeadSource
    from app.models.tenant import Tenant
    from app.models.user import User

    db.create_all()
    tenant = Tenant(name='Health Check Tenant', slug='health-check-tenant')
    db.session.add(tenant)
    db.session.flush()

    admin = User(
        name='Admin', email='healthcheck-admin@example.invalid',
        password_hash='x', role='superadmin', tenant_id=tenant.id, is_active=True,
    )
    other_role = User(
        name='Caller', email='healthcheck-caller@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id, is_active=True,
    )
    db.session.add_all([admin, other_role])
    db.session.flush()

    source = LeadSource(
        tenant_id=tenant.id, name='Meta - Health Check Page', source_type='meta',
        is_active=True, credentials={'user_token': 'fake-token', 'page_id': '123'},
    )
    db.session.add(source)
    db.session.commit()
    return tenant, admin, other_role, source


def test_invalid_token_notifies_admins_and_marks_source_error():
    from app import create_app
    from app.models.notification import Notification
    from app.models.push import NotificationEvent

    app = create_app('testing')
    with app.app_context():
        tenant, admin, other_role, source = _bootstrap(app)

        with patch(
            'app.services.lead_source_health._debug_token_status',
            return_value=(False, {'error': {'message': 'Session invalidated'}}),
        ):
            from app.services.lead_source_health import check_lead_source_health
            summary = check_lead_source_health()

        assert summary['checked'] == 1
        assert summary['invalid'] == 1
        assert summary['notified'] == 1

        from app.models.base import db
        db.session.refresh(source)
        assert source.permission_status == 'error'
        assert source.last_test_result == 'fail'
        assert 'Session invalidated' in source.last_test_message

        notifs = Notification.query.filter_by(tenant_id=tenant.id).all()
        assert len(notifs) == 1
        assert notifs[0].user_id == admin.id
        assert notifs[0].category == 'lead_source_health'

        events = NotificationEvent.query.filter_by(tenant_id=tenant.id).all()
        assert len(events) == 1
        assert events[0].user_id == admin.id
        assert events[0].event_type == 'lead_source_health'


def test_second_consecutive_failure_does_not_renotify():
    from app import create_app
    from app.models.notification import Notification

    app = create_app('testing')
    with app.app_context():
        tenant, admin, other_role, source = _bootstrap(app)

        with patch(
            'app.services.lead_source_health._debug_token_status',
            return_value=(False, {'error': {'message': 'Session invalidated'}}),
        ):
            from app.services.lead_source_health import check_lead_source_health
            check_lead_source_health()
            summary = check_lead_source_health()

        assert summary['invalid'] == 1
        assert summary['notified'] == 0

        notifs = Notification.query.filter_by(tenant_id=tenant.id).all()
        assert len(notifs) == 1


def test_recovery_clears_alert_marker_and_status():
    from app import create_app
    from app.models.base import db

    app = create_app('testing')
    with app.app_context():
        tenant, admin, other_role, source = _bootstrap(app)

        with patch(
            'app.services.lead_source_health._debug_token_status',
            return_value=(False, {'error': {'message': 'Session invalidated'}}),
        ):
            from app.services.lead_source_health import check_lead_source_health
            check_lead_source_health()

        with patch(
            'app.services.lead_source_health._debug_token_status',
            return_value=(True, {'is_valid': True}),
        ):
            summary = check_lead_source_health()

        assert summary['recovered'] == 1
        db.session.refresh(source)
        assert source.permission_status == 'ok'
        assert (source.permission_details or {}).get('health_alert_sent_at') is None
