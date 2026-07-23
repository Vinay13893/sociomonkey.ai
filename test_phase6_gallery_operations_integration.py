"""In-memory end-to-end checks for Phase 6 Gallery Operations."""


def test_gallery_operations_workflow():
    from app import create_app
    from app.models.activity import ActivityLog
    from app.models.base import db
    from app.models.location import Location, MeetingRoom
    from app.models.notification import Notification
    from app.models.product import Product, TenantProduct
    from app.models.push import NotificationEvent
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import (
        Visit, VisitStatusConfiguration, VisitTypeConfiguration,
    )
    from app.utils.jwt import create_token
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Phase 6 Tenant', slug='phase6')
        other = Tenant(name='Other Tenant', slug='other-phase6')
        db.session.add_all([tenant, other])
        db.session.flush()
        receptionist = User(
            name='Reception Test', email='reception-phase6@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            is_active=True,
        )
        assignee = User(
            name='RM Test', email='rm-phase6@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            is_active=True,
        )
        other_user = User(
            name='Other User', email='other-phase6@example.invalid',
            password_hash='x', role='team_member', tenant_id=other.id,
            is_active=True,
        )
        db.session.add_all([receptionist, assignee, other_user])
        db.session.flush()
        product = Product.query.filter_by(slug='lms').first()
        assert product
        db.session.add(TenantProduct(
            tenant_id=tenant.id, product_id=product.id, status='active'
        ))
        location = Location(
            tenant_id=tenant.id, code='GALLERY', name='Test Gallery',
            location_type='SALES_GALLERY', created_by=receptionist.id,
            updated_by=receptionist.id,
        )
        other_location = Location(
            tenant_id=other.id, code='OTHER', name='Other Gallery',
            location_type='SALES_GALLERY', created_by=other_user.id,
            updated_by=other_user.id,
        )
        db.session.add_all([location, other_location])
        db.session.flush()
        room = MeetingRoom(
            tenant_id=tenant.id, location_id=location.id, name='Room One',
            capacity=4, created_by=receptionist.id, updated_by=receptionist.id,
        )
        other_room = MeetingRoom(
            tenant_id=other.id, location_id=other_location.id, name='Other Room',
            capacity=4, created_by=other_user.id, updated_by=other_user.id,
        )
        db.session.add_all([room, other_room])
        db.session.add(VisitTypeConfiguration(
            tenant_id=tenant.id, internal_key='WALK_IN',
            display_name='Walk-in', display_order=1,
            updated_by=receptionist.id,
        ))
        for order, key in enumerate([
            'SCHEDULED', 'CHECKED_IN', 'WAITING', 'CALLED',
            'IN_MEETING', 'COMPLETED', 'NO_SHOW',
        ], 1):
            db.session.add(VisitStatusConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=key.title(), display_order=order,
                updated_by=receptionist.id,
                is_terminal=key in ('COMPLETED', 'NO_SHOW'),
            ))
        db.session.commit()

        token = create_token(
            str(receptionist.id), 'team_member', tenant.id,
            login_context='tenant'
        )
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Product-Slug': 'lms',
            'Content-Type': 'application/json',
        }
        client = app.test_client()
        refs = client.get('/api/gallery-operations/references', headers=headers)
        assert refs.status_code == 200, refs.get_data(as_text=True)
        assert len(refs.get_json()['locations']) == 1

        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id,
                'assigned_user_id': assignee.id,
                'participant': {
                    'type': 'INTERNAL_VISITOR',
                    'display_name': 'Internal Test Visitor',
                },
                'purpose': 'Phase 6 integration test',
            },
        )
        assert created.status_code == 201
        visit_id = created.get_json()['visit']['id']
        assert Notification.query.filter_by(
            user_id=assignee.id, source='gallery_operations'
        ).count() == 1
        assert NotificationEvent.query.filter_by(
            user_id=assignee.id, event_type='visit_assigned'
        ).count() == 1
        assert ActivityLog.query.filter_by(
            resource_id=visit_id, module='gallery_operations'
        ).count() == 1

        for status in ('WAITING', 'CALLED', 'IN_MEETING'):
            response = client.post(
                f'/api/gallery-operations/visits/{visit_id}/queue-state',
                headers=headers, json={'status': status},
            )
            assert response.status_code == 200
        assert client.put(
            f'/api/gallery-operations/visits/{visit_id}/room',
            headers=headers, json={'meeting_room_id': other_room.id},
        ).status_code == 400
        assert client.put(
            f'/api/gallery-operations/visits/{visit_id}/room',
            headers=headers, json={'meeting_room_id': room.id},
        ).status_code == 200
        dashboard = client.get(
            '/api/gallery-operations/dashboard', headers=headers
        )
        assert dashboard.status_code == 200
        assert dashboard.get_json()['summary']['in_meeting'] == 1
        assert client.post(
            f'/api/gallery-operations/visits/{visit_id}/check-out',
            headers=headers,
        ).status_code == 200
        assert db.session.get(Visit, visit_id).status_key == 'COMPLETED'
        completed = client.get(
            '/api/gallery-operations/visits?view=completed', headers=headers
        )
        assert completed.get_json()['pagination']['total'] == 1


if __name__ == '__main__':
    test_gallery_operations_workflow()
    print('Phase 6 Gallery Operations integration passed')
