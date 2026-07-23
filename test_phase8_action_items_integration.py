"""In-memory Phase 8 Action Item workflow checks."""


def test_action_item_workflow():
    from app import create_app
    from app.models.action_item import (
        ActionItem,
        ActionPriorityConfiguration,
        ActionStatusConfiguration,
        ActionTypeConfiguration,
    )
    from app.models.activity import ActivityLog
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.location import Location
    from app.models.notification import Notification
    from app.models.organisation import ReportingRelationship
    from app.models.product import Product, TenantProduct
    from app.models.project import Project
    from app.models.push import NotificationEvent
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import Visit
    from app.utils.jwt import create_token
    import app.routes.action_items as action_routes
    import app.services.permissions as permissions

    app = create_app('testing')

    def decision(user, capability, scope='OWN', scope_ref_id=None):
        if user.role == 'superadmin':
            granted = 'TENANT'
        elif user.role == 'sales_manager':
            granted = 'TEAM'
        else:
            granted = 'OWN'
        return {'allowed': True, 'source': 'test', 'scope': granted}

    permissions.capability_decision = decision
    action_routes.capability_decision = decision

    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Phase 8 Tenant', slug='phase8')
        other = Tenant(name='Other Phase 8 Tenant', slug='other-phase8')
        db.session.add_all([tenant, other])
        db.session.flush()
        admin = User(
            name='Phase 8 Admin', email='admin-phase8@example.invalid',
            password_hash='x', role='superadmin', tenant_id=tenant.id,
            is_active=True,
        )
        manager = User(
            name='Phase 8 Manager', email='manager-phase8@example.invalid',
            password_hash='x', role='sales_manager', tenant_id=tenant.id,
            is_active=True,
        )
        member = User(
            name='Phase 8 Member', email='member-phase8@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            is_active=True,
        )
        second_member = User(
            name='Phase 8 Second', email='second-phase8@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            is_active=True,
        )
        other_user = User(
            name='Other Phase 8 User', email='other-phase8@example.invalid',
            password_hash='x', role='superadmin', tenant_id=other.id,
            is_active=True,
        )
        db.session.add_all([
            admin, manager, member, second_member, other_user,
        ])
        db.session.flush()
        db.session.add_all([
            ReportingRelationship(
                tenant_id=tenant.id, user_id=member.id,
                manager_id=manager.id, is_active=True, created_by=admin.id,
            ),
            ReportingRelationship(
                tenant_id=tenant.id, user_id=second_member.id,
                manager_id=manager.id, is_active=True, created_by=admin.id,
            ),
        ])
        product = Product.query.filter_by(slug='lms').first()
        db.session.add_all([
            TenantProduct(
                tenant_id=tenant.id, product_id=product.id, status='active'
            ),
            TenantProduct(
                tenant_id=other.id, product_id=product.id, status='active'
            ),
        ])
        project = Project(
            tenant_id=tenant.id, name='Phase 8 Project',
            is_active=True, created_by=admin.id,
        )
        other_project = Project(
            tenant_id=other.id, name='Other Project',
            is_active=True, created_by=other_user.id,
        )
        location = Location(
            tenant_id=tenant.id, code='P8-GALLERY',
            name='Phase 8 Gallery', location_type='SALES_GALLERY',
            created_by=admin.id, updated_by=admin.id,
        )
        db.session.add_all([project, other_project, location])
        db.session.flush()
        lead = Lead(
            tenant_id=tenant.id, name='Phase 8 Test Lead',
            project_id=project.id, assigned_to=member.id,
            created_by=admin.id, is_active=True,
        )
        other_lead = Lead(
            tenant_id=other.id, name='Other Test Lead',
            project_id=other_project.id, created_by=other_user.id,
            is_active=True,
        )
        visit = Visit(
            tenant_id=tenant.id, visit_type_key='SCHEDULED_VISIT',
            status_key='SCHEDULED', location_id=location.id,
            project_id=project.id, assigned_user_id=member.id,
            purpose='Phase 8 gallery meeting', created_by=admin.id,
            updated_by=admin.id,
        )
        db.session.add_all([lead, other_lead, visit])
        for order, (key, name, priority) in enumerate([
            ('CALL', 'Call', 'NORMAL'),
            ('GALLERY_VISIT', 'Gallery Visit', 'HIGH'),
            ('INTERNAL_TASK', 'Internal Task', 'NORMAL'),
        ], 1):
            db.session.add(ActionTypeConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=name, display_order=order,
                default_priority_key=priority, updated_by=admin.id,
            ))
        for order, key in enumerate([
            'PENDING', 'SCHEDULED', 'IN_PROGRESS', 'WAITING',
            'COMPLETED', 'CANCELLED', 'EXPIRED',
        ], 1):
            db.session.add(ActionStatusConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=key.replace('_', ' ').title(),
                display_order=order,
                is_terminal=key in {'COMPLETED', 'CANCELLED', 'EXPIRED'},
                updated_by=admin.id,
            ))
        for order, key in enumerate(['LOW', 'NORMAL', 'HIGH', 'URGENT'], 1):
            db.session.add(ActionPriorityConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=key.title(), display_order=order,
                weight=order * 10, is_default=key == 'NORMAL',
                updated_by=admin.id,
            ))
        db.session.commit()

        def headers(user):
            token = create_token(
                str(user.id), user.role, tenant.id, login_context='tenant'
            )
            return {
                'Authorization': f'Bearer {token}',
                'X-Product-Slug': 'lms',
                'Content-Type': 'application/json',
            }

        client = app.test_client()
        generated = client.post(
            '/api/action-items/generate', headers=headers(manager),
            json={
                'source_type': 'LEAD', 'source_id': lead.id,
                'idempotency_key': 'phase8-lead-follow-up',
            },
        )
        assert generated.status_code == 201, generated.get_json()
        action_id = generated.get_json()['action_item']['id']
        duplicate = client.post(
            '/api/action-items/generate', headers=headers(manager),
            json={
                'source_type': 'LEAD', 'source_id': lead.id,
                'idempotency_key': 'phase8-lead-follow-up',
            },
        )
        assert duplicate.status_code == 200
        assert duplicate.get_json()['created'] is False
        assert ActionItem.query.filter_by(
            tenant_id=tenant.id, idempotency_key='phase8-lead-follow-up'
        ).count() == 1
        assert NotificationEvent.query.filter_by(
            action_item_id=action_id, event_type='action_assigned'
        ).count() == 1
        assert Notification.query.filter_by(
            user_id=member.id, source='action_items'
        ).count() == 1

        visit_action = client.post(
            '/api/action-items/generate', headers=headers(manager),
            json={
                'source_type': 'VISIT', 'source_id': visit.id,
                'idempotency_key': 'phase8-visit-meeting',
            },
        )
        assert visit_action.status_code == 201, visit_action.get_json()
        assert visit_action.get_json()['action_item']['location_id'] == location.id

        cross_tenant = client.post(
            '/api/action-items/generate', headers=headers(manager),
            json={'source_type': 'LEAD', 'source_id': other_lead.id},
        )
        assert cross_tenant.status_code == 400

        team_board = client.get(
            '/api/action-items', headers=headers(manager)
        )
        assert team_board.status_code == 200
        assert team_board.get_json()['pagination']['total'] == 2
        member_board = client.get(
            '/api/action-items', headers=headers(member)
        )
        assert member_board.status_code == 200
        assert member_board.get_json()['pagination']['total'] == 2

        forbidden_assignment = client.post(
            f'/api/action-items/{action_id}/assign',
            headers=headers(member),
            json={'assigned_user_id': second_member.id},
        )
        assert forbidden_assignment.status_code == 403

        source_rebind = client.put(
            f'/api/action-items/{action_id}', headers=headers(manager),
            json={'source_type': 'VISIT', 'source_id': visit.id},
        )
        assert source_rebind.status_code == 400

        updated = client.put(
            f'/api/action-items/{action_id}', headers=headers(manager),
            json={
                'title': 'Phase 8 Updated Follow-up',
                'priority_key': 'HIGH',
            },
        )
        assert updated.status_code == 200, updated.get_json()
        assert updated.get_json()['action_item']['title'] == (
            'Phase 8 Updated Follow-up'
        )

        reassigned = client.post(
            f'/api/action-items/{action_id}/assign',
            headers=headers(manager),
            json={'assigned_user_id': second_member.id},
        )
        assert reassigned.status_code == 200, reassigned.get_json()
        assert NotificationEvent.query.filter_by(
            action_item_id=action_id, event_type='action_reassigned',
            user_id=second_member.id,
        ).count() == 1

        completed = client.post(
            f'/api/action-items/{action_id}/status',
            headers=headers(second_member),
            json={'status_key': 'COMPLETED'},
        )
        assert completed.status_code == 200, completed.get_json()
        assert completed.get_json()['action_item']['completed_at']
        assert NotificationEvent.query.filter_by(
            action_item_id=action_id, event_type='action_completed',
            user_id=manager.id,
        ).count() == 1

        dashboard = client.get(
            '/api/action-items/dashboard', headers=headers(manager)
        )
        assert dashboard.status_code == 200
        assert dashboard.get_json()['metrics']['completed_today'] == 1

        config_update = client.put(
            '/api/action-items/configuration/types/CALL',
            headers=headers(admin),
            json={'display_name': 'Customer Call', 'display_order': 2},
        )
        assert config_update.status_code == 200, config_update.get_json()
        assert config_update.get_json()['configuration']['internal_key'] == 'CALL'
        assert config_update.get_json()['configuration']['display_name'] == 'Customer Call'

        invalid_type = client.post(
            '/api/action-items/configuration/types',
            headers=headers(admin),
            json={
                'internal_key': 'INVALID_DEFAULT',
                'display_name': 'Invalid Default',
                'default_priority_key': 'NOT_A_PRIORITY',
            },
        )
        assert invalid_type.status_code == 400

        references = client.get(
            '/api/action-items/references', headers=headers(manager)
        )
        assert references.status_code == 200
        assert all(references.get_json()['board_profile']['capabilities'].values())

        assert client.post(
            f'/api/action-items/{visit_action.get_json()["action_item"]["id"]}/archive',
            headers=headers(admin),
        ).status_code == 200
        assert client.post(
            f'/api/action-items/{visit_action.get_json()["action_item"]["id"]}/restore',
            headers=headers(admin),
        ).status_code == 200

        assert ActivityLog.query.filter_by(
            tenant_id=tenant.id, module='action_items'
        ).count() >= 8
        assert client.get(
            f'/api/action-items/{action_id}',
            headers={
                **headers(other_user),
                'Authorization': f"Bearer {create_token(str(other_user.id), other_user.role, other.id, login_context='tenant')}",
            },
        ).status_code == 404


if __name__ == '__main__':
    test_action_item_workflow()
    print('Phase 8 Action Item integration passed')
