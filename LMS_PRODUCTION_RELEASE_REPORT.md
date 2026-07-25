# Sociomonkey LMS Production Release Report

Release date: 25 July 2026

Business timezone: Asia/Kolkata (IST, UTC+05:30)

Tenant route: `ganga-realty`

Tenant data scope: `ganga`

## Overall Status

**Production Blocked**

The approved V2 release candidate is deployed and its additive migration chain
is present in the canonical production database. Core application health,
database connectivity, notification workers and reminder workers are healthy.

Production sign-off is blocked because all four active Meta Page credentials
currently fail direct Meta Graph validation with OAuth error `190`. Live Meta
lead delivery, webhook subscription, form refresh and spend synchronization
therefore cannot be certified. No release-ready claim is made while this
tenant-critical ingestion path is unavailable.

## Deployment

| Component | Vercel project | Deployment ID | Canonical alias | Status |
|---|---|---|---|---|
| Backend | `backend` | `dpl_CGnUbbL6o58Gy821jdY6SVomaDNw` | `https://smk-backend-api.vercel.app` | Ready |
| Frontend | `frontend_static` | `dpl_CKzUoFjbRqHAAjr1Wqx8f4QHup1H` | `https://lms.sociomonkey.com` | Ready |

Backend release commit: `f3e45924fab49dc394f8eb698e88e08d6aecf059`

Frontend release commit: `fb0b5d9`

The backend fix preserves an existing Meta source identity when OAuth
reauthorization omits `source_id`. The frontend fix preserves the OAuth callback
query string while normalizing legacy routes.

### Deployment incident

During deployment, a parent-directory Vercel project link caused one frontend
archive to be sent to the backend project. The issue was detected immediately.
The canonical backend was restored from the backend release worktree, and the
frontend was then deployed from an isolated directory explicitly linked to
`frontend_static`. Final aliases and project ownership were re-verified.

## Environment Certification

Only presence and runtime behavior were inspected; no secret values are recorded.

| Configuration | Result |
|---|---|
| Production `DATABASE_URL` | VALID |
| `META_APP_ID` | VALID |
| `META_APP_SECRET` | VALID |
| VAPID public key | VALID |
| VAPID private key | VALID |
| VAPID claims/contact configuration | VALID as `VAPID_CLAIMS_EMAIL` |
| `CRON_SECRET` | VALID |
| Canonical frontend URL | VALID |
| Production environment mode | VALID |

`VAPID_CLAIMS_SUBJECT` is not the runtime key used by this codebase. The
dispatcher reads `VAPID_CLAIMS_EMAIL`, which is present.

The production database target was explicitly checked before migration. It was
confirmed to be the production Neon branch and not the approved recovery branch.
Connection details are intentionally omitted.

## Migration Certification

The approved additive V2 migration chain was applied in order:

1. Phase 1 reliability
2. Phase 2 organisation and permissions
3. Phase 3 business configuration
4. Phase 4 locations and meeting rooms
5. Phase 5 visits
6. Phase 6 gallery operations
7. Phase 7 channel partners
8. Phase 8 action items
9. Phase 9 pipeline engine
10. Phase 11 notification reliability

Results:

- First production migration application completed.
- Second application completed without further schema changes.
- Required schema and capability seeds were present.
- Migrations remained additive and idempotent.
- No historical Lead, Visit or Pipeline data was rewritten.
- Post-migration database connectivity is healthy.

## Production Health

| Check | Result | Observed latency |
|---|---|---:|
| Backend `/api/health` | HTTP 200 | 759 ms cold/warm mixed |
| Cron health | HTTP 200 | 296 ms |
| Frontend root | HTTP 200 | 278 ms |
| Tenant login route | HTTP 200 | 286 ms |
| Public push configuration | HTTP 200 | 307 ms |

The database had two observed connections: one active and one idle. Production
table sizes remain modest; the largest observed table was
`meta_campaign_snapshots` at approximately 17.9 MB.

## Scheduler Certification

Recurring task ownership is singular:

| Job | Authority | Schedule | State |
|---|---|---|---|
| Notification Drain, job `7720618` | cron-job.org | Every 2 minutes, Asia/Kolkata | Active |
| Reminder Processor, job `7720616` | cron-job.org | Every 5 minutes, Asia/Kolkata | Active |
| Meta Lead Poll, job `7889113` | cron-job.org | N/A | Inactive |
| Meta Report Sync, job `7889135` | cron-job.org | N/A | Inactive |
| Daily Meta report/source spend | Vercel | `29 18 * * *` (11:59 PM IST) | Configured |

Consecutive production executions were verified from backend logs:

| Worker | UTC executions | Result |
|---|---|---|
| Notification Drain | 06:02:02, 06:04:02, 06:06:02 | HTTP 200 |
| Reminder Processor | 05:55:03, 06:00:19, 06:05:03 | HTTP 200 |

Observed zero-work Notification Drain runs completed in 10-31 ms with bounded
batch size, no overlap, no retry storm and no remaining due events.

## Notification and PWA Certification

Production state:

- 2,593 notification events are marked sent.
- 55 historical events are skipped.
- No pending, failed or dead-letter notification events exist.
- 27 active push subscriptions exist: 17 iOS and 10 web.
- Public push configuration returns successfully.
- Authenticated browser registration called `/api/push/register` successfully.
- Bell history/delta requests return HTTP 200.
- Notification and reminder workers are executing successfully.

Static PWA contracts for service-worker registration, subscription creation,
push display, click handling and tenant deep links passed during V2-12.

Physical foreground/background delivery on both Android and iOS was not repeated
as part of this final automated pass. It remains a tenant UAT item, not the cause
of the current release block.

## Meta Certification

The Meta OAuth callback route and canonical frontend return were exercised
successfully. The wizard loaded accessible Pages and forms, and saving an
existing Page preserved its source record rather than creating a duplicate.

However, aggregate-only production diagnostics found:

| Source ID | Stored token | Page read | Forms read | Webhook subscription read | Result |
|---|---|---|---|---|---|
| 11 | Present | HTTP 401 | HTTP 401 | HTTP 401 | OAuth error 190 |
| 12 | Present | HTTP 401 | HTTP 401 | HTTP 401 | OAuth error 190 |
| 13 | Present | HTTP 401 | HTTP 401 | HTTP 401 | OAuth error 190 |
| 14 | Present | HTTP 401 | HTTP 401 | HTTP 401 | OAuth error 190 |

The sanitized Meta error category indicates an invalidated Facebook session.
The database still contains Page IDs, form mappings and source mappings, so the
business configuration has not been lost. The credentials themselves are not
currently usable.

Consequences:

- Live webhook delivery cannot be proven.
- Manual form refresh cannot be trusted.
- Controlled Meta test-lead delivery cannot be completed.
- Duplicate delivery protection was not re-exercised against a live delivery.
- Current Meta spend/report synchronization cannot retrieve fresh data.
- Source test timestamps that still show `pass` are stale for three sources and
  must not be treated as current token evidence.

Multiple independent Page reauthorization attempts are not an acceptable
release procedure because a later login may invalidate credentials saved by an
earlier login. The release requires one authorization session that refreshes
every existing authorized Page while preserving source and form mappings,
followed by direct Graph, webhook, form and test-lead validation.

## Browser and Workflow QA

Authenticated Admin navigation and production API traffic were verified for the
deployed tenant. The deployed UI exposes Dashboard, Leads, Reception, Channel
Partners, Pipeline, Allocation, Team, Projects, Imports, Exports, Activity Logs,
Reports, Lead Sources and Administration.

The complete V2-12 bounded regression evidence remains:

| Suite | Result |
|---|---|
| Backend bounded regression | 138 passed |
| Frontend contract suites | 13 passed |
| Phase 12 security contracts | 5 passed |
| Python compilation | 143 files, 0 failures |
| JavaScript syntax | 86 files, 0 failures |
| Duplicate route/method registrations | 0 |
| Secret-pattern scan | Passed |

The following live production operations were deliberately not performed after
Meta certification failed:

- Client-visible test Lead submission.
- Duplicate live webhook delivery.
- Broad manual Meta synchronization.
- Synthetic Visit, Channel Partner or Pipeline records.

This prevents client-facing noise and avoids representing partial evidence as a
successful end-to-end release.

## Performance Review

- Production database connections were low at the observation point.
- Notification workers are bounded and lightweight at zero work.
- Queue depth, failures and dead letters were zero.
- Interactive reporting uses bounded SQL aggregation.
- Large exports remain separate from interactive APIs.
- Production storage remains small.

Real tenant load, Neon monthly transfer and role-by-role endpoint latency still
require post-release monitoring under representative traffic.

## Remaining Defects

### Critical

1. All active Meta Page credentials fail with OAuth error `190`; real-time lead
   ingestion and Meta reporting cannot be certified.

### Major

1. A single-session, multi-Page credential refresh must be completed without
   duplicating sources or losing existing mappings.
2. After refresh, each Page must pass direct Page, forms and subscribed-app
   checks, followed by one test Lead and one duplicate delivery.
3. Physical Android/iOS push delivery and notification-click deep links require
   final tenant-device confirmation.
4. Authenticated role-by-role browser UAT remains required for non-Admin roles.

### Minor

1. Historical manual test harness and SQLAlchemy deprecation debt remains.
2. Legacy Vercel aliases remain attached and should be decommissioned only after
   a successful release window.
3. Nineteen reminder records remain `pending`, but eighteen already have their
   due notification marked sent; this is historical lifecycle cleanup rather
   than an active worker backlog.

## Rollback Position

Approved Neon rollback branch:
`pre-lms-v2-phase1-20260722`

Rollback deployment records:

- Backend: use the previous known-good canonical backend deployment.
- Frontend: use the previous known-good `frontend_static` deployment.

Rollback must be triggered for migration corruption, health failure,
authentication regression, tenant-isolation failure, sustained queue failure or
an unrecoverable ingestion regression. The current Meta credential failure is
external credential state; rolling back application code would not restore the
invalid tokens.

## Required Closure Sequence

1. Complete one Meta authorization that refreshes all four existing Pages.
2. Confirm all four source records retain their IDs and mappings.
3. Verify Page access, forms access and `subscribed_apps` for every source.
4. Run Refresh Forms and source Test for every source.
5. Submit one controlled Meta test Lead.
6. Replay the same delivery and prove exactly-once ingestion.
7. Confirm assignment, Pipeline entry, Action Item, notification and report
   update.
8. Complete role and device UAT.
9. Re-run this production sign-off and change status only on evidence.

## Final Status

**Production Blocked**

The software release candidate is deployed and operational, but the tenant
cannot be declared production-ready while its primary Meta lead-ingestion
credentials are invalid.
