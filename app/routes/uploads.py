from datetime import datetime
import base64

from flask import Blueprint, jsonify, request, send_file

from app.middleware import require_auth, require_role
from app.services.excel import ExcelService
from app.utils.leads import get_user_visible_leads

uploads_bp = Blueprint('uploads', __name__, url_prefix='/api/leads')


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

    result = ExcelService.import_leads(file, request.current_user)

    # Generate Excel report and attach as base64 for instant download
    try:
        report_buf = ExcelService.build_import_report(
            result.get('imported_leads', []),
            result.get('errors', []),
        )
        result['report_b64'] = base64.b64encode(report_buf.read()).decode('utf-8')
    except Exception:
        result['report_b64'] = None

    return jsonify(result), 200


@uploads_bp.route('/export/excel', methods=['GET'])
@require_auth
def export_leads_excel():
    """Export filtered leads as a formatted Excel file."""
    user = request.current_user
    query = get_user_visible_leads(user)

    status = request.args.get('status')
    project_id = request.args.get('project_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    if status:
        query = query.filter_by(status=status)
    if project_id:
        query = query.filter_by(project_id=int(project_id))
    if date_from:
        try:
            query = query.filter(
                __import__('app.models.lead', fromlist=['Lead']).Lead.created_at
                >= datetime.strptime(date_from, '%Y-%m-%d')
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                __import__('app.models.lead', fromlist=['Lead']).Lead.created_at
                <= datetime.strptime(date_to, '%Y-%m-%d')
            )
        except ValueError:
            pass

    leads = query.all()
    buf = ExcelService.export_leads(leads, title='Leads Export')
    filename = f'leads_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )
