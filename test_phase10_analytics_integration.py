from datetime import datetime


def test_phase10_analytics_integration():
    from app import create_app, db
    from app.models.action_item import ActionItem
    from app.models.business_configuration import LeadStatusConfiguration
    from app.models.channel_partner import ChannelPartner
    from app.models.lead import Lead
    from app.models.location import Location, MeetingRoom
    from app.models.organisation import (
        OrganisationUnit, OrganisationUnitMembership,
    )
    from app.models.pipeline import PipelineTransition
    from app.models.product import Product, TenantProduct
    from app.models.project import Project
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import Visit, VisitParticipant
    from app.utils.jwt import create_token

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Analytics Tenant', slug='analytics')
        other = Tenant(name='Other Analytics', slug='other-analytics')
        db.session.add_all([tenant, other])
        db.session.flush()
        admin = User(
            name='Analytics Admin', email='analytics-admin@example.invalid',
            password_hash='x', role='superadmin', tenant_id=tenant.id,
            is_active=True,
        )
        manager = User(
            name='Analytics Manager', email='analytics-manager@example.invalid',
            password_hash='x', role='sales_manager', tenant_id=tenant.id,
            is_active=True,
        )
        member = User(
            name='Analytics Member', email='analytics-member@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            manager_id=manager.id, is_active=True,
        )
        other_admin = User(
            name='Other Admin', email='analytics-other@example.invalid',
            password_hash='x', role='superadmin', tenant_id=other.id,
            is_active=True,
        )
        db.session.add_all([admin, manager, member, other_admin])
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
        unit = OrganisationUnit(
            tenant_id=tenant.id, code='SALES', name='Sales',
            unit_type='SALES', created_by=admin.id,
        )
        project = Project(
            tenant_id=tenant.id, name='Analytics Project',
            is_active=True, created_by=admin.id,
        )
        location = Location(
            tenant_id=tenant.id, code='GALLERY', name='Analytics Gallery',
            location_type='SALES_GALLERY', created_by=admin.id,
            updated_by=admin.id,
        )
        partner = ChannelPartner(
            tenant_id=tenant.id, code='CP-10', partner_type='INDIVIDUAL',
            name='Analytics Partner', created_by=admin.id,
            updated_by=admin.id,
        )
        db.session.add_all([unit, project, location, partner])
        db.session.flush()
        db.session.add(OrganisationUnitMembership(
            tenant_id=tenant.id, organisation_unit_id=unit.id,
            user_id=member.id, is_primary=True, created_by=admin.id,
        ))
        room = MeetingRoom(
            tenant_id=tenant.id, location_id=location.id,
            name='Room One', capacity=6, created_by=admin.id,
            updated_by=admin.id,
        )
        db.session.add(room)
        db.session.flush()
        lead = Lead(
            tenant_id=tenant.id, name='Analytics Lead', source='Meta',
            status='booking_done', project_id=project.id,
            assigned_to=member.id, channel_partner_id=partner.id,
            created_by=admin.id, is_active=True, is_test=False,
        )
        other_lead = Lead(
            tenant_id=other.id, name='Other Lead', source='Other',
            status='new', created_by=other_admin.id, is_active=True,
            is_test=False,
        )
        db.session.add_all([lead, other_lead])
        db.session.flush()
        visit = Visit(
            tenant_id=tenant.id, visit_type_key='WALK_IN',
            status_key='COMPLETED', location_id=location.id,
            meeting_room_id=room.id, project_id=project.id,
            lead_id=lead.id, assigned_user_id=member.id,
            visitor_count=2, actual_check_in=datetime.utcnow(),
            actual_check_out=datetime.utcnow(),
            created_by=admin.id, updated_by=admin.id,
        )
        db.session.add(visit)
        db.session.flush()
        db.session.add(VisitParticipant(
            tenant_id=tenant.id, visit_id=visit.id,
            participant_type='CHANNEL_PARTNER',
            reference_id=partner.id, display_name='CP',
        ))
        db.session.add(ActionItem(
            tenant_id=tenant.id, source_type='LEAD', source_id=lead.id,
            action_type_key='FOLLOW_UP', status_key='COMPLETED',
            priority_key='NORMAL', title='Analytics action',
            assigned_user_id=member.id, organisation_unit_id=unit.id,
            project_id=project.id, location_id=location.id,
            created_by=admin.id, updated_by=admin.id,
        ))
        db.session.add(PipelineTransition(
            tenant_id=tenant.id, lead_id=lead.id,
            from_stage_key='new', to_stage_key='booking_done',
            changed_by_user_id=admin.id, source='PIPELINE',
            correlation_id='phase10-analytics-transition',
            rule_evaluation={}, transition_context={},
            current_owner_id=member.id,
        ))
        for key, label, success in (
            ('new', 'New', False), ('booking_done', 'Booked', True),
        ):
            db.session.add(LeadStatusConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=label, display_order=1,
                is_success=success, updated_by=admin.id,
            ))
        db.session.commit()

        def headers(user):
            token = create_token(
                str(user.id), user.role, user.tenant_id,
                login_context='tenant',
            )
            return {
                'Authorization': f'Bearer {token}',
                'X-Product-Slug': 'lms',
            }

        client = app.test_client()
        options = client.get(
            '/api/reports/v2/filters', headers=headers(admin)
        )
        assert options.status_code == 200
        assert options.get_json()['scope'] == 'TENANT'

        for report in (
            'pipeline', 'leads', 'organisations', 'users', 'projects',
            'locations', 'visits', 'reception', 'meeting-rooms',
            'channel-partners', 'action-items',
        ):
            response = client.get(
                f'/api/reports/v2/{report}?limit=10',
                headers=headers(admin),
            )
            assert response.status_code == 200, (
                report, response.get_json()
            )
            body = response.get_json()
            assert body['report'] == report
            assert len(body['rows']) <= 10
            assert body['scope'] == 'TENANT'

        leads = client.get(
            '/api/reports/v2/leads', headers=headers(admin)
        ).get_json()
        assert next(
            metric['value'] for metric in leads['summary']
            if metric['key'] == 'leads'
        ) == 1
        assert all(row['source'] != 'Other' for row in leads['rows'])

        export = client.get(
            '/api/reports/v2/pipeline/export', headers=headers(admin)
        )
        assert export.status_code == 200
        assert export.mimetype == (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        denied = client.get(
            '/api/reports/v2/leads', headers=headers(member)
        )
        assert denied.status_code == 403

        manager_report = client.get(
            '/api/reports/v2/users', headers=headers(manager)
        )
        assert manager_report.status_code == 200
        assert manager_report.get_json()['scope'] == 'TEAM'

        manager_export = client.get(
            '/api/reports/v2/users/export', headers=headers(manager)
        )
        assert manager_export.status_code == 403

        invalid = client.get(
            '/api/reports/v2/leads'
            '?date_from=2024-01-01&date_to=2026-01-01',
            headers=headers(admin),
        )
        assert invalid.status_code == 400

        unknown = client.get(
            '/api/reports/v2/not-a-report', headers=headers(admin)
        )
        assert unknown.status_code == 404
