from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, send_file
from io import BytesIO

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from app import db
from app.middleware import require_auth, require_role
from app.models.activity import ActivityLog
from app.models.lead import Lead, StatusHistory
from app.models.user import User
from app.services.reports import ReportService
from app.utils.leads import get_user_visible_leads

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


def _resolve_date_window(range_key: str, date_from: str, date_to: str):
    now = datetime.utcnow()
    key = (range_key or '').strip().lower()

    if date_from or date_to:
        try:
            start = datetime.strptime(date_from, '%Y-%m-%d') if date_from else None
            end = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1) if date_to else None
            return start, end
        except ValueError:
            return None, None

    today_start = datetime(now.year, now.month, now.day)
    if key == 'today':
        return today_start, today_start + timedelta(days=1)
    if key == 'yesterday':
        start = today_start - timedelta(days=1)
        return start, today_start
    if key == 'last_week':
        this_week_start = today_start - timedelta(days=today_start.weekday())
        start = this_week_start - timedelta(days=7)
        return start, this_week_start
    if key == 'last_30_days':
        return now - timedelta(days=30), now + timedelta(seconds=1)
    if key == 'this_month':
        start = datetime(now.year, now.month, 1)
        return start, now + timedelta(seconds=1)
    if key == 'last_month':
        this_month_start = datetime(now.year, now.month, 1)
        prev_end = this_month_start
        prev_start = datetime(prev_end.year if prev_end.month > 1 else prev_end.year - 1,
                              prev_end.month - 1 if prev_end.month > 1 else 12,
                              1)
        return prev_start, prev_end

    return None, None


def _apply_created_date_filters(query, range_key: str, date_from: str, date_to: str):
    start, end = _resolve_date_window(range_key, date_from, date_to)
    if start:
        query = query.filter(Lead.created_at >= start)
    if end:
        query = query.filter(Lead.created_at < end)
    return query


def _period_metrics(user, start_dt: datetime, end_dt: datetime):
    visible_ids = [r[0] for r in get_user_visible_leads(user).with_entities(Lead.id).all()]
    if not visible_ids:
        return {
            'leads_added': 0,
            'calls_done': 0,
            'follow_ups': 0,
            'site_visits': 0,
            'closures': 0,
            'conversion_pct': 0,
        }

    leads_added = Lead.query.filter(
        Lead.id.in_(visible_ids),
        Lead.created_at >= start_dt,
        Lead.created_at < end_dt,
    ).count()

    calls_done = ActivityLog.query.filter(
        ActivityLog.module == 'leads',
        ActivityLog.resource_id.in_(visible_ids),
        ActivityLog.action.like('call_%'),
        ActivityLog.action != 'call_initiated',
        ActivityLog.created_at >= start_dt,
        ActivityLog.created_at < end_dt,
    ).count()

    follow_ups = StatusHistory.query.join(Lead, Lead.id == StatusHistory.lead_id).filter(
        Lead.id.in_(visible_ids),
        StatusHistory.new_status == 'follow_up',
        StatusHistory.changed_at >= start_dt,
        StatusHistory.changed_at < end_dt,
    ).count()

    site_visits = StatusHistory.query.join(Lead, Lead.id == StatusHistory.lead_id).filter(
        Lead.id.in_(visible_ids),
        StatusHistory.new_status.in_(['site_visit_planned', 'site_visit_done']),
        StatusHistory.changed_at >= start_dt,
        StatusHistory.changed_at < end_dt,
    ).count()

    closures = StatusHistory.query.join(Lead, Lead.id == StatusHistory.lead_id).filter(
        Lead.id.in_(visible_ids),
        StatusHistory.new_status == 'booking_done',
        StatusHistory.changed_at >= start_dt,
        StatusHistory.changed_at < end_dt,
    ).count()

    conversion_pct = round((closures / leads_added) * 100, 2) if leads_added else 0
    return {
        'leads_added': leads_added,
        'calls_done': calls_done,
        'follow_ups': follow_ups,
        'site_visits': site_visits,
        'closures': closures,
        'conversion_pct': conversion_pct,
    }


def _build_comparison_payload(user):
    now = datetime.utcnow()
    this_week_start = datetime(now.year, now.month, now.day) - timedelta(days=datetime(now.year, now.month, now.day).weekday())
    last_week_start = this_week_start - timedelta(days=7)
    this_month_start = datetime(now.year, now.month, 1)
    last_month_end = this_month_start
    last_month_start = datetime(last_month_end.year if last_month_end.month > 1 else last_month_end.year - 1,
                                last_month_end.month - 1 if last_month_end.month > 1 else 12,
                                1)

    week_current = _period_metrics(user, this_week_start, now + timedelta(seconds=1))
    week_last = _period_metrics(user, last_week_start, this_week_start)
    month_current = _period_metrics(user, this_month_start, now + timedelta(seconds=1))
    month_last = _period_metrics(user, last_month_start, last_month_end)

    return {
        'week': {
            'label_current': 'This Week',
            'label_previous': 'Last Week',
            'current': week_current,
            'previous': week_last,
        },
        'month': {
            'label_current': 'This Month',
            'label_previous': 'Last Month',
            'current': month_current,
            'previous': month_last,
        },
    }


# ---------------------------------------------------------------------------
# JSON reports
# ---------------------------------------------------------------------------

@reports_bp.route('/leads', methods=['GET'])
@require_auth
def lead_report():
    user = request.current_user
    query = get_user_visible_leads(user)

    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')
    if date_from:
        try:
            query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Lead.created_at <= dt_to)
        except ValueError:
            pass

    leads = query.all()
    total = len(leads)

    status_counts: dict = {}
    source_counts: dict = {}
    project_counts: dict = {}
    converted_statuses = {'booking_done', 'negotiation'}
    converted: list = []

    for lead in leads:
        s = lead.status or 'unknown'
        status_counts[s] = status_counts.get(s, 0) + 1

        src = lead.source or 'unknown'
        source_counts[src] = source_counts.get(src, 0) + 1

        if lead.project:
            project_counts[lead.project.name] = (
                project_counts.get(lead.project.name, 0) + 1
            )

        if lead.status in converted_statuses:
            converted.append(lead)

    conversion_rate = round(len(converted) / total * 100, 2) if total else 0

    # Leads per day — use filtered leads if date filter applied, else last 30 days
    if date_from or date_to:
        trend_leads = leads
    else:
        cutoff = datetime.utcnow() - timedelta(days=30)
        trend_leads = [l for l in leads if l.created_at and l.created_at >= cutoff]
    by_date: dict = {}
    for lead in trend_leads:
        d = lead.created_at.strftime('%Y-%m-%d')
        by_date[d] = by_date.get(d, 0) + 1

    return jsonify({
        'total_leads': total,
        'leads_by_status': status_counts,
        'leads_by_source': source_counts,
        'leads_by_project': project_counts,
        'conversion_rate': conversion_rate,
        'leads_by_date': by_date,
    }), 200


@reports_bp.route('/team', methods=['GET'])
@require_auth
def team_report():
    current_user = request.current_user

    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')
    range_key = request.args.get('range')

    def apply_date_filters(q):
        return _apply_created_date_filters(q, range_key, date_from, date_to)

    def build_stats_for_user(u, q):
        q = apply_date_filters(q)
        leads = q.all()
        total            = len(leads)
        interested       = sum(1 for l in leads if l.status == 'interested')
        site_visit_plan  = sum(1 for l in leads if l.status == 'site_visit_planned')
        site_visit_done  = sum(1 for l in leads if l.status == 'site_visit_done')
        negotiation      = sum(1 for l in leads if l.status == 'negotiation')
        booking_done     = sum(1 for l in leads if l.status == 'booking_done')
        warm_leads       = interested + site_visit_plan
        hot_leads        = site_visit_done + negotiation
        warm_rate        = round((interested + site_visit_plan) / total * 100, 2) if total else 0
        hot_rate         = round((hot_leads / total) * 100, 2) if total else 0
        return {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'total_leads': total,
            'interested': interested,
            'site_visit_planned': site_visit_plan,
            'site_visit_done': site_visit_done,
            'negotiation': negotiation,
            'booking_done': booking_done,
            'warm_leads': warm_leads,
            'hot_leads': hot_leads,
            'warm_rate': warm_rate,
            'hot_rate': hot_rate,
            'last_login': u.last_login.isoformat() if u.last_login else None,
        }

    def get_stats(u):
        tid = u.tenant_id
        if u.role == 'sales_manager':
            # Reports manager row should reflect only leads directly assigned to the manager.
            q = Lead.query.filter_by(
                assigned_to=u.id,
                is_active=True,
                tenant_id=tid,
            )
            return build_stats_for_user(u, q)

        q = Lead.query.filter_by(assigned_to=u.id, is_active=True, tenant_id=tid)
        return build_stats_for_user(u, q)

    if current_user.role == 'sales_manager':
        # Return just this manager's group
        manager_stats = get_stats(current_user)
        members = [
            get_stats(u)
            for u in User.query.filter_by(
                manager_id=current_user.id,
                is_active=True,
                tenant_id=current_user.tenant_id,
            ).all()
        ]
        return jsonify({
            'team_groups': [{
                'manager': manager_stats,
                'members': sorted(members, key=lambda x: -x['total_leads']),
            }]
        }), 200

    # superadmin: group all team members under their manager
    tid = current_user.tenant_id
    managers = User.query.filter_by(
        role='sales_manager', is_active=True, tenant_id=tid,
    ).order_by(User.name).all()
    groups = []
    assigned_member_ids = set()
    for mgr in managers:
        members = User.query.filter_by(manager_id=mgr.id, is_active=True, tenant_id=tid).all()
        for m in members:
            assigned_member_ids.add(m.id)
        groups.append({
            'manager': get_stats(mgr),
            'members': sorted([get_stats(m) for m in members], key=lambda x: -x['total_leads']),
        })

    # Unassigned team members (no manager) — scoped to tenant
    unassigned = User.query.filter(
        User.role == 'team_member',
        User.is_active == True,
        User.tenant_id == tid,
        ~User.id.in_(assigned_member_ids) if assigned_member_ids else True,
    ).all()

    return jsonify({
        'team_groups': groups,
        'unassigned_members': sorted([get_stats(u) for u in unassigned], key=lambda x: -x['total_leads']),
    }), 200


@reports_bp.route('/comparison', methods=['GET'])
@require_auth
def comparison_report():
    user = request.current_user
    return jsonify({'comparison': _build_comparison_payload(user)}), 200


@reports_bp.route('/activity', methods=['GET'])
@require_role('superadmin')
def activity_report():
    user_activity: dict = {}
    action_activity: dict = {}
    module_activity: dict = {}

    for log in ActivityLog.query.all():
        name = log.user.name if log.user else 'Unknown'
        user_activity[name] = user_activity.get(name, 0) + 1
        action_activity[log.action] = action_activity.get(log.action, 0) + 1
        module_activity[log.module] = module_activity.get(log.module, 0) + 1

    cutoff = datetime.utcnow() - timedelta(days=7)
    by_date: dict = {}
    for log in ActivityLog.query.filter(ActivityLog.created_at >= cutoff).all():
        d = log.created_at.strftime('%Y-%m-%d')
        by_date[d] = by_date.get(d, 0) + 1

    return jsonify({
        'activity_by_user': user_activity,
        'activity_by_action': action_activity,
        'activity_by_module': module_activity,
        'activity_last_7_days': by_date,
        'total_activities': ActivityLog.query.count(),
    }), 200


@reports_bp.route('/activity-logs', methods=['GET'])
@require_role('superadmin')
def get_activity_logs():
    user_id = request.args.get('user_id')
    action = request.args.get('action')
    module = request.args.get('module')
    limit = request.args.get('limit', 100, type=int)
    sort = (request.args.get('sort') or 'newest').strip().lower()

    query = ActivityLog.query
    if user_id:
        query = query.filter_by(user_id=int(user_id))
    if action:
        query = query.filter_by(action=action)
    if module:
        query = query.filter_by(module=module)

    order_by = ActivityLog.created_at.asc() if sort == 'oldest' else ActivityLog.created_at.desc()
    logs = query.order_by(order_by).limit(limit).all()
    return jsonify({'activity_logs': [l.to_dict() for l in logs]}), 200


@reports_bp.route('/activity-logs/download', methods=['GET'])
@require_role('superadmin')
def download_activity_logs():
    user_id = request.args.get('user_id')
    action  = request.args.get('action')
    module  = request.args.get('module')

    query = ActivityLog.query
    if user_id:
        query = query.filter_by(user_id=int(user_id))
    if action:
        query = query.filter_by(action=action)
    if module:
        query = query.filter_by(module=module)

    logs = query.order_by(ActivityLog.created_at.desc()).all()

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Activity Logs'

    headers = ['#', 'User', 'Action', 'Module', 'Resource Type', 'Resource ID', 'Description', 'IP Address', 'Timestamp']
    header_fill = PatternFill('solid', fgColor='1E3A5F')
    header_font = Font(color='FFFFFF', bold=True, size=11)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    alt_fill = PatternFill('solid', fgColor='EEF2F7')
    for row_idx, log in enumerate(logs, 2):
        fill = alt_fill if row_idx % 2 == 0 else PatternFill()
        values = [
            log.id,
            log.user.name if log.user else '',
            log.action,
            log.module,
            log.resource_type or '',
            log.resource_id or '',
            log.description or '',
            log.ip_address or '',
            log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.fill = fill

    col_widths = [6, 22, 22, 14, 18, 12, 55, 16, 22]
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{get_column_letter(len(headers))}1'

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f'activity_logs_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Downloadable Excel reports
# ---------------------------------------------------------------------------

@reports_bp.route('/leads/download', methods=['GET'])
@require_auth
def download_lead_report():
    user = request.current_user
    leads = get_user_visible_leads(user).all()
    buf = ReportService.lead_report_excel(leads)
    filename = f'lead_report_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@reports_bp.route('/team/download', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def download_team_report():
    user = request.current_user
    if user.role == 'superadmin':
        users = User.query.all()
    else:
        users = User.query.filter(
            (User.manager_id == user.id) | (User.id == user.id)
        ).all()

    buf = ReportService.team_report_excel(users)
    filename = f'team_report_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@reports_bp.route('/management/download', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def download_management_report():
    user = request.current_user
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    range_key = request.args.get('range')

    leads_q = _apply_created_date_filters(get_user_visible_leads(user), range_key, date_from, date_to)
    leads = leads_q.all()

    # Team / manager scope
    if user.role == 'superadmin':
        manager_users = User.query.filter_by(role='sales_manager', tenant_id=user.tenant_id, is_active=True).all()
        team_users = User.query.filter_by(role='team_member', tenant_id=user.tenant_id, is_active=True).all()
    else:
        manager_users = [user]
        team_users = User.query.filter_by(role='team_member', manager_id=user.id, tenant_id=user.tenant_id, is_active=True).all()

    # Helper maps
    leads_by_assignee = {}
    for lead in leads:
        if lead.assigned_to:
            leads_by_assignee.setdefault(lead.assigned_to, []).append(lead)

    def _row_stats(row_leads):
        total = len(row_leads)
        interested = sum(1 for l in row_leads if l.status == 'interested')
        sv_plan = sum(1 for l in row_leads if l.status == 'site_visit_planned')
        sv_done = sum(1 for l in row_leads if l.status == 'site_visit_done')
        negotiation = sum(1 for l in row_leads if l.status == 'negotiation')
        closed = sum(1 for l in row_leads if l.status == 'booking_done')
        conversion = round((closed / total) * 100, 2) if total else 0
        return {
            'total': total,
            'interested': interested,
            'site_visit_planned': sv_plan,
            'site_visit_done': sv_done,
            'negotiation': negotiation,
            'closures': closed,
            'conversion_pct': conversion,
        }

    wb = openpyxl.Workbook()
    ws_team = wb.active
    ws_team.title = 'Team Performance'
    ws_mgr = wb.create_sheet('Manager Performance')
    ws_status = wb.create_sheet('Lead Status Breakdown')
    ws_conv = wb.create_sheet('Conversion Metrics')

    header_fill = PatternFill('solid', fgColor='1E3A5F')
    header_font = Font(color='FFFFFF', bold=True, size=11)

    def _write_sheet_header(ws, title, headers):
        ws['A1'] = title
        ws['A1'].font = Font(bold=True, size=14, color='1E3A5F')
        ws['A2'] = f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}'
        if date_from or date_to or range_key:
            ws['A3'] = f'Range: {range_key or "custom"} {date_from or ""} {date_to or ""}'.strip()
        head_row = 5
        for col, h in enumerate(headers, 1):
            c = ws.cell(row=head_row, column=col, value=h)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal='center', vertical='center')
        return head_row + 1

    # Team sheet
    team_headers = ['Name', 'Role', 'Total Leads', 'Interested', 'Site Visit Planned', 'Site Visit Done', 'Negotiation', 'Closures', 'Conversion %']
    r = _write_sheet_header(ws_team, 'Team Performance', team_headers)
    for tm in team_users:
        s = _row_stats(leads_by_assignee.get(tm.id, []))
        values = [tm.name, 'team_member', s['total'], s['interested'], s['site_visit_planned'], s['site_visit_done'], s['negotiation'], s['closures'], s['conversion_pct']]
        for i, v in enumerate(values, 1):
            ws_team.cell(row=r, column=i, value=v)
        r += 1

    # Manager sheet (manager own + team members)
    mgr_headers = ['Manager', 'Total Leads', 'Interested', 'Site Visit Planned', 'Site Visit Done', 'Negotiation', 'Closures', 'Conversion %']
    r = _write_sheet_header(ws_mgr, 'Manager Performance', mgr_headers)
    for mgr in manager_users:
        mgr_leads = list(leads_by_assignee.get(mgr.id, []))
        member_ids = [u.id for u in team_users if u.manager_id == mgr.id]
        for uid in member_ids:
            mgr_leads.extend(leads_by_assignee.get(uid, []))
        s = _row_stats(mgr_leads)
        values = [mgr.name, s['total'], s['interested'], s['site_visit_planned'], s['site_visit_done'], s['negotiation'], s['closures'], s['conversion_pct']]
        for i, v in enumerate(values, 1):
            ws_mgr.cell(row=r, column=i, value=v)
        r += 1

    # Status breakdown sheet
    status_headers = ['Status', 'Count', 'Percent']
    r = _write_sheet_header(ws_status, 'Lead Status Breakdown', status_headers)
    status_counts = {}
    for lead in leads:
        key = lead.status or 'unknown'
        status_counts[key] = status_counts.get(key, 0) + 1
    total = len(leads)
    for status, count in sorted(status_counts.items(), key=lambda item: item[0]):
        pct = round((count / total) * 100, 2) if total else 0
        ws_status.cell(row=r, column=1, value=status)
        ws_status.cell(row=r, column=2, value=count)
        ws_status.cell(row=r, column=3, value=pct)
        r += 1

    # Conversion sheet (includes WoW and MoM)
    conv_headers = ['Metric', 'Value']
    r = _write_sheet_header(ws_conv, 'Conversion Metrics', conv_headers)
    stats = _row_stats(leads)
    base_rows = [
        ('Total Leads', stats['total']),
        ('Interested', stats['interested']),
        ('Site Visit Planned', stats['site_visit_planned']),
        ('Site Visit Done', stats['site_visit_done']),
        ('Negotiation', stats['negotiation']),
        ('Closures', stats['closures']),
        ('Conversion %', stats['conversion_pct']),
    ]
    for key, val in base_rows:
        ws_conv.cell(row=r, column=1, value=key)
        ws_conv.cell(row=r, column=2, value=val)
        r += 1

    comparison = _build_comparison_payload(user)
    r += 1
    ws_conv.cell(row=r, column=1, value='Week-on-Week (This Week vs Last Week)').font = Font(bold=True)
    r += 1
    for metric in ['leads_added', 'calls_done', 'follow_ups', 'site_visits', 'closures', 'conversion_pct']:
        ws_conv.cell(row=r, column=1, value=f'{metric} (This Week)')
        ws_conv.cell(row=r, column=2, value=comparison['week']['current'][metric])
        r += 1
        ws_conv.cell(row=r, column=1, value=f'{metric} (Last Week)')
        ws_conv.cell(row=r, column=2, value=comparison['week']['previous'][metric])
        r += 1

    r += 1
    ws_conv.cell(row=r, column=1, value='Month-on-Month (This Month vs Last Month)').font = Font(bold=True)
    r += 1
    for metric in ['leads_added', 'calls_done', 'follow_ups', 'site_visits', 'closures', 'conversion_pct']:
        ws_conv.cell(row=r, column=1, value=f'{metric} (This Month)')
        ws_conv.cell(row=r, column=2, value=comparison['month']['current'][metric])
        r += 1
        ws_conv.cell(row=r, column=1, value=f'{metric} (Last Month)')
        ws_conv.cell(row=r, column=2, value=comparison['month']['previous'][metric])
        r += 1

    for ws in [ws_team, ws_mgr, ws_status, ws_conv]:
        for col in range(1, 10):
            ws.column_dimensions[get_column_letter(col)].width = 24

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f'management_report_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@reports_bp.route('/activity/download', methods=['GET'])
@require_role('superadmin')
def download_activity_report():
    days = request.args.get('days', 30, type=int)
    buf = ReportService.activity_report_excel(days=days)
    filename = f'activity_report_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )
