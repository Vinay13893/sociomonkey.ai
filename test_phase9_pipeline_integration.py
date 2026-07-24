"""In-memory Phase 9 Pipeline Engine workflow checks."""


def test_pipeline_engine_workflow():
    from app import create_app
    from app.models.action_item import (
        ActionItem, ActionPriorityConfiguration, ActionStatusConfiguration,
        ActionTypeConfiguration,
    )
    from app.models.activity import ActivityLog
    from app.models.base import db
    from app.models.business_configuration import (
        BusinessRuleConfiguration, LeadStatusConfiguration,
    )
    from app.models.channel_partner import ChannelPartner
    from app.models.lead import Lead, LeadAssignmentHistory, StatusHistory
    from app.models.location import Location
    from app.models.notification import Notification
    from app.models.pipeline import PipelineTransition
    from app.models.product import Product, TenantProduct
    from app.models.project import Project
    from app.models.push import NotificationEvent
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import Visit
    from app.utils.jwt import create_token
    import app.routes.pipeline as pipeline_routes
    import app.services.permissions as permissions

    app = create_app('testing')

    def decision(user, capability, scope='OWN', scope_ref_id=None):
        if user.role == 'superadmin':
            granted = 'TENANT'
        elif user.role == 'sales_manager':
            granted = 'TEAM'
        else:
            granted = 'OWN'
        allowed = not (
            capability in {'pipeline.assign', 'pipeline.override'}
            and user.role == 'team_member'
        )
        return {'allowed': allowed, 'source': 'test', 'scope': granted}

    permissions.capability_decision = decision
    pipeline_routes.capability_decision = decision

    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Phase 9 Tenant', slug='phase9')
        other = Tenant(name='Other Phase 9', slug='other-phase9')
        db.session.add_all([tenant, other])
        db.session.flush()
        admin = User(
            name='Phase 9 Admin', email='admin-phase9@example.invalid',
            password_hash='x', role='superadmin', tenant_id=tenant.id,
            is_active=True,
        )
        manager = User(
            name='Phase 9 Manager', email='manager-phase9@example.invalid',
            password_hash='x', role='sales_manager', tenant_id=tenant.id,
            is_active=True,
        )
        member = User(
            name='Phase 9 Member', email='member-phase9@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            manager_id=manager.id, is_active=True,
        )
        second = User(
            name='Phase 9 Second', email='second-phase9@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            manager_id=manager.id, is_active=True,
        )
        other_admin = User(
            name='Other Admin', email='other-admin-phase9@example.invalid',
            password_hash='x', role='superadmin', tenant_id=other.id,
            is_active=True,
        )
        db.session.add_all([admin, manager, member, second, other_admin])
        db.session.flush()
        member.manager_id = manager.id
        second.manager_id = manager.id
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
            tenant_id=tenant.id, name='Phase 9 Project',
            is_active=True, created_by=admin.id,
        )
        location = Location(
            tenant_id=tenant.id, code='P9',
            name='Phase 9 Gallery', location_type='SALES_GALLERY',
            created_by=admin.id, updated_by=admin.id,
        )
        partner = ChannelPartner(
            tenant_id=tenant.id, code='P9-CP', partner_type='INDIVIDUAL',
            name='Phase 9 Partner', created_by=admin.id,
            updated_by=admin.id,
        )
        db.session.add_all([project, location, partner])
        db.session.flush()
        lead = Lead(
            tenant_id=tenant.id, name='Phase 9 Lead', status='new',
            phone='9999999999', source='Manual',
            project_id=project.id, assigned_to=member.id,
            channel_partner_id=partner.id, created_by=admin.id, is_active=True,
        )
        other_lead = Lead(
            tenant_id=other.id, name='Other Lead', status='new',
            phone='8888888888', source='Manual',
            created_by=other_admin.id, is_active=True,
        )
        db.session.add_all([lead, other_lead])
        db.session.flush()
        visit = Visit(
            tenant_id=tenant.id, visit_type_key='SCHEDULED_VISIT',
            status_key='COMPLETED', location_id=location.id,
            lead_id=lead.id, project_id=project.id,
            assigned_user_id=member.id, purpose='Pipeline rule visit',
            created_by=admin.id, updated_by=admin.id,
        )
        db.session.add(visit)
        for order, (key, name) in enumerate([
            ('FOLLOW_UP', 'Follow-up'), ('APPROVAL', 'Approval'),
        ], 1):
            db.session.add(ActionTypeConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=name, display_order=order,
                default_priority_key='NORMAL', updated_by=admin.id,
            ))
        for order, key in enumerate(['PENDING', 'COMPLETED'], 1):
            db.session.add(ActionStatusConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=key.title(), display_order=order,
                is_terminal=key == 'COMPLETED', updated_by=admin.id,
            ))
        db.session.add(ActionPriorityConfiguration(
            tenant_id=tenant.id, internal_key='NORMAL',
            display_name='Normal', display_order=1, weight=20,
            is_default=True, updated_by=admin.id,
        ))
        configs = {
            'new': {},
            'follow_up': {
                'required_action_type_keys': ['FOLLOW_UP'],
                'default_actions': [{
                    'action_type_key': 'FOLLOW_UP',
                    'title': 'Complete Lead follow-up',
                }],
            },
            'site_visit_done': {
                'entry_rule_keys': ['pipeline_visit_completed'],
            },
            'interested': {
                'entry_rule_keys': ['pipeline_approval_received'],
            },
        }
        for order, (key, values) in enumerate(configs.items(), 1):
            db.session.add(LeadStatusConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=key.replace('_', ' ').title(),
                display_order=order, is_active=True, visibility='VISIBLE',
                required_action_type_keys=values.get(
                    'required_action_type_keys', []
                ),
                default_actions=values.get('default_actions', []),
                entry_rule_keys=values.get('entry_rule_keys', []),
                exit_rule_keys=[],
                updated_by=admin.id,
            ))
        db.session.add(BusinessRuleConfiguration(
            tenant_id=tenant.id,
            rule_key='pipeline_approval_received',
            display_name='Approval received', version=1,
            definition={
                'field': 'approval_received',
                'operator': 'equals', 'value': True,
            },
            created_by=admin.id,
        ))
        db.session.commit()

        def headers(user, tenant_id=None):
            tenant_id = tenant_id or user.tenant_id
            token = create_token(
                str(user.id), user.role, tenant_id, login_context='tenant'
            )
            return {
                'Authorization': f'Bearer {token}',
                'X-Product-Slug': 'lms',
                'Content-Type': 'application/json',
            }

        client = app.test_client()
        moved = client.post(
            f'/api/pipeline/leads/{lead.id}/move',
            headers=headers(admin),
            json={'to_status': 'follow_up'},
        )
        assert moved.status_code == 200, moved.get_json()
        transition_id = moved.get_json()['transition']['id']
        assert moved.get_json()['transition']['channel_partner_id'] == partner.id
        assert ActionItem.query.filter_by(
            tenant_id=tenant.id, source_type='LEAD', source_id=lead.id,
            action_type_key='FOLLOW_UP',
        ).count() == 1
        assert StatusHistory.query.filter_by(
            lead_id=lead.id, new_status='follow_up'
        ).count() == 1
        assert ActivityLog.query.filter_by(
            tenant_id=tenant.id, action='pipeline_stage_transition'
        ).count() == 1
        assert NotificationEvent.query.filter_by(
            pipeline_transition_id=transition_id,
            event_type='pipeline_stage_changed',
        ).count() == 1
        assert Notification.query.filter_by(
            tenant_id=tenant.id, source='pipeline'
        ).count() == 1
        manager_state = db.session.get(User, manager.id)
        assert member.id in [row.id for row in manager_state.team_members]
        assert client.get(
            '/api/pipeline/dashboard', headers=headers(manager)
        ).get_json()['total_leads'] == 1

        blocked = client.post(
            f'/api/pipeline/leads/{lead.id}/move',
            headers=headers(manager),
            json={'to_status': 'interested'},
        )
        assert blocked.status_code == 409, blocked.get_json()
        assert blocked.get_json()['code'] == 'RULES_NOT_SATISFIED'

        overridden = client.post(
            f'/api/pipeline/leads/{lead.id}/move',
            headers=headers(manager),
            json={
                'to_status': 'interested', 'manager_override': True,
                'reason': 'Approved exception',
            },
        )
        assert overridden.status_code == 200, overridden.get_json()
        assert overridden.get_json()['transition']['manager_override'] is True

        visit_move = client.post(
            f'/api/pipeline/leads/{lead.id}/move',
            headers=headers(manager),
            json={
                'to_status': 'site_visit_done', 'visit_id': visit.id,
            },
        )
        assert visit_move.status_code == 200, visit_move.get_json()
        assert visit_move.get_json()['transition']['visit_id'] == visit.id

        assigned = client.post(
            f'/api/pipeline/leads/{lead.id}/assign',
            headers=headers(manager),
            json={'assigned_to': second.id, 'reason': 'Balance workload'},
        )
        assert assigned.status_code == 200, assigned.get_json()
        assert LeadAssignmentHistory.query.filter_by(
            lead_id=lead.id, assigned_to=second.id, source='PIPELINE'
        ).count() == 1

        history = client.get(
            f'/api/pipeline/leads/{lead.id}/history',
            headers=headers(manager),
        )
        assert history.status_code == 200
        assert len(history.get_json()['history']) == 3

        dashboard = client.get(
            '/api/pipeline/dashboard', headers=headers(manager)
        )
        assert dashboard.status_code == 200
        assert dashboard.get_json()['total_leads'] == 1
        assert 'todays_movements' in dashboard.get_json()
        assert dashboard.get_json()['conversion_funnel']
        assert dashboard.get_json()['stage_ageing']
        visit_ageing = next(
            row for row in dashboard.get_json()['stage_ageing']
            if row['internal_key'] == 'site_visit_done'
        )
        assert sum(visit_ageing['buckets'].values()) == 1

        stage_page = client.get(
            '/api/pipeline/stages/site_visit_done/leads?per_page=3',
            headers=headers(manager),
        )
        assert stage_page.status_code == 200
        assert stage_page.get_json()['pagination']['total'] == 1

        cross_tenant = client.post(
            f'/api/pipeline/leads/{other_lead.id}/move',
            headers=headers(admin),
            json={'to_status': 'follow_up'},
        )
        assert cross_tenant.status_code == 404
        assert PipelineTransition.query.filter_by(
            tenant_id=other.id
        ).count() == 0


if __name__ == '__main__':
    test_pipeline_engine_workflow()
    print('Phase 9 Pipeline integration passed')
