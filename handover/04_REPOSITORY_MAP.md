# Repository Map

## Backend

- Canonical entry: `api/index.py` imports the Flask app; `app/__init__.py` creates the app and registers active blueprints.
- Active routes: `app/routes/{auth,leads,team,organisation,configuration,locations,visits,gallery_operations,channel_partners,action_items,projects,pipeline,reports,uploads,tenants,public,provisioning,push,cron,whatsapp,ingestion,lead_sources}.py`.
- Active models: package `app/models/`, including tenant, user, lead, organisation, configuration, location, visit, channel partner, action item, pipeline, notification, push, ingestion, projects/products and supporting records.
- Services: `app/services/` for permissions, analytics/reports, ingestion, Pipeline, Actions, callbacks, notification queue/worker/operations, reminders and push.
- Migrations: `migrations/`; safety guard: `db_safety.py`.
- Tests: root `test_*.py`. `test_login.py` is now sanitized but remains a manual localhost harness; `_test_otp.py` and underscore scripts are manual helpers, not bounded regression tests.
- Config/deploy: `.env.example`, `app/config/settings.py`, `requirements.txt`, `runtime.txt`, `vercel.json`, `wsgi.py`.
- Release docs: root `LMS_*.md`.
- Legacy/inactive: `app/routes.py`, `app/routes_old.py`, and `app/models.py` look active but are superseded by `app/routes/` and `app/models/`. Do not edit them for active V2 behavior without proving import use.

## Frontend

- Entry: `index.html` -> `src/main.js`; routing in `src/router/router.js`; API base in `src/config/constants.js` and `env.js`.
- LMS modules: `src/products/lms/`; shell/context/auth/shared services under `src/`.
- PWA: `manifest.json`, `service-worker.js`, `Assets/pwa/`, `src/shared/services/push.js`.
- Tests: root `test_*_contract.js`.
- Config/deploy: `env.example.js`, `env.js`, `vercel.json`, `deploy.ps1`.
- Historical/legacy: `src/products/lms/lead-sources.js` and `src/products/lms/lead-sources-v2.js` coexist; V2 is the canonical lead-source workspace. `src/products/lms/action-board.js` is compatibility/history while `action-items-board.js` is the modern unified workspace. `src/products/crm/` is not the LMS implementation.

## Commands and current verification

Run from the correct worktree with the environment’s Python:

```powershell
# Backend bounded suite (historical Phase 12 command shape; current default
# Python 3.14 lacks pytest, so restore the approved Python 3.11 test environment first)
python -m pytest -q --ignore=test_login.py --ignore=test_app.py

# Frontend contract suites
Get-ChildItem -File test_*_contract.js | ForEach-Object { node $_.FullName }

# Compilation and syntax
python -m compileall -q app migrations api
Get-ChildItem -Recurse -File -Include *.js | Where-Object { $_.FullName -notlike '*\node_modules\*' } | ForEach-Object { node --check $_.FullName }

# Git whitespace and route duplication
git diff --check
python -c "from app import create_app; a=create_app(); r=[(x.rule,tuple(sorted(x.methods-{'HEAD','OPTIONS'}))) for x in a.url_map.iter_rules()]; assert len(r)==len(set(r)); print(len(r),'unique route/method contracts')"
```

At handover time Python compilation passed, all 86 frontend JavaScript files passed syntax checking, and all 13 frontend contract suites passed. Backend pytest did not run because the default Python 3.14 installation has no `pytest`; the documented 138-pass result remains historical Phase 12 evidence. Secret and migration checks must use the reviewed patterns/guarded scripts in [12_COMMAND_REFERENCE.md](12_COMMAND_REFERENCE.md). Local health requires a deliberately local database and explicit local environment; never let helper scripts inherit production `DATABASE_URL`.
