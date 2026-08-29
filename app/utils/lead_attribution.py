"""Batched acquisition attribution helpers for lead lists and exports."""

from sqlalchemy import func

from app.models.base import db
from app.models.ingestion import IngestedLeadLog, LeadSource
from app.models.lead_source_mapping import MetaCampaignSnapshot


def _page_name_from_source(source, page_id=''):
    if not source:
        return ''
    credentials = source.credentials or {}
    page_name = str(credentials.get('page_name') or '').strip()
    if page_name:
        return page_name
    connected = str(source.connected_account or '').strip()
    marker = ' (Page ID:'
    if marker in connected:
        return connected.split(marker, 1)[0].strip()
    return connected or str(page_id or '').strip()


def latest_meta_attribution_for_leads(lead_ids):
    """Return the latest stored Meta attribution for each lead ID in one batch."""
    ids = sorted({int(lead_id) for lead_id in (lead_ids or []) if lead_id})
    if not ids:
        return {}

    latest_log_ids = (
        db.session.query(
            IngestedLeadLog.lead_id.label('lead_id'),
            func.max(IngestedLeadLog.id).label('log_id'),
        )
        .filter(IngestedLeadLog.lead_id.in_(ids), IngestedLeadLog.source_type == 'meta')
        .group_by(IngestedLeadLog.lead_id)
        .subquery()
    )
    rows = (
        db.session.query(IngestedLeadLog, LeadSource)
        .join(latest_log_ids, IngestedLeadLog.id == latest_log_ids.c.log_id)
        .outerjoin(LeadSource, IngestedLeadLog.source_id == LeadSource.id)
        .all()
    )

    result = {}
    for log, source in rows:
        raw = log.raw_payload or {}
        mapped = log.mapped_fields or {}
        result[int(log.lead_id)] = {
            'platform_lead_id': str(log.platform_lead_id or '').strip(),
            'page_id': str(log.page_id or '').strip(),
            'page_name': str(raw.get('page_name') or mapped.get('page_name') or _page_name_from_source(source, log.page_id) or '').strip(),
            'audience': str(log.ad_set_name or '').strip(),
            'ad_set_id': str(log.ad_set_id or '').strip(),
            'ad_set_name': str(log.ad_set_name or '').strip(),
            'ad_id': str(log.ad_id or '').strip(),
            'ad_name': str(log.ad_name or '').strip(),
        }

    missing_ids = [lead_id for lead_id, item in result.items() if not item.get('page_name') or not item.get('audience') or not item.get('ad_name')]
    if missing_ids:
        latest_snapshot_ids = (
            db.session.query(
                MetaCampaignSnapshot.lead_id.label('lead_id'),
                func.max(MetaCampaignSnapshot.id).label('snapshot_id'),
            )
            .filter(MetaCampaignSnapshot.lead_id.in_(missing_ids))
            .group_by(MetaCampaignSnapshot.lead_id)
            .subquery()
        )
        snapshots = MetaCampaignSnapshot.query.join(
            latest_snapshot_ids,
            MetaCampaignSnapshot.id == latest_snapshot_ids.c.snapshot_id,
        ).all()
        for snapshot in snapshots:
            item = result.get(int(snapshot.lead_id))
            if not item:
                continue
            extra = snapshot.extra_metrics or {}
            item['page_name'] = item['page_name'] or str(extra.get('page_name') or '').strip()
            item['audience'] = item['audience'] or str(snapshot.ad_set_name or snapshot.audience or '').strip()
            item['ad_set_name'] = item['ad_set_name'] or str(snapshot.ad_set_name or '').strip()
            item['ad_set_id'] = item['ad_set_id'] or str(snapshot.ad_set_id or '').strip()
            item['ad_name'] = item['ad_name'] or str(snapshot.ad_name or '').strip()
            item['ad_id'] = item['ad_id'] or str(snapshot.ad_id or '').strip()
    return result
