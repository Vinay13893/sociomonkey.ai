# LMS Phase 12 Release Readiness Report

Date: 24 July 2026

## Overall Status

**RELEASE CANDIDATE WITH EXTERNAL GATES**

The V2 codebase, additive migration chain, local contracts and approved Neon
recovery-branch rehearsal are certified. No production deployment, production
database write, push or external scheduler change was performed.

| Decision | Status | Condition |
|---|---|---|
| Ready for staging | Conditional Yes | First verify that staging/preview uses the approved non-production Neon branch |
| Ready for tenant UAT | No | Requires staging deployment and authenticated cross-role browser/device QA |
| Ready for production | No | Requires successful UAT, Meta, scheduler and physical PWA certification |

## Environment Certification

Canonical targets:

| Component | Project | Canonical URL | Certification |
|---|---|---|---|
| Backend | `backend` | `https://smk-backend-api.vercel.app` | Confirmed |
| Frontend | `frontend_static` | `https://lms.sociomonkey.com` | Confirmed |

The current production backend and frontend deployments are both in Vercel
`Ready` state. The backend health endpoint, frontend tenant login, PWA manifest,
service worker and public push configuration all returned HTTP 200.

Production backend variable presence:

| Variable group | Result |
|---|---|
| `DATABASE_URL`, `SECRET_KEY`, `CRON_SECRET` | Present; sensitive values not exposed |
| `META_APP_ID`, `META_APP_SECRET`, `META_OAUTH_SCOPES` | Present; values not exposed |
| VAPID public/private/contact variables | Present; public runtime configuration enabled |
| Backend/frontend canonical URLs | Present |
| Google integration variables | Present |
| `CORS_ORIGINS` | Missing; release fix now uses a canonical HTTPS-only production default |
| Bootstrap passwords | Optional explicit variables documented; no hard-coded fallback remains |

Sensitive values could not be decrypted by the available Vercel read-only
surface. Presence is certified; exact value correctness is deferred to staging
smoke tests. The separate `backend-staging` project still exists, but its
database host could not be compared with production.

## Migration Certification

The complete migration chain was run only against the approved Neon recovery
branch:

1. Phase 1 reliability
2. Phase 2 organisation and permissions
3. Phase 3 business configuration
4. Phase 4 locations and rooms
5. Phase 5 visits
6. Phase 6 gallery operations
7. Phase 7 channel partners
8. Phase 8 action items
9. Phase 9 pipeline engine
10. Phase 11 notification reliability

Results:

- Guarded preflight check passed.
- First full application passed.
- Second full application passed with no further changes.
- Final schema check passed.
- Destructive-statement scan found no destructive migration operations.
- Transactional rollback rehearsal retained no synthetic row.
- The chain is additive and idempotent.
- No production database was accessed.

Expected production locking is limited to normal PostgreSQL DDL locks while
creating absent tables, columns, indexes and constraints. Execute during the
approved maintenance window and stop on the first migration error.

## OAuth Certification

Static and recovery evidence confirms:

- Production Meta application ID/secret variable names are present.
- Meta webhook signature validation is fail-closed in production.
- Four active Meta sources in the recovery snapshot have page identifiers,
  access-token records, webhook tokens and a passing source test state.
- Duplicate ingestion remains protected by the existing idempotent ingestion
  contracts.
- Source and form mappings remain in the existing data model.

Not certified:

- Interactive Meta OAuth for a second business user against the staged V2 build.
- Live webhook verification and signed delivery against the staged V2 build.
- One controlled Meta form lead from delivery through deduplication and display.

These are external release gates, not failures found in the V2 code.

## Scheduler Certification

Vercel owns only the daily Meta report/source-spend job:

| Job | Owner | Schedule |
|---|---|---|
| Meta report/source spend | Vercel | `29 18 * * *` (11:59 PM IST) |
| Notification drain | cron-job.org | Target every 2 minutes |
| Reminder processor | cron-job.org | Target every 5 minutes |

Safe unauthenticated checks confirmed that all three protected worker routes
reject requests. Current cron-job.org job IDs, masked headers and two consecutive
successful runs could not be retrieved because no authenticated cron-job.org API
or browser session was available. Meta Lead Poll and duplicate Meta Report Sync
must remain inactive.

## Browser QA

No authenticated browser surface was available during certification. Therefore
desktop and responsive role-by-role QA was not represented as passed.

Static route, permission, tenant-isolation, frontend contract and integration
tests cover Admin, organisation, configuration, locations, visits, gallery,
channel partners, action boards, pipeline, reports and notification operations.
Authenticated browser QA for Admin, Sales Manager, Caller, RM, Reception and
Platform Owner remains mandatory on staging.

## PWA QA

Certified statically:

- Installable manifest, standalone mode, start URL and scope.
- Root-scoped service-worker registration.
- VAPID public-key retrieval.
- Push subscription registration endpoint.
- Push event display and notification-click handling.
- Existing-client focus and deep-link fallback.
- Android/iOS platform detection and subscription refresh after login.

The live public push configuration is enabled and exposes a valid public key.
Physical Android and iOS delivery, reinstall/re-registration behavior, background
delivery and deep-link clicks must be tested on the staged V2 build.

## Security Review

Release-blocking repository findings were corrected:

- Removed hard-coded bootstrap and demo passwords.
- Production bootstrap now requires explicit environment-backed credentials.
- Non-production bootstrap uses generated values when explicit values are absent.
- User, team and tenant provisioning no longer supplies default passwords.
- Password creation contracts enforce explicit minimum lengths.
- Removed credentials and import-time live requests from `test_login.py`.
- Production fails closed on a missing/default application secret.
- Production CORS defaults are restricted to canonical HTTPS origins.
- Added backend and frontend release-security contract tests.

Final secret-pattern scan of runtime/test source passed. No secret values are
included in this report.

Inherited technical debt:

- `app/models.py` duplicates names from the active `app/models/` package but is
  not imported by the application. It should be removed in a separately tested
  cleanup phase.
- Two manual Flask harness files are collected by unrestricted `pytest` and fail
  outside an app context. The bounded regression command excludes them.
- Python/SQLAlchemy deprecation warnings remain.

## Performance Review

- Backend pool is bounded at 5 connections plus 10 overflow, with 30-second pool
  timeout and 10-second connect timeout.
- Notification drain is capped at 10 events and a 45-second worker deadline.
- Push attempts are capped and use retry/dead-letter handling.
- Reminder processing is bounded to 500 rows.
- Interactive analytics use SQL aggregation and bounded result limits.
- Large exports remain separate from interactive reports.
- Route map contains 306 unique route/method contracts and no duplicates.
- Recovery snapshot sizes remain modest; the largest observed table was
  `meta_campaign_snapshots` at approximately 17.9 MB.
- Recovery queue snapshot contained 2,593 sent and 55 skipped events, with no
  pending, failed or dead-letter backlog.

Real staging latency, response-size, Neon transfer and 12-user load thresholds
cannot be certified without staging traffic.

## Test Results

| Check | Result |
|---|---|
| Backend bounded regression | 138 passed |
| Frontend contract suites | 13 passed |
| Phase 12 backend security contract | 5 passed |
| Python compilation | 143 files, 0 failures |
| JavaScript syntax | 86 files, 0 failures |
| Duplicate route/method registration | 0 |
| Migration apply/idempotency/check | Passed |
| Rollback-only database workflow | Passed |
| Secret-pattern scan | Passed |

## Remaining Defects and Gates

### Critical

None identified in the release candidate.

### Major

1. Staging/preview database isolation is not yet proven.
2. Authenticated cross-role desktop/responsive browser QA has not run.
3. Live Meta OAuth, webhook and controlled lead delivery are not certified.
4. Current cron-job.org configuration and consecutive successful runs are not
   independently certified.
5. Physical Android and iOS PWA push is not certified against the V2 candidate.
6. No staging capacity run has measured endpoint budgets and Neon usage.

### Minor

1. Inherited UTC and SQLAlchemy API deprecation warnings.
2. Legacy `app/models.py` and manual Flask harnesses remain.
3. Sensitive Vercel variable values cannot be decrypted with current access.
4. Old staging/legacy deployment assets require an owner-approved decommission
   decision after successful production rollout.

## Release Candidate Status

The code is suitable for an isolated staging deployment. It is not certified
for tenant UAT or production until every Major gate above is closed.

## Required Deployment Order

1. Confirm staging Vercel projects and approved non-production Neon branch.
2. Apply the rehearsed migration chain to staging.
3. Deploy backend to staging and run health/auth/schema checks.
4. Deploy frontend to staging and run authenticated role QA.
5. Validate Meta OAuth/webhook/form delivery.
6. Validate notification and reminder scheduler runs.
7. Validate Android/iOS PWA push.
8. Run capacity checks and obtain owner UAT approval.
9. Record a fresh production rollback point.
10. Apply migrations, deploy backend, then deploy frontend.
11. Execute production smoke tests before restoring tenant access.

## Final Recommendation

**Proceed to isolated staging after verifying its database target. Do not deploy
to production yet.** The remaining work is external release validation, not
additional architecture or feature development.
