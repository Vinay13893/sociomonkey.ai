from datetime import datetime, timedelta
import hashlib
import os
import secrets

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app.middleware import require_auth
from app.models.base import db
from app.models.user import User
from app.utils.jwt import check_password, create_token
from app.utils.activity import log_activity

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Invalid credentials'}), 401

    user = User.query.filter_by(email=email).first()

    # Fail fast when user is unknown. This avoids heavy bcrypt work on
    # non-existent users and keeps serverless auth latency predictable.
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    password_ok = check_password(password, user.password_hash)
    if not password_ok:
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

_OTP_MAX_ATTEMPTS        = 5
_OTP_RESEND_COOLDOWN     = 30   # seconds between resends (UX guard)
_OTP_RATE_LIMIT          = 5    # max OTP requests per email per window
_OTP_RATE_WINDOW_MINUTES = 15   # rolling window in minutes
_OTP_LENGTH              = 6    # fixed policy: 6 digits
_OTP_EXPIRY_MINUTES      = 5    # fixed policy: 5 minutes


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def _client_ip(req) -> str:
    forwarded = req.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()[:45]
    return (req.remote_addr or '')[:45]


@auth_bp.route('/send-otp', methods=['POST'])
def send_otp():
    data        = request.get_json() or {}
    email       = (data.get('email')       or '').strip().lower()
    tenant_slug = (data.get('tenant_slug') or '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'error': 'Invalid email address'}), 400

    # Look up user (generic response prevents email enumeration)
    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        return jsonify({'message': 'If this email is registered, an OTP has been sent.'}), 200

    # Validate tenant_slug when provided
    if tenant_slug and user.role != 'platform_owner':
        from app.models.tenant import Tenant
        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 400
        if user.tenant and user.tenant.slug != tenant_slug:
            return jsonify({'message': 'If this email is registered, an OTP has been sent.'}), 200

    from app.models.base import db as _db
    from app.models.otp import OtpCode

    now = datetime.utcnow()

    # Per-email rate limit: max 5 OTP requests in any rolling 15-minute window
    rate_cutoff = now - timedelta(minutes=_OTP_RATE_WINDOW_MINUTES)
    recent_count = OtpCode.query.filter_by(email=email).filter(
        OtpCode.created_at >= rate_cutoff
    ).count()
    if recent_count >= _OTP_RATE_LIMIT:
        return jsonify({
            'error': f'Too many OTP requests. Please wait {_OTP_RATE_WINDOW_MINUTES} minutes before trying again.',
            'cooldown': _OTP_RATE_WINDOW_MINUTES * 60,
        }), 429

    # 30-second resend cooldown (UX guard — prevents accidental double-sends)
    cooldown_cutoff = now - timedelta(seconds=_OTP_RESEND_COOLDOWN)
    recent = (
        OtpCode.query
        .filter_by(email=email, used=False)
        .filter(OtpCode.created_at >= cooldown_cutoff)
        .filter(OtpCode.expires_at  >  now)
        .first()
    )
    if recent:
        elapsed  = int((now - recent.created_at).total_seconds())
        wait_sec = max(1, _OTP_RESEND_COOLDOWN - elapsed)
        return jsonify({
            'error':    f'Please wait {wait_sec} second(s) before requesting a new OTP.',
            'cooldown': wait_sec,
        }), 429

    # Invalidate all previous unused OTPs for this email
    _db.session.query(OtpCode).filter_by(email=email, used=False).update({'used': True})

    # Crypto-safe OTP with fixed policy constraints.
    raw_otp    = ''.join(str(secrets.randbelow(10)) for _ in range(_OTP_LENGTH))
    expiry_min = _OTP_EXPIRY_MINUTES

    code_row = OtpCode(
        email       = email,
        otp_hash    = _hash_otp(raw_otp),
        tenant_slug = tenant_slug or None,
        expires_at  = datetime.utcnow() + timedelta(minutes=expiry_min),
        ip_address  = _client_ip(request),
    )
    _db.session.add(code_row)
    _db.session.commit()

    # ── Send email ────────────────────────────────────────────────────────────
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    smtp_from = os.environ.get('SMTP_FROM', smtp_user)
    brevo_key  = os.environ.get('BREVO_API_KEY', '')
    brevo_from = os.environ.get('BREVO_FROM', '')
    resend_key = os.environ.get('RESEND_API_KEY', '')

    if not brevo_key and not resend_key and (not smtp_user or not smtp_pass):
        _db.session.delete(code_row)
        _db.session.commit()
        return jsonify({'error': 'Email service not configured on this server'}), 503

    html_body = (
        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;'
        'padding:24px;background:#f8fafc;border-radius:12px;">'
        '<div style="text-align:center;margin-bottom:20px;">'
        '<h2 style="color:#1e3a5f;margin:0;">Ganga Realty LMS</h2>'
        '</div>'
        '<div style="background:#ffffff;border-radius:8px;padding:32px;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.06);">'
        f'<p style="color:#334155;font-size:16px;margin-top:0;">Hello {user.name},</p>'
        '<p style="color:#334155;font-size:14px;">Use the code below to sign in. '
        f'It is valid for <strong>{expiry_min} minutes</strong> and can only be used once.</p>'
        '<div style="text-align:center;margin:28px 0;">'
        '<div style="display:inline-block;background:#1e3a5f;color:#ffffff;'
        'font-size:36px;font-weight:700;letter-spacing:14px;'
        'padding:18px 36px;border-radius:8px;font-family:Courier New,monospace;">'
        f'{raw_otp}</div>'
        '</div>'
        '<p style="color:#64748b;font-size:13px;margin-bottom:0;">'
        'If you did not request this code, please ignore this email. '
        'Never share this code with anyone.</p>'
        '</div>'
        '<p style="text-align:center;color:#94a3b8;font-size:11px;margin-top:16px;">'
        'Ganga Realty &mdash; Powered by SocioMonkey.ai</p>'
        '</div>'
    )
    text_body = (
        f'Hello {user.name},\n\n'
        f'Your Ganga Realty LMS login OTP is: {raw_otp}\n'
        f'This code is valid for {expiry_min} minutes and can be used only once.\n\n'
        'If you did not request this code, please ignore this email.\n\n'
        'Ganga Realty - Powered by SocioMonkey.ai'
    )

    try:
        if brevo_key:
            # ── Brevo API (HTTPS — works on Railway, sends to any recipient) ─
            import urllib.request as _ur, json as _json
            sender_email = brevo_from or smtp_from or smtp_user
            payload = {
                'sender':      {'name': 'Ganga Realty LMS', 'email': sender_email},
                'to':          [{'email': email}],
                'subject':     'Your Ganga Realty LMS Login OTP',
                'htmlContent': html_body,
                'textContent': text_body,
            }
            api_req = _ur.Request(
                'https://api.brevo.com/v3/smtp/email',
                data=_json.dumps(payload).encode(),
                headers={
                    'api-key':      brevo_key,
                    'Content-Type': 'application/json',
                },
                method='POST',
            )
            try:
                _ur.urlopen(api_req, timeout=15)
            except _ur.error.HTTPError as _he:
                _body = _he.read().decode('utf-8', errors='replace')
                raise RuntimeError(f'Brevo {_he.code}: {_body}')
        elif resend_key:
            # ── Resend API (HTTPS — works on Railway) ────────────────────────
            import urllib.request as _ur, json as _json
            resend_from = os.environ.get('RESEND_FROM', 'Ganga Realty LMS <onboarding@resend.dev>')
            payload = {
                'from':    resend_from,
                'to':      [email],
                'subject': 'Your Ganga Realty LMS Login OTP',
                'html':    html_body,
            }
            api_req = _ur.Request(
                'https://api.resend.com/emails',
                data=_json.dumps(payload).encode(),
                headers={
                    'Authorization': f'Bearer {resend_key}',
                    'Content-Type':  'application/json',
                },
                method='POST',
            )
            try:
                _ur.urlopen(api_req, timeout=15)
            except _ur.error.HTTPError as _he:
                _body = _he.read().decode('utf-8', errors='replace')
                raise RuntimeError(f'Resend {_he.code}: {_body}')
        else:
            # ── SMTP fallback (may be blocked on Railway) ─────────────────────
            import smtplib, socket
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            if not smtp_user or not smtp_pass:
                raise RuntimeError('No email provider configured (set BREVO_API_KEY, RESEND_API_KEY, or SMTP_USER/SMTP_PASS)')

            msg            = MIMEMultipart('alternative')
            msg['Subject'] = 'Your Ganga Realty LMS Login OTP'
            msg['From']    = f'Ganga Realty LMS <{smtp_from}>'
            msg['To']      = email
            msg.attach(MIMEText(html_body, 'html'))

            try:
                smtp_ip = socket.getaddrinfo(smtp_host, smtp_port, socket.AF_INET)[0][4][0]
            except Exception:
                smtp_ip = smtp_host

            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_ip, smtp_port, timeout=15) as srv:
                    srv.login(smtp_user, smtp_pass)
                    srv.sendmail(smtp_from, email, msg.as_string())
            else:
                with smtplib.SMTP(smtp_ip, smtp_port, timeout=15) as srv:
                    srv.ehlo()
                    srv.starttls()
                    srv.login(smtp_user, smtp_pass)
                    srv.sendmail(smtp_from, email, msg.as_string())

    except Exception as exc:
        _db.session.delete(code_row)
        _db.session.commit()
        return jsonify({'error': f'Failed to send OTP email: {exc}'}), 503

    log_activity(user.id, 'otp_sent', 'auth', description=f'OTP sent to {email}')
    return jsonify({
        'message':    'OTP sent successfully',
        'expires_in': expiry_min * 60,
    }), 200


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    data        = request.get_json() or {}
    email       = (data.get('email')       or '').strip().lower()
    otp         = (data.get('otp')         or '').strip()
    tenant_slug = (data.get('tenant_slug') or '').strip().lower()

    if not email or not otp:
        return jsonify({'error': 'Email and OTP are required'}), 400
    if len(otp) != _OTP_LENGTH or not otp.isdigit():
        return jsonify({'error': f'OTP must be exactly {_OTP_LENGTH} digits.'}), 400

    from app.models.base import db as _db
    from app.models.otp import OtpCode

    code_row = (
        OtpCode.query
        .filter_by(email=email, used=False)
        .order_by(OtpCode.created_at.desc())
        .first()
    )

    if not code_row:
        return jsonify({'error': 'No active OTP found. Please request a new one.'}), 401

    if datetime.utcnow() > code_row.expires_at:
        code_row.used = True
        _db.session.commit()
        return jsonify({'error': 'OTP has expired. Please request a new one.'}), 401

    if code_row.attempts >= _OTP_MAX_ATTEMPTS:
        code_row.used = True
        _db.session.commit()
        return jsonify({'error': 'Too many failed attempts. Please request a new OTP.'}), 429

    # Increment attempts before hash check (timing-attack mitigation)
    code_row.attempts += 1
    _db.session.commit()

    if code_row.otp_hash != _hash_otp(otp):
        remaining = _OTP_MAX_ATTEMPTS - code_row.attempts
        if remaining <= 0:
            code_row.used = True
            _db.session.commit()
            return jsonify({
                'error': 'Incorrect OTP. No attempts remaining — please request a new one.'
            }), 401
        return jsonify({
            'error': f'Incorrect OTP. {remaining} attempt(s) remaining.'
        }), 401

    # ── OTP verified ──────────────────────────────────────────────────────────
    code_row.used = True
    _db.session.commit()

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active:
        return jsonify({'error': 'Account not found or inactive'}), 403

    if tenant_slug and user.role != 'platform_owner':
        if user.tenant and user.tenant.slug != tenant_slug:
            return jsonify({'error': 'Access denied for this tenant'}), 403

    user.last_login = datetime.utcnow()
    _db.session.commit()

    jwt_token = create_token(user.id, user.role, tenant_id=user.tenant_id)
    log_activity(user.id, 'login_otp', 'auth', description=f'{user.email} logged in via OTP')

    return jsonify({
        'token':    jwt_token,
        'user':     user.to_dict(),
        'products': _get_user_products(user),
    }), 200


def _get_user_products(user):
    """Return list of products available to this user's tenant (or all for platform_owner)."""
    try:
        from app.models.product import Product, TenantProduct
        if user.role == 'platform_owner':
            products = Product.query.filter_by(is_active=True).all()
            product_ids = [p.id for p in products]
            counts_by_product = {}
            if product_ids:
                count_rows = (
                    db.session.query(
                        TenantProduct.product_id,
                        func.count(TenantProduct.id).label('tenant_count'),
                    )
                    .filter(
                        TenantProduct.product_id.in_(product_ids),
                        TenantProduct.status == 'active',
                    )
                    .group_by(TenantProduct.product_id)
                    .all()
                )
                counts_by_product = {
                    row.product_id: int(row.tenant_count or 0)
                    for row in count_rows
                }
            return [
                {
                    **p.to_dict(),
                    'tenant_count': counts_by_product.get(p.id, 0),
                }
                for p in products
            ]
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