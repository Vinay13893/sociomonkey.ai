"""
Public API — no authentication required.

These endpoints are called by the frontend *before* login to load
tenant branding, enabled products, and feature flags so the login page
and tenant application can be white-labelled correctly.
"""
from flask import Blueprint, jsonify

from app.models.base import db
from app.models.tenant import Tenant

public_bp = Blueprint('public', __name__, url_prefix='/api/public')


@public_bp.route('/tenants/<slug>/config', methods=['GET'])
def get_tenant_config(slug):
    """
    Public — returns the full white-label config for a tenant identified by slug.
    Used by the frontend to apply branding before and during login.

    Response includes:
      - Branding  (colors, logo, favicon, brand name)
      - Products  (list of enabled product slugs)
      - Feature flags (per-tenant flag map: { pipeline: true, reports: false, … })
    """
    tenant = Tenant.query.filter_by(slug=slug).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404
    if tenant.status not in ('active', 'trial'):
        return jsonify({'error': 'Tenant is not available'}), 403

    # Enabled products (TenantProduct rows with status='active')
    from app.models.product import Product, TenantProduct, FeatureFlag
    enabled_products = (
        db.session.query(Product)
        .join(TenantProduct, TenantProduct.product_id == Product.id)
        .filter(
            TenantProduct.tenant_id == tenant.id,
            TenantProduct.status == 'active',
        )
        .all()
    )
    product_slugs = [p.slug for p in enabled_products]

    # If no explicit product subscriptions yet, fall back to CRM (existing tenants)
    if not product_slugs:
        product_slugs = ['crm']

    # Tenant-scoped feature flags  (flag_key → is_enabled)
    flags = FeatureFlag.query.filter_by(tenant_id=tenant.id).all()
    feature_map = {f.flag_key: f.is_enabled for f in flags}

    return jsonify({
        # Identity
        'id':           tenant.id,
        'slug':         tenant.slug,
        'name':         tenant.name,
        'brand_name':   tenant.brand_name or tenant.name,

        # Branding
        'logo_url':        tenant.logo_url,
        'favicon_url':     tenant.favicon_url,
        'primary_color':   tenant.primary_color   or '#0284c7',
        'secondary_color': tenant.secondary_color or '#0ea5e9',
        'accent_color':    tenant.accent_color    or '#10b981',
        'sidebar_bg_color': tenant.sidebar_bg_color or '#1e293b',
        'login_bg_color':  tenant.login_bg_color  or '#f1f5f9',

        # Products & features
        'products':      product_slugs,
        'feature_flags': feature_map,

        # Plan info (non-sensitive)
        'plan':   tenant.plan,
        'status': tenant.status,
    }), 200
