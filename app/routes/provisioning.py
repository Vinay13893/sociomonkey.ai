"""
Tenant Provisioning Engine
==========================
Atomic organization creation with full setup in a single transaction.

Endpoints:
  POST /api/platform/provision                  — full atomic provisioning
  POST /api/platform/tenants/:id/impersonate    — generate JWT for tenant admin
  GET  /api/platform/tenants/:id/usage          — usage statistics
"""
import re
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from app.middleware import require_platform_owner
from app.models.base import db
from app.models.product import FeatureFlag, Product, TenantProduct
from app.models.tenant import Tenant
from app.models.user import User
from app.utils.activity import log_activity
from app.utils.jwt import create_token, hash_password


provisioning_bp = Blueprint('provisioning', __name__, url_prefix='/api/platform')

# ── Constants ──────────────────────────────────────────────────────────────────

RESERVED_SLUGS = frozenset([
    'api', 'login', 'logout', 'admin', 'platform', 'products', 'applications',
    'users', 'organizations', 'analytics', 'billing', 'integrations', 'automation',
    'settings', 'audit-logs', 'support', 'health', 'static', 'public',
    'sociomonkey', 'www', 'app', 'portal', 'dashboard', 'provision',
])

# Default feature flags seeded per product on provisioning
PRODUCT_DEFAULT_FLAGS = {
    'crm': [
        ('pipeline',        True),
        ('reports',         True),
        ('bulk_import',     True),
        ('export',          True),
        ('team_management', True),
        ('activity_logs',   True),
        ('automation',      False),
        ('ai_assist',       False),
    ],
}


# ── Provision ─────────────────────────────────────────────────────────────────

@provisioning_bp.route('/provision', methods=['POST'])
@require_platform_owner
def provision_tenant():
    """
    Atomically create a fully configured organization:
      1. Tenant record with branding
      2. Admin user (role=superadmin)
      3. Product subscriptions
      4. Feature flags (defaults + caller overrides)

    Body:
      name*, slug*, admin_email*, admin_password*, admin_name
      plan, industry, max_users, notes
      brand_name, logo_url, favicon_url
      primary_color, secondary_color, accent_color, sidebar_bg_color, login_bg_color
      products: ['crm', ...]
      feature_flags: { pipeline: true, reports: false, ... }
    """
    owner = request.current_user
    data  = request.get_json() or {}

    # ── Required field validation ──────────────────────────────────────────
    name  = (data.get('name') or '').strip()
    slug  = (data.get('slug') or '').strip().lower()
    if not name:
        return jsonify({'error': 'Organization name is required'}), 400
    if not slug:
        return jsonify({'error': 'Slug is required'}), 400
    if not re.match(r'^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$', slug):
        return jsonify({'error': 'Slug must be 3–50 lowercase letters, numbers, or hyphens and start/end with alphanumeric'}), 400
    if slug in RESERVED_SLUGS:
        return jsonify({'error': f'"{slug}" is a reserved identifier and cannot be used'}), 400
    if Tenant.query.filter_by(slug=slug).first():
        return jsonify({'error': f'Slug "{slug}" is already taken'}), 400

    admin_email    = (data.get('admin_email') or '').strip().lower()
    admin_password = (data.get('admin_password') or '').strip()
    admin_name     = (data.get('admin_name') or '').strip() or f'{name} Admin'

    if not admin_email:
        return jsonify({'error': 'Admin email is required'}), 400
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', admin_email):
        return jsonify({'error': 'Invalid admin email address'}), 400
    if not admin_password or len(admin_password) < 6:
        return jsonify({'error': 'Admin password must be at least 6 characters'}), 400
    if User.query.filter_by(email=admin_email).first():
        return jsonify({'error': f'Email {admin_email} is already registered'}), 400

    # ── Validate products ──────────────────────────────────────────────────
    products_requested = data.get('products') or ['crm']
    valid_products = []
    for p_slug in products_requested:
        p = Product.query.filter_by(slug=p_slug, is_active=True).first()
        if p:
            valid_products.append(p)
    if not valid_products:
        return jsonify({'error': 'At least one valid active product is required'}), 400

    # ── Create tenant ──────────────────────────────────────────────────────
    tenant = Tenant(
        name=name,
        slug=slug,
        brand_name=data.get('brand_name') or name,
        logo_url=data.get('logo_url') or None,
        favicon_url=data.get('favicon_url') or None,
        primary_color=data.get('primary_color') or '#1e3a5f',
        secondary_color=data.get('secondary_color') or '#3b82f6',
        accent_color=data.get('accent_color') or '#10b981',
        sidebar_bg_color=data.get('sidebar_bg_color') or '#1e293b',
        login_bg_color=data.get('login_bg_color') or '#f1f5f9',
        plan=data.get('plan') or 'starter',
        status='active',
        max_users=int(data.get('max_users') or 20),
        admin_email=admin_email,
        admin_name=admin_name,
    )
    # Optional extended fields (added via migration; safe with hasattr guard)
    if hasattr(tenant, 'industry') and data.get('industry'):
        tenant.industry = data['industry']
    if hasattr(tenant, 'notes') and data.get('notes'):
        tenant.notes = data['notes']

    db.session.add(tenant)
    db.session.flush()  # get tenant.id before subsequent inserts

    # ── Create admin user ──────────────────────────────────────────────────
    admin_user = User(
        name=admin_name,
        email=admin_email,
        password_hash=hash_password(admin_password),
        role='superadmin',
        tenant_id=tenant.id,
        is_active=True,
    )
    db.session.add(admin_user)

    # ── Subscribe to products ──────────────────────────────────────────────
    provisioned_slugs = []
    for product in valid_products:
        sub = TenantProduct(
            tenant_id=tenant.id,
            product_id=product.id,
            status='active',
        )
        db.session.add(sub)
        provisioned_slugs.append(product.slug)

    # ── Seed feature flags ─────────────────────────────────────────────────
    flag_overrides = data.get('feature_flags') or {}
    for product in valid_products:
        default_flags = PRODUCT_DEFAULT_FLAGS.get(product.slug, [])
        for flag_key, default_val in default_flags:
            is_enabled = flag_overrides.get(flag_key, default_val)
            db.session.add(FeatureFlag(
                flag_key=flag_key,
                is_enabled=bool(is_enabled),
                tenant_id=tenant.id,
                product_id=product.id,
                description=f'Auto-seeded during provisioning of {name}',
            ))

    db.session.commit()

    log_activity(
        owner.id, 'provision_tenant', 'platform', tenant.id, 'Tenant',
        description=f'Provisioned: {name} ({slug}) | products: {", ".join(provisioned_slugs)}',
    )

    return jsonify({
        'success':              True,
        'tenant':               tenant.to_dict(include_stats=True),
        'admin_user':           {'id': admin_user.id, 'email': admin_user.email, 'name': admin_user.name},
        'products_provisioned': provisioned_slugs,
        'login_url':            f'/{slug}/{provisioned_slugs[0]}/login',
    }), 201


# ── Impersonation ──────────────────────────────────────────────────────────────

@provisioning_bp.route('/tenants/<int:tenant_id>/impersonate', methods=['POST'])
@require_platform_owner
def impersonate_tenant(tenant_id):
    """
    Generate a short-lived JWT for the tenant's primary admin.
    Platform admins can use this to view the tenant app as that user.
    Token expires in 4 hours.
    """
    owner  = request.current_user
    tenant = Tenant.query.get_or_404(tenant_id)

    # Find primary admin (superadmin first, then any active user)
    admin = (
        User.query
        .filter_by(tenant_id=tenant_id, role='superadmin', is_active=True)
        .order_by(User.id)
        .first()
    ) or (
        User.query
        .filter_by(tenant_id=tenant_id, is_active=True)
        .order_by(User.id)
        .first()
    )

    if not admin:
        return jsonify({'error': 'No active users found in this organization'}), 404

    imp_token = create_token(admin.id, admin.role, tenant_id=admin.tenant_id, expires_minutes=240)  # 4 hours

    log_activity(
        owner.id, 'impersonate_tenant', 'platform', tenant_id, 'Tenant',
        description=f'{owner.email} impersonated {tenant.slug} as {admin.email}',
    )

    return jsonify({
        'token':       imp_token,
        'user':        admin.to_dict(),
        'tenant_slug': tenant.slug,
        'tenant_name': tenant.name,
        'expires_in':  14400,
    }), 200


# ── Usage Statistics ───────────────────────────────────────────────────────────

@provisioning_bp.route('/tenants/<int:tenant_id>/usage', methods=['GET'])
@require_platform_owner
def get_tenant_usage(tenant_id):
    """Return usage statistics for a single tenant."""
    from app.models.lead import Lead

    tenant = Tenant.query.get_or_404(tenant_id)

    user_count = User.query.filter_by(tenant_id=tenant_id, is_active=True).count()
    lead_count = Lead.query.filter_by(tenant_id=tenant_id, is_active=True).count()

    # Active users in the last 30 days
    cutoff = datetime.utcnow() - timedelta(days=30)
    active_30d = User.query.filter(
        User.tenant_id == tenant_id,
        User.last_login >= cutoff,
        User.is_active == True,
    ).count()

    products = (
        db.session.query(Product.slug, Product.name, Product.icon)
        .join(TenantProduct, TenantProduct.product_id == Product.id)
        .filter(TenantProduct.tenant_id == tenant_id, TenantProduct.status == 'active')
        .all()
    )

    return jsonify({
        'tenant_id':        tenant_id,
        'tenant_name':      tenant.name,
        'plan':             tenant.plan,
        'status':           tenant.status,
        'user_count':       user_count,
        'lead_count':       lead_count,
        'active_30d':       active_30d,
        'max_users':        tenant.max_users,
        'user_utilization': round(user_count / max(tenant.max_users, 1) * 100, 1),
        'products':         [{'slug': p[0], 'name': p[1], 'icon': p[2]} for p in products],
    }), 200
