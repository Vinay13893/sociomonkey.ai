# File Index

Paths are relative to backend root unless prefixed `frontend:`.

| Path | Purpose | Relevance | Authority | Last phase |
|---|---|---|---|---|
| `app/__init__.py`, `api/index.py` | Backend app/entry | current | authoritative | V2-12 |
| `app/routes/` | Active API packages | current | authoritative | V2-12 |
| `app/models/` | Active model package | current | authoritative | V2-11 |
| `app/services/` | Domain/queue/report services | current | authoritative | V2-11 |
| `app/routes.py`, `app/routes_old.py`, `app/models.py` | Superseded monoliths | legacy | historical | pre-V2 |
| `migrations/phase1_reliability_20260722.py` | Reliability schema | current | authoritative | V2-1 |
| `migrations/phase2_organisation_permissions_20260723.py` | Org/capabilities | current | authoritative | V2-2 |
| `migrations/phase3_business_configuration_20260723.py` | Configuration | current | authoritative | V2-3 |
| `migrations/phase4_locations_rooms_20260723.py` | Locations/rooms | current | authoritative | V2-4 |
| `migrations/phase5_visits_20260723.py` | Visits | current | authoritative | V2-5 |
| `migrations/phase6_gallery_operations_20260723.py` | Reception/gallery | current | authoritative | V2-6 |
| `migrations/phase7_channel_partners_20260723.py` | Partners | current | authoritative | V2-7 |
| `migrations/phase8_action_items_20260723.py` | Actions | current | authoritative | V2-8 |
| `migrations/phase9_pipeline_engine_20260724.py` | Pipeline | current | authoritative | V2-9 |
| `migrations/phase11_notification_reliability_20260724.py` | Queue reliability | current | authoritative | V2-11 |
| `test_phase12_release_security_contract.py` | Backend security | current | authoritative test | V2-12 |
| `test_phase*_contract.py`, `test_phase*_integration.py` | V2 contracts/workflows | current | authoritative tests | V2-1..11 |
| `LMS_MASTER_IMPLEMENTATION_ROADMAP.md` | Approved scope/order/deferred work | current | authoritative plan | V2-12 |
| `LMS_PHASE2_RESULTS.md` ... `LMS_PHASE12_RESULTS.md` | Detailed phase evidence | current/history | authoritative local evidence | corresponding |
| `LMS_PHASE1_5_PRODUCTION_READINESS.md` | Early production/Meta/scheduler evidence | historical | reported state | V2-1 |
| `LMS_RELEASE_CHECKLIST.md`, `LMS_DEPLOYMENT_CHECKLIST.md` | release gates/order | current | authoritative procedure | V2-12 |
| `LMS_SMOKE_TEST_CHECKLIST.md`, `LMS_TENANT_UAT_CHECKLIST.md` | validation | current | authoritative procedure | V2-12 |
| `LMS_ROLLBACK_CHECKLIST.md` | rollback gates | current | authoritative procedure | V2-12 |
| `LMS_REPORTS_ANALYTICS_V2.md` | report contract | current | authoritative | V2-10 |
| `LMS_PLATFORM_INFRASTRUCTURE_MAP.md` | canonical/legacy assets | historical baseline | reported state | V2-1 |
| `frontend:index.html`, `src/main.js`, `src/router/router.js` | frontend entry/router | current | authoritative | V2-12 |
| `frontend:src/products/lms/` | LMS workspaces | current | authoritative | V2-11 |
| `frontend:manifest.json`, `service-worker.js`, `src/shared/services/push.js` | PWA/push | current | authoritative | V2-12 |
| `frontend:test_*_contract.js` | frontend validation | current | authoritative tests | V2-2..12 |
| `frontend:vercel.json`, `env.example.js` | deployment/public config | current | authoritative | V2-12 |
| `handover/*.md`, `handover_state.json` | takeover package | current | authoritative handover snapshot; refreshed 25 July ~12:15 IST post-deployment | post-V2-12 |
| `LMS_PRODUCTION_RELEASE_REPORT.md` | production deployment/certification evidence | current | authoritative; overall status "Production Blocked" pending Meta | post-deployment |
| `LMS_RECEPTION_WORKFLOW_STABILIZATION.md`, `LMS_RECEPTION_STABILIZATION_RESULTS.md` | Reception/Site Visit UX+workflow fixes, tested, not yet deployed | current | authoritative | post-deployment |
| `app/services/visit_builder.py` | shared Visit-payload validation + Lead-intake helpers, extracted from `visits.py` | current | authoritative | post-deployment |

Phase links: [2](../LMS_PHASE2_RESULTS.md), [3](../LMS_PHASE3_RESULTS.md), [4](../LMS_PHASE4_RESULTS.md), [5](../LMS_PHASE5_RESULTS.md), [6](../LMS_PHASE6_RESULTS.md), [7](../LMS_PHASE7_RESULTS.md), [8](../LMS_PHASE8_RESULTS.md), [9](../LMS_PHASE9_RESULTS.md), [10](../LMS_PHASE10_RESULTS.md), [11](../LMS_PHASE11_RESULTS.md), [12](../LMS_PHASE12_RESULTS.md). V2-0/1 are covered by the [roadmap](../LMS_MASTER_IMPLEMENTATION_ROADMAP.md) and [Phase 1.5 readiness](../LMS_PHASE1_5_PRODUCTION_READINESS.md).
