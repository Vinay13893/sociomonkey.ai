"""
Cron endpoints for background job processing.

Designed for Vercel Cron Jobs (vercel.json crons array).
Auth: Bearer token matching CRON_SECRET env var.  Set the same secret
in vercel.json under `crons[].headers` or send it as a query param
(query param is fine since Vercel cron calls are internal).

Endpoints:
  GET  /api/cron/drain-notifications
       Process queued NotificationEvent rows → Web Push delivery.
       Run every minute in production.

  GET  /api/cron/health
       Lightweight health-check for cron monitoring.
"""
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

from flask import Blueprint, jsonify, request, current_app, g
from app.models.base import db
from app.utils.time_utils import parse_business_date, utc_naive_to_business_datetime

logger = logging.getLogger(__name__)

cron_bp = Blueprint('cron', __name__, url_prefix='/api/cron')


def _cron_arg(name, default=''):
    defaults = getattr(g, 'meta_backfill_defaults', {}) or {}
    return request.args.get(name, defaults.get(name, default))


def _auth_cron():
    """Return True if the cron request carries the correct CRON_SECRET or Vercel cron header."""
    # Vercel automatically injects 'x-vercel-cron: 1' on all cron invocations.
    from flask import request as _req
    if _req.headers.get('x-vercel-cron') == '1':
        return True
    secret = current_app.config.get('CRON_SECRET', '')
    if not secret:
        # No secret configured — open in dev / staging only.
        # In production you MUST set CRON_SECRET.
        env = current_app.config.get('ENV', 'development')
        if env in ('production', 'prod'):
            return False
        return True

    # Accept cron-job.org custom headers, Vercel-style bearer auth, or ?secret=.
    provided_header = (request.headers.get('X-Cron-Secret') or '').strip()
    if provided_header == secret:
        return True
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip() == secret
    query_secret = request.args.get('secret', '')
    return query_secret == secret


@cron_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'ok': True, 'ts': datetime.utcnow().isoformat()}), 200


@cron_bp.route('/drain-notifications', methods=['GET', 'POST'])
def drain_notifications():
    """
    Process queued notification events and deliver them via Web Push.

    Vercel Cron configuration (vercel.json):
      {
        "crons": [
          {
            "path": "/api/cron/drain-notifications",
            "schedule": "* * * * *"
          }
        ]
      }
    """
    if not _auth_cron():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from app.services.notification_processor import process_notification_queue
        batch = int(request.args.get('batch', 5))
        batch = max(1, min(batch, 10))  # keep worker runs below platform timeout
        summary = process_notification_queue(batch_size=batch)

        logger.info('[Cron] drain-notifications complete: %s', summary)
        return jsonify({
            'ok': True,
            'ts': datetime.utcnow().isoformat(),
            'summary': summary,
        }), 200

    except Exception as exc:
        logger.exception('[Cron] drain-notifications error: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500


@cron_bp.route('/meta-backfill', methods=['GET', 'POST'])
def meta_backfill():
    """
    Pull a small recent batch of Meta form leads for active Meta sources.
    This protects ingestion continuity when webhook delivery is delayed.
    """
    if not _auth_cron():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        import json as _json
        import urllib.parse as _parse
        import urllib.request as _req

        from app.models.ingestion import LeadSource, IngestedLeadLog
        from app.services.ingestion_engine import ingest_lead
        from app.routes.ingestion import _resolve_meta_target_source, _normalise_meta
        from app.utils.lead_source_cutoff import lead_source_cutoff_for

        # `per_form_limit` is a total-per-form cap; use pagination to reach it.
        per_form_limit = max(1, min(int(_cron_arg('per_form_limit', 5000)), 10000))
        page_size = max(1, min(int(_cron_arg('page_size', min(100, per_form_limit))), 100))
        max_pages = max(1, min(int(_cron_arg('max_pages', 50)), 200))
        include_archived = str(_cron_arg('include_archived', '')).strip().lower() in ('1', 'true', 'yes')
        full_history = str(_cron_arg('full_history', '1')).strip().lower() in ('1', 'true', 'yes', 'on')
        skip_audit = str(_cron_arg('skip_audit', '')).strip().lower() in ('1', 'true', 'yes', 'on')
        tenant_slug = str(_cron_arg('tenant_slug', '')).strip()
        source_id = request.args.get('source_id', type=int)
        source_name = str(_cron_arg('source_name', '')).strip()
        requested_form_id = str(_cron_arg('form_id', '')).strip()
        forced_date_from = str(_cron_arg('date_from', '')).strip()
        forced_date_to = str(_cron_arg('date_to', '')).strip()

        parsed_forced_from = None
        parsed_forced_to_exclusive = None
        if forced_date_from:
            try:
                parsed_forced_from = parse_business_date(forced_date_from)
            except ValueError:
                parsed_forced_from = None
        if forced_date_to:
            try:
                parsed_forced_to_exclusive = parse_business_date(forced_date_to) + timedelta(days=1)
            except ValueError:
                parsed_forced_to_exclusive = None

        sources_query = LeadSource.query.filter_by(source_type='meta', is_active=True)
        if tenant_slug:
            from app.models.tenant import Tenant
            sources_query = sources_query.join(Tenant, LeadSource.tenant_id == Tenant.id).filter(Tenant.slug == tenant_slug)
        if source_id:
            sources_query = sources_query.filter(LeadSource.id == source_id)
        if source_name:
            sources_query = sources_query.filter(LeadSource.name == source_name)
        sources = sources_query.order_by(LeadSource.id.asc()).all()
        summary = {
            'sources': len(sources),
            'full_history': full_history,
            'skip_audit': skip_audit,
            'tenant_slug': tenant_slug,
            'source_id': source_id,
            'source_name': source_name,
            'form_id': requested_form_id,
            'available_forms': [],
            'date_from': forced_date_from,
            'date_to': forced_date_to,
            'forms_scanned': 0,
            'entries_seen': 0,
            'created': 0,
            'updated': 0,
            'duplicate': 0,
            'ignored': 0,
            'error': 0,
            'subscriptions_ok': 0,
            'subscriptions_failed': 0,
            'lead_sources_patched': 0,
        }

        for source in sources:
            source_from_date = parsed_forced_from
            source_to_exclusive_date = parsed_forced_to_exclusive
            if full_history and not source_from_date and source.created_at:
                source_from_date = utc_naive_to_business_datetime(source.created_at).date()

            creds = source.credentials or {}
            page_token = (creds.get('page_access_token') or creds.get('access_token') or '').strip()
            token = (creds.get('user_token') or page_token or '').strip()
            page_id = str((creds.get('page_id') or '')).strip()
            if not token:
                continue

            if page_id:
                try:
                    sub_url = f'https://graph.facebook.com/v25.0/{_parse.quote(page_id)}/subscribed_apps'
                    sub_body = _parse.urlencode({
                        'access_token': page_token or token,
                        'subscribed_fields': 'leadgen',
                    }).encode('utf-8')
                    with _req.urlopen(_req.Request(sub_url, data=sub_body, method='POST'), timeout=15) as resp:
                        sub_payload = _json.loads(resp.read())
                    if bool((sub_payload or {}).get('success')):
                        summary['subscriptions_ok'] += 1
                    else:
                        summary['subscriptions_failed'] += 1
                except Exception:
                    summary['subscriptions_failed'] += 1

            forms = source.available_forms or []
            form_ids = []
            form_names = {}
            for f in forms:
                if isinstance(f, dict):
                    fid = str(f.get('id') or '').strip()
                    fstatus = str(f.get('status') or '').strip().upper()
                    if not fid:
                        continue
                    if not include_archived and fstatus == 'ARCHIVED':
                        continue
                    form_ids.append(fid)
                    form_names[fid] = str(f.get('name') or '').strip()
                else:
                    fid = str(f or '').strip()
                    if fid:
                        form_ids.append(fid)

            seen_form = set()
            form_ids = [fid for fid in form_ids if not (fid in seen_form or seen_form.add(fid))]
            summary['available_forms'].extend([
                {'source_id': source.id, 'form_id': fid, 'form_name': form_names.get(fid, '')}
                for fid in form_ids
            ])
            if requested_form_id:
                form_ids = [fid for fid in form_ids if fid == requested_form_id]

            for fid in form_ids:
                summary['forms_scanned'] += 1
                entries = []
                after = None
                page_count = 0
                try:
                    while len(entries) < per_form_limit and page_count < max_pages:
                        page_count += 1
                        url = (
                            f'https://graph.facebook.com/v25.0/{_parse.quote(fid)}/leads'
                            f'?fields=id,created_time,field_data,ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,form_id,page_id'
                            f'&limit={page_size}'
                            f'&access_token={_parse.quote(token)}'
                        )
                        if after:
                            url += f'&after={_parse.quote(after)}'

                        with _req.urlopen(_req.Request(url), timeout=15) as resp:
                            payload = _json.loads(resp.read())
                        page_entries = payload.get('data', []) if isinstance(payload, dict) else []
                        if not page_entries:
                            break

                        reached_older_than_from = False
                        for row in page_entries:
                            created_time = str((row or {}).get('created_time') or '').strip()
                            created_date = None
                            if created_time:
                                try:
                                    created_date = utc_naive_to_business_datetime(
                                        datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                                    ).date()
                                except ValueError:
                                    created_date = None

                            if source_from_date and created_date and created_date < source_from_date:
                                reached_older_than_from = True
                                continue
                            if source_to_exclusive_date and created_date and created_date >= source_to_exclusive_date:
                                continue

                            entries.append(row)
                            if len(entries) >= per_form_limit:
                                break

                        if reached_older_than_from:
                            break

                        paging = payload.get('paging', {}) if isinstance(payload, dict) else {}
                        cursors = paging.get('cursors', {}) if isinstance(paging, dict) else {}
                        after = cursors.get('after')
                        if not after:
                            break
                except Exception:
                    continue

                for raw in entries:
                    summary['entries_seen'] += 1
                    entry = dict(raw or {})
                    platform_lead_id = str(entry.get('id') or entry.get('leadgen_id') or '').strip()
                    if not platform_lead_id:
                        continue

                    existing = IngestedLeadLog.query.filter_by(
                        tenant_id=source.tenant_id,
                        source_type='meta',
                        platform_lead_id=platform_lead_id,
                    ).first()
                    if existing and existing.status != 'error':
                        continue

                    entry['leadgen_id'] = platform_lead_id
                    entry['form_id'] = str(entry.get('form_id') or fid)
                    entry['page_id'] = str(entry.get('page_id') or page_id)
                    entry['form_name'] = str(entry.get('form_name') or form_names.get(entry['form_id']) or '')

                    target_source = _resolve_meta_target_source(source, entry['page_id'], entry['form_id'])
                    normalised = _normalise_meta(entry)
                    if not normalised.get('page_id'):
                        normalised['page_id'] = str(page_id or '')
                    result = ingest_lead(target_source, entry, normalised)
                    status = result.get('status', 'error')
                    if status == 'created':
                        summary['created'] += 1
                    elif status == 'updated':
                        summary['updated'] += 1
                    elif status == 'duplicate':
                        summary['duplicate'] += 1
                    elif status == 'ignored':
                        summary['ignored'] += 1
                    else:
                        summary['error'] += 1

        if skip_audit:
            logger.info('[Cron] meta-backfill lightweight complete: %s', summary)
            return jsonify({'ok': True, 'ts': datetime.utcnow().isoformat(), 'summary': summary}), 200

        audit_rows = (
            IngestedLeadLog.query
            .join(LeadSource, IngestedLeadLog.source_id == LeadSource.id)
            .filter(LeadSource.source_type == 'meta')
            .filter(LeadSource.is_active == True)
            .filter(IngestedLeadLog.is_test == False)
            .filter(IngestedLeadLog.status.in_(['processed', 'duplicate', 'error']))
            .order_by(IngestedLeadLog.received_at.desc(), IngestedLeadLog.id.desc())
        )
        tenant_cutoffs = {}
        source_tenant_ids = {source.id: source.tenant_id for source in sources}
        for tenant_id in sorted({tid for tid in source_tenant_ids.values() if tid}):
            tenant_tenant_cutoff = lead_source_cutoff_for(tenant_id=tenant_id)
            if tenant_tenant_cutoff:
                tenant_cutoffs[tenant_id] = tenant_tenant_cutoff
        if tenant_cutoffs:
            tenant_ids_without_cutoff = [
                tid for tid in sorted({tid for tid in source_tenant_ids.values() if tid})
                if tid not in tenant_cutoffs
            ]
            cutoff_clauses = [
                db.and_(LeadSource.tenant_id == tid, IngestedLeadLog.received_at >= cutoff)
                for tid, cutoff in tenant_cutoffs.items()
            ]
            if tenant_ids_without_cutoff:
                cutoff_clauses.append(LeadSource.tenant_id.in_(tenant_ids_without_cutoff))
            audit_rows = audit_rows.filter(db.or_(*cutoff_clauses))
        audit_rows = audit_rows.all()
        for row in audit_rows:
            if row.lead and row.source and row.lead.source != row.source.name:
                row.lead.source = row.source.name
                summary['lead_sources_patched'] += 1
        if summary['lead_sources_patched']:
            db.session.commit()

        audit_seen = set()
        audit_counts = {'processed': 0, 'duplicate': 0, 'error': 0}
        for row in audit_rows:
            platform_id = str(row.platform_lead_id or '').strip()
            if platform_id:
                identity = ('platform', row.source_id, platform_id)
            elif row.status == 'processed' and row.lead_id:
                identity = ('processed-lead', row.source_id, row.lead_id)
            else:
                identity = (str(row.status or ''), row.id)
            if identity in audit_seen:
                continue
            audit_seen.add(identity)
            status = str(row.status or '').lower()
            if status in audit_counts:
                audit_counts[status] += 1
        audit_counts['total'] = sum(audit_counts.values())
        summary['canonical_counts'] = audit_counts

        tenant_ids = sorted({int(source.tenant_id) for source in sources if source.tenant_id})
        logs_counts = {'processed': 0, 'duplicate': 0, 'error': 0, 'total': 0}
        report_counts = {'processed': 0, 'duplicate': 0, 'errors': 0, 'total': 0}
        report_source_rows = []
        from app.routes.lead_sources import (
            _apply_test_data_filter,
            _build_performance_report,
            _connected_source_logs_query,
            _dedupe_report_source_logs,
        )
        for tenant_id in tenant_ids:
            audit_user = SimpleNamespace(tenant_id=tenant_id)
            logs_query = _connected_source_logs_query(audit_user)
            logs_query = logs_query.filter(
                IngestedLeadLog.status.in_(['processed', 'duplicate', 'error'])
            )
            logs_query = _apply_test_data_filter(logs_query, IngestedLeadLog)
            canonical_logs = _dedupe_report_source_logs(logs_query, audit_user)
            for row in canonical_logs:
                row_status = str(row.status or '').lower()
                if row_status in {'processed', 'duplicate', 'error'}:
                    logs_counts[row_status] += 1

            report = _build_performance_report(
                audit_user,
                include_unpriced=True,
            )
            snapshot = report.get('snapshot') or {}
            for source_row in report.get('source_rows') or []:
                report_source_rows.append({
                    'source_id': source_row.get('source_id'),
                    'source_name': source_row.get('source_name'),
                    'project_name': source_row.get('project_name'),
                    'leads': int(source_row.get('leads') or 0),
                    'duplicates': int(source_row.get('duplicates') or 0),
                    'errors': int(source_row.get('errors') or 0),
                    'spend': source_row.get('spend'),
                })
            report_counts['processed'] += int(snapshot.get('processed') or 0)
            report_counts['duplicate'] += int(snapshot.get('duplicate') or 0)
            report_counts['errors'] += int(snapshot.get('errors') or 0)
            report_counts['total'] += int(snapshot.get('total') or 0)
        logs_counts['total'] = (
            logs_counts['processed']
            + logs_counts['duplicate']
            + logs_counts['error']
        )
        summary['logs_counts'] = logs_counts
        summary['report_counts'] = report_counts
        summary['report_source_rows'] = report_source_rows
        summary['counts_match'] = (
            logs_counts['processed'] == report_counts['processed']
            and logs_counts['duplicate'] == report_counts['duplicate']
            and logs_counts['error'] == report_counts['errors']
            and logs_counts['total'] == report_counts['total']
        )

        logger.info('[Cron] meta-backfill complete: %s', summary)
        return jsonify({'ok': True, 'ts': datetime.utcnow().isoformat(), 'summary': summary}), 200

    except Exception as exc:
        logger.exception('[Cron] meta-backfill error: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500


@cron_bp.route('/meta-poll-5m', methods=['GET', 'POST'])
def meta_poll_5m():
    """
    Lightweight Meta lead poll for external schedulers.

    Designed for cron-job.org every 5 minutes: one Meta page per form, small
    page size, no full report audit, and a compact response.
    """
    if not _auth_cron():
        return jsonify({'error': 'Unauthorized'}), 401

    # Reuse meta_backfill with light defaults unless the scheduler overrides.
    g.meta_backfill_defaults = {
        'full_history': '0',
        'per_form_limit': '25',
        'page_size': '25',
        'max_pages': '1',
        'skip_audit': '1',
    }
    return meta_backfill()


@cron_bp.route('/meta-report-sync', methods=['GET', 'POST'])
def meta_report_sync():
    """
    Refresh Meta ad insight snapshots for report spend/CPL metrics.

    This is the server-owned equivalent of the Lead Sources report
    "Sync from Meta" button, intended to run from Vercel Cron.
    """
    if not _auth_cron():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from app.models.ingestion import LeadSource
        from app.models.tenant import Tenant
        from app.routes.lead_sources import _sync_meta_report_snapshots

        tenant_slug = str(request.args.get('tenant_slug') or '').strip()
        source_id = request.args.get('source_id', type=int)
        date_from = str(request.args.get('date_from') or '').strip()
        date_to = str(request.args.get('date_to') or '').strip()
        max_tenants = max(1, min(int(request.args.get('max_tenants', 25)), 100))

        tenant_query = (
            db.session.query(Tenant)
            .join(LeadSource, LeadSource.tenant_id == Tenant.id)
            .filter(LeadSource.source_type == 'meta')
            .filter(LeadSource.is_active == True)
            .filter(Tenant.status.in_(['active', 'trial']))
            .distinct()
            .order_by(Tenant.id.asc())
        )
        if tenant_slug:
            tenant_query = tenant_query.filter(Tenant.slug == tenant_slug)

        tenants = tenant_query.limit(max_tenants).all()
        summary = {
            'tenants_checked': len(tenants),
            'synced_rows': 0,
            'synced_sources': 0,
            'errors': [],
            'tenant_results': [],
        }

        for tenant in tenants:
            user = SimpleNamespace(tenant_id=tenant.id)
            result = _sync_meta_report_snapshots(
                user,
                date_from=date_from,
                date_to=date_to,
                source_id=source_id,
            )
            summary['synced_rows'] += int(result.get('synced_rows') or 0)
            summary['synced_sources'] += int(result.get('synced_sources') or 0)
            if result.get('errors'):
                for err in result.get('errors') or []:
                    err = dict(err or {})
                    err['tenant_id'] = tenant.id
                    err['tenant_slug'] = tenant.slug
                    summary['errors'].append(err)
            summary['tenant_results'].append({
                'tenant_id': tenant.id,
                'tenant_slug': tenant.slug,
                'synced_rows': result.get('synced_rows', 0),
                'synced_sources': result.get('synced_sources', 0),
                'last_synced_at': result.get('last_synced_at'),
            })

        summary['errors'] = summary['errors'][:20]
        logger.info('[Cron] meta-report-sync complete: %s', summary)
        return jsonify({'ok': True, 'ts': datetime.utcnow().isoformat(), 'summary': summary}), 200

    except Exception as exc:
        logger.exception('[Cron] meta-report-sync error: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500


@cron_bp.route('/check-lead-source-health', methods=['GET', 'POST'])
def check_lead_source_health_route():
    """
    Live token-validity check on every active Meta lead source. Alerts
    tenant admins (in-app + push) the first time a source's OAuth token
    goes invalid, then again roughly once/day while it stays broken.
    """
    import os as _os
    internal_token = _os.environ.get('INTERNAL_OPS_TOKEN')
    internal_ok = bool(internal_token) and request.headers.get('X-Internal-Token') == internal_token
    if not _auth_cron() and not internal_ok:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from app.services.lead_source_health import check_lead_source_health
        summary = check_lead_source_health()
        logger.info('[Cron] check-lead-source-health complete: %s', summary)
        return jsonify({'ok': True, 'ts': datetime.utcnow().isoformat(), 'summary': summary}), 200
    except Exception as exc:
        logger.exception('[Cron] check-lead-source-health error: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500


@cron_bp.route('/google-sheets-sync', methods=['GET', 'POST'])
def google_sheets_sync_route():
    """Nightly authoritative LMS-to-Sheets reconciliation for enabled tenants."""
    if not _auth_cron():
        return jsonify({'error': 'Unauthorized'}), 401

    from app.models.ingestion import LeadSource
    from app.models.business_configuration import BusinessRuleConfiguration
    from app.services.google_sheets_sync import full_sync

    sources = (
        LeadSource.query.filter_by(source_type='google', is_active=True)
        .order_by(LeadSource.tenant_id.asc(), LeadSource.id.desc()).all()
    )
    configured = {}
    script_rules = BusinessRuleConfiguration.query.filter_by(
        rule_key='google_sheets_sync', is_active=True
    ).all()
    for rule in script_rules:
        cfg = dict(rule.definition or {})
        if cfg.get('enabled') and cfg.get('script_url'):
            configured[int(rule.tenant_id)] = rule.id
    for source in sources:
        config = dict((source.credentials or {}).get('sheets_sync') or {})
        if config.get('enabled') and config.get('spreadsheet_id'):
            configured.setdefault(int(source.tenant_id), source.id)

    results, errors = [], []
    for tenant_id in configured:
        try:
            results.append({'tenant_id': tenant_id, **full_sync(tenant_id)})
        except Exception as exc:
            logger.exception('[Cron] google-sheets-sync tenant=%s failed', tenant_id)
            errors.append({'tenant_id': tenant_id, 'error': str(exc)[:300]})

    return jsonify({
        'ok': not errors,
        'tenants_configured': len(configured),
        'results': results,
        'errors': errors,
        'ts': datetime.utcnow().isoformat(),
    }), 200 if not errors else 207


@cron_bp.route('/repair-source-lead-visibility', methods=['POST'])
def repair_source_lead_visibility():
    """Repair leads linked to valid post-cutoff lead-source logs."""
    if not _auth_cron():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from app.models.ingestion import LeadSource, IngestedLeadLog
        from app.models.lead import Lead
        from app.utils.lead_source_cutoff import lead_source_cutoff_for

        rows = (
            db.session.query(IngestedLeadLog, Lead, LeadSource)
            .join(Lead, IngestedLeadLog.lead_id == Lead.id)
            .join(LeadSource, IngestedLeadLog.source_id == LeadSource.id)
            .filter(LeadSource.is_active == True)
            .filter(IngestedLeadLog.status == 'processed')
            .filter(IngestedLeadLog.lead_id.isnot(None))
            .order_by(IngestedLeadLog.received_at.desc(), IngestedLeadLog.id.desc())
            .limit(5000)
            .all()
        )

        repaired = 0
        activated = 0
        source_patched = 0
        created_at_patched = 0
        for log_row, lead, source in rows:
            cutoff = lead_source_cutoff_for(source, tenant_id=source.tenant_id)
            if cutoff and log_row.received_at and log_row.received_at < cutoff:
                continue

            changed = False
            if not lead.is_active:
                lead.is_active = True
                activated += 1
                changed = True
            if source.name and lead.source != source.name:
                lead.source = source.name
                source_patched += 1
                changed = True
            if log_row.received_at and lead.created_at != log_row.received_at:
                lead.created_at = log_row.received_at
                created_at_patched += 1
                changed = True
            if changed:
                repaired += 1

        if repaired:
            db.session.commit()

        return jsonify({
            'ok': True,
            'scanned': len(rows),
            'repaired': repaired,
            'activated': activated,
            'source_patched': source_patched,
            'created_at_patched': created_at_patched,
        }), 200
    except Exception as exc:
        db.session.rollback()
        logger.exception('[Cron] repair-source-lead-visibility failed: %s', exc)
        return jsonify({'ok': False, 'error': str(exc)}), 500
