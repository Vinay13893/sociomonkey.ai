from datetime import datetime, timedelta
import hashlib
import os
import random
import string

from flask import Blueprint, jsonify, request

from app.middleware import require_auth
from app.models.user import User
from app.utils.jwt import check_password, create_token
from app.utils.activity import log_activity

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()

    # Always run a password check to prevent timing-based user enumeration.
    # If no real user exists, compare against a dummy hash (result is always False).
    _DUMMY_HASH = '$2b$12$invalidhashpaddingthatislong'
    real_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = check_password(password, real_hash)

    if not user or not password_ok:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is inactive'}), 403

    # If a tenant slug is provided (from subdomain), validate the user belongs to that tenant
    tenant_slug = data.get('tenant_slug', '').strip().lower()
    if tenant_slug and user.role != 'platform_owner':
        from app.models.tenant import Tenant
        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        if tenant and user.tenant_id != tenant.id:
            return jsonify({'error': 'Invalid credentials'}), 401

    user.last_login = datetime.utcnow()
    from app.models.base import db
    db.session.commit()

    token = create_token(user.id, user.role, tenant_id=user.tenant_id)
    log_activity(user.id, 'login', 'auth', description=f'{user.email} logged in')

    return jsonify({'token': token, 'user': user.to_dict(), 'products': _get_user_products(user)}), 200


@auth_bp.route('/me', methods=['GET'])
@require_auth
def me():
    user = request.current_user
    return jsonify({'user': user.to_dict(), 'products': _get_user_products(user)}), 200


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    user = request.current_user
    log_activity(user.id, 'logout', 'auth', description=f'{user.email} logged out')
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/refresh', methods=['POST'])
@require_auth
def refresh():
    """Issue a fresh token for the currently authenticated user."""
    user = request.current_user
    new_token = create_token(user.id, user.role, tenant_id=user.tenant_id)
    return jsonify({'token': new_token, 'user': user.to_dict()}), 200


@auth_bp.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    user = request.current_user
    data = request.get_json() or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '').strip()

    if not new_password or len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    if not check_password(current_password, user.password_hash):
        return jsonify({'error': 'Current password is incorrect'}), 401

    from app.utils.jwt import hash_password
    from app.models.base import db
    user.password_hash = hash_password(new_password)
    db.session.commit()

    log_activity(
        user.id, 'change_password', 'auth',
        description=f'{user.email} changed their password',
    )
    return jsonify({'message': 'Password changed successfully'}), 200


# ---------------------------------------------------------------------------
# OTP Login
# ---------------------------------------------------------------------------

def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


@auth_bp.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        # Return generic message to avoid email enumeration
        return jsonify({'message': 'If this email is registered, an OTP has been sent.'}), 200

    from app.models.base import db as _db
    from app.models.otp import OtpToken

    # Invalidate any existing unused OTPs for this email
    _db.session.query(OtpToken).filter_by(email=email, used=False).update({'used': True})

    otp = ''.join(random.choices(string.digits, k=6))
    token = OtpToken(
        email=email,
        otp_hash=_hash_otp(otp),
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    _db.session.add(token)
    _db.session.commit()

    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASSWORD', '')

    if not smtp_user or not smtp_pass:
        return jsonify({'error': 'Email service not configured'}), 503

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Your Ganga Realty LMS Login OTP'
        msg['From'] = f'Ganga Realty LMS <{smtp_user}>'
        msg['To'] = email
        html_body = (
            f'<p>Hello {user.name},</p>'
            f'<p>Your one-time login code is:</p>'
            f'<h2 style="letter-spacing:6px;font-family:monospace;">{otp}</h2>'
            f'<p>This code expires in <strong>10 minutes</strong>. Do not share it with anyone.</p>'
            f'<p style="color:#64748b;font-size:12px;">Ganga Realty LMS</p>'
        )
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, email, msg.as_string())
    except Exception as exc:
        return jsonify({'error': f'Failed to send email: {str(exc)}'}), 503

    return jsonify({'message': 'OTP sent successfully'}), 200


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    otp = (data.get('otp') or '').strip()

    if not email or not otp:
        return jsonify({'error': 'Email and OTP are required'}), 400

    from app.models.base import db as _db
    from app.models.otp import OtpToken

    token_row = (
        OtpToken.query
        .filter_by(email=email, used=False)
        .order_by(OtpToken.created_at.desc())
        .first()
    )

    if not token_row:
        return jsonify({'error': 'Invalid or expired OTP'}), 401

    if datetime.utcnow() > token_row.expires_at:
        return jsonify({'error': 'OTP has expired. Please request a new one.'}), 401

    if token_row.otp_hash != _hash_otp(otp):
        return jsonify({'error': 'Incorrect OTP'}), 401

    token_row.used = True
    _db.session.commit()

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        return jsonify({'error': 'Account not found or inactive'}), 403

    user.last_login = datetime.utcnow()
    _db.session.commit()

    jwt_token = create_token(user.id, user.role, tenant_id=user.tenant_id)
    log_activity(user.id, 'login_otp', 'auth', description=f'{user.email} logged in via OTP')

    return jsonify({'token': jwt_token, 'user': user.to_dict(), 'products': _get_user_products(user)}), 200


def _get_user_products(user):
    """Return list of products available to this user's tenant (or all for platform_owner)."""
    try:
        from app.models.product import Product, TenantProduct
        if user.role == 'platform_owner':
            return [p.to_dict(include_stats=True) for p in Product.query.filter_by(is_active=True).all()]
        if user.tenant_id:
            subs = TenantProduct.query.filter_by(
                tenant_id=user.tenant_id, status='active'
            ).all()
            return [
                {**s.product.to_dict(), 'subscription_status': s.status}
                for s in subs if s.product and s.product.is_active
            ]
    except Exception:
        pass
    return []


@auth_bp.route('/branding', methods=['GET'])
def get_tenant_branding():
    """Public endpoint — return branding for a given tenant slug (for login page)."""
    slug = (request.args.get('slug') or '').strip().lower()
    if not slug:
        # Default SocioMonkey branding
        return jsonify({'branding': {
            'name': 'SocioMonkey CRM',
            'logo_url': None,
            'primary_color': '#1e3a5f',
            'secondary_color': '#3b82f6',
            'accent_color': '#10b981',
        }}), 200

    from app.models.tenant import Tenant
    tenant = Tenant.query.filter_by(slug=slug, status='active').first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    return jsonify({'branding': {
        'name': tenant.name,
        'slug': tenant.slug,
        'logo_url': tenant.logo_url,
        'primary_color': tenant.primary_color,
        'secondary_color': tenant.secondary_color,
        'accent_color': tenant.accent_color,
    }}), 200