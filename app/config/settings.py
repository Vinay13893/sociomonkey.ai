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
    JWT_EXPIRY_MINUTES         = int(os.getenv('JWT_EXPIRY_MINUTES', 1440))         # 24 hours
    JWT_REFRESH_EXPIRY_MINUTES = int(os.getenv('JWT_REFRESH_EXPIRY_MINUTES', 43200)) # 30 days
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    CORS_ORIGINS = _parse_cors_origins(os.getenv('CORS_ORIGINS', '*'))
    ENV = os.getenv('APP_ENV', os.getenv('FLASK_ENV', 'development')).lower()

    # VAPID for Web Push (RFC 8292). Generate with: python -m py_vapid
    # Store VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY as env vars on Vercel.
    VAPID_PUBLIC_KEY   = os.getenv('VAPID_PUBLIC_KEY', '')
    VAPID_PRIVATE_KEY  = os.getenv('VAPID_PRIVATE_KEY', '')
    VAPID_CLAIMS_EMAIL = os.getenv('VAPID_CLAIMS_EMAIL', 'mailto:push@sociomonkey.com')

    # Cron secret — set CRON_SECRET env var on Vercel, add same value to cron job auth.
    CRON_SECRET = os.getenv('CRON_SECRET', '')

    # Meta application secret used to verify X-Hub-Signature-256.
    META_APP_SECRET = os.getenv('META_APP_SECRET', '')

    # Meta signs every production webhook delivery. Development fixtures may
    # opt out explicitly, but production must fail closed.
    META_WEBHOOK_REQUIRE_SIGNATURE = _to_bool(
        os.getenv('META_WEBHOOK_REQUIRE_SIGNATURE'),
        default=ENV in ('production', 'prod'),
    )

    # Max push attempts before marking a subscription dead and deactivating it.
    PUSH_MAX_ATTEMPTS = int(os.getenv('PUSH_MAX_ATTEMPTS', 3))


def _resolve_db_url(default: str) -> str:
    raw = os.getenv('DATABASE_URL')
    url = (raw or '').strip()
    if not url:
        url = default
    # SQLAlchemy 1.4+ requires postgresql:// not postgres://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _resolve_db_url('sqlite:///mvp.db')


_prod_db_url = _resolve_db_url('sqlite:///mvp.db')
_runtime_env = os.getenv('APP_ENV', os.getenv('FLASK_ENV', 'development')).strip().lower()
_is_serverless = bool(os.getenv('VERCEL'))

if _runtime_env in ('prod', 'production') and _is_serverless:
    _raw_database_url = (os.getenv('DATABASE_URL') or '').strip()
    if not _raw_database_url:
        raise RuntimeError(
            'DATABASE_URL is empty in production serverless runtime. '
            'Refusing SQLite fallback on Vercel.'
        )
    if _prod_db_url.startswith('sqlite://'):
        raise RuntimeError(
            'DATABASE_URL resolved to SQLite in production serverless runtime. '
            'Set DATABASE_URL to a PostgreSQL connection string.'
        )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _prod_db_url
    SECRET_KEY = os.getenv('SECRET_KEY', 'REPLACE-WITH-SECURE-SECRET')

    # Neon PostgreSQL requires short-lived connections (serverless)
    # connect_args with connect_timeout only valid for PostgreSQL, not SQLite
    _engine_opts: dict = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 30,
    }
    if _prod_db_url.startswith('postgresql'):
        _engine_opts['connect_args'] = {'connect_timeout': 10}
    SQLALCHEMY_ENGINE_OPTIONS = _engine_opts

    # Guardrails for safer production defaults without hard-failing startup
    if SECRET_KEY in ('change-me-in-production', 'REPLACE-WITH-SECURE-SECRET'):
        print('[WARN] Using insecure SECRET_KEY default in production. Set SECRET_KEY env var.')

    if os.getenv('CORS_ORIGINS', '*') == '*':
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
