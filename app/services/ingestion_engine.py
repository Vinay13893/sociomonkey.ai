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
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.models.base import db
from app.models import Lead, StatusHistory, LeadNote, ActivityLog, User
from app.models.ingestion import IngestedLeadLog
from app.models.lead_source_mapping import LeadSourceFormMapping, MetaCampaignSnapshot
from app.services.notification_events import enqueue_lead_assigned
from app.utils.lead_source_cutoff import is_before_lead_source_cutoff

logger = logging.getLogger(__name__)


def ingestion_idempotency_key(source, platform_lead_id: str) -> str | None:
    platform_lead_id = str(platform_lead_id or '').strip()
    if not platform_lead_id:
        return None
    return f'{source.tenant_id}:{source.source_type}:{platform_lead_id}'


def capture_ingestion_event(source, raw_payload: dict, platform_lead_id: str = '', **metadata):
    """Persist the provider event before any remote enrichment or processing."""
    key = ingestion_idempotency_key(source, platform_lead_id)
    if key:
        existing = IngestedLeadLog.query.filter_by(idempotency_key=key).first()
        if existing:
            return existing, False

    log = IngestedLeadLog(
        tenant_id=source.tenant_id,
        source_id=source.id,
        source_type=source.source_type,
        correlation_id=str(uuid.uuid4()),
        idempotency_key=key,
        platform_lead_id=str(platform_lead_id or '').strip() or None,
        raw_payload=raw_payload or {},
        page_id=str(metadata.get('page_id') or '').strip() or None,
        form_id=str(metadata.get('form_id') or '').strip() or None,
        status='queued',
        received_at=datetime.utcnow(),
    )
    db.session.add(log)
    try:
        db.session.commit()
        return log, True
    except IntegrityError:
        db.session.rollback()
        if key:
            existing = IngestedLeadLog.query.filter_by(idempotency_key=key).first()
            if existing:
                return existing, False
        raise

# ── LMS fields that ingestion is allowed to set ────────────────────────────────
ALLOWED_LEAD_FIELDS = frozenset({
    'name', 'phone', 'alternate_phone', 'email',
    'source', 'project_id',
    'gclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'landing_page_url',
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


def _parse_platform_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


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


def lead_payload_has_required_identity(mapped: dict) -> bool:
    name = str(mapped.get('name') or '').strip()
    has_contact = any(str(mapped.get(field) or '').strip() for field in ('phone', 'alternate_phone', 'email'))
    return bool(name and has_contact)


def apply_form_project_mapping(source, normalised: dict, mapped: dict):
    """
    For source types that expose platform forms (Meta/Google), enforce mapping
    of form_id -> project_id before allowing ingestion.
    """
    if source.source_type not in ('meta', 'google'):
        return mapped, None

    form_id = str(normalised.get('form_id') or '').strip()
    row = None

    if form_id:
        row = LeadSourceFormMapping.query.filter_by(
            tenant_id=source.tenant_id,
            source_id=source.id,
            form_id=form_id,
            is_active=True,
        ).first()
    else:
        # Some webhook payloads arrive without form_id. If exactly one active mapping
        # exists for this source, safely infer that mapping.
        candidates = LeadSourceFormMapping.query.filter_by(
            tenant_id=source.tenant_id,
            source_id=source.id,
            is_active=True,
        ).all()
        if len(candidates) == 1:
            row = candidates[0]
            form_id = str(row.form_id or '').strip()
            normalised['form_id'] = form_id
            if not normalised.get('form_name') and row.form_name:
                normalised['form_name'] = row.form_name
        else:
            return mapped, None

    if not row or not row.project_id:
        return mapped, None

    mapped['project_id'] = row.project_id
    return mapped, row


def persist_meta_snapshot(source, normalised: dict, log: IngestedLeadLog, lead_id=None, is_test: bool = False):
    """Store non-overwrite attribution snapshot for Meta events."""
    if source.source_type != 'meta':
        return

    project_id = None
    project_name = None
    if lead_id:
        lead = Lead.query.get(lead_id)
        if lead:
            project_id = getattr(lead, 'project_id', None)
            project_name = getattr(lead, 'project_name', None)

    snapshot = MetaCampaignSnapshot(
        tenant_id=source.tenant_id,
        source_id=source.id,
        lead_id=lead_id,
        ingested_log_id=log.id,
        page_id=normalised.get('page_id'),
        form_id=normalised.get('form_id'),
        form_name=normalised.get('form_name'),
        campaign_id=normalised.get('campaign_id'),
        campaign_name=normalised.get('campaign_name'),
        ad_set_id=normalised.get('ad_set_id'),
        ad_set_name=normalised.get('ad_set_name'),
        ad_id=normalised.get('ad_id'),
        ad_name=normalised.get('ad_name'),
        is_test=is_test,
        spend=normalised.get('spend'),
        cost_per_result=normalised.get('cost_per_result'),
        ctr=normalised.get('ctr'),
        cpc=normalised.get('cpc'),
        cpm=normalised.get('cpm'),
        impressions=normalised.get('impressions'),
        reach=normalised.get('reach'),
        audience=normalised.get('audience'),
        placement=normalised.get('placement'),
        extra_metrics={
            'source': normalised.get('source'),
            'city': normalised.get('city'),
            'platform_lead_id': normalised.get('platform_lead_id'),
            'page_name': normalised.get('page_name'),
            'project_id': project_id,
            'project_name': project_name,
        },
        snapshot_at=datetime.utcnow(),
    )
    db.session.add(snapshot)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 – DUPLICATE DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

def normalize_phone_for_duplicate(value) -> str:
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    if len(digits) > 10 and digits.startswith('91'):
        digits = digits[-10:]
    return digits


def detect_duplicate(mapped: dict, source) -> Lead | None:
    """
    Returns an existing Lead if a duplicate is found, else None.
    Checks mobile/contact number only. Email is not a duplicate signal.
    Only checks within the same tenant.
    """
    tenant_id = source.tenant_id
    phone = normalize_phone_for_duplicate(mapped.get('phone'))

    if source.dup_check_phone and phone:
        candidates = Lead.query.filter_by(tenant_id=tenant_id, is_active=True).filter(Lead.phone != None).all()
        for existing in candidates:
            if normalize_phone_for_duplicate(existing.phone) == phone:
                return existing

    return None


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 – ASSIGNMENT ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def resolve_assignee(source, mapped: dict, form_mapping: LeadSourceFormMapping | None = None) -> User | None:
    """
    Determines which User to assign the new lead to based on source strategy.
    Returns a User ORM object, or None (lead stays unassigned).
    """
    strategy = source.assign_strategy or 'none'
    tenant_id = source.tenant_id

    # Per-form manager assignment has precedence for Meta/Google mapped forms.
    if form_mapping:
        mode = str(getattr(form_mapping, 'manager_assign_mode', '') or 'none').strip().lower()

        if mode == 'fixed_manager':
            manager_id = getattr(form_mapping, 'manager_id', None)
            if manager_id:
                manager = User.query.filter_by(
                    id=manager_id,
                    tenant_id=tenant_id,
                    role='sales_manager',
                    is_active=True,
                ).first()
                if manager:
                    return manager
            return None

        if mode == 'round_robin_pool':
            raw_pool = getattr(form_mapping, 'rr_manager_pool', None) or []
            pool_ids = []
            for item in raw_pool:
                try:
                    pool_ids.append(int(item))
                except (TypeError, ValueError):
                    continue
            pool_ids = [pid for pid in pool_ids if pid > 0]
            if not pool_ids:
                return None

            managers = User.query.filter(
                User.tenant_id == tenant_id,
                User.role == 'sales_manager',
                User.is_active == True,
                User.id.in_(pool_ids),
            ).order_by(User.id.asc()).all()
            if not managers:
                return None

            ordered = sorted(managers, key=lambda u: pool_ids.index(int(u.id)) if int(u.id) in pool_ids else 999999)
            next_idx = int(getattr(form_mapping, 'rr_last_index', 0) or 0) % len(ordered)
            user = ordered[next_idx]
            form_mapping.rr_last_index = (next_idx + 1) % len(ordered)
            db.session.add(form_mapping)
            return user

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

def _org_scoped_assignment_enabled(tenant_id):
    """Dark-launch gate (Phase 13d): off for every tenant unless a
    FeatureFlag row is explicitly created with is_enabled=True for that
    tenant. Keeps the new Calling Manager auto-assign tier entirely inert
    (one indexed lookup, no behaviour change) until a tenant is
    deliberately opted in."""
    from app.models.product import FeatureFlag

    flag = FeatureFlag.query.filter_by(
        tenant_id=tenant_id, flag_key='org_scoped_calling_manager_assignment',
    ).first()
    return bool(flag and flag.is_enabled)


def _resolve_calling_manager_id(tenant_id, project_id):
    """Best-effort, additive Calling Manager auto-assign - independent of
    (and never touching) the existing assignee/sales_manager_id/assigned_to
    resolution above. Returns None (leaves the slot empty) on any missing
    config or unexpected error; must never block inbound lead creation."""
    if not project_id or not _org_scoped_assignment_enabled(tenant_id):
        return None
    try:
        from app.models.project import Project
        from app.services.org_scope import resolve_org_scoped_assignee

        proj = Project.query.filter_by(id=project_id, tenant_id=tenant_id).first()
        if not proj:
            return None
        chosen = resolve_org_scoped_assignee(
            tenant_id, 'CALLING_MANAGER', proj.organisation_unit_id,
        )
        return chosen.id if chosen else None
    except Exception:
        logger.exception(
            'org-scoped Calling Manager assignment failed for tenant %s project %s',
            tenant_id, project_id,
        )
        return None


def create_lead(
    mapped: dict,
    source,
    assignee: User | None,
    log: IngestedLeadLog,
    is_test: bool = False,
    platform_created_at: datetime | None = None,
) -> Lead:
    """Create a new LMS Lead from mapped fields."""
    assigned_to = None
    sales_manager_id = None
    if assignee:
        if getattr(assignee, 'role', None) == 'sales_manager' or getattr(assignee, 'role', None) == 'superadmin':
            sales_manager_id = assignee.id
        else:
            assigned_to = assignee.id

    project_id = mapped.get('project_id')
    calling_manager_id = _resolve_calling_manager_id(source.tenant_id, project_id)

    lead = Lead(
        tenant_id=source.tenant_id,
        name=mapped.get('name') or 'Unknown',
        phone=mapped.get('phone') or '',
        alternate_phone=mapped.get('alternate_phone'),
        email=mapped.get('email'),
        source=source.name or mapped.get('source') or SOURCE_DISPLAY_NAMES.get(source.source_type, source.source_type),
        gclid=mapped.get('gclid'),
        utm_source=mapped.get('utm_source'),
        utm_medium=mapped.get('utm_medium'),
        utm_campaign=mapped.get('utm_campaign'),
        utm_content=mapped.get('utm_content'),
        utm_term=mapped.get('utm_term'),
        landing_page_url=mapped.get('landing_page_url'),
        project_id=project_id,
        budget_min=mapped.get('budget_min'),
        budget_max=mapped.get('budget_max'),
        status=mapped.get('status', 'new'),
        assigned_to=assigned_to,
        sales_manager_id=sales_manager_id,
        calling_manager_id=calling_manager_id,
        created_by=None,   # system-created
        is_test=is_test,
        created_at=platform_created_at or datetime.utcnow(),
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
    from app.services.pipeline_engine import record_initial_stage
    record_initial_stage(lead, source='INGESTION')

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
        correlation_id=log.correlation_id,
    )
    db.session.add(entry)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 6 – NOTIFICATION DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def dispatch_notification(lead: Lead, assignee: User, log: IngestedLeadLog):
    """Persist in-app and push delivery records in the lead transaction."""
    from app.services.reminder_scheduler import push_notification

    push_notification(assignee.id, {
        'type': 'lead_assigned',
        'kind': 'info',
        'title': 'New Lead Assigned',
        'message': f'New lead "{lead.name}" has been assigned to you.',
        'lead_id': lead.id,
        'lead_name': lead.name,
        'source': 'lead_ingestion',
        'tenant_id': lead.tenant_id,
        'correlation_id': log.correlation_id,
    })
    enqueue_lead_assigned(
        assignee,
        lead,
        correlation_id=log.correlation_id,
        idempotency_key=f'ingestion:{log.id}:lead-assigned:{assignee.id}',
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def ingest_lead(
    source,
    raw_payload: dict,
    normalised: dict,
    is_test: bool = False,
    ingestion_log: IngestedLeadLog | None = None,
) -> dict:
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
    platform_received_at = _parse_platform_datetime(
        normalised.get('platform_created_at')
        or normalised.get('created_time')
        or (raw_payload or {}).get('created_time')
        or (raw_payload or {}).get('created_at')
        or (raw_payload or {}).get('submission_time')
    )
    ingest_now = datetime.utcnow()
    platform_lead_id = str(normalised.get('platform_lead_id') or '').strip()

    existing_log = ingestion_log
    if existing_log is None and platform_lead_id:
        existing_log = IngestedLeadLog.query.filter_by(
            tenant_id=source.tenant_id,
            source_type=source.source_type,
            platform_lead_id=platform_lead_id,
        ).order_by(IngestedLeadLog.id.desc()).first()

    if existing_log and existing_log.status in ('processed', 'duplicate', 'ignored'):
        return {
            'status': 'duplicate',
            'lead_id': existing_log.lead_id or existing_log.dup_of_lead_id,
            'log_id': existing_log.id,
            'message': 'Meta lead already ingested',
        }

    log = existing_log or IngestedLeadLog(
        tenant_id=source.tenant_id,
        source_id=source.id,
        source_type=source.source_type,
        correlation_id=str(uuid.uuid4()),
        idempotency_key=ingestion_idempotency_key(source, platform_lead_id),
        is_test=is_test,
    )
    log.source_id = source.id
    log.received_at = platform_received_at or ingest_now
    log.raw_payload = raw_payload
    log.platform_lead_id = platform_lead_id or None
    log.campaign_id = normalised.get('campaign_id')
    log.campaign_name = normalised.get('campaign_name')
    log.ad_set_id = normalised.get('ad_set_id')
    log.ad_set_name = normalised.get('ad_set_name')
    log.ad_id = normalised.get('ad_id')
    log.ad_name = normalised.get('ad_name')
    log.form_id = normalised.get('form_id')
    log.form_name = normalised.get('form_name')
    log.page_id = normalised.get('page_id')
    log.gclid = normalised.get('gclid')
    log.utm_source = normalised.get('utm_source')
    log.utm_medium = normalised.get('utm_medium')
    log.utm_campaign = normalised.get('utm_campaign')
    log.utm_content = normalised.get('utm_content')
    log.utm_term = normalised.get('utm_term')
    log.landing_page_url = normalised.get('landing_page_url')
    log.status = 'queued'
    log.error_message = None
    log.processed_at = None
    log.next_retry_at = None
    log.attempt_count = int(log.attempt_count or 0) + 1
    log.last_attempt_at = ingest_now
    db.session.add(log)
    db.session.flush()   # get log.id early for error reporting

    if is_before_lead_source_cutoff(platform_received_at, source):
        log.status = 'ignored'
        log.processed_at = datetime.utcnow()
        db.session.commit()
        return {
            'status': 'ignored',
            'lead_id': None,
            'log_id': log.id,
            'message': 'Lead received before the tenant lead-source cutoff',
        }

    try:
        # ── STAGE 1: Field mapping ─────────────────────────────────────────
        mapped = map_fields(normalised, source)
        mapped, form_mapping = apply_form_project_mapping(source, normalised, mapped)
        if not log.form_id and normalised.get('form_id'):
            log.form_id = normalised.get('form_id')
        if not log.form_name and normalised.get('form_name'):
            log.form_name = normalised.get('form_name')
        log.mapped_fields = mapped

        if not lead_payload_has_required_identity(mapped):
            log.status = 'error'
            log.error_message = 'Lead payload missing name or contact method'
            log.processed_at = datetime.utcnow()
            log.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
            source.total_errors = int(source.total_errors or 0) + 1
            source.last_tested_at = datetime.utcnow()
            source.last_test_result = 'fail'
            source.last_test_message = 'Lead payload missing name or contact method.'
            db.session.commit()
            return {
                'status': 'error',
                'lead_id': None,
                'log_id': log.id,
                'message': 'Lead payload missing name or contact method',
            }

        # ── STAGE 2: Duplicate detection ──────────────────────────────────
        existing = detect_duplicate(mapped, source)
        if existing:
            dup_mode = source.dup_mode or 'skip'

            if dup_mode == 'skip':
                log.status = 'duplicate'
                log.dup_of_lead_id = existing.id
                log.processed_at = datetime.utcnow()
                source.total_leads_ingested += 1
                source.last_lead_at = platform_received_at or datetime.utcnow()
                source.last_tested_at = datetime.utcnow()
                source.last_test_result = 'pass'
                source.last_test_message = 'Realtime webhook event processed (duplicate skipped).'
                persist_meta_snapshot(source, normalised, log, existing.id, is_test=is_test)
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
                source.last_lead_at = platform_received_at or datetime.utcnow()
                source.last_tested_at = datetime.utcnow()
                source.last_test_result = 'pass'
                source.last_test_message = 'Realtime webhook event processed (duplicate updated).'
                persist_meta_snapshot(source, normalised, log, existing.id, is_test=is_test)
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
        assignee = resolve_assignee(source, mapped, form_mapping)

        # ── STAGE 4: Lead creation ─────────────────────────────────────────
        flag_dup_of = mapped.pop('_flag_dup_of', None)
        lead = create_lead(
            mapped,
            source,
            assignee,
            log,
            is_test=is_test,
            platform_created_at=platform_received_at,
        )

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
        source.last_lead_at = platform_received_at or datetime.utcnow()
        source.last_tested_at = datetime.utcnow()
        source.last_test_result = 'pass'
        source.last_test_message = 'Realtime webhook event processed.'
        db.session.add(source)
        persist_meta_snapshot(source, normalised, log, lead.id, is_test=is_test)

        if assignee:
            dispatch_notification(lead, assignee, log)
        db.session.commit()

        return {
            'status': 'created',
            'lead_id': lead.id,
            'log_id': log.id,
            'message': f'Lead #{lead.id} created',
        }

    except Exception as exc:
        logger.exception('ingestion_engine: pipeline error: %s', exc)
        try:
            failed_log_id = getattr(log, 'id', None)
            source_id = getattr(source, 'id', None)
            db.session.rollback()
            log = db.session.get(IngestedLeadLog, failed_log_id) if failed_log_id else log
            source = db.session.get(type(source), source_id) if source_id else source
            log.status = 'error'
            log.error_message = str(exc)[:1000]
            log.processed_at = datetime.utcnow()
            log.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
            source.total_errors = int(source.total_errors or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()
        return {
            'status': 'error',
            'lead_id': None,
            'log_id': getattr(log, 'id', None),
            'message': str(exc),
        }
