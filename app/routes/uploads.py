import os
import re
import uuid
from datetime import datetime, timedelta
import base64
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from app.models.base import db
from app.models.job import ImportJob, ImportJobRow, ExportJob
from app.middleware import require_auth, require_role
from app.services.excel import ExcelService
from app.utils.leads import get_user_visible_leads, VALID_STATUSES, STATUS_ALIASES
from app.utils.activity import log_activity

uploads_bp = Blueprint('uploads', __name__, url_prefix='/api/leads')


# ── Database-backed preview jobs (TTL: 10 min logical expiry) ────────────────
_PREVIEW_TTL  = timedelta(minutes=10)

# Role-based field permissions
_MANAGER_FIELDS = frozenset([
    'name', 'email', 'status', 'source', 'project_id',
    'budget_min', 'budget_max', 'assigned_to', 'notes', 'callback_dt',
])
_TEAM_FIELDS = frozenset(['name', 'status', 'notes', 'callback_dt'])


def _preview_token_for(job_id: int) -> str:
    return f'preview:{job_id}'


def _preview_job_from_token(token: str) -> 'ImportJob | None':
    raw = (token or '').strip()
    if raw.startswith('preview:'):
        raw = raw.split(':', 1)[1]
    if not raw.isdigit():
        return None
    return ImportJob.query.get(int(raw))


def _create_preview_job(user, rows: list[dict], summary: dict) -> str:
    job = ImportJob(
        tenant_id=user.tenant_id,
        user_id=user.id,
        product_slug=getattr(getattr(request, 'current_product', None), 'slug', None),
        filename='bulk_update_preview',
        file_type='bulk_update',
        status='previewed',
        summary={
            'summary': summary,
            'rows': rows,
            'preview_expires_in_seconds': int(_PREVIEW_TTL.total_seconds()),
        },
        started_at=datetime.utcnow(),
    )
    db.session.add(job)
    db.session.flush()

    for index, row in enumerate(rows, start=1):
        db.session.add(ImportJobRow(
            import_job_id=job.id,
            row_number=index,
            lead_id=row.get('lead_id'),
            status='valid' if row.get('valid') else 'invalid',
            payload=row,
            errors=row.get('errors'),
            warnings=row.get('warnings'),
        ))

    db.session.commit()
    return _preview_token_for(job.id)


def _runtime_prefers_async_jobs() -> bool:
    return (os.environ.get('VERCEL') or '').strip().lower() in {'1', 'true', 'yes'}


def _captured_upload_bytes(file_storage) -> tuple[str, str | None, str]:
    file_storage.stream.seek(0)
    raw = file_storage.read()
    file_storage.stream.seek(0)
    return base64.b64encode(raw).decode('utf-8'), getattr(file_storage, 'mimetype', None), file_storage.filename or ''


def _import_file_from_job(job: ImportJob):
    data = base64.b64decode(job.source_data_b64 or '')
    buf = BytesIO(data)
    buf.filename = job.filename or ''
    return buf


def _process_import_job(job: ImportJob) -> dict:
    user = job.user
    if not user:
        raise RuntimeError('Import job owner not found')

    job.status = 'processing'
    job.started_at = job.started_at or datetime.utcnow()
    db.session.commit()

    result = ExcelService.import_leads(_import_file_from_job(job), user)
    job.summary = {
        'imported_count': len(result.get('imported_leads', []) or []),
        'error_count': len(result.get('errors', []) or []),
        'result': {k: v for k, v in result.items() if k != 'report_b64'},
    }
    job.status = 'completed'
    job.completed_at = datetime.utcnow()

    imported_rows = result.get('imported_leads', []) or []
    for index, lead in enumerate(imported_rows, start=1):
        db.session.add(ImportJobRow(
            import_job_id=job.id,
            row_number=index,
            lead_id=lead.get('lead_id') if isinstance(lead, dict) else None,
            status='completed',
            payload=lead if isinstance(lead, dict) else {'value': lead},
        ))

    for index, error in enumerate(result.get('errors', []) or [], start=1):
        db.session.add(ImportJobRow(
            import_job_id=job.id,
            row_number=len(imported_rows) + index,
            status='failed',
            payload=error if isinstance(error, dict) else {'value': error},
            errors=error if isinstance(error, list) else [str(error)],
        ))

    try:
        report_buf = ExcelService.build_import_report(
            result.get('imported_leads', []),
            result.get('errors', []),
        )
        result['report_b64'] = base64.b64encode(report_buf.read()).decode('utf-8')
    except Exception:
        result['report_b64'] = None

    db.session.commit()
    result['job'] = job.to_dict()
    return result


def process_queued_import_jobs(limit: int = 10) -> dict:
    processed = failed = 0
    rows = (
        ImportJob.query
        .filter(ImportJob.status.in_(['queued', 'processing']))
        .order_by(ImportJob.created_at.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    for job in rows:
        if job.status == 'completed':
            continue
        try:
            _process_import_job(job)
            processed += 1
        except Exception as exc:
            db.session.rollback()
            job.status = 'failed'
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.session.commit()
            failed += 1
    return {'queued_scanned': len(rows), 'processed': processed, 'failed': failed}


def _process_export_job(job: ExportJob) -> dict:
    user = job.user
    if not user:
        raise RuntimeError('Export job owner not found')

    from app.models.lead import Lead

    query = get_user_visible_leads(user)
    filters = job.filters or {}
    status = filters.get('status')
    project_id = filters.get('project_id')
    date_from = filters.get('date_from')
    date_to = filters.get('date_to')

    if status:
        query = query.filter_by(status=status)
    if project_id:
        query = query.filter_by(project_id=int(project_id))
    if date_from:
        try:
            query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Lead.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
        except ValueError:
            pass

    job.status = 'processing'
    job.started_at = job.started_at or datetime.utcnow()
    db.session.commit()

    leads = query.all()
    buf = ExcelService.export_leads(leads, title='Leads Export')
    filename = f'leads_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'

    job.status = 'completed'
    job.completed_at = datetime.utcnow()
    job.artifact_url = filename
    job.artifact_data_b64 = base64.b64encode(buf.read()).decode('utf-8')
    job.artifact_mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    db.session.commit()

    return {'job': job.to_dict(), 'filename': filename}


def process_queued_export_jobs(limit: int = 10) -> dict:
    processed = failed = 0
    rows = (
        ExportJob.query
        .filter(ExportJob.status.in_(['queued', 'processing']))
        .order_by(ExportJob.created_at.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    for job in rows:
        if job.status == 'completed':
            continue
        try:
            _process_export_job(job)
            processed += 1
        except Exception as exc:
            db.session.rollback()
            job.status = 'failed'
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.session.commit()
            failed += 1
    return {'queued_scanned': len(rows), 'processed': processed, 'failed': failed}


def _norm_phone_upd(raw) -> 'str | None':
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() == 'nan':
        return None
    if s.endswith('.0') and s[:-2].isdigit():
        s = s[:-2]
    return s or None


def _parse_update_file(file_storage, user) -> dict:
    """Parse uploaded update file; diff each row against DB. No writes."""
    import pandas as pd
    from app.models.lead import Lead
    from app.models.user import User
    from app.models.project import Project

    filename = file_storage.filename or ''
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {'.xlsx', '.xls', '.csv'}:
        return {'error': 'File type not supported — use .xlsx or .csv'}

    try:
        if ext == '.csv':
            df = pd.read_csv(file_storage)
        else:
            xl = pd.ExcelFile(file_storage)
            df = None
            for sheet in xl.sheet_names:
                if 'instruction' in sheet.lower():
                    continue
                candidate = xl.parse(sheet)
                if candidate.empty:
                    continue
                norm = candidate.columns.str.lower().str.strip()
                norm = pd.Index([re.sub(r'\s*[\[\(][^\]\)]*[\]\)]\s*', '', c).strip() for c in norm])
                if 'lead_id' in norm or 'phone' in norm:
                    candidate.columns = norm
                    df = candidate
                    break
            if df is None:
                for sheet in xl.sheet_names:
                    if 'instruction' not in sheet.lower():
                        df = xl.parse(sheet)
                        break
            if df is None:
                df = xl.parse(xl.sheet_names[0])
    except Exception as exc:
        return {'error': f'Could not parse file: {exc}'}

    # Normalise column names
    df.columns = df.columns.str.lower().str.strip()
    df.columns = pd.Index([re.sub(r'\s*[\[\(][^\]\)]*[\]\)]\s*', '', c).strip() for c in df.columns])
    df.rename(columns={
        'lead id': 'lead_id', 'id': 'lead_id',
        'customer_name': 'name', 'customer name': 'name',
        'full name': 'name', 'lead name': 'name',
        'phone number': 'phone', 'mobile': 'phone', 'mobile number': 'phone',
        'project name': 'project', 'project id': 'project_id',
        'callback date': 'callback_date', 'callback time': 'callback_time',
        'budget min': 'budget_min', 'budget max': 'budget_max',
        'min budget': 'budget_min', 'max budget': 'budget_max',
        'note': 'notes',
        'assigned to': 'assigned_to_email', 'assignee': 'assigned_to_email',
        'assign to': 'assigned_to_email',
    }, inplace=True)

    if 'lead_id' not in df.columns and 'phone' not in df.columns:
        return {'error': 'File must contain a "lead_id" or "phone" column to match existing leads'}

    if len(df) > 5000:
        return {'error': f'File has {len(df)} rows — maximum allowed is 5 000 per upload'}

    allowed = _MANAGER_FIELDS if user.role in ('superadmin', 'sales_manager') else _TEAM_FIELDS

    # Pre-load lookup tables
    projects_by_name = {p.name.lower(): p for p in
                        Project.query.filter_by(tenant_id=user.tenant_id).all()}
    users_by_email   = {u.email.lower(): u for u in
                        User.query.filter_by(tenant_id=user.tenant_id, is_active=True).all()}

    rows = []
    valid_count = invalid_count = skipped_count = 0

    for idx, row in df.iterrows():
        row_num = int(idx) + 2
        entry = {
            'row': row_num, 'lead_id': None, 'lead_name': '', 'phone': '',
            'valid': False, 'errors': [], 'warnings': [],
            'field_updates': {}, 'note_text': None, 'callback_dt': None,
        }

        def _v(col):
            val = row.get(col)
            if val is None:
                return None
            s = str(val).strip()
            return None if (not s or s.lower() == 'nan') else s

        # ── Find the lead ─────────────────────────────────────────────
        lead = None
        raw_id    = _v('lead_id')
        raw_phone = _norm_phone_upd(row.get('phone'))

        if raw_id:
            try:
                lid  = int(float(raw_id))
                lead = Lead.query.filter_by(id=lid, tenant_id=user.tenant_id,
                                            is_active=True).first()
                if not lead:
                    entry['errors'].append(f'Lead ID {lid} not found in your account')
            except (ValueError, TypeError):
                entry['errors'].append(f'Invalid lead_id "{raw_id}"')

        if not lead and not entry['errors'] and raw_phone:
            norm = re.sub(r'\D', '', raw_phone)[-10:]
            matches = Lead.query.filter(
                Lead.tenant_id == user.tenant_id,
                Lead.is_active.is_(True),
                Lead.phone.like(f'%{norm}'),
            ).all()
            if len(matches) == 1:
                lead = matches[0]
            elif len(matches) > 1:
                entry['errors'].append(
                    f'Phone {raw_phone} matches {len(matches)} leads — add a lead_id column'
                )
            else:
                entry['errors'].append(f'No lead found with phone {raw_phone}')

        if not lead:
            if not entry['errors']:
                entry['errors'].append('Could not identify lead — provide lead_id or phone')
            invalid_count += 1
            rows.append(entry)
            continue

        entry['lead_id']   = lead.id
        entry['lead_name'] = lead.name or ''
        entry['phone']     = lead.phone or ''

        # Phone immutability
        if raw_phone and lead.phone:
            nf = re.sub(r'\D', '', raw_phone)[-10:]
            nd = re.sub(r'\D', '', lead.phone)[-10:]
            if nf != nd:
                entry['warnings'].append('Phone change ignored — phone cannot be modified via bulk update')

        fu = entry['field_updates']  # alias for brevity

        # name
        new_name = _v('name') or _v('customer_name')
        if 'name' in allowed and new_name and new_name != lead.name:
            fu['name'] = {'old': lead.name, 'new': new_name}

        # email (manager+)
        if 'email' in allowed:
            new_email = _v('email')
            if new_email and new_email != (lead.email or ''):
                fu['email'] = {'old': lead.email or '', 'new': new_email}

        # status
        if 'status' in allowed:
            ns = _v('status')
            if ns:
                ns = STATUS_ALIASES.get(ns.lower(), ns.lower())
                if ns in VALID_STATUSES:
                    if ns != lead.status:
                        fu['status'] = {'old': lead.status, 'new': ns}
                else:
                    entry['warnings'].append(
                        f'Invalid status "{ns}" — skipped (valid: {", ".join(VALID_STATUSES)})'
                    )

        # source (manager+)
        if 'source' in allowed:
            ns2 = _v('source')
            if ns2 and ns2 != (lead.source or ''):
                fu['source'] = {'old': lead.source or '', 'new': ns2}

        # project (manager+)
        if 'project_id' in allowed:
            new_proj = None
            raw_pn = _v('project')
            raw_pi = _v('project_id')
            if raw_pi:
                try:
                    new_proj = Project.query.filter_by(
                        id=int(float(raw_pi)), tenant_id=user.tenant_id
                    ).first()
                except (ValueError, TypeError):
                    pass
            if not new_proj and raw_pn:
                new_proj = projects_by_name.get(raw_pn.lower())
            if new_proj and new_proj.id != lead.project_id:
                fu['project_id'] = {
                    'old': lead.project.name if lead.project else None,
                    'new': new_proj.name,
                    '_project_id_val': new_proj.id,
                }
            elif raw_pn and not new_proj:
                entry['warnings'].append(f'Project "{raw_pn}" not found — skipped')

        # budget (manager+)
        if 'budget_min' in allowed:
            for bf in ('budget_min', 'budget_max'):
                rb = _v(bf)
                if rb:
                    try:
                        nb = float(rb.replace(',', ''))
                        ob = getattr(lead, bf)
                        if ob is None or abs(nb - ob) > 0.99:
                            fu[bf] = {'old': ob, 'new': nb}
                    except (ValueError, AttributeError):
                        entry['warnings'].append(f'Invalid {bf} value "{rb}" — skipped')

        # assigned_to (manager+)
        if 'assigned_to' in allowed:
            ae = _v('assigned_to_email')
            if ae:
                nu = users_by_email.get(ae.lower())
                if nu:
                    if nu.id != lead.assigned_to:
                        fu['assigned_to'] = {
                            'old': lead.assigned_user.name if lead.assigned_user else None,
                            'new': nu.name,
                            '_user_id_val': nu.id,
                        }
                else:
                    entry['warnings'].append(f'Assignee "{ae}" not found in your team — skipped')

        # notes (always append)
        if 'notes' in allowed:
            nt = _v('notes')
            if nt:
                entry['note_text'] = nt

        # callback
        if 'callback_dt' in allowed:
            cb_date = _v('callback_date')
            cb_time = _v('callback_time') or '09:00'
            if cb_date:
                cb_dt = None
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
                    try:
                        cb_dt = datetime.strptime(f'{cb_date} {cb_time[:5]}', f'{fmt} %H:%M')
                        break
                    except ValueError:
                        pass
                if cb_dt:
                    if cb_dt > datetime.utcnow():
                        entry['callback_dt'] = cb_dt.isoformat()
                    else:
                        entry['warnings'].append(
                            f'Callback date {cb_date} is in the past — skipped'
                        )
                else:
                    entry['warnings'].append(
                        f'Unrecognized callback_date format "{cb_date}" — skipped'
                    )

        # Decide validity
        has_changes = bool(fu or entry['note_text'] or entry['callback_dt'])
        if entry['errors']:
            invalid_count += 1
            entry['valid'] = False
        elif not has_changes:
            skipped_count += 1
            entry['valid'] = False
            entry['warnings'].append('No changes detected — row will be skipped')
        else:
            valid_count += 1
            entry['valid'] = True

        rows.append(entry)

    return {
        'rows': rows,
        'summary': {
            'total': len(rows),
            'valid': valid_count,
            'invalid': invalid_count,
            'skipped': skipped_count,
        },
    }


@uploads_bp.route('/import/template', methods=['GET'])
@require_auth
def get_import_template():
    """Download a pre-formatted Excel template for bulk lead import."""
    buf = ExcelService.build_import_template()
    filename = 'lead_import_template.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@uploads_bp.route('/import/excel', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def import_leads_excel():
    """Upload an Excel/CSV file and bulk-create leads."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    user = request.current_user
    queued = _runtime_prefers_async_jobs() or request.args.get('async', '').strip() == '1'
    source_data_b64, source_mime_type, _filename = _captured_upload_bytes(file)
    job = ImportJob(
        tenant_id=user.tenant_id,
        user_id=user.id,
        product_slug=getattr(getattr(request, 'current_product', None), 'slug', None),
        filename=file.filename,
        file_type=os.path.splitext(file.filename)[1].lstrip('.').lower() or None,
        source_data_b64=source_data_b64,
        source_mime_type=source_mime_type,
        status='queued' if queued else 'processing',
        started_at=datetime.utcnow() if not queued else None,
    )
    db.session.add(job)
    db.session.flush()
    db.session.commit()

    if queued:
        return jsonify({'job': job.to_dict(), 'status': 'queued'}), 202

    result = _process_import_job(job)
    return jsonify(result), 200


@uploads_bp.route('/export/excel', methods=['GET'])
@require_auth
def export_leads_excel():
    """Export filtered leads as a formatted Excel file."""
    user = request.current_user
    queued = _runtime_prefers_async_jobs() or request.args.get('async', '').strip() == '1'
    status = request.args.get('status')
    project_id = request.args.get('project_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    export_job = ExportJob(
        tenant_id=user.tenant_id,
        user_id=user.id,
        product_slug=getattr(getattr(request, 'current_product', None), 'slug', None),
        export_type='leads',
        filters={
            'status': status,
            'project_id': project_id,
            'date_from': date_from,
            'date_to': date_to,
        },
        status='queued' if queued else 'processing',
        started_at=datetime.utcnow() if not queued else None,
    )
    db.session.add(export_job)
    db.session.flush()
    db.session.commit()

    if queued:
        return jsonify({'job': export_job.to_dict(), 'status': 'queued'}), 202

    result = _process_export_job(export_job)
    buf = BytesIO(base64.b64decode(export_job.artifact_data_b64 or ''))
    return send_file(
        buf,
        mimetype=export_job.artifact_mime_type or 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=result['filename'],
    )


# ── Bulk Update: Export template ──────────────────────────────────────────────

@uploads_bp.route('/export/update-template', methods=['GET'])
@require_auth
def export_update_template():
    """Download current leads in the bulk-update format (lead_id + phone locked)."""
    user   = request.current_user
    leads  = get_user_visible_leads(user).all()
    buf    = ExcelService.export_leads_for_update(leads)
    fname  = f'leads_update_template_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=fname,
    )


# ── Bulk Update: Preview (no DB writes) ───────────────────────────────────────

@uploads_bp.route('/bulk-update/preview', methods=['POST'])
@require_auth
def bulk_update_preview():
    """Parse uploaded update file, validate rows, compute diffs. No DB writes.
    Returns a preview_token + per-row diff for the user to review before applying."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    user   = request.current_user
    result = _parse_update_file(file, user)
    if 'error' in result:
        return jsonify({'error': result['error']}), 400

    token = _create_preview_job(user, result['rows'], result['summary'])

    return jsonify({
        'preview_token':    token,
        'expires_in_seconds': int(_PREVIEW_TTL.total_seconds()),
        'rows':             result['rows'],
        'summary':          result['summary'],
    }), 200


# ── Bulk Update: Apply ────────────────────────────────────────────────────────

@uploads_bp.route('/bulk-update/apply', methods=['POST'])
@require_auth
def bulk_update_apply():
    """Apply a previously previewed bulk update using its token.
    All valid rows are committed in a single transaction; rolled back on any error."""
    from app.models.lead import Lead, LeadNote, StatusHistory, CallbackReminder, LeadAssignmentHistory
    from app.models.base import db

    data  = request.get_json(silent=True) or {}
    token = (data.get('preview_token') or '').strip()
    if not token:
        return jsonify({'error': 'preview_token is required'}), 400

    preview_job = _preview_job_from_token(token)
    if not preview_job or preview_job.file_type != 'bulk_update':
        return jsonify({'error': 'Preview expired or not found — please re-upload the file'}), 400

    user = request.current_user
    if preview_job.user_id != user.id or preview_job.tenant_id != user.tenant_id:
        return jsonify({'error': 'Preview token does not belong to current user'}), 403

    preview = preview_job.summary or {}
    rows = preview.get('rows') or [row.to_dict() for row in sorted(preview_job.rows, key=lambda r: r.row_number)]

    updated = failed = skipped = 0
    results = []

    try:
        preview_job.status = 'processing'
        preview_job.started_at = preview_job.started_at or datetime.utcnow()

        for row in rows:
            if not row['valid']:
                if row.get('errors'):
                    failed += 1
                else:
                    skipped += 1
                results.append({**row, 'applied': False})
                continue

            lead = Lead.query.filter_by(
                id=row['lead_id'], tenant_id=user.tenant_id, is_active=True
            ).first()
            if not lead:
                failed += 1
                results.append({
                    **row, 'applied': False,
                    'errors': [*(row.get('errors') or []), 'Lead no longer exists'],
                })
                continue

            old_status    = lead.status
            field_updates = row.get('field_updates') or {}

            for field, change in field_updates.items():
                if field.startswith('_'):
                    continue
                if field == 'project_id':
                    lead.project_id = change.get('_project_id_val', lead.project_id)
                elif field == 'assigned_to':
                    old_uid = lead.assigned_to
                    new_uid = change.get('_user_id_val')
                    if new_uid:
                        lead.assigned_to = new_uid
                        db.session.add(LeadAssignmentHistory(
                            lead_id=lead.id,
                            assigned_from=old_uid,
                            assigned_to=new_uid,
                            assigned_by=user.id,
                            reason='Bulk update',
                        ))
                else:
                    setattr(lead, field, change['new'])

            # Status history entry
            new_status = field_updates.get('status', {}).get('new')
            if new_status and new_status != old_status:
                db.session.add(StatusHistory(
                    lead_id=lead.id,
                    old_status=old_status,
                    new_status=new_status,
                    changed_by=user.id,
                ))

            # Append note (immutable timeline)
            note_text = row.get('note_text')
            if note_text:
                db.session.add(LeadNote(
                    lead_id=lead.id,
                    note=note_text,
                    created_by=user.id,
                ))

            # Schedule callback reminder
            cb_dt_str = row.get('callback_dt')
            if cb_dt_str:
                try:
                    cb_dt = datetime.fromisoformat(cb_dt_str)
                    db.session.add(CallbackReminder(
                        lead_id=lead.id,
                        tenant_id=user.tenant_id,
                        assigned_user_id=lead.assigned_to,
                        manager_id=(
                            user.id
                            if user.role in ('sales_manager', 'superadmin')
                            else None
                        ),
                        callback_datetime=cb_dt,
                        created_by=user.id,
                        notes='Scheduled via bulk update',
                    ))
                except (ValueError, TypeError):
                    pass

            lead.updated_at = datetime.utcnow()

            changed_fields = ', '.join(
                k for k in field_updates if not k.startswith('_')
            )
            if note_text:
                changed_fields += ' + note'
            if cb_dt_str:
                changed_fields += ' + callback'

            log_activity(
                user_id=user.id,
                action='bulk_update_lead',
                module='leads',
                resource_id=lead.id,
                resource_type='Lead',
                description=f'Bulk update applied: {changed_fields}',
            )
            updated += 1
            results.append({**row, 'applied': True})

        db.session.commit()
        preview_job.status = 'completed'
        preview_job.completed_at = datetime.utcnow()
        preview_job.summary = {
            **preview,
            'applied_summary': {
                'updated': updated,
                'failed': failed,
                'skipped': skipped,
                'total': len(rows),
            },
        }
        db.session.commit()

    except Exception as exc:
        db.session.rollback()
        preview_job.status = 'failed'
        preview_job.error_message = str(exc)
        db.session.commit()
        return jsonify({'error': f'Update failed: {exc}', 'rolled_back': True}), 500

    # Build downloadable report
    try:
        report_buf = ExcelService.build_update_report(results)
        report_b64 = base64.b64encode(report_buf.read()).decode('utf-8')
    except Exception:
        report_b64 = None

    return jsonify({
        'updated':    updated,
        'failed':     failed,
        'skipped':    skipped,
        'total':      len(rows),
        'report_b64': report_b64,
    }), 200


@uploads_bp.route('/import/jobs/<int:job_id>', methods=['GET'])
@require_auth
def get_import_job(job_id):
    job = ImportJob.query.get(job_id)
    user = request.current_user
    if not job or job.tenant_id != user.tenant_id:
        return jsonify({'error': 'Job not found'}), 404
    if job.user_id != user.id and user.role not in ('sales_manager', 'superadmin'):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify({'job': job.to_dict()}), 200


@uploads_bp.route('/export/jobs/<int:job_id>', methods=['GET'])
@require_auth
def get_export_job(job_id):
    job = ExportJob.query.get(job_id)
    user = request.current_user
    if not job or job.tenant_id != user.tenant_id:
        return jsonify({'error': 'Job not found'}), 404
    if job.user_id != user.id and user.role not in ('sales_manager', 'superadmin'):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify({'job': job.to_dict()}), 200


@uploads_bp.route('/import/jobs/<int:job_id>/process', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def process_import_job(job_id):
    job = ImportJob.query.get(job_id)
    user = request.current_user
    if not job or job.tenant_id != user.tenant_id:
        return jsonify({'error': 'Job not found'}), 404
    if job.user_id != user.id and user.role not in ('sales_manager', 'superadmin'):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(_process_import_job(job)), 200


@uploads_bp.route('/export/jobs/<int:job_id>/process', methods=['POST'])
@require_auth
def process_export_job(job_id):
    job = ExportJob.query.get(job_id)
    user = request.current_user
    if not job or job.tenant_id != user.tenant_id:
        return jsonify({'error': 'Job not found'}), 404
    if job.user_id != user.id and user.role not in ('sales_manager', 'superadmin'):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(_process_export_job(job)), 200
