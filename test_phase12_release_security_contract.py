from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_user_and_tenant_creation_require_explicit_passwords():
    team = (ROOT / 'app' / 'routes' / 'team.py').read_text(encoding='utf-8')
    tenants = (
        ROOT / 'app' / 'routes' / 'tenants.py'
    ).read_text(encoding='utf-8')
    assert "password = data.get('password', '')" in team
    assert 'not email or not name or not password' in team
    assert "data.get('password'," not in team.replace(
        "data.get('password', '')", ''
    )
    assert "admin_password = data.get('admin_password', '')" in tenants
    assert 'len(admin_password) < 8' in tenants


def test_production_bootstrap_fails_closed_without_credentials(monkeypatch):
    import app as app_module

    monkeypatch.delenv('PLATFORM_OWNER_BOOTSTRAP_PASSWORD', raising=False)
    configured_app = type(
        'ConfiguredApp', (), {'config': {'ENV': 'production'}}
    )()

    try:
        app_module._bootstrap_password(
            configured_app, 'PLATFORM_OWNER_BOOTSTRAP_PASSWORD'
        )
    except RuntimeError as exc:
        assert 'required for production bootstrap' in str(exc)
    else:
        raise AssertionError('Production bootstrap accepted a missing password')


def test_manual_login_check_has_no_import_time_network_call():
    source = (ROOT / 'test_login.py').read_text(encoding='utf-8')
    assert "if __name__ == '__main__':" in source
    assert "os.getenv('LMS_TEST_PASSWORD')" in source
    assert 'response.read()' not in source


def test_production_cors_fallback_excludes_local_origins():
    import app as app_module

    production = app_module._resolve_cors_origins('*', 'production')
    development = app_module._resolve_cors_origins('*', 'development')
    assert 'https://lms.sociomonkey.com' in production
    assert all('localhost' not in origin for origin in production)
    assert all('127.0.0.1' not in origin for origin in production)
    assert any('localhost' in origin for origin in development)


def test_production_secret_validation_runs_only_for_production():
    settings = (
        ROOT / 'app' / 'config' / 'settings.py'
    ).read_text(encoding='utf-8')
    app_factory = (ROOT / 'app' / '__init__.py').read_text(encoding='utf-8')
    assert 'Using insecure SECRET_KEY default' not in settings
    assert "if config_name == 'production'" in app_factory
    assert 'SECRET_KEY is required and must be non-default' in app_factory
