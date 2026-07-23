"""Channel Partner events routed through existing notification infrastructure."""

from app.models.channel_partner import (
    ChannelPartner,
    ChannelPartnerAssignment,
)
from app.models.visit import VisitParticipant
from app.services.notification_events import enqueue_channel_partner_event
from app.services.reminder_scheduler import push_notification


def _notify(user, partner, kind, correlation_id, visit=None):
    titles = {
        'assigned': 'Channel Partner Assigned',
        'visit_arrival': 'Channel Partner Arrived',
        'visit_completed': 'Channel Partner Visit Completed',
        'profile_changed': 'Channel Partner Profile Updated',
    }
    push_notification(user.id, {
        'tenant_id': partner.tenant_id,
        'type': f'channel_partner_{kind}',
        'kind': 'info',
        'title': titles[kind],
        'message': partner.name,
        'source': 'channel_partners',
        'channel_partner_id': partner.id,
        'visit_id': getattr(visit, 'id', None),
        'correlation_id': correlation_id,
    })
    enqueue_channel_partner_event(
        user, partner, kind, correlation_id=correlation_id, visit=visit,
        idempotency_key=(
            f'channel-partner:{partner.id}:{kind}:'
            f'{getattr(visit, "id", "profile")}:{user.id}:{correlation_id}'
        ),
    )


def notify_channel_partner_assignment(user, partner, correlation_id):
    _notify(user, partner, 'assigned', correlation_id)


def notify_channel_partner_profile_change(partner, correlation_id):
    assignments = ChannelPartnerAssignment.query.filter_by(
        tenant_id=partner.tenant_id,
        channel_partner_id=partner.id,
        is_active=True,
    ).all()
    seen = set()
    for assignment in assignments:
        if assignment.user_id in seen or not assignment.user:
            continue
        seen.add(assignment.user_id)
        _notify(
            assignment.user, partner, 'profile_changed', correlation_id
        )


def notify_channel_partner_visit(visit, kind, correlation_id):
    if kind not in {'visit_arrival', 'visit_completed'}:
        return
    participant_rows = VisitParticipant.query.filter_by(
        tenant_id=visit.tenant_id,
        visit_id=visit.id,
        participant_type='CHANNEL_PARTNER',
    ).filter(VisitParticipant.reference_id.isnot(None)).all()
    partner_ids = {row.reference_id for row in participant_rows}
    if not partner_ids:
        return
    partners = ChannelPartner.query.filter(
        ChannelPartner.tenant_id == visit.tenant_id,
        ChannelPartner.id.in_(partner_ids),
        ChannelPartner.is_active.is_(True),
    ).all()
    for partner in partners:
        assignments = ChannelPartnerAssignment.query.filter_by(
            tenant_id=visit.tenant_id,
            channel_partner_id=partner.id,
            is_active=True,
        ).all()
        seen = set()
        for assignment in assignments:
            if assignment.user_id in seen or not assignment.user:
                continue
            seen.add(assignment.user_id)
            _notify(
                assignment.user, partner, kind, correlation_id, visit=visit
            )
