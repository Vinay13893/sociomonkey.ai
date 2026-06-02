"""
Lead Ingestion Engine
======================
Generic pipeline for all lead sources.

Pipeline:
  raw_payload  (source-specific)
      │
      ▼
  FieldMapper          – maps source fields → LMS fields
      │
      ▼
  DuplicateDetector    – phone/email match against existing leads
      │
      ▼
  AssignmentEngine     – round-robin / fixed / project / manager
      │
      ▼
  LeadCreator          – persists Lead + StatusHistory
      │
      ▼
  TimelineWriter       – ActivityLog entry ("Lead created via Facebook")
      │
      ▼
  NotificationDispatcher – enqueues push notification to assigned user

Each stage is a plain function that accepts/returns a context dict so new
sources only need to implement a Normalizer → everything else is shared.

Usage:
    from app.services.ingestion_engine import ingest_lead

    result = ingest_lead(source, raw_payload, normalizer_fn)
    # result: {'status': 'created'|'duplicate'|'updated'|'flagged'|'error',
    #          'lead_id': int, 'log_id': int, 'message': str}
"""

import logging
from datetime import datetime

from app.models.base import db
from app.models import Lead, StatusHistory, LeadNote, ActivityLog, User
from app.models.ingestion import IngestedLeadLog
from app.services.notification_events import enqueue_lead_assigned

logger = logging.getLogger(__name__)

# ── LMS fields that ingestion is allowed to set ────────────────────────────────
ALLOWED_LEAD_FIELDS = frozenset({
    'name', 'phone', 'alternate_phone', 'email',
    'source', 'project_id',
    'budget_min', 'budget_max',
    'status',
})

SOURCE_DISPLAY_NAMES = {
    'meta':           'Facebook / Instagram',
    'google':         'Google Lead Form',
    'webhook':        'Website Form',
    'housing':        'Housing.com',
    'magicbricks':    'MagicBricks',
    'ninetynineacres': '99acres',
    'indiamart':      'IndiaMART',
    'whatsapp_form':  'WhatsApp Form',
}


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 – FIELD MAPPER
# ══════════════════════════════════════════════════════════════════════════════

def map_fields(normalised: dict, source) -> dict:
    """
    Apply the source's custom field_mapping to the normalised payload,
    then merge source.default_values (defaults are overridden by actual data).

    normalised  – dict with canonical field names already resolved by the
                  platform-specific normalizer (e.g. meta_normalizer)
    source      – LeadSource ORM row
    returns dict of LMS field names → values (only ALLOWED_LEAD_FIELDS)
    """
    mapping = source.field_mapping or {}
    defaults = source.default_values or {}

    mapped = {}
    # Start from defaults
    for k, v in defaults.items():
        if k in ALLOWED_LEAD_FIELDS:
            mapped[k] = v

    # Apply normalised values (override defaults)
    for src_field, value in normalised.items():
        lms_field = mapping.get(src_field, src_field)   # identity if not in mapping
        if lms_field in ALLOWED_LEAD_FIELDS and value not in (None, ''):
            mapped[lms_field] = value

    return mapped


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 – DUPLICATE DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

def detect_duplicate(mapped: dict, source) -> Lead | None:
    """
    Returns an existing Lead if a duplicate is found, else None.
    Checks phone first (primary), then email (secondary).
    Only checks within the same tenant.
    """
    tenant_id = source.tenant_id
    phone = (mapped.get('phone') or '').strip()
    email = (mapped.get('email') or '').strip().lower()

    # Phone check (primary)
    if source.dup_check_phone and phone:
        existing = Lead.query.filter_by(
            tenant_id=tenant_id, is_active=True
        ).filter(Lead.phone == phone).first()
        if existing:
            return existing

    # Email check (secondary)
    if source.dup_check_email and email:
        existing = Lead.query.filter(
            Lead.tenant_id == tenant_id,
            Lead.is_active == True,
            Lead.email != None,
            db.func.lower(Lead.email) == email,
        ).first()
        if existing:
            return existing

    return None


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 – ASSIGNMENT ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def resolve_assignee(source, mapped: dict) -> User | None:
    """
    Determines which User to assign the new lead to based on source strategy.
    Returns a User ORM object, or None (lead stays unassigned).
    """
    strategy = source.assign_strategy or 'none'
    tenant_id = source.tenant_id

    if strategy == 'none':
        return None

    if strategy == 'fixed_user':
        if source.assign_fixed_user_id:
            return User.query.filter_by(
                id=source.assign_fixed_user_id,
                tenant_id=tenant_id,
                is_active=True,
            ).first()
        return None

    if strategy == 'manager_based':
        if source.assign_manager_id:
            return User.query.filter_by(
                id=source.assign_manager_id,
                tenant_id=tenant_id,
                is_active=True,
            ).first()
        return None

    if strategy == 'project_based':
        project_id = mapped.get('project_id')
        if project_id:
            # Assign to the sales_manager linked to this project, if set
            from app.models.project import Project
            proj = Project.query.filter_by(id=project_id, tenant_id=tenant_id).first()
            if proj and proj.sales_manager_id:
                return User.query.filter_by(
                    id=proj.sales_manager_id, is_active=True
                ).first()
        return None

    if strategy == 'round_robin':
        pool_ids = source.rr_user_pool or []
        if not pool_ids:
            # Fall back to all active team_members in tenant
            pool = User.query.filter_by(
                tenant_id=tenant_id, is_active=True, role='team_member'
            ).order_by(User.id).all()
            pool_ids = [u.id for u in pool]
        if not pool_ids:
            return None
        # Advance index (with wrapping)
        next_idx = (source.rr_last_index or 0) % len(pool_ids)
        user = User.query.filter_by(
            id=pool_ids[next_idx], tenant_id=tenant_id, is_active=True
        ).first()
        source.rr_last_index = (next_idx + 1) % len(pool_ids)
        db.session.add(source)
        return user

    return None


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 – LEAD CREATOR / UPDATER
# ══════════════════════════════════════════════════════════════════════════════

def create_lead(mapped: dict, source, assignee: User | None, log: IngestedLeadLog) -> Lead:
    """Create a new LMS Lead from mapped fields."""
    lead = Lead(
        tenant_id=source.tenant_id,
        name=mapped.get('name') or 'Unknown',
        phone=mapped.get('phone') or '',
        alternate_phone=mapped.get('alternate_phone'),
        email=mapped.get('email'),
        source=mapped.get('source') or SOURCE_DISPLAY_NAMES.get(source.source_type, source.source_type),
        project_id=mapped.get('project_id'),
        budget_min=mapped.get('budget_min'),
        budget_max=mapped.get('budget_max'),
        status=mapped.get('status', 'new'),
        assigned_to=assignee.id if assignee else None,
        created_by=None,   # system-created
    )
    db.session.add(lead)
    db.session.flush()   # get lead.id

    # Status history entry
    db.session.add(StatusHistory(
        lead_id=lead.id,
        old_status=None,
        new_status=lead.status,
        changed_by=None,
    ))

    return lead


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 5 – TIMELINE WRITER
# ══════════════════════════════════════════════════════════════════════════════

def write_timeline(lead: Lead, source, log: IngestedLeadLog):
    """
    Create an ActivityLog entry describing how the lead arrived.
    Visible in Lead Timeline and Activity Logs.
    """
    src_label = SOURCE_DISPLAY_NAMES.get(source.source_type, source.source_type)
    parts = [f'Lead created via {src_label}']
    if log.campaign_name:
        parts.append(f'Campaign: {log.campaign_name}')
    if log.ad_name:
        parts.append(f'Ad: {log.ad_name}')
    if log.form_name:
        parts.append(f'Form: {log.form_name}')

    entry = ActivityLog(
        tenant_id=source.tenant_id,
        user_id=None,
        action='lead_ingested',
        module='ingestion',
        resource_id=lead.id,
        resource_type='Lead',
        new_value={
            'source_type':    source.source_type,
            'source_name':    source.name,
            'campaign':       log.campaign_name,
            'ad_name':        log.ad_name,
            'form_name':      log.form_name,
            'platform_lead_id': log.platform_lead_id,
        },
        description='. '.join(parts),
    )
    db.session.add(entry)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 6 – NOTIFICATION DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def dispatch_notification(lead: Lead, assignee: User):
    """Enqueue a push notification to the assigned user."""
    try:
        enqueue_lead_assigned(assignee, lead)
    except Exception as exc:
        logger.warning('ingestion_engine: notification enqueue failed: %s', exc)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def ingest_lead(source, raw_payload: dict, normalised: dict) -> dict:
    """
    Run the full ingestion pipeline for a single lead.

    source      – LeadSource ORM row (loaded with tenant relationship)
    raw_payload – Exact payload received (stored verbatim for audit)
    normalised  – Dict with canonical field names already extracted by the
                  platform normalizer (name, phone, email, campaign_name, …)

    Returns:
        {
          'status':   'created' | 'duplicate' | 'updated' | 'flagged' | 'error',
          'lead_id':  int | None,
          'log_id':   int,
          'message':  str,
        }
    """
    log = IngestedLeadLog(
        tenant_id=source.tenant_id,
        source_id=source.id,
        source_type=source.source_type,
        raw_payload=raw_payload,
        platform_lead_id=normalised.get('platform_lead_id'),
        campaign_id=normalised.get('campaign_id'),
        campaign_name=normalised.get('campaign_name'),
        ad_set_id=normalised.get('ad_set_id'),
        ad_set_name=normalised.get('ad_set_name'),
        ad_id=normalised.get('ad_id'),
        ad_name=normalised.get('ad_name'),
        form_id=normalised.get('form_id'),
        form_name=normalised.get('form_name'),
        page_id=normalised.get('page_id'),
        status='queued',
    )
    db.session.add(log)
    db.session.flush()   # get log.id early for error reporting

    try:
        # ── STAGE 1: Field mapping ─────────────────────────────────────────
        mapped = map_fields(normalised, source)
        log.mapped_fields = mapped

        # ── STAGE 2: Duplicate detection ──────────────────────────────────
        existing = detect_duplicate(mapped, source)
        if existing:
            dup_mode = source.dup_mode or 'skip'

            if dup_mode == 'skip':
                log.status = 'duplicate'
                log.dup_of_lead_id = existing.id
                log.processed_at = datetime.utcnow()
                source.total_leads_ingested += 1
                source.last_lead_at = datetime.utcnow()
                db.session.commit()
                return {
                    'status': 'duplicate',
                    'lead_id': existing.id,
                    'log_id': log.id,
                    'message': f'Duplicate of lead #{existing.id} – skipped',
                }

            if dup_mode == 'update':
                # Update non-null fields on the existing lead
                for field, val in mapped.items():
                    if val is not None and field in ALLOWED_LEAD_FIELDS:
                        setattr(existing, field, val)
                existing.updated_at = datetime.utcnow()
                log.status = 'duplicate'
                log.lead_id = existing.id
                log.dup_of_lead_id = existing.id
                log.processed_at = datetime.utcnow()
                source.total_leads_ingested += 1
                source.last_lead_at = datetime.utcnow()
                db.session.commit()
                return {
                    'status': 'updated',
                    'lead_id': existing.id,
                    'log_id': log.id,
                    'message': f'Duplicate – updated existing lead #{existing.id}',
                }

            if dup_mode == 'flag':
                # Create lead but mark as duplicate in note
                note_text = f'⚠️ Flagged duplicate of lead #{existing.id}'
                # fall through to create, add note after
                mapped['_flag_dup_of'] = existing.id
                # (handled after lead creation below)

            # dup_mode == 'create_duplicate': fall through – create normally

        # ── STAGE 3: Assignment ────────────────────────────────────────────
        assignee = resolve_assignee(source, mapped)

        # ── STAGE 4: Lead creation ─────────────────────────────────────────
        flag_dup_of = mapped.pop('_flag_dup_of', None)
        lead = create_lead(mapped, source, assignee, log)

        if flag_dup_of:
            db.session.add(LeadNote(
                lead_id=lead.id,
                note=f'⚠️ Flagged as possible duplicate of lead #{flag_dup_of}',
                created_by=None,
            ))
            log.dup_of_lead_id = flag_dup_of

        log.lead_id = lead.id
        log.status = 'processed'
        log.processed_at = datetime.utcnow()

        # ── STAGE 5: Activity timeline ─────────────────────────────────────
        write_timeline(lead, source, log)

        # ── Update source stats ────────────────────────────────────────────
        source.total_leads_ingested += 1
        source.last_lead_at = datetime.utcnow()
        db.session.add(source)

        db.session.commit()

        # ── STAGE 6: Push notification (post-commit, non-fatal) ───────────
        if assignee:
            dispatch_notification(lead, assignee)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        return {
            'status': 'created',
            'lead_id': lead.id,
            'log_id': log.id,
            'message': f'Lead #{lead.id} created',
        }

    except Exception as exc:
        logger.exception('ingestion_engine: pipeline error: %s', exc)
        try:
            log.status = 'error'
            log.error_message = str(exc)[:1000]
            log.processed_at = datetime.utcnow()
            source.total_errors += 1
            db.session.commit()
        except Exception:
            db.session.rollback()
        return {
            'status': 'error',
            'lead_id': None,
            'log_id': getattr(log, 'id', None),
            'message': str(exc),
        }
