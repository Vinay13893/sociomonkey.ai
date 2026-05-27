from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, send_file

from app import db
from app.middleware import require_auth, require_role
from app.models.activity import ActivityLog
from app.models.lead import Lead
from app.models.user import User
from app.services.reports import ReportService
from app.utils.leads import get_user_visible_leads

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


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

    def get_stats(u):
        tid = u.tenant_id
        if u.role == 'sales_manager':
            team_ids = [tm.id for tm in u.team_members]
            q = Lead.query.filter(
                Lead.is_active == True,
                Lead.tenant_id == tid,
                db.or_(
                    Lead.sales_manager_id == u.id,
                    Lead.assigned_to == u.id,
                    Lead.assigned_to.in_(team_ids),
                )
            )
        else:
            q = Lead.query.filter_by(assigned_to=u.id, is_active=True, tenant_id=tid)
        if date_from:
            try:
                q = q.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                q = q.filter(Lead.created_at <= dt_to)
            except ValueError:
                pass
        leads = q.all()
        total            = len(leads)
        interested       = sum(1 for l in leads if l.status == 'interested')
        site_visit_plan  = sum(1 for l in leads if l.status == 'site_visit_planned')
        site_visit_done  = sum(1 for l in leads if l.status == 'site_visit_done')
        booking_done     = sum(1 for l in leads if l.status == 'booking_done')
        warm_rate        = round(interested / total * 100, 2) if total else 0
        return {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'total_leads': total,
            'interested': interested,
            'site_visit_planned': site_visit_plan,
            'site_visit_done': site_visit_done,
            'booking_done': booking_done,
            'warm_rate': warm_rate,
            'last_login': u.last_login.isoformat() if u.last_login else None,
        }

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

    query = ActivityLog.query
    if user_id:
        query = query.filter_by(user_id=int(user_id))
    if action:
        query = query.filter_by(action=action)
    if module:
        query = query.filter_by(module=module)

    logs = query.order_by(ActivityLog.created_at.desc()).limit(limit).all()
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
