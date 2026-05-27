import bcrypt
import jwt
from flask import current_app
from datetime import datetime, timedelta

SECRET = lambda: current_app.config.get('SECRET_KEY', 'dev-secret')

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, pw_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8'))

def create_token(user_id: int, role: str, expires_minutes=60*24):
    payload = {
        'sub': user_id,
        'role': role,
        'exp': datetime.utcnow() + timedelta(minutes=expires_minutes)
    }
    return jwt.encode(payload, SECRET(), algorithm='HS256')

def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET(), algorithms=['HS256'])
    except Exception:
        return None
