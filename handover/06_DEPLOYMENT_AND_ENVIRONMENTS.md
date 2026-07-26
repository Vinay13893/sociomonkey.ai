# Deployment and Environments

Allowed status vocabulary in this file: `PRESENT`, `MISSING`, `VALID`, `INVALID`, `UNVERIFIABLE`.

## Projects and aliases

| Item | Value | Status |
|---|---|---|
| Canonical backend project | `backend` | VALID |
| Backend alias | `smk-backend-api.vercel.app` | PRESENT; resolves to `dpl_CGnUbbL6o58Gy821jdY6SVomaDNw` in project `backend`, Ready |
| Canonical frontend project | `frontend_static` | VALID |
| Frontend alias | `lms.sociomonkey.com` | PRESENT; resolves to `dpl_CKzUoFjbRqHAAjr1Wqx8f4QHup1H` in project `frontend_static`, Ready |
| Current frontend alias project | **RESOLVED.** Now correctly resolves to `frontend_static`, not `backend`. Re-verified independently at ~12:10 IST 25 July. | VALID |
| Known staging project | `backend-staging` | PRESENT; database isolation still UNVERIFIABLE (non-blocking for production) |
| Old/ambiguous | `kitchen-discovery-survey-app`, `backend-nu-nine-20.vercel.app`, `sociomonkey-ai.vercel.app`, `frontendstatic-nine.vercel.app`, legacy Railway URLs | PRESENT / use INVALID; decommission deferred until after a successful release window |

Commit parity for both canonical deployments is VERIFIED per
`../LMS_PRODUCTION_RELEASE_REPORT.md`: backend `f3e45924fab49dc394f8eb698e88e08d6aecf059`,
frontend `fb0b5d9c44b9e68e10dc7d3f968dc256d11606a1`.

## Backend variables

| Group | Names | Sensitive | Current validation |
|---|---|---:|---|
| Runtime/database | `APP_ENV`, `FLASK_ENV`, `DATABASE_URL`, `SECRET_KEY` | mixed/yes | VALID (presence + runtime behavior confirmed; values not read) |
| URLs/CORS | `FRONTEND_URL`, `CORS_ORIGINS` | no | VALID |
| Scheduler | `CRON_SECRET` | yes | VALID |
| Meta | `META_APP_ID`, `META_APP_SECRET`, `META_OAUTH_SCOPES`, `META_WEBHOOK_REQUIRE_SIGNATURE` | mixed/yes | VALID presence; stored Page tokens themselves are INVALID (OAuth error 190) — see [07_META_AND_LEAD_INGESTION.md](07_META_AND_LEAD_INGESTION.md) |
| Push | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`, `PUSH_MAX_ATTEMPTS` | mixed/yes | VALID |
| Email | `BREVO_*`, `RESEND_*`, `SMTP_*` | mostly yes | UNVERIFIABLE (not release-blocking) |
| Bootstrap | explicit `*_BOOTSTRAP_PASSWORD` and seed passwords | yes | VALID; no hard-coded fallback remains per Phase 12 security fix |

Frontend config: API base resolves through the canonical backend; public VAPID
configuration matches backend per release report. `env.js` is runtime/public
and does not contain private credentials.

`FRONTEND_URL` is confirmed present and VALID in the current backend
deployment's environment certification. CORS is restricted to canonical HTTPS
production origins per the Phase 12 security fix. VAPID public/private pair
and claims contact (`VAPID_CLAIMS_EMAIL`) match; note `VAPID_CLAIMS_SUBJECT` is
not the runtime key this codebase reads.

## Approved deployment shape

Backend-first, health checks, then frontend, followed by authenticated QA —
this order was followed for the completed deployment. One deployment incident
occurred and was corrected: a parent-directory Vercel project link initially
sent a frontend archive to the backend project; canonical backend was restored
from the backend release worktree, and frontend was redeployed from an
isolated directory explicitly linked to `frontend_static`. Final aliases and
project ownership were re-verified independently by this agent.

Health: `/api/health` (200), tenant login route `/ganga-realty` (200),
frontend root (200), public push configuration (200) — all re-verified.
Cross-role authenticated workflows beyond Admin remain outstanding (see
[10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md](10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md)).

Roll back by reassigning aliases to the last independently proven Ready
deployment; do not use Git reset. Approved Neon rollback branch:
`pre-lms-v2-phase1-20260722`. The current Meta credential failure is external
credential state — rolling back application code would not restore the
invalid tokens, so rollback is not an appropriate response to the Meta
blocker.
