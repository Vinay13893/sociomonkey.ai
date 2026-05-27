import os
from typing import List, Union


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_cors_origins(raw: str) -> Union[List[str], str]:
    if not raw:
        return '*'
    value = raw.strip()
    if value == '*':
        return '*'
    origins = [o.strip() for o in value.split(',') if o.strip()]
    return origins or '*'


class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    JWT_EXPIRY_MINUTES = int(os.getenv('JWT_EXPIRY_MINUTES', 1440))  # 24 hours
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    CORS_ORIGINS = _parse_cors_origins(os.getenv('CORS_ORIGINS', '*'))
    ENV = os.getenv('APP_ENV', os.getenv('FLASK_ENV', 'development')).lower()


def _resolve_db_url(default: str) -> str:
    url = os.getenv('DATABASE_URL', default)
    # SQLAlchemy 1.4+ requires postgresql:// not postgres://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _resolve_db_url('sqlite:///mvp.db')


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _resolve_db_url('sqlite:///mvp.db')
    SECRET_KEY = os.getenv('SECRET_KEY', 'REPLACE-WITH-SECURE-SECRET')

    # Neon PostgreSQL requires short-lived connections (serverless)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 30,
        'connect_args': {'connect_timeout': 10},
    }

    # Guardrails for safer production defaults without hard-failing startup
    if SECRET_KEY in ('change-me-in-production', 'REPLACE-WITH-SECURE-SECRET'):
        print('[WARN] Using insecure SECRET_KEY default in production. Set SECRET_KEY env var.')

    if CORS_ORIGINS == '*':
        print('[WARN] CORS_ORIGINS is wildcard (*) in production. Restrict to app origin(s).')


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret'


def get_config_name(default: str = 'development') -> str:
    """Resolve config profile from environment for all entry points."""
    env = os.getenv('APP_ENV', os.getenv('FLASK_ENV', default)).strip().lower()
    if env in ('prod', 'production'):
        return 'production'
    if env in ('test', 'testing'):
        return 'testing'
    return 'development'
