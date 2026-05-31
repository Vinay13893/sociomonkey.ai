from functools import wraps

from flask import jsonify, request
from sqlalchemy import and_

from app.models.base import db
from app.models.user import User
from app.utils.jwt import decode_token


ROLES_HIERARCHY = ['team_member', 'sales_manager', 'superadmin', 'platform_owner']


def _auth_cache():
    cache = getattr(request, '_auth_cache', None)
    if cache is None:
        cache = {}
        request._auth_cache = cache
    return cache


def get_auth_user():
    """Extract and validate JWT token from Authorization header, return User or None."""
    cache = _auth_cache()
    if 'user' in cache:
        return cache['user']

    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        cache['user'] = None
        return None
    token = auth.split(' ', 1)[1]
    payload = decode_token(token)
    if not payload:
        cache['user'] = None
        return None

    user_id = payload.get('sub')
    if user_id is None:
        cache['user'] = None
        return None

    user = db.session.get(User, user_id)
    cache['user'] = user
    return user


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
    cache = _auth_cache()
    if cache.get('product_attached'):
        request.current_product_slug = cache.get('product_slug')
        request.current_product = cache.get('product')
        return cache.get('product_error')

    from app.models.product import Product, TenantProduct

    # Auth/session endpoints should not be product-gated. They are used to
    # establish session state and discover available subscriptions.
    if request.path.startswith('/api/auth/'):
        cache['product_slug'] = None
        cache['product'] = None
        cache['product_error'] = None
        cache['product_attached'] = True
        request.current_product_slug = None
        request.current_product = None
        return None

    slug = _resolve_product_context()
    product = None
    product_error = None

    request.current_product_slug = slug
    request.current_product = None

    if user.role == 'platform_owner':
        cache['product_slug'] = slug
        cache['product'] = None
        cache['product_error'] = None
        cache['product_attached'] = True
        return None

    product_row = (
        db.session.query(Product, TenantProduct.id.label('subscription_id'))
        .outerjoin(
            TenantProduct,
            and_(
                TenantProduct.product_id == Product.id,
                TenantProduct.tenant_id == user.tenant_id,
                TenantProduct.status == 'active',
            ),
        )
        .filter(Product.slug == slug)
        .first()
    )

    def _tenant_subscription_fallback():
        # Fallback for legacy clients that do not pass X-Product-Slug.
        # Prefer LMS when available, otherwise use first active subscription.
        return (
            db.session.query(Product)
            .join(
                TenantProduct,
                and_(
                    TenantProduct.product_id == Product.id,
                    TenantProduct.tenant_id == user.tenant_id,
                    TenantProduct.status == 'active',
                ),
            )
            .filter(Product.is_active.is_(True))
            .order_by(db.case((Product.slug == 'lms', 0), else_=1), Product.slug.asc())
            .first()
        )

    if product_row:
        product, subscription_id = product_row
        request.current_product = product
        if product.is_active and not subscription_id:
            fallback_product = _tenant_subscription_fallback() if slug == 'crm' else None
            if fallback_product:
                request.current_product = fallback_product
                request.current_product_slug = fallback_product.slug
                slug = fallback_product.slug
            else:
                product_error = jsonify({
                    'error': f'Your account does not have access to {product.name}',
                    'product': slug,
                }), 403
    elif slug == 'crm':
        fallback_product = _tenant_subscription_fallback()
        if fallback_product:
            request.current_product = fallback_product
            request.current_product_slug = fallback_product.slug
            slug = fallback_product.slug

    cache['product_slug'] = slug
    cache['product'] = request.current_product
    cache['product_error'] = product_error
    cache['product_attached'] = True
    return product_error


def _resolve_current_tenant_id(user):
    cache = _auth_cache()
    if 'tenant_id' in cache:
        return cache['tenant_id']

    tenant_id = user.tenant_id
    if user.role == 'platform_owner':
        tenant_slug = request.headers.get('X-Tenant-Slug', '').strip().lower()
        if tenant_slug:
            from app.models.tenant import Tenant

            tenant_id = (
                db.session.query(Tenant.id)
                .filter(Tenant.slug == tenant_slug)
                .scalar()
            ) or tenant_id

    cache['tenant_id'] = tenant_id
    return tenant_id


def _prepare_auth_request_context():
    user = get_auth_user()
    if not user:
        return None, (jsonify({'error': 'Authentication required'}), 401)
    if not user.is_active:
        return None, (jsonify({'error': 'Account is inactive'}), 403)

    request.current_user = user
    request.current_tenant_id = _resolve_current_tenant_id(user)
    err = _attach_product(user)
    if err:
        return None, err
    return user, None


def require_auth(func):
    """Decorator: require a valid JWT. Sets request.current_user, request.current_tenant_id,
    request.current_product_slug, request.current_product."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user, err = _prepare_auth_request_context()
        if err:
            return err
        return func(*args, **kwargs)
    return wrapper


def require_role(*roles):
    """Decorator: require authentication AND one of the specified roles."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user, err = _prepare_auth_request_context()
            if err:
                return err
            if user.role not in roles:
                return jsonify({'error': 'Permission denied'}), 403
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
