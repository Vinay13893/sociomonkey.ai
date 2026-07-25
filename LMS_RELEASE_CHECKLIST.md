# LMS V2 Release Checklist

Updated 25 July 2026 ~16:00 IST. Production deployment already occurred (see
`LMS_PRODUCTION_RELEASE_REPORT.md`) directly rather than via a separate
staging environment step; this checklist is annotated against actual
production state rather than the originally planned staging sequence.

## Release Candidate

- [x] V2-0 through V2-11 implementation approved.
- [x] Phase 12 security blockers corrected locally.
- [x] Backend and frontend regression suites pass.
- [x] Complete migration chain rehearsed twice on the recovery branch.
- [x] Rollback-only database workflow leaves no synthetic data.
- [x] Secret-pattern scan passes.
- [ ] Confirm staging database is isolated from production. N/A — staging was
      bypassed; production deployed directly.
- [x] Backend/frontend release commits recorded: backend `417889d`
      (includes post-release webhook fix on top of `f3e4592`), frontend
      `fb0b5d9`. Not yet pushed to any remote branch — owner decision pending.

## Production Certification (in place of Staging Certification)

- [x] Backend deployed to canonical `backend` project (`dpl_DJ9HgwTCGDtuyRJ4xE21z6V8n5A6`).
- [x] Migrations applied in rehearsed order; second apply produced no further changes.
- [x] Frontend deployed to canonical `frontend_static` project (`dpl_CKzUoFjbRqHAAjr1Wqx8f4QHup1H`).
- [x] Authenticated Admin desktop QA run. Manager/Caller/RM/Reception/Platform
      Owner QA **not yet run**.
- [ ] Validate Meta OAuth, webhook signature and one controlled lead.
      Webhook signature/delivery mechanism **fixed and proven** (25 July);
      OAuth token validity still failing (`190/460`), blocking full-data lead
      capture.
- [x] Validate notification drain and reminder processor: confirmed healthy,
      correct 2-min/5-min cadence, directly observed in cron-job.org console.
- [ ] Validate Android and iOS push and deep links against current deployment.
- [x] Measure endpoint budgets, DB connections and Neon usage: DB 40 MB total,
      2 connections (1 active/1 idle), endpoint latency 200-460ms across
      health/leads/lead-sources/frontend routes, notification queue 0
      pending/failed/dead-letter.
- [ ] Obtain tenant UAT sign-off.

## Production Gate

- [x] Production branch/deployment IDs recorded above. Neon rollback branch:
      `pre-lms-v2-phase1-20260722`.
- [x] Confirm production environment variable presence and owner validation
      (per `LMS_PRODUCTION_RELEASE_REPORT.md` environment certification).
- [x] Confirm only approved schedulers are enabled: `LMS - Meta Lead Poll` and
      `LMS - Meta Report Sync` were found incorrectly active (every 5 min) on
      25 July and disabled by the owner; Notification Drain, Reminder
      Processor and Vercel daily spend sync confirmed as the only active
      schedulers.
- [x] Maintenance window / rollback authority: rollback deployment IDs
      recorded; live tenant access was not suspended during this session's
      changes (webhook fix and cron correction were low-risk, backwards
      compatible).
- [x] Migrations, backend, frontend already applied/deployed in that order.
- [x] Smoke tests: health, tenant login, manifest/service-worker, notification
      queue all re-verified healthy this session.
- [ ] Monitor at 1 hour, 24 hours, 7 days and 14 days — monitoring window has
      not yet elapsed; Meta certification remains the blocking item before
      starting the formal post-deployment monitoring clock.
