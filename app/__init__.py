import time
import uuid
import os

from flask import Flask, g, has_request_context, jsonify, request
from flask_cors import CORS
from sqlalchemy import event, inspect, text

from app.models.base import db
from app.config import config_map, get_config_name

PRIMARY_ADMIN_OLD_EMAIL = 'admin@sociomonkey.ai'
PRIMARY_ADMIN_NEW_EMAIL = 'aseem@sociomonkey.com'
PRIMARY_ADMIN_NAME = 'Aseem'
DEMO_TENANT_SLUG = 'demo'
DEMO_TENANT_NAME = 'Sociomonkey Demo'
DEMO_BRAND_NAME = 'LMS Demo'
DEMO_LOGO_URL = 'Assets/top-banner-logo.png'
DEMO_FAVICON_URL = 'Assets/top-banner-logo.png'
DEMO_ADMIN_EMAIL = 'demo.admin@sociomonkey.com'
DEMO_ADMIN_NAME = 'Sociomonkey Admin'
DEMO_ADMIN_PASSWORD = 'SocioMonkey#2024'


def _perf_now_ms() -> int:
    return int(time.time() * 1000)


def _perf_elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _perf_match_route(req) -> str:
    path = req.path or ''
    method = (req.method or 'GET').upper()
    if method == 'POST' and path == '/api/auth/login':
        return 'login'
    if method == 'GET' and path == '/api/auth/me':
        return 'auth_me'
    if method == 'GET' and path.startswith('/api/public/tenants/') and path.endswith('/config'):
        return 'tenant_config'
    if method == 'GET' and path == '/api/projects':
        return 'projects'
    if method == 'GET' and path == '/api/leads/dashboard/stats':
        return 'dashboard_stats'
    if method == 'GET' and path == '/api/leads':
        return 'leads'
    return ''


def _perf_sql_snippet(statement: str) -> str:
    compact = ' '.join((statement or '').split())
    return compact[:180]


def _perf_emit(app: Flask, message: str):
    app.logger.info(message)
    print(message, flush=True)


def _register_api_perf(app: Flask):
    if getattr(app, '_api_perf_registered', False):
        return

    @app.before_request
    def _api_perf_before_request():
        route_key = _perf_match_route(request)
        if not route_key:
            return None
        g._api_perf_route = route_key
        g._api_perf_request_id = uuid.uuid4().hex[:10]
        g._api_perf_started = time.perf_counter()
        g._api_perf_request_received_at_ms = _perf_now_ms()
        g._api_perf_db_total_ms = 0.0
        g._api_perf_db_query_count = 0
        _perf_emit(
            app,
            '[API-PERF] req={req} route={route} stage=request_received method={method} path={path} received_at_ms={received}'.format(
                req=g._api_perf_request_id,
                route=g._api_perf_route,
                method=request.method,
                path=request.full_path.rstrip('?'),
                received=g._api_perf_request_received_at_ms,
            ),
        )
        return None

    @app.after_request
    def _api_perf_after_request(response):
        route_key = getattr(g, '_api_perf_route', '')
        if not route_key:
            return response

        backend_ms = _perf_elapsed_ms(g._api_perf_started)
        response_sent_at_ms = _perf_now_ms()
        db_ms = round(float(getattr(g, '_api_perf_db_total_ms', 0.0)), 2)
        query_count = int(getattr(g, '_api_perf_db_query_count', 0) or 0)
        response.headers['X-Perf-Route-Key'] = route_key
        response.headers['X-Perf-Request-Id'] = g._api_perf_request_id
        response.headers['X-Perf-Request-Received-At-Ms'] = str(g._api_perf_request_received_at_ms)
        response.headers['X-Perf-Response-Sent-At-Ms'] = str(response_sent_at_ms)
        response.headers['X-Perf-Backend-Duration-Ms'] = f'{backend_ms:.2f}'
        response.headers['X-Perf-Db-Duration-Ms'] = f'{db_ms:.2f}'
        response.headers['X-Perf-Db-Query-Count'] = str(query_count)
        _perf_emit(
            app,
            '[API-PERF] req={req} route={route} stage=response_sent status={status} backend_ms={backend:.2f} db_ms={db_ms:.2f} queries={queries} received_at_ms={received} response_sent_at_ms={sent}'.format(
                req=g._api_perf_request_id,
                route=route_key,
                status=response.status_code,
                backend=backend_ms,
                db_ms=db_ms,
                queries=query_count,
                received=g._api_perf_request_received_at_ms,
                sent=response_sent_at_ms,
            ),
        )
        return response

    app._api_perf_registered = True


def _register_db_perf(app: Flask):
    if getattr(app, '_db_perf_registered', False):
        return

    engine = db.engine

    @event.listens_for(engine, 'before_cursor_execute')
    def _before_cursor_execute(_conn, _cursor, statement, _parameters, context, _executemany):
        if not has_request_context() or not getattr(g, '_api_perf_route', ''):
            return
        context._db_perf_started = time.perf_counter()
        context._db_perf_started_at_ms = _perf_now_ms()
        next_index = int(getattr(g, '_api_perf_db_query_count', 0) or 0) + 1
        _perf_emit(
            app,
            '[DB-PERF] req={req} route={route} stage=query_start query_index={index} started_at_ms={started} sql="{sql}"'.format(
                req=g._api_perf_request_id,
                route=g._api_perf_route,
                index=next_index,
                started=context._db_perf_started_at_ms,
                sql=_perf_sql_snippet(statement),
            ),
        )

    @event.listens_for(engine, 'after_cursor_execute')
    def _after_cursor_execute(_conn, cursor, _statement, _parameters, context, _executemany):
        if not has_request_context() or not getattr(g, '_api_perf_route', ''):
            return
        started = getattr(context, '_db_perf_started', None)
        if started is None:
            return
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        ended_at_ms = _perf_now_ms()
        g._api_perf_db_total_ms = float(getattr(g, '_api_perf_db_total_ms', 0.0)) + duration_ms
        g._api_perf_db_query_count = int(getattr(g, '_api_perf_db_query_count', 0) or 0) + 1
        _perf_emit(
            app,
            '[DB-PERF] req={req} route={route} stage=query_end query_index={index} ended_at_ms={ended} duration_ms={duration:.2f} rowcount={rowcount}'.format(
                req=g._api_perf_request_id,
                route=g._api_perf_route,
                index=g._api_perf_db_query_count,
                ended=ended_at_ms,
                duration=duration_ms,
                rowcount=getattr(cursor, 'rowcount', -1),
            ),
        )

    app._db_perf_registered = True


def create_app(config_name: str = None) -> Flask:
    app = Flask(__name__)

    # ------------------------------------------------------------------ Config
    if not config_name:
        config_name = get_config_name('development')
    cfg = config_map.get(config_name, config_map['development'])
    app.config.from_object(cfg)

    # ------------------------------------------------------------------ Extensions
    db.init_app(app)
    CORS(app, resources={r'/api/*': {'origins': app.config.get('CORS_ORIGINS', '*')}})
    _register_api_perf(app)

    # ------------------------------------------------------------------ Blueprints
    from app.routes.auth import auth_bp
    from app.routes.leads import leads_bp
    from app.routes.team import team_bp
    from app.routes.projects import projects_bp
    from app.routes.pipeline import pipeline_bp
    from app.routes.reports import reports_bp
    from app.routes.uploads import uploads_bp
    from app.routes.tenants import tenants_bp
    from app.routes.public import public_bp
    from app.routes.provisioning import provisioning_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(provisioning_bp)

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'ok',
            'service': 'sociomonkey-backend',
            'env': app.config.get('ENV', config_name),
        }), 200

    @app.errorhandler(404)
    def not_found(_err):
        return jsonify({'error': 'Route not found'}), 404

    @app.errorhandler(500)
    def server_error(_err):
        return jsonify({'error': 'Internal server error'}), 500

    # ------------------------------------------------------------------ DB init + seed
    with app.app_context():
        _register_db_perf(app)
        # Import all models so SQLAlchemy registers the tables
        from app.models import (  # noqa: F401
            User, Role, Project, Lead,
            StatusHistory, LeadNote, LeadAssignmentHistory, ActivityLog,
            DemoRequest, Product, TenantProduct, FeatureFlag, UsageLog, CallbackReminder,
            ProjectAsset,
        )
        from app.models.otp import OtpToken  # noqa: F401
        from app.models.tenant import Tenant  # noqa: F401
        db.create_all()
        try:
            _run_tenant_migration(app)
        except Exception as e:
            app.logger.warning('Tenant migration skipped: %s', e)
        try:
            _run_product_migration(app)
        except Exception as e:
            app.logger.warning('Product migration skipped: %s', e)
        try:
            _run_leads_schema_hotfix(app)
        except Exception as e:
            app.logger.warning('Leads schema hotfix skipped: %s', e)
        try:
            _ensure_demo_lms_tenant(app)
        except Exception as e:
            app.logger.warning('Demo tenant bootstrap skipped: %s', e)
        try:
            _migrate_primary_admin_identity(app)
        except Exception as e:
            app.logger.warning('Primary admin identity migration skipped: %s', e)
        # Only seed on a completely fresh database (no users = first-ever boot)
        from app.models.user import User as _User
        if _User.query.count() == 0:
            _seed(app)
        else:
            # Ensure platform owner always exists
            _ensure_platform_owner(app)

    # ------------------------------------------------------------------ Scheduler
    # Start the callback reminder background thread (once per process)
    from app.services.reminder_scheduler import start_scheduler
    start_scheduler(app)

    # ------------------------------------------------------------------ Notifications endpoint
    from flask import request as _req
    from app.middleware import require_auth as _require_auth
    from app.services.reminder_scheduler import drain_notifications, process_pending_reminders
    from app.routes.uploads import process_queued_import_jobs, process_queued_export_jobs
    from app.routes.leads import process_queued_reshuffle_jobs

    def _cron_authorized(req) -> bool:
        expected = os.environ.get('CRON_SECRET', '').strip()
        if not expected:
            return True
        provided_header = (req.headers.get('X-Cron-Secret') or '').strip()
        if provided_header == expected:
            return True
        authz = (req.headers.get('Authorization') or '').strip()
        if authz == f'Bearer {expected}':
            return True
        return False

    @app.route('/api/leads/notifications', methods=['GET'])
    @_require_auth
    def get_notifications():
        user = _req.current_user
        notes = drain_notifications(user.id)
        return jsonify({'notifications': notes}), 200

    @app.route('/api/internal/reminders/process', methods=['GET', 'POST'])
    def process_reminders_once():
        if not _cron_authorized(_req):
            return jsonify({'error': 'Forbidden'}), 403
        process_pending_reminders()
        return jsonify({'status': 'ok'}), 200

    @app.route('/api/internal/jobs/process', methods=['GET', 'POST'])
    def process_jobs_once():
        if not _cron_authorized(_req):
            return jsonify({'error': 'Forbidden'}), 403

        limit_raw = (_req.args.get('limit') or _req.headers.get('X-Job-Limit') or '10').strip()
        try:
            limit = max(1, min(100, int(limit_raw)))
        except ValueError:
            limit = 10

        summary = {
            'imports': process_queued_import_jobs(limit=limit),
            'exports': process_queued_export_jobs(limit=limit),
            'reshuffles': process_queued_reshuffle_jobs(limit=limit),
        }
        return jsonify({'status': 'ok', 'summary': summary}), 200

    return app


# ---------------------------------------------------------------------------
# Tenant migration (idempotent – safe to call on every startup)
# ---------------------------------------------------------------------------

def _run_tenant_migration(app: 'Flask'):
    """Add multi-tenant columns to existing tables and seed Ganga Realty as tenant #1."""
    from sqlalchemy import text
    with app.app_context():
        with db.engine.connect() as conn:
            # 1. Ensure tenants table exists (db.create_all handles this, but be safe)
            # 2. Seed Ganga Realty as tenant #1
            row = conn.execute(text("SELECT id FROM tenants WHERE slug='ganga'")).fetchone()
            if not row:
                conn.execute(text("""
                    INSERT INTO tenants (name, slug, primary_color, secondary_color,
                        accent_color, plan, status, max_users, admin_email, admin_name,
                        created_at, updated_at)
                    VALUES ('Ganga Realty', 'ganga', '#1e3a5f', '#3b82f6',
                        '#10b981', 'enterprise', 'active', 100,
                        'communication@gangarealty.com', 'Ganga Realty Admin',
                        NOW(), NOW())
                """))
                conn.commit()

            ganga_row = conn.execute(text("SELECT id FROM tenants WHERE slug='ganga'")).fetchone()
            ganga_id = ganga_row[0]

            # 3. Add tenant_id FK column to existing tables (idempotent)
            for tbl in ['users', 'leads', 'projects', 'activity_logs']:
                try:
                    conn.execute(text(
                        f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS "
                        f"tenant_id INTEGER REFERENCES tenants(id)"
                    ))
                    conn.commit()
                except Exception:
                    conn.rollback()

            # 4. Back-fill existing rows to Ganga Realty
            for tbl in ['users', 'leads', 'projects', 'activity_logs']:
                try:
                    conn.execute(text(
                        f"UPDATE {tbl} SET tenant_id = {ganga_id} WHERE tenant_id IS NULL"
                    ))
                    conn.commit()
                except Exception:
                    conn.rollback()

            # 5. Add new white-label branding columns to tenants table (idempotent)
            new_cols = [
                ("brand_name",      "VARCHAR(200)"),
                ("favicon_url",     "VARCHAR(500)"),
                ("sidebar_bg_color","VARCHAR(20)"),
                ("login_bg_color",  "VARCHAR(20)"),
                ("industry",        "VARCHAR(100)"),
                ("notes",           "TEXT"),
                ("trial_ends_at",   "TIMESTAMP"),
            ]
            for col_name, col_type in new_cols:
                try:
                    conn.execute(text(
                        f"ALTER TABLE tenants ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                    ))
                    conn.commit()
                except Exception:
                    conn.rollback()


def _run_leads_schema_hotfix(app: 'Flask'):
    """Emergency schema sync for production: ensure leads.alternate_phone exists."""
    with app.app_context():
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        if 'leads' not in tables:
            return

        lead_columns = {col.get('name') for col in insp.get_columns('leads')}
        if 'alternate_phone' in lead_columns:
            return

        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE leads ADD COLUMN alternate_phone VARCHAR(20)'))
        app.logger.warning('Applied leads schema hotfix: added missing alternate_phone column')


def _ensure_platform_owner(app: 'Flask'):
    """Make sure the SocioMonkey platform owner account exists."""
    with app.app_context():
        _ensure_user(
            name=PRIMARY_ADMIN_NAME,
            email=PRIMARY_ADMIN_NEW_EMAIL,
            password='SocioMonkey#2024',
            role='platform_owner',
            tenant_id=None,
        )
        db.session.commit()


def _migrate_primary_admin_identity(app: 'Flask'):
    """Idempotently migrate hardcoded primary admin identity to the new address."""
    with app.app_context():
        from app.models.user import User
        from app.models.tenant import Tenant

        old_user = User.query.filter_by(email=PRIMARY_ADMIN_OLD_EMAIL).first()
        new_user = User.query.filter_by(email=PRIMARY_ADMIN_NEW_EMAIL).first()

        if old_user and not new_user:
            old_user.email = PRIMARY_ADMIN_NEW_EMAIL
            old_user.name = PRIMARY_ADMIN_NAME
            old_user.role = 'platform_owner'
        elif old_user and new_user and old_user.id != new_user.id:
            old_user.is_active = False

        Tenant.query.filter_by(admin_email=PRIMARY_ADMIN_OLD_EMAIL).update(
            {'admin_email': PRIMARY_ADMIN_NEW_EMAIL},
            synchronize_session=False,
        )

        db.session.commit()


# ---------------------------------------------------------------------------
# Product migration (idempotent – safe to call on every startup)
# ---------------------------------------------------------------------------

PLATFORM_PRODUCTS = [
    dict(
        name='CRM / Lead Management',
        slug='crm',
        description='Full-featured CRM with lead tracking, pipeline management, '
                    'team collaboration, and Excel import/export.',
        icon='📊',
        color='#1e3a5f',
        category='Sales & Marketing',
        version='2.0.0',
    ),
    dict(
        name='Lead Management System (LMS)',
        slug='lms',
        description='Ganga Realty branded Lead Management System — track leads, '
                    'projects, pipeline and performance in one place.',
        icon='📋',
        color='#1e3a5f',
        category='Sales & Marketing',
        version='1.0.0',
    ),
    dict(
        name='Procurement & Vendor Management',
        slug='procurement',
        description='End-to-end procurement workflow: purchase orders, vendor management, '
                    'approvals, and spend analytics.',
        icon='🛒',
        color='#7c3aed',
        category='Operations',
        version='1.0.0',
        is_active=True,
    ),
    dict(
        name='Warehouse Management (WMS)',
        slug='wms',
        description='Real-time inventory tracking, goods receipt, stock movements, '
                    'and warehouse operations.',
        icon='🏭',
        color='#d97706',
        category='Operations',
        version='1.0.0',
        is_active=True,
    ),
    dict(
        name='Amazon Data Intelligence & Analytics',
        slug='amazon',
        description='Keyword tracking, ranking analytics, advertising insights, and market intelligence.',
        icon='🛍️',
        color='#f97316',
        category='E-commerce',
        version='1.0.0',
        is_active=True,
    ),
    dict(
        name='Human Resource Management (HRMS)',
        slug='hrms',
        description='Employee lifecycle management: onboarding, payroll, leaves, '
                    'performance, and compliance.',
        icon='👥',
        color='#0891b2',
        category='HR',
        version='1.0.0',
        is_active=False,
    ),
    dict(
        name='Enterprise Resource Planning (ERP)',
        slug='erp',
        description='Unified business management: finance, accounting, assets, '
                    'and cross-department workflows.',
        icon='🏢',
        color='#be185d',
        category='Finance',
        version='1.0.0',
        is_active=False,
    ),
]


def _run_product_migration(app: 'Flask'):
    """Seed platform products and subscribe existing tenants to CRM (idempotent)."""
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant

    with app.app_context():
        # 1. Ensure all platform products exist
        for p_data in PLATFORM_PRODUCTS:
            existing = Product.query.filter_by(slug=p_data['slug']).first()
            if not existing:
                db.session.add(Product(**p_data))
            else:
                for key, value in p_data.items():
                    setattr(existing, key, value)
        db.session.commit()

        # 2. Subscribe every existing active tenant to CRM (if not already subscribed)
        crm = Product.query.filter_by(slug='crm').first()
        if crm:
            for tenant in Tenant.query.filter_by(status='active').all():
                exists = TenantProduct.query.filter_by(
                    tenant_id=tenant.id, product_id=crm.id
                ).first()
                if not exists:
                    db.session.add(TenantProduct(
                        tenant_id=tenant.id,
                        product_id=crm.id,
                        status='active',
                    ))
            db.session.commit()

        # 3. Subscribe Ganga Realty to LMS product
        lms = Product.query.filter_by(slug='lms').first()
        if lms:
            ganga = Tenant.query.filter_by(slug='ganga').first()
            if ganga:
                exists = TenantProduct.query.filter_by(
                    tenant_id=ganga.id, product_id=lms.id
                ).first()
                if not exists:
                    db.session.add(TenantProduct(
                        tenant_id=ganga.id,
                        product_id=lms.id,
                        status='active',
                    ))
                db.session.commit()


def _ensure_demo_lms_tenant(app: 'Flask'):
    """
    Ensure a dedicated internal LMS demo tenant exists at /demo/lms.

    Guarantees:
    - Demo tenant is not created through client provisioning flow.
    - Demo tenant uses dummy data and a dedicated demo superadmin.
    - LMS feature flags stay in sync with Ganga on each startup.
    """
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.project import Project
    from app.models.lead import Lead
    from app.models.product import Product, TenantProduct, FeatureFlag
    from app.utils.jwt import hash_password

    with app.app_context():
        ganga = Tenant.query.filter_by(slug='ganga').first()
        lms = Product.query.filter_by(slug='lms').first()
        if not lms:
            return

        demo = Tenant.query.filter_by(slug=DEMO_TENANT_SLUG).first()
        if not demo:
            demo = Tenant(
                name=DEMO_TENANT_NAME,
                slug=DEMO_TENANT_SLUG,
                brand_name=DEMO_BRAND_NAME,
                logo_url=DEMO_LOGO_URL,
                favicon_url=DEMO_FAVICON_URL,
                primary_color=(ganga.primary_color if ganga else '#1e3a5f'),
                secondary_color=(ganga.secondary_color if ganga else '#3b82f6'),
                accent_color=(ganga.accent_color if ganga else '#10b981'),
                sidebar_bg_color=(ganga.sidebar_bg_color if ganga else '#1e293b'),
                login_bg_color=(ganga.login_bg_color if ganga else '#f1f5f9'),
                plan=(ganga.plan if ganga else 'enterprise'),
                status='active',
                max_users=(ganga.max_users if ganga else 100),
                admin_email=DEMO_ADMIN_EMAIL,
                admin_name=DEMO_ADMIN_NAME,
                industry='Demo',
                notes='Internal LMS demo tenant. Not a client account.',
            )
            db.session.add(demo)
            db.session.flush()
        else:
            demo.name = DEMO_TENANT_NAME
            demo.brand_name = DEMO_BRAND_NAME
            demo.logo_url = DEMO_LOGO_URL
            demo.favicon_url = DEMO_FAVICON_URL
            demo.status = 'active'
            demo.admin_email = DEMO_ADMIN_EMAIL
            demo.admin_name = DEMO_ADMIN_NAME
            demo.notes = 'Internal LMS demo tenant. Not a client account.'
            if ganga:
                demo.primary_color = ganga.primary_color
                demo.secondary_color = ganga.secondary_color
                demo.accent_color = ganga.accent_color
                demo.sidebar_bg_color = ganga.sidebar_bg_color
                demo.login_bg_color = ganga.login_bg_color
                demo.plan = ganga.plan
                demo.max_users = ganga.max_users

        demo_admin = User.query.filter_by(email=DEMO_ADMIN_EMAIL).first()
        if not demo_admin:
            demo_admin = User(
                name=DEMO_ADMIN_NAME,
                email=DEMO_ADMIN_EMAIL,
                password_hash=hash_password(DEMO_ADMIN_PASSWORD),
                role='superadmin',
                tenant_id=demo.id,
                is_active=True,
            )
            db.session.add(demo_admin)
            db.session.flush()
        else:
            demo_admin.name = DEMO_ADMIN_NAME
            demo_admin.role = 'superadmin'
            demo_admin.tenant_id = demo.id
            demo_admin.is_active = True

        demo_sub = TenantProduct.query.filter_by(tenant_id=demo.id, product_id=lms.id).first()
        if not demo_sub:
            db.session.add(TenantProduct(
                tenant_id=demo.id,
                product_id=lms.id,
                status='active',
            ))
        else:
            demo_sub.status = 'active'

        # Keep demo focused on LMS only.
        TenantProduct.query.filter(
            TenantProduct.tenant_id == demo.id,
            TenantProduct.product_id != lms.id,
        ).delete(synchronize_session=False)

        # Mirror LMS feature flags from Ganga to demo on every startup.
        if ganga:
            source_flags = FeatureFlag.query.filter_by(
                tenant_id=ganga.id,
                product_id=lms.id,
            ).all()
            for src in source_flags:
                dst = FeatureFlag.query.filter_by(
                    tenant_id=demo.id,
                    product_id=lms.id,
                    flag_key=src.flag_key,
                ).first()
                if not dst:
                    dst = FeatureFlag(
                        flag_key=src.flag_key,
                        tenant_id=demo.id,
                        product_id=lms.id,
                    )
                    db.session.add(dst)
                dst.is_enabled = src.is_enabled
                dst.flag_value = src.flag_value
                dst.description = src.description

        _seed_demo_lms_data(demo.id, demo_admin.id)
        db.session.commit()


def _seed_demo_lms_data(demo_tenant_id: int, demo_admin_id: int):
    """Seed deterministic dummy LMS data for demo tenant if empty."""
    from app.models.project import Project
    from app.models.lead import Lead

    if Project.query.filter_by(tenant_id=demo_tenant_id).count() == 0:
        demo_projects = [
            dict(
                name='Demo Residency Alpha',
                description='Dummy inventory for product walkthrough.',
                location='Demo City',
                developer='Sociomonkey Demo Builders',
                project_type='Residential',
                budget_min=3500000,
                budget_max=7800000,
            ),
            dict(
                name='Demo Business Plaza',
                description='Dummy commercial catalogue for LMS simulation.',
                location='Demo Tech Park',
                developer='Sociomonkey Demo Builders',
                project_type='Commercial',
                budget_min=9000000,
                budget_max=24000000,
            ),
            dict(
                name='Demo Heights Premium',
                description='Dummy premium segment portfolio.',
                location='Demo Central',
                developer='Sociomonkey Demo Builders',
                project_type='Luxury Residential',
                budget_min=12000000,
                budget_max=36000000,
            ),
        ]
        for proj in demo_projects:
            db.session.add(Project(
                tenant_id=demo_tenant_id,
                created_by=demo_admin_id,
                **proj,
            ))
        db.session.flush()

    if Lead.query.filter_by(tenant_id=demo_tenant_id).count() == 0:
        project_ids = [p.id for p in Project.query.filter_by(tenant_id=demo_tenant_id).order_by(Project.id).all()]
        demo_leads = [
            dict(name='Demo Lead One', phone='9000000001', email='demo.lead1@example.com', source='Demo Campaign', status='new'),
            dict(name='Demo Lead Two', phone='9000000002', email='demo.lead2@example.com', source='Demo Website', status='interested'),
            dict(name='Demo Lead Three', phone='9000000003', email='demo.lead3@example.com', source='Demo Referral', status='site_visit_planned'),
            dict(name='Demo Lead Four', phone='9000000004', email='demo.lead4@example.com', source='Demo Walk-in', status='site_visit_done'),
            dict(name='Demo Lead Five', phone='9000000005', email='demo.lead5@example.com', source='Demo Social', status='negotiation'),
            dict(name='Demo Lead Six', phone='9000000006', email='demo.lead6@example.com', source='Demo Campaign', status='booking_done'),
        ]
        for idx, ld in enumerate(demo_leads):
            project_id = project_ids[idx % len(project_ids)] if project_ids else None
            db.session.add(Lead(
                tenant_id=demo_tenant_id,
                project_id=project_id,
                created_by=demo_admin_id,
                budget_min=3500000,
                budget_max=15000000,
                **ld,
            ))


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed(app: Flask):
    from app.models.user import User, Role
    from app.models.project import Project
    from app.models.lead import Lead
    from app.models.tenant import Tenant

    with app.app_context():
        # Get Ganga Realty tenant (should already exist from migration)
        ganga = Tenant.query.filter_by(slug='ganga').first()
        ganga_id = ganga.id if ganga else None
        # --- Roles ---
        if Role.query.count() == 0:
            db.session.add_all([
                Role(name='superadmin', display_name='Super Admin',
                     permissions={'all': True}),
                Role(name='sales_manager', display_name='Sales Manager',
                     permissions={'view_team': True, 'manage_leads': True, 'upload_leads': True}),
                Role(name='team_member', display_name='Team Member / Sales Executive',
                     permissions={'view_assigned': True, 'update_status': True}),
            ])
            db.session.commit()

        # --- Admin user ---
        _ensure_user(
            name='Ganga Realty Admin',
            email='admin@gangarealty.com',
            phone='+91 99999 99999',
            password='Admin@123',
            role='superadmin',
            tenant_id=ganga_id,
        )

        # --- Managers ---
        _ensure_user(
            name='Raj Kumar (Manager)',
            email='manager1@gangarealty.com',
            phone='+91 98765 43210',
            password='Manager@123',
            role='sales_manager',
            tenant_id=ganga_id,
        )
        _ensure_user(
            name='Priya Sharma (Manager)',
            email='manager2@gangarealty.com',
            phone='+91 98888 77777',
            password='Manager@123',
            role='sales_manager',
            tenant_id=ganga_id,
        )
        db.session.commit()

        manager1 = User.query.filter_by(email='manager1@gangarealty.com').first()
        manager2 = User.query.filter_by(email='manager2@gangarealty.com').first()

        # --- Team members under Manager 1 ---
        for member in [
            ('Akhil Singh',   'akhil.singh@gangarealty.com',   '+91 98765 11111'),
            ('Bhavna Verma',  'bhavna.verma@gangarealty.com',  '+91 98765 22222'),
            ('Chirag Mehta',  'chirag.mehta@gangarealty.com',  '+91 98765 33333'),
            ('Divya Nair',    'divya.nair@gangarealty.com',    '+91 98765 44444'),
            ('Esha Gupta',    'esha.gupta@gangarealty.com',    '+91 98765 55555'),
        ]:
            _ensure_user(
                name=member[0], email=member[1], phone=member[2],
                password='TeamMember@123', role='team_member',
                manager_id=manager1.id if manager1 else None,
                tenant_id=ganga_id,
            )

        # --- Team members under Manager 2 ---
        for member in [
            ('Farhan Khan',   'farhan.khan@gangarealty.com',   '+91 98888 11111'),
            ('Geeta Pillai',  'geeta.pillai@gangarealty.com',  '+91 98888 22222'),
            ('Harsh Tiwari',  'harsh.tiwari@gangarealty.com',  '+91 98888 33333'),
        ]:
            _ensure_user(
                name=member[0], email=member[1], phone=member[2],
                password='TeamMember@123', role='team_member',
                manager_id=manager2.id if manager2 else None,
                tenant_id=ganga_id,
            )
        db.session.commit()

        # --- Projects ---
        for proj in [
            dict(name='Ganga Residency Phase 1',
                 description='Premium 2BHK and 3BHK apartments',
                 location='Pune, Maharashtra',
                 developer='Ganga Realty Pvt Ltd',
                 project_type='Residential',
                 budget_min=4500000, budget_max=8500000),
            dict(name='Ganga Business Park',
                 description='Modern commercial office spaces',
                 location='Hinjewadi, Pune',
                 developer='Ganga Realty Pvt Ltd',
                 project_type='Commercial',
                 budget_min=8000000, budget_max=25000000),
            dict(name='Ganga Heights',
                 description='Luxury 4BHK penthouses with amenities',
                 location='Koregaon Park, Pune',
                 developer='Ganga Realty Pvt Ltd',
                 project_type='Luxury Residential',
                 budget_min=12000000, budget_max=35000000),
        ]:
            if not Project.query.filter_by(name=proj['name'], tenant_id=ganga_id).first():
                admin = User.query.filter_by(email='admin@gangarealty.com').first()
                db.session.add(Project(**proj, tenant_id=ganga_id, created_by=admin.id if admin else None))
        db.session.commit()

        # --- Sample leads ---
        if Lead.query.count() == 0:
            admin = User.query.filter_by(email='admin@gangarealty.com').first()
            manager1 = User.query.filter_by(email='manager1@gangarealty.com').first()
            manager2 = User.query.filter_by(email='manager2@gangarealty.com').first()
            team = User.query.filter_by(role='team_member').all()
            projects = Project.query.all()

            sample_leads = [
                Lead(name='Priya Singh',    email='priya.singh@example.com',
                     phone='9876543210', source='Website', status='new',
                     project_id=projects[0].id if projects else None,
                     assigned_to=team[0].id if team else None,
                     assigned_by=manager1.id if manager1 else None,
                     tenant_id=ganga_id, created_by=admin.id),
                Lead(name='Rahul Kumar',    email='rahul.kumar@example.com',
                     phone='9123456780', source='Referral', status='interested',
                     project_id=projects[1].id if len(projects) > 1 else None,
                     assigned_to=team[1].id if len(team) > 1 else None,
                     assigned_by=manager1.id if manager1 else None,
                     tenant_id=ganga_id, created_by=admin.id),
                Lead(name='Anita Patel',    email='anita.patel@example.com',
                     phone='9988776655', source='Walk-in', status='site_visit_planned',
                     project_id=projects[0].id if projects else None,
                     assigned_to=team[2].id if len(team) > 2 else None,
                     assigned_by=manager1.id if manager1 else None,
                     tenant_id=ganga_id, created_by=admin.id),
                Lead(name='Sandeep Joshi',  email='sandeep.joshi@example.com',
                     phone='9012345678', source='Email Campaign', status='negotiation',
                     project_id=projects[2].id if len(projects) > 2 else None,
                     assigned_to=team[3].id if len(team) > 3 else None,
                     assigned_by=manager2.id if manager2 else None,
                     tenant_id=ganga_id, created_by=admin.id),
                Lead(name='Meera Sharma',   email='meera.sharma@example.com',
                     phone='9090909090', source='Social Media', status='booking_done',
                     project_id=projects[1].id if len(projects) > 1 else None,
                     assigned_to=team[4].id if len(team) > 4 else None,
                     assigned_by=manager2.id if manager2 else None,
                     tenant_id=ganga_id, created_by=admin.id),
                Lead(name='Test Lead',      phone='9999999999', source='Demo',
                     status='new',
                     project_id=projects[0].id if projects else None,
                     tenant_id=ganga_id, created_by=admin.id),
            ]
            db.session.add_all(sample_leads)
            db.session.commit()


        # Seed platform owner
        _ensure_user(
            name=PRIMARY_ADMIN_NAME,
            email=PRIMARY_ADMIN_NEW_EMAIL,
            password='SocioMonkey#2024',
            role='platform_owner',
            tenant_id=None,
        )
        db.session.commit()


def _ensure_user(name, email, password, role, phone=None, manager_id=None, tenant_id=None):
    from app.models.user import User
    from app.utils.jwt import hash_password
    if not User.query.filter_by(email=email).first():
        db.session.add(User(
            name=name, email=email, phone=phone,
            password_hash=hash_password(password),
            role=role,
            manager_id=manager_id,
            tenant_id=tenant_id,
            is_active=True,
        ))
