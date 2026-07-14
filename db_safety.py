import os
import sys
from urllib.parse import urlparse


PRODUCTION_CONFIRMATION_ENV = "ALLOW_PRODUCTION_DB_OPERATION"
DESTRUCTIVE_CONFIRMATION_ENV = "CONFIRM_DESTRUCTIVE_DB_OPERATION"


def _normalize_database_url(database_url):
    database_url = (database_url or "").strip()
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def _truthy_env(name):
    return (os.environ.get(name) or "").strip().lower() == "true"


def masked_database_identity(database_url):
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    if host.endswith(".neon.tech"):
        host = "*.neon.tech"
    database = (parsed.path or "/unknown-db").lstrip("/") or "unknown-db"
    username = parsed.username or "unknown-user"
    return f"{parsed.scheme}://{username}:***@{host}/{database}"


def looks_like_production_database(database_url):
    parsed = urlparse(database_url)
    host = (parsed.hostname or "").lower()
    app_env = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "").lower()
    return (
        "neon.tech" in host
        or app_env == "production"
        or app_env == "prod"
        or _truthy_env("DATABASE_IS_PRODUCTION")
    )


def get_database_url(env_var="DATABASE_URL", *, require_production_confirmation=True, destructive=False):
    database_url = _normalize_database_url(os.environ.get(env_var))
    if not database_url:
        print(f"ERROR: {env_var} is not set. Refusing to continue.", file=sys.stderr)
        sys.exit(1)

    is_production = looks_like_production_database(database_url)
    if require_production_confirmation and is_production and not _truthy_env(PRODUCTION_CONFIRMATION_ENV):
        print(
            "ERROR: database appears production-like. Set "
            f"{PRODUCTION_CONFIRMATION_ENV}=true only after confirming this operation is intended.",
            file=sys.stderr,
        )
        print(f"Database identity: {masked_database_identity(database_url)}", file=sys.stderr)
        sys.exit(1)

    if destructive and not _truthy_env(DESTRUCTIVE_CONFIRMATION_ENV):
        print(
            "ERROR: destructive operation refused. Set "
            f"{DESTRUCTIVE_CONFIRMATION_ENV}=true only after an explicit backup and approval.",
            file=sys.stderr,
        )
        print(f"Database identity: {masked_database_identity(database_url)}", file=sys.stderr)
        sys.exit(1)

    print(f"Database identity: {masked_database_identity(database_url)}")
    return database_url


def _database_url_from_engine(engine):
    url = getattr(engine, "url", None)
    if url is None:
        return ""
    try:
        return url.render_as_string(hide_password=False)
    except Exception:
        return str(url)


def guard_sqlalchemy_engine(engine, *, destructive=False):
    database_url = _database_url_from_engine(engine)
    if not database_url:
        print("ERROR: could not determine SQLAlchemy database URL. Refusing to continue.", file=sys.stderr)
        sys.exit(1)

    is_production = looks_like_production_database(database_url)
    if is_production and not _truthy_env(PRODUCTION_CONFIRMATION_ENV):
        print(
            "ERROR: SQLAlchemy engine appears production-like. Set "
            f"{PRODUCTION_CONFIRMATION_ENV}=true only after confirming this operation is intended.",
            file=sys.stderr,
        )
        print(f"Database identity: {masked_database_identity(database_url)}", file=sys.stderr)
        sys.exit(1)

    if destructive and not _truthy_env(DESTRUCTIVE_CONFIRMATION_ENV):
        print(
            "ERROR: destructive operation refused. Set "
            f"{DESTRUCTIVE_CONFIRMATION_ENV}=true only after an explicit backup and approval.",
            file=sys.stderr,
        )
        print(f"Database identity: {masked_database_identity(database_url)}", file=sys.stderr)
        sys.exit(1)

    print(f"Database identity: {masked_database_identity(database_url)}")
