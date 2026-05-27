from flask import Flask, jsonify
from flask_cors import CORS

from app.models.base import db
from app.config import config_map, get_config_name


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
        # Import all models so SQLAlchemy registers the tables
        from app.models import (  # noqa: F401
            User, Role, Project, Lead,
            StatusHistory, LeadNote, LeadAssignmentHistory, ActivityLog,
            Product, TenantProduct, FeatureFlag, UsageLog,
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
        # Only seed on a completely fresh database (no users = first-ever boot)
        from app.models.user import User as _User
        if _User.query.count() == 0:
            _seed(app)
        else:
            # Ensure platform owner always exists
            _ensure_platform_owner(app)

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


def _ensure_platform_owner(app: 'Flask'):
    """Make sure the SocioMonkey platform owner account exists."""
    with app.app_context():
        _ensure_user(
            name='SocioMonkey Admin',
            email='admin@sociomonkey.ai',
            password='SocioMonkey#2024',
            role='platform_owner',
            tenant_id=None,
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
        name='Procurement & Vendor Management',
        slug='procurement',
        description='End-to-end procurement workflow: purchase orders, vendor management, '
                    'approvals, and spend analytics.',
        icon='🛒',
        color='#7c3aed',
        category='Operations',
        version='1.0.0',
        is_active=False,
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
        is_active=False,
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
            if not Product.query.filter_by(slug=p_data['slug']).first():
                db.session.add(Product(**p_data))
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
            name='SocioMonkey Admin',
            email='admin@sociomonkey.ai',
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
