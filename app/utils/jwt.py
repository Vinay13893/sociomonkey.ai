import bcrypt
import jwt
from datetime import datetime, timedelta
from flask import current_app


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8'))
    except (ValueError, Exception):
        return False


def create_token(user_id: int, role: str, tenant_id: int = None, expires_minutes: int = None) -> str:
    if expires_minutes is None:
        expires_minutes = current_app.config.get('JWT_EXPIRY_MINUTES', 1440)
    payload = {
        'sub': user_id,
        'role': role,
        'tid': tenant_id,  # tenant_id; None for platform_owner
        'typ': 'access',
        'exp': datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256',
    )


def create_refresh_token(user_id: int, role: str, tenant_id: int = None, expires_minutes: int = None) -> str:
    """Long-lived refresh token. Used only by /auth/refresh to mint new access tokens."""
    if expires_minutes is None:
        # 30 days default; configurable via env
        expires_minutes = current_app.config.get('JWT_REFRESH_EXPIRY_MINUTES', 43200)
    payload = {
        'sub': user_id,
        'role': role,
        'tid': tenant_id,
        'typ': 'refresh',
        'exp': datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256',
    )


def decode_token(token: str):
    try:
        return jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256'],
        )
    except Exception:
        return None
