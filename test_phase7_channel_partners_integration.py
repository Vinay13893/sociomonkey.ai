"""In-memory workflow checks for Phase 7 Channel Partners."""


def test_channel_partner_workflow():
    from app import create_app
    from app.models.activity import ActivityLog
    from app.models.base import db
    from app.models.channel_partner import (
        ChannelPartner,
        ChannelPartnerAssignment,
        ChannelPartnerContact,
    )
    from app.models.location import Location
    from app.models.notification import Notification
    from app.models.organisation import BusinessRole, UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.project import Project
    from app.models.push import NotificationEvent
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import (
        VisitStatusConfiguration,
        VisitTypeConfiguration,
    )
    from app.utils.jwt import create_token
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = (
        lambda user, capability, scope='OWN', scope_ref_id=None: {
            'allowed': True, 'source': 'test', 'scope': scope,
        }
    )
    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Phase 7 Tenant', slug='phase7')
        other = Tenant(name='Other Phase 7 Tenant', slug='other-phase7')
        db.session.add_all([tenant, other])
        db.session.flush()
        admin = User(
            name='Phase 7 Admin', email='admin-phase7@example.invalid',
            password_hash='x', role='superadmin', tenant_id=tenant.id,
            is_active=True,
        )
        manager = User(
            name='Phase 7 Manager', email='manager-phase7@example.invalid',
            password_hash='x', role='sales_manager', tenant_id=tenant.id,
            is_active=True,
        )
        rm = User(
            name='Phase 7 RM', email='rm-phase7@example.invalid',
            password_hash='x', role='team_member', tenant_id=tenant.id,
            is_active=True,
        )
        other_user = User(
            name='Other User', email='other-cp@example.invalid',
            password_hash='x', role='superadmin', tenant_id=other.id,
            is_active=True,
        )
        db.session.add_all([admin, manager, rm, other_user])
        db.session.flush()
        sales_role = BusinessRole(
            tenant_id=tenant.id, key='SALES_MANAGER',
            display_name='Sales Manager', is_active=True,
        )
        rm_role = BusinessRole(
            tenant_id=tenant.id, key='RELATIONSHIP_MANAGER',
            display_name='Relationship Manager', is_active=True,
        )
        db.session.add_all([sales_role, rm_role])
        db.session.flush()
        db.session.add_all([
            UserBusinessRole(
                tenant_id=tenant.id, user_id=manager.id,
                business_role_id=sales_role.id, is_primary=True,
                assigned_by=admin.id,
            ),
            UserBusinessRole(
                tenant_id=tenant.id, user_id=rm.id,
                business_role_id=rm_role.id, is_primary=True,
                assigned_by=admin.id,
            ),
        ])
        product = Product.query.filter_by(slug='lms').first()
        db.session.add(TenantProduct(
            tenant_id=tenant.id, product_id=product.id, status='active'
        ))
        project = Project(
            tenant_id=tenant.id, name='Phase 7 Project',
            is_active=True, created_by=admin.id,
        )
        other_project = Project(
            tenant_id=other.id, name='Other Project',
            is_active=True, created_by=other_user.id,
        )
        location = Location(
            tenant_id=tenant.id, code='P7-GALLERY',
            name='Phase 7 Gallery', location_type='SALES_GALLERY',
            created_by=admin.id, updated_by=admin.id,
        )
        db.session.add_all([project, other_project, location])
        db.session.add(VisitTypeConfiguration(
            tenant_id=tenant.id, internal_key='CHANNEL_PARTNER',
            display_name='Channel Partner Visit', display_order=1,
            updated_by=admin.id,
        ))
        for order, key in enumerate(
            ['SCHEDULED', 'CHECKED_IN', 'COMPLETED'], 1
        ):
            db.session.add(VisitStatusConfiguration(
                tenant_id=tenant.id, internal_key=key,
                display_name=key.title(), display_order=order,
                updated_by=admin.id, is_terminal=key == 'COMPLETED',
            ))
        db.session.commit()

        token = create_token(
            str(admin.id), 'superadmin', tenant.id, login_context='tenant'
        )
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Product-Slug': 'lms',
            'Content-Type': 'application/json',
        }
        client = app.test_client()
        created = client.post(
            '/api/channel-partners', headers=headers,
            json={
                'partner_type': 'ORGANISATION',
                'name': 'Phase 7 Partner',
                'organisation_name': 'Phase 7 Partner Organisation',
                'gst_number': 'GSTPHASE70001',
                'tags': ['priority'],
            },
        )
        assert created.status_code == 201, created.get_json()
        partner_id = created.get_json()['channel_partner']['id']

        contact = client.post(
            f'/api/channel-partners/{partner_id}/contacts',
            headers=headers,
            json={
                'name': 'Primary Contact',
                'mobile_numbers': ['+919999999999'],
                'email_addresses': ['primary@example.invalid'],
                'is_primary': True,
            },
        )
        assert contact.status_code == 201, contact.get_json()
        assert ChannelPartnerContact.query.filter_by(
            channel_partner_id=partner_id, is_primary=True
        ).count() == 1
        replacement_contact = client.post(
            f'/api/channel-partners/{partner_id}/contacts',
            headers=headers,
            json={
                'name': 'Replacement Primary Contact',
                'mobile_numbers': ['+918888888888'],
                'is_primary': True,
            },
        )
        assert replacement_contact.status_code == 201, (
            replacement_contact.get_json()
        )
        assert ChannelPartnerContact.query.filter_by(
            channel_partner_id=partner_id, is_primary=True, is_active=True
        ).count() == 1

        project_link = client.post(
            f'/api/channel-partners/{partner_id}/projects',
            headers=headers,
            json={'project_id': project.id, 'relationship_type': 'PREFERRED'},
        )
        assert project_link.status_code == 201
        cross_project = client.post(
            f'/api/channel-partners/{partner_id}/projects',
            headers=headers,
            json={
                'project_id': other_project.id,
                'relationship_type': 'ACTIVE',
            },
        )
        assert cross_project.status_code == 400

        sales_assignment = client.post(
            f'/api/channel-partners/{partner_id}/assignments',
            headers=headers,
            json={
                'user_id': manager.id,
                'assignment_type': 'SALES_MANAGER',
            },
        )
        assert sales_assignment.status_code == 201, sales_assignment.get_json()
        rm_assignment = client.post(
            f'/api/channel-partners/{partner_id}/assignments',
            headers=headers,
            json={
                'user_id': rm.id,
                'assignment_type': 'RELATIONSHIP_MANAGER',
            },
        )
        assert rm_assignment.status_code == 201, rm_assignment.get_json()
        assert ChannelPartnerAssignment.query.filter_by(
            channel_partner_id=partner_id, is_active=True
        ).count() == 2
        assert Notification.query.filter(
            Notification.user_id.in_([manager.id, rm.id]),
            Notification.source == 'channel_partners',
        ).count() == 2
        assert NotificationEvent.query.filter_by(
            channel_partner_id=partner_id,
            event_type='channel_partner_assigned',
        ).count() == 2

        note = client.post(
            f'/api/channel-partners/{partner_id}/notes',
            headers=headers, json={'content': 'Internal relationship note'},
        )
        assert note.status_code == 201

        visit = client.post(
            '/api/visits', headers=headers,
            json={
                'visit_type_key': 'CHANNEL_PARTNER',
                'status_key': 'SCHEDULED',
                'location_id': location.id,
                'purpose': 'Partner project discussion',
                'participants': [{
                    'participant_type': 'CHANNEL_PARTNER',
                    'reference_id': partner_id,
                    'is_primary': True,
                }],
            },
        )
        assert visit.status_code == 201, visit.get_json()
        visit_id = visit.get_json()['visit']['id']
        arrived = client.put(
            f'/api/visits/{visit_id}', headers=headers,
            json={'status_key': 'CHECKED_IN'},
        )
        assert arrived.status_code == 200, arrived.get_json()
        assert NotificationEvent.query.filter_by(
            channel_partner_id=partner_id,
            event_type='channel_partner_visit_arrival',
        ).count() == 2
        completed = client.put(
            f'/api/visits/{visit_id}', headers=headers,
            json={'status_key': 'COMPLETED'},
        )
        assert completed.status_code == 200
        assert NotificationEvent.query.filter_by(
            channel_partner_id=partner_id,
            event_type='channel_partner_visit_completed',
        ).count() == 2

        timeline = client.get(
            f'/api/channel-partners/{partner_id}/timeline',
            headers=headers,
        )
        assert timeline.status_code == 200
        timeline_types = {
            row['type'] for row in timeline.get_json()['timeline']
        }
        assert {
            'VISIT', 'NOTE', 'ASSIGNMENT', 'ACTIVITY', 'NOTIFICATION',
        }.issubset(timeline_types)

        updated = client.put(
            f'/api/channel-partners/{partner_id}',
            headers=headers, json={'rera_number': 'RERA-PHASE7'},
        )
        assert updated.status_code == 200
        assert NotificationEvent.query.filter_by(
            channel_partner_id=partner_id,
            event_type='channel_partner_profile_changed',
        ).count() == 2

        other_partner = ChannelPartner(
            tenant_id=other.id, code='OTHER-CP',
            partner_type='INDIVIDUAL', name='Other Partner',
            created_by=other_user.id, updated_by=other_user.id,
        )
        db.session.add(other_partner)
        db.session.commit()
        assert client.get(
            f'/api/channel-partners/{other_partner.id}', headers=headers
        ).status_code == 404

        assert client.post(
            f'/api/channel-partners/{partner_id}/archive', headers=headers
        ).status_code == 200
        assert client.post(
            f'/api/channel-partners/{partner_id}/restore', headers=headers
        ).status_code == 200
        assert ActivityLog.query.filter_by(
            tenant_id=tenant.id, module='channel_partners'
        ).count() >= 8


if __name__ == '__main__':
    test_channel_partner_workflow()
    print('Phase 7 Channel Partner integration passed')
