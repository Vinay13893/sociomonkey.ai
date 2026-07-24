from datetime import datetime, timedelta


def test_phase11_notification_reliability_workflow(monkeypatch):
    from app import create_app, db
    from app.models.activity import ActivityLog
    from app.models.lead import CallbackReminder, Lead
    from app.models.product import Product, TenantProduct
    from app.models.push import (
        NotificationDeliveryAttempt,
        NotificationEvent,
        PushSubscription,
    )
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.services.notification_processor import process_notification_queue
    from app.services.push_dispatcher import PushResult
    from app.services.reminder_scheduler import process_pending_reminders
    from app.utils.jwt import create_token
    import app.services.push_dispatcher as dispatcher

    app = create_app('testing')
    app.config['VAPID_PUBLIC_KEY'] = 'test-public'
    app.config['VAPID_PRIVATE_KEY'] = 'test-private'
    app.config['PUSH_MAX_ATTEMPTS'] = 3

    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Phase 11 Tenant', slug='phase11')
        other = Tenant(name='Other Phase 11', slug='other-phase11')
        db.session.add_all([tenant, other])
        db.session.flush()
        admin = User(
            name='Phase 11 Admin', email='phase11-admin@example.invalid',
            password_hash='x', role='superadmin', tenant_id=tenant.id,
            is_active=True,
        )
        member = User(
            name='Phase 11 Member', email='phase11-member@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            is_active=True,
        )
        other_admin = User(
            name='Other Phase 11', email='phase11-other@example.invalid',
            password_hash='x', role='superadmin', tenant_id=other.id,
            is_active=True,
        )
        db.session.add_all([admin, member, other_admin])
        db.session.flush()
        product = Product.query.filter_by(slug='lms').first()
        db.session.add_all([
            TenantProduct(
                tenant_id=tenant.id, product_id=product.id, status='active'
            ),
            TenantProduct(
                tenant_id=other.id, product_id=product.id, status='active'
            ),
        ])
        subscription = PushSubscription(
            tenant_id=tenant.id,
            user_id=member.id,
            endpoint='https://push.example.invalid/subscription',
            p256dh='test-key',
            auth='test-auth',
            is_active=True,
        )
        event = NotificationEvent(
            tenant_id=tenant.id,
            user_id=member.id,
            event_type='lead_assigned',
            correlation_id='phase11-success',
            idempotency_key='phase11-success',
            title='Assigned',
            body='One lead assigned',
            status='queued',
            scheduled_for=datetime.utcnow() - timedelta(seconds=1),
            origin_type='LEAD',
            origin_id=101,
        )
        db.session.add_all([subscription, event])
        db.session.commit()

        monkeypatch.setattr(
            dispatcher,
            'send_web_push',
            lambda *args, **kwargs: PushResult(True, 201, '', 'ok'),
        )
        success = process_notification_queue(batch_size=5)
        db.session.refresh(event)
        db.session.refresh(subscription)
        assert success['sent'] == 1
        assert success['claimed'] == 1
        assert event.status == 'sent'
        assert subscription.last_success_at is not None
        success_attempt = NotificationDeliveryAttempt.query.filter_by(
            notification_event_id=event.id,
            outcome='sent',
        ).one()
        assert success_attempt.correlation_id == 'phase11-success'

        retry_event = NotificationEvent(
            tenant_id=tenant.id,
            user_id=member.id,
            event_type='callback_due_now',
            correlation_id='phase11-retry',
            idempotency_key='phase11-retry',
            title='Callback',
            body='Callback due',
            status='queued',
            scheduled_for=datetime.utcnow() - timedelta(seconds=1),
        )
        db.session.add(retry_event)
        db.session.commit()
        monkeypatch.setattr(
            dispatcher,
            'send_web_push',
            lambda *args, **kwargs: PushResult(
                False, 503, 'Push service unavailable', 'retry'
            ),
        )
        retry = process_notification_queue(batch_size=5)
        db.session.refresh(retry_event)
        assert retry['retrying'] == 1
        assert retry_event.status == 'queued'
        assert retry_event.failure_category == 'provider_transient'
        assert retry_event.scheduled_for > datetime.utcnow()
        assert NotificationDeliveryAttempt.query.filter_by(
            notification_event_id=retry_event.id,
            outcome='retry_scheduled',
        ).count() == 1

        retry_event.attempts = 2
        retry_event.scheduled_for = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        dead = process_notification_queue(batch_size=5)
        db.session.refresh(retry_event)
        assert dead['failed'] == 1
        assert retry_event.status == 'failed'
        assert retry_event.dead_lettered_at is not None

        no_subscription = NotificationEvent(
            tenant_id=tenant.id,
            user_id=admin.id,
            event_type='action_assigned',
            correlation_id='phase11-no-subscription',
            idempotency_key='phase11-no-subscription',
            title='Action',
            status='queued',
            scheduled_for=datetime.utcnow() - timedelta(seconds=1),
        )
        db.session.add(no_subscription)
        db.session.commit()
        skipped = process_notification_queue(batch_size=5)
        db.session.refresh(no_subscription)
        assert skipped['skipped'] == 1
        assert no_subscription.status == 'skipped'
        assert no_subscription.failure_category == 'no_subscription'

        lead = Lead(
            tenant_id=tenant.id,
            name='Phase 11 Internal Test',
            assigned_to=member.id,
            created_by=admin.id,
            is_active=True,
            is_test=True,
        )
        db.session.add(lead)
        db.session.flush()
        callback = CallbackReminder(
            tenant_id=tenant.id,
            lead_id=lead.id,
            assigned_user_id=member.id,
            callback_datetime=datetime.utcnow() - timedelta(seconds=1),
            status='pending',
            correlation_id='phase11-reminder',
            created_by=admin.id,
        )
        db.session.add(callback)
        db.session.commit()
        reminder_result = process_pending_reminders(batch_size=10)
        db.session.refresh(callback)
        assert reminder_result['processed_due'] == 1
        assert callback.reminder_due_sent is True
        assert NotificationEvent.query.filter_by(
            callback_id=callback.id,
            correlation_id='phase11-reminder',
        ).count() == 1
        second_reminder = process_pending_reminders(batch_size=10)
        assert second_reminder['processed_due'] == 0

        archived = NotificationEvent(
            tenant_id=tenant.id,
            user_id=member.id,
            event_type='old_sent',
            correlation_id='phase11-archive',
            idempotency_key='phase11-archive',
            status='sent',
            sent_at=datetime.utcnow() - timedelta(days=40),
            created_at=datetime.utcnow() - timedelta(days=40),
        )
        other_event = NotificationEvent(
            tenant_id=other.id,
            user_id=other_admin.id,
            event_type='other_failed',
            correlation_id='phase11-other',
            idempotency_key='phase11-other',
            status='failed',
            dead_lettered_at=datetime.utcnow(),
        )
        db.session.add_all([archived, other_event])
        db.session.commit()

        def headers(user):
            token = create_token(
                str(user.id), user.role, user.tenant_id,
                login_context='tenant',
            )
            return {
                'Authorization': f'Bearer {token}',
                'X-Product-Slug': 'lms',
                'Content-Type': 'application/json',
            }

        client = app.test_client()
        summary = client.get(
            '/api/push/operations/summary', headers=headers(admin)
        )
        assert summary.status_code == 200
        health = summary.get_json()['health']
        assert health['queue']['dead_letter'] >= 1
        assert health['subscriptions']['active'] == 1

        events = client.get(
            '/api/push/operations/events?status=failed',
            headers=headers(admin),
        )
        assert events.status_code == 200
        assert all(
            row['correlation_id'] != 'phase11-other'
            for row in events.get_json()['events']
        )
        cross_tenant = client.get(
            f'/api/push/operations/events/{other_event.id}',
            headers=headers(admin),
        )
        assert cross_tenant.status_code == 404
        denied = client.get(
            '/api/push/operations/summary', headers=headers(member)
        )
        assert denied.status_code == 403

        replay = client.post(
            f'/api/push/operations/events/{retry_event.id}/replay',
            headers=headers(admin),
            json={},
        )
        assert replay.status_code == 200
        db.session.refresh(retry_event)
        assert retry_event.status == 'queued'
        assert retry_event.replay_count == 1
        assert NotificationDeliveryAttempt.query.filter_by(
            notification_event_id=retry_event.id,
            outcome='manual_replay',
        ).count() == 1
        assert ActivityLog.query.filter_by(
            tenant_id=tenant.id,
            module='notifications',
            action='REPLAY',
        ).count() == 1

        archive = client.post(
            '/api/push/operations/events/archive-completed',
            headers=headers(admin),
            json={'older_than_days': 30, 'limit': 500},
        )
        assert archive.status_code == 200
        assert archive.get_json()['archived'] >= 1
        db.session.refresh(archived)
        assert archived.archived_at is not None
