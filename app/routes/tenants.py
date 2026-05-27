"""
Platform-owner routes: tenant CRUD, platform analytics.
All endpoints require the `platform_owner` role.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.middleware import require_auth, require_platform_owner
from app.models.base import db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.lead import Lead
from app.models.activity import ActivityLog
from app.utils.jwt import hash_password
from app.utils.activity import log_activity

tenants_bp = Blueprint('tenants', __name__, url_prefix='/api/platform')


# ─────────────────────────────────────────────────────────────
# Platform-wide analytics
# ─────────────────────────────────────────────────────────────
@tenants_bp.route('/analytics', methods=['GET'])
@require_platform_owner
def platform_analytics():
    tenants     = Tenant.query.all()
    total_users = User.query.filter(User.role != 'platform_owner').count()
    total_leads = Lead.query.filter_by(is_active=True).count()
    active_t    = sum(1 for t in tenants if t.status == 'active')

    tenant_stats = []
    for t in tenants:
        tenant_stats.append({
            'id':         t.id,
            'name':       t.name,
            'slug':       t.slug,
            'status':     t.status,
            'plan':       t.plan,
            'user_count': User.query.filter_by(tenant_id=t.id, is_active=True).count(),
            'lead_count': Lead.query.filter_by(tenant_id=t.id, is_active=True).count(),
            'created_at': t.created_at.isoformat(),
        })

    return jsonify({
        'stats': {
            'total_tenants':  len(tenants),
            'active_tenants': active_t,
            'total_users':    total_users,
            'total_leads':    total_leads,
        },
        'tenants': tenant_stats,
    }), 200


# ─────────────────────────────────────────────────────────────
# Tenant CRUD
# ─────────────────────────────────────────────────────────────
@tenants_bp.route('/tenants', methods=['GET'])
@require_platform_owner
def list_tenants():
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    return jsonify({'tenants': [t.to_dict(include_stats=True) for t in tenants]}), 200


@tenants_bp.route('/tenants', methods=['POST'])
@require_platform_owner
def create_tenant():
    owner = request.current_user
    data  = request.get_json() or {}

    name  = data.get('name', '').strip()
    slug  = data.get('slug', '').strip().lower()
    admin_email = data.get('admin_email', '').strip()
    admin_name  = data.get('admin_name', '').strip()

    if not name or not slug:
        return jsonify({'error': 'name and slug are required'}), 400
    if Tenant.query.filter_by(slug=slug).first():
        return jsonify({'error': f'Slug "{slug}" is already taken'}), 400

    tenant = Tenant(
        name=name,
        slug=slug,
        logo_url=data.get('logo_url'),
        primary_color=data.get('primary_color', '#1e3a5f'),
        secondary_color=data.get('secondary_color', '#3b82f6'),
        accent_color=data.get('accent_color', '#10b981'),
        custom_domain=data.get('custom_domain'),
        plan=data.get('plan', 'starter'),
        status='active',
        max_users=data.get('max_users', 20),
        admin_email=admin_email or None,
        admin_name=admin_name or None,
    )
    db.session.add(tenant)
    db.session.flush()  # get tenant.id before creating admin user

    # Auto-create default super-admin for the tenant if credentials provided
    admin_password = data.get('admin_password', 'Admin@123')
    if admin_email:
        if User.query.filter_by(email=admin_email).first():
            db.session.rollback()
            return jsonify({'error': f'Email {admin_email} is already in use'}), 400
        admin_user = User(
            name=admin_name or f'{name} Admin',
            email=admin_email,
            password_hash=hash_password(admin_password),
            role='superadmin',
            tenant_id=tenant.id,
            is_active=True,
        )
        db.session.add(admin_user)

    db.session.commit()
    log_activity(owner.id, 'create_tenant', 'platform', tenant.id, 'Tenant',
                 description=f'Created tenant: {name} ({slug})')

    return jsonify({'tenant': tenant.to_dict(include_stats=True)}), 201


@tenants_bp.route('/tenants/<int:tenant_id>', methods=['GET'])
@require_platform_owner
def get_tenant(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    users  = User.query.filter_by(tenant_id=tenant_id).order_by(User.created_at).all()
    return jsonify({
        'tenant': tenant.to_dict(include_stats=True),
        'users':  [u.to_dict() for u in users],
    }), 200


@tenants_bp.route('/tenants/<int:tenant_id>', methods=['PUT'])
@require_platform_owner
def update_tenant(tenant_id):
    owner  = request.current_user
    tenant = Tenant.query.get_or_404(tenant_id)
    data   = request.get_json() or {}

    for field in ['name', 'brand_name', 'logo_url', 'favicon_url', 'primary_color',
                  'secondary_color', 'accent_color', 'sidebar_bg_color', 'login_bg_color',
                  'custom_domain', 'plan', 'status', 'max_users',
                  'admin_email', 'admin_name', 'industry', 'notes']:
        if field in data:
            setattr(tenant, field, data[field])

    # Slug change requires uniqueness check
    new_slug = data.get('slug', '').strip().lower()
    if new_slug and new_slug != tenant.slug:
        if Tenant.query.filter_by(slug=new_slug).first():
            return jsonify({'error': f'Slug "{new_slug}" already taken'}), 400
        tenant.slug = new_slug

    tenant.updated_at = datetime.utcnow()
    db.session.commit()
    log_activity(owner.id, 'update_tenant', 'platform', tenant.id, 'Tenant',
                 description=f'Updated tenant: {tenant.name}')
    return jsonify({'tenant': tenant.to_dict(include_stats=True)}), 200


@tenants_bp.route('/tenants/<int:tenant_id>/status', methods=['POST'])
@require_platform_owner
def toggle_tenant_status(tenant_id):
    owner  = request.current_user
    tenant = Tenant.query.get_or_404(tenant_id)
    data   = request.get_json() or {}
    new_status = data.get('status', 'active')
    if new_status not in ('active', 'inactive', 'suspended'):
        return jsonify({'error': 'Invalid status'}), 400
    tenant.status = new_status
    tenant.updated_at = datetime.utcnow()
    db.session.commit()
    log_activity(owner.id, 'update_tenant_status', 'platform', tenant.id, 'Tenant',
                 description=f'Tenant {tenant.slug} status → {new_status}')
    return jsonify({'tenant': tenant.to_dict()}), 200


# ─────────────────────────────────────────────────────────────
# Product Management  (platform_owner only)
# ─────────────────────────────────────────────────────────────

@tenants_bp.route('/products', methods=['GET'])
@require_platform_owner
def list_products():
    """List all platform products with stats."""
    from app.models.product import Product
    products = Product.query.order_by(Product.id).all()
    return jsonify({'products': [p.to_dict(include_stats=True) for p in products]}), 200


@tenants_bp.route('/products', methods=['POST'])
@require_platform_owner
def create_product():
    """Create a new platform product."""
    owner = request.current_user
    data  = request.get_json() or {}
    from app.models.product import Product

    name = data.get('name', '').strip()
    slug = data.get('slug', '').strip().lower()
    if not name or not slug:
        return jsonify({'error': 'name and slug are required'}), 400
    if Product.query.filter_by(slug=slug).first():
        return jsonify({'error': f'Slug "{slug}" already exists'}), 400

    product = Product(
        name=name,
        slug=slug,
        description=data.get('description'),
        icon=data.get('icon', '📦'),
        color=data.get('color', '#3b82f6'),
        category=data.get('category', 'General'),
        version=data.get('version', '1.0.0'),
        is_active=data.get('is_active', True),
        is_public=data.get('is_public', True),
    )
    db.session.add(product)
    db.session.commit()
    log_activity(owner.id, 'create_product', 'platform', product.id, 'Product',
                 description=f'Created product: {name} ({slug})')
    return jsonify({'product': product.to_dict()}), 201


@tenants_bp.route('/products/<int:product_id>', methods=['PUT'])
@require_platform_owner
def update_product(product_id):
    """Update a platform product."""
    owner = request.current_user
    from app.models.product import Product
    product = Product.query.get_or_404(product_id)
    data = request.get_json() or {}

    for field in ['name', 'description', 'icon', 'color', 'category', 'version',
                  'is_active', 'is_public']:
        if field in data:
            setattr(product, field, data[field])
    product.updated_at = datetime.utcnow()
    db.session.commit()
    log_activity(owner.id, 'update_product', 'platform', product.id, 'Product',
                 description=f'Updated product: {product.name}')
    return jsonify({'product': product.to_dict(include_stats=True)}), 200


# ─────────────────────────────────────────────────────────────
# Tenant ↔ Product subscriptions
# ─────────────────────────────────────────────────────────────

@tenants_bp.route('/tenants/<int:tenant_id>/products', methods=['GET'])
@require_platform_owner
def get_tenant_products(tenant_id):
    """List products subscribed by a tenant."""
    Tenant.query.get_or_404(tenant_id)
    from app.models.product import Product, TenantProduct
    subs = TenantProduct.query.filter_by(tenant_id=tenant_id).all()
    subscribed_ids = {s.product_id for s in subs}
    all_products = Product.query.order_by(Product.id).all()
    return jsonify({
        'subscriptions': [s.to_dict() for s in subs],
        'available_products': [
            {**p.to_dict(), 'subscribed': p.id in subscribed_ids}
            for p in all_products
        ],
    }), 200


@tenants_bp.route('/tenants/<int:tenant_id>/products', methods=['POST'])
@require_platform_owner
def subscribe_tenant_product(tenant_id):
    """Subscribe a tenant to a product (or update existing subscription)."""
    owner = request.current_user
    Tenant.query.get_or_404(tenant_id)
    data = request.get_json() or {}
    product_id = data.get('product_id')
    if not product_id:
        return jsonify({'error': 'product_id is required'}), 400

    from app.models.product import Product, TenantProduct
    product = Product.query.get_or_404(product_id)

    sub = TenantProduct.query.filter_by(tenant_id=tenant_id, product_id=product_id).first()
    if sub:
        sub.status = data.get('status', 'active')
    else:
        sub = TenantProduct(
            tenant_id=tenant_id,
            product_id=product_id,
            status=data.get('status', 'active'),
        )
        db.session.add(sub)
    db.session.commit()
    log_activity(owner.id, 'subscribe_product', 'platform', tenant_id, 'Tenant',
                 description=f'Tenant {tenant_id} subscribed to {product.name}')
    return jsonify({'subscription': sub.to_dict()}), 200


@tenants_bp.route('/tenants/<int:tenant_id>/products/<int:product_id>', methods=['DELETE'])
@require_platform_owner
def unsubscribe_tenant_product(tenant_id, product_id):
    """Remove a tenant's subscription to a product."""
    owner = request.current_user
    from app.models.product import TenantProduct
    sub = TenantProduct.query.filter_by(
        tenant_id=tenant_id, product_id=product_id
    ).first()
    if not sub:
        return jsonify({'error': 'Subscription not found'}), 404
    db.session.delete(sub)
    db.session.commit()
    log_activity(owner.id, 'unsubscribe_product', 'platform', tenant_id, 'Tenant',
                 description=f'Tenant {tenant_id} unsubscribed from product {product_id}')
    return jsonify({'message': 'Unsubscribed'}), 200


# ─────────────────────────────────────────────────────────────
# Feature Flags
# ─────────────────────────────────────────────────────────────

@tenants_bp.route('/feature-flags', methods=['GET'])
@require_platform_owner
def list_feature_flags():
    from app.models.product import FeatureFlag
    tenant_id  = request.args.get('tenant_id', type=int)
    product_id = request.args.get('product_id', type=int)
    q = FeatureFlag.query
    if tenant_id:
        q = q.filter_by(tenant_id=tenant_id)
    if product_id:
        q = q.filter_by(product_id=product_id)
    return jsonify({'feature_flags': [f.to_dict() for f in q.all()]}), 200


@tenants_bp.route('/feature-flags', methods=['POST'])
@require_platform_owner
def set_feature_flag():
    from app.models.product import FeatureFlag
    owner = request.current_user
    data  = request.get_json() or {}
    flag_key   = data.get('flag_key', '').strip()
    if not flag_key:
        return jsonify({'error': 'flag_key is required'}), 400

    tenant_id  = data.get('tenant_id')
    product_id = data.get('product_id')
    existing   = FeatureFlag.query.filter_by(
        flag_key=flag_key, tenant_id=tenant_id, product_id=product_id
    ).first()

    if existing:
        existing.is_enabled  = data.get('is_enabled', existing.is_enabled)
        existing.flag_value  = data.get('flag_value', existing.flag_value)
        existing.description = data.get('description', existing.description)
        existing.updated_at  = datetime.utcnow()
        flag = existing
    else:
        flag = FeatureFlag(
            flag_key=flag_key,
            flag_value=data.get('flag_value'),
            is_enabled=data.get('is_enabled', True),
            tenant_id=tenant_id,
            product_id=product_id,
            description=data.get('description'),
        )
        db.session.add(flag)

    db.session.commit()
    return jsonify({'feature_flag': flag.to_dict()}), 200


# ─────────────────────────────────────────────────────────────
# Public: product catalog (for login-page product picker)
# ─────────────────────────────────────────────────────────────

@tenants_bp.route('/catalog', methods=['GET'])
def product_catalog():
    """Public — list all active, public products (no auth required)."""
    from app.models.product import Product
    products = Product.query.filter_by(is_active=True, is_public=True).order_by(Product.id).all()
    return jsonify({'products': [p.to_dict() for p in products]}), 200
