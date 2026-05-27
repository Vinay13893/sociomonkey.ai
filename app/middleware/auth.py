from functools import wraps
from flask import request, jsonify
from app.models.user import User
from app.utils.jwt import decode_token


ROLES_HIERARCHY = ['team_member', 'sales_manager', 'superadmin', 'platform_owner']


def get_auth_user():
    """Extract and validate JWT token from Authorization header, return User or None."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth.split(' ', 1)[1]
    payload = decode_token(token)
    if not payload:
        return None
    return User.query.get(payload.get('sub'))


def _resolve_product_context():
    """
    Determine the active product slug from the request.

    Priority order:
      1. X-Product-Slug request header
      2. URL path prefix  /api/products/<slug>/...
      3. Defaults to 'crm' (backward-compat with all existing routes)
    """
    slug = request.headers.get('X-Product-Slug', '').strip().lower()
    if slug:
        return slug
    # Path-based: /api/products/<slug>/...
    parts = request.path.strip('/').split('/')
    if len(parts) >= 3 and parts[0] == 'api' and parts[1] == 'products':
        return parts[2]
    return 'crm'


def _attach_product(user):
    """
    Load the active Product and verify the user's tenant is subscribed to it.
    Sets request.current_product_slug and request.current_product.
    platform_owner bypasses subscription check.
    """
    from app.models.product import Product, TenantProduct

    slug = _resolve_product_context()
    product = Product.query.filter_by(slug=slug).first()

    request.current_product_slug = slug
    request.current_product = product

    if user.role == 'platform_owner':
        return None  # Platform owner has access to everything

    if product and product.is_active and user.tenant_id:
        sub = TenantProduct.query.filter_by(
            tenant_id=user.tenant_id,
            product_id=product.id,
            status='active',
        ).first()
        if not sub:
            return jsonify({
                'error': f'Your account does not have access to {product.name}',
                'product': slug,
            }), 403
    return None


def require_auth(func):
    """Decorator: require a valid JWT. Sets request.current_user, request.current_tenant_id,
    request.current_product_slug, request.current_product."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_auth_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        if not user.is_active:
            return jsonify({'error': 'Account is inactive'}), 403
        request.current_user = user
        request.current_tenant_id = user.tenant_id
        # Platform owner can view any tenant's data by sending X-Tenant-Slug header
        if user.role == 'platform_owner':
            tenant_slug = request.headers.get('X-Tenant-Slug', '').strip().lower()
            if tenant_slug:
                from app.models.tenant import Tenant
                tenant = Tenant.query.filter_by(slug=tenant_slug).first()
                if tenant:
                    request.current_tenant_id = tenant.id
        err = _attach_product(user)
        if err:
            return err
        return func(*args, **kwargs)
    return wrapper


def require_role(*roles):
    """Decorator: require authentication AND one of the specified roles."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_auth_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401
            if not user.is_active:
                return jsonify({'error': 'Account is inactive'}), 403
            if user.role not in roles:
                return jsonify({'error': 'Permission denied'}), 403
            request.current_user = user
            request.current_tenant_id = user.tenant_id
            err = _attach_product(user)
            if err:
                return err
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_platform_owner(func):
    """Decorator: restrict to platform_owner role only."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_auth_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        if not user.is_active:
            return jsonify({'error': 'Account is inactive'}), 403
        if user.role != 'platform_owner':
            return jsonify({'error': 'Platform owner access required'}), 403
        request.current_user = user
        request.current_tenant_id = None
        request.current_product_slug = _resolve_product_context()
        request.current_product = None
        return func(*args, **kwargs)
    return wrapper
