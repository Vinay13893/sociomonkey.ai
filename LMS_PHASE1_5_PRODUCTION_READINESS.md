# LMS Phase 1.5 Production Readiness

Date: 23 July 2026  
Business timezone: Asia/Kolkata (IST)  
Assessment status: **NOT READY**

## Scope

This is a read-only production-readiness assessment. No production database
schema, Vercel deployment, alias, environment variable, scheduler, webhook, or
external service was changed.

## Deployment Targets

| Component | Canonical project | Production target | Current deployment | Canonical alias | Source |
|---|---|---|---|---|---|
| Backend | `backend` (`prj_sDFBth4N54neEa7PVHxUITQImtFR`) | Vercel production | `dpl_4v1mZApihPA6zMhKZZFN8MAuBM8A` | `smk-backend-api.vercel.app` | Manual deployment; project is not Git-linked |
| Frontend | `frontend_static` (`prj_A6b6jLRXwpf5axKz1MNEqpr9j0Vl`) | Vercel production | `dpl_5NDixiRyttiNP7ADNquyvB1RekCN` | `lms.sociomonkey.com` | GitHub `Vinay13893/sociomonkey.ai`, production branch `main` |

The backend must be deployed from an explicitly linked clean directory. The
repository worktree must never inherit the frontend project's `.vercel`
configuration.

A legacy failed deployment in project `kitchen-discovery-survey-app` retains
historical alias metadata for `smk-backend-api.vercel.app`. The live alias is
currently attached to the canonical backend deployment, but this legacy project
must not be used for LMS deployment.

## Environment Verification

Vercel marks these values sensitive, so plaintext validation was neither
possible nor attempted.

| Requirement | Production metadata | Runtime/code finding | Classification |
|---|---|---|---|
| `META_APP_SECRET` | Exists, sensitive, production | Read by Phase 1 webhook signature validation | Exists; value not directly verifiable |
| `META_APP_ID` | Exists, sensitive, production | Used by Meta integration | Exists; value not directly verifiable |
| Meta Page/User access tokens | Stored per source in Neon | All active-source tokens fail Graph validation | **Invalid** |
| `VAPID_PUBLIC_KEY` | Exists, sensitive, production | Read by push dispatcher | Exists; operationally indicated |
| `VAPID_PRIVATE_KEY` | Exists, sensitive, production | Read by push dispatcher | Exists; operationally indicated |
| `VAPID_CLAIMS_EMAIL` | Exists, sensitive, production | This is the variable current code reads | Exists |
| `VAPID_CLAIMS_SUBJECT` | Missing | Current code does not read this name | Naming mismatch, not a runtime blocker |
| `CRON_SECRET` | Exists, sensitive, production | Read by internal/cron route authentication | Exists; scheduler match not directly verified |
| `DATABASE_URL` | Exists, sensitive, production | Health endpoint and recovery snapshot prove PostgreSQL access | Exists and operationally indicated |
| `APP_ENV` | Exists, sensitive, production | Required for production guardrails | Exists |
| `FLASK_ENV` | Exists, sensitive, production | Runtime profile | Exists |
| Push/worker feature flags | Not configured | Current implementation has no required feature flag | Not required by current code |
| Webhook verification tokens | Present for all five active sources | Stored per-source in Neon | Exists |

## Meta Integration

Recovery snapshot evidence:

- Four active Meta sources exist.
- All four report healthy stored permission status.
- All four have source-specific webhook tokens and credential records.
- Ingestion logs contain 2,008 processed, 125 duplicate, and 10 error events.
- Latest processed event in the snapshot: 22 July 2026 03:20:15 UTC.
- Raw webhook persistence and idempotency are implemented in Phase 1.

Direct read-only Graph validation on 23 July 2026:

- Every stored `user_token`, `page_access_token`, and fallback `access_token`
  for the four active sources failed.
- Graph response category: HTTP 400, OAuth error code `190`, subcode `460`.
- Page subscription state could not be read because authentication failed.
- Active webhook registration therefore cannot be fully certified.

**Release blocker:** reconnect/reauthorize the four Meta sources and then verify
both the app `leadgen` subscription and each Page's subscribed-app state.

## Notification and Reminder Infrastructure

Recovery snapshot:

| Process | State | Evidence |
|---|---|---|
| Notification delivery | Operational historically | 2,593 sent events; latest 22 July 2026 |
| Skipped delivery | Visible | 55 skipped events; Phase 1 adds retry/dead-letter diagnostics |
| Push subscriptions | Available | 27 active, 1 inactive |
| Callback reminders | Backlog requires review | 19 pending; 18 were already due at snapshot time |
| Queue claiming | Hardened in Phase 1 | Conditional claims and stale-claim recovery |
| Manual retry | Added in Phase 1 | Tenant-scoped admin route |
| Diagnostics | Added in Phase 1 | Tenant-scoped aggregate routes |

The VAPID pair is operationally indicated by prior successful pushes and sent
delivery records. Exact key-pair equality cannot be proven from sensitive
metadata alone and must be reconfirmed by a controlled push smoke test.

## Scheduler Inventory

| Owner | Job | Frequency | Trigger | Dependency | Required now | Direction |
|---|---|---:|---|---|---|---|
| Vercel | Meta report/source-spend sync | `29 18 * * *` (23:59 IST) | `/api/cron/meta-report-sync` | Meta credentials, Neon | Yes | Daily schedule remains appropriate |
| cron-job.org | Notification drain | Target every 2 minutes | `/api/cron/drain-notifications` | `CRON_SECRET`, VAPID, Neon | Yes | Replace with managed queue worker later |
| cron-job.org | Reminder processor | Target every 5 minutes | `/api/internal/reminders/process` | `CRON_SECRET`, Neon | Yes | Event scheduling/managed delayed queue later |
| cron-job.org | Meta Lead Poll | Inactive | Legacy polling route | Meta credentials | No | Keep inactive; webhooks are canonical |
| cron-job.org | Meta Report Sync | Inactive | Duplicate report route | Meta credentials, Neon | No | Keep inactive; Vercel owns daily run |

Current cron-job.org headers, enabled states, and latest executions could not be
retrieved because no API credential or connected browser session was available.
This is a release blocker because matching `CRON_SECRET` and successful current
runs cannot be certified from repository state.

## Deployment Dry Run

1. Freeze inbound tenant use and record the production database timestamp.
2. Confirm the Neon recovery branch remains healthy.
3. Reauthorize all four Meta sources and verify `leadgen` subscriptions.
4. Verify cron-job.org notification and reminder jobs, including masked
   authorization format and two consecutive successful runs.
5. Apply `migrations/phase1_reliability_20260722.py` to production using the
   exact production host guard.
6. Run migration `--check`; require no missing columns or indexes.
7. Deploy backend commit `aa62a9a807758c2b6182641612d8e39b8436f1b6` explicitly
   to Vercel project `backend`.
8. Verify health, unauthenticated worker rejection, and diagnostics.
9. Run controlled ingestion, duplicate, reprocessing, assignment, reminder, and
   push tests.
10. Deploy frontend only if a frontend change is included in the release.
11. Restore tenant access only after every success criterion passes.

### Migration Characteristics

- Additive only: nine columns and five indexes.
- Recovery-branch execution was idempotent.
- Tables contain only thousands of rows in the snapshot.
- Expected execution: under 30 seconds including connection startup.
- `ALTER TABLE` obtains brief table locks.
- Non-concurrent index creation can block writes briefly; perform during the
  existing tenant outage.
- No row rewrite is expected for nullable columns. `attempt_count` uses a
  constant default supported efficiently by current PostgreSQL.

## Smoke-Test Sequence

1. Backend and frontend return HTTP 200.
2. Existing admin, manager, and team-member login succeeds.
3. Existing lead, assignment, Action Board, Pipeline, import, and export views
   remain intact.
4. Send one controlled Meta test lead.
5. Confirm raw ingestion event, processed state, lead creation, and assignment.
6. Redeliver the same provider event; confirm no second lead.
7. Force one controlled ingestion error and reprocess it once.
8. Confirm assignment creates in-app and push delivery records.
9. Confirm notification drain sends the push and marks the event sent.
10. Schedule one callback; verify warning/due notification exactly once.
11. Verify failed push is visible and manually retryable.
12. Confirm tenant-scoped diagnostics reveal no cross-tenant data.

### Success Criteria

- No migration error or missing schema element.
- No 5xx response in health or controlled workflows.
- One provider ID creates at most one lead.
- Failed ingestion remains durably reprocessable.
- Assignment and callback notifications appear in-app and on the test PWA.
- Notification/reminder workers complete two consecutive scheduled runs.
- Existing LMS counts and workflows remain unchanged.

### Failure and Rollback Triggers

- Migration validation failure.
- Login, lead visibility, assignment, Action Board, or Pipeline regression.
- Meta webhook 4xx/5xx or missing durable ingestion event.
- Duplicate provider delivery creates a second lead.
- Worker authentication or repeated delivery failure.
- Cross-tenant visibility.
- Unexpected database error or elevated latency.

## Rollback Procedure

### Preferred Application Rollback

The migration is additive and backward-compatible. If application validation
fails:

1. Keep tenant access disabled.
2. Reassign `smk-backend-api.vercel.app` to backend deployment
   `dpl_4v1mZApihPA6zMhKZZFN8MAuBM8A`.
3. If frontend changed, reassign `lms.sociomonkey.com` to
   `dpl_5NDixiRyttiNP7ADNquyvB1RekCN`.
4. Leave additive database columns in place.
5. Verify health and the previous application smoke tests.

### Full Database Rollback

Use only for proven data corruption, not ordinary code failure:

1. Keep tenant access and all workers disabled.
2. Record the production failure timestamp and retain the failed database state.
3. Point a controlled backend deployment at Neon branch
   `pre-lms-v2-phase1-20260722` and validate it before alias movement.
4. Restore/promote from that branch using Neon's supported branch restore
   workflow only after owner approval.
5. Reattach the previous backend deployment and execute complete smoke tests.

Because a database snapshot discards writes made after its creation, full
rollback is appropriate only while the tenant remains offline or after explicit
reconciliation of post-snapshot writes.

## Final Recommendation

**NOT READY**

Reasons:

1. All active Meta source tokens are invalid (OAuth `190/460`).
2. Current cron-job.org job headers and latest executions could not be directly
   certified without read-only owner/API access.
3. Phase 1 has not yet been applied or smoke-tested on production.

Phase 2 development may proceed independently on the implementation branch and
recovery database, but no production deployment should occur until these gates
are cleared.
