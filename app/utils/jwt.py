import bcrypt
import jwt
from datetime import datetime, timedelta
from flask import current_app


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password: str, pw_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8'))


def create_token(user_id: int, role: str, tenant_id: int = None, expires_minutes: int = None) -> str:
    if expires_minutes is None:
        expires_minutes = current_app.config.get('JWT_EXPIRY_MINUTES', 1440)
    payload = {
        'sub': user_id,
        'role': role,
        'tid': tenant_id,  # tenant_id; None for platform_owner
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
