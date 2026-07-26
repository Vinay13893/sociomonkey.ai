# Current Release State

Snapshot: 25 July 2026, approximately 11:00 IST (deployment/certification), independently
re-verified by the takeover agent at approximately 12:10 IST.

## Git release inputs — VERIFIED

| Item | Backend | Frontend |
|---|---|---|
| Path | `D:\AI\release_worktrees\backend-final-freeze` | `D:\AI\release_worktrees\frontend-final-freeze` |
| Repository | `Vinay13893/sociomonkey.ai` | same |
| Branch | `implementation/lms-v2-phase0-1-20260722` | same |
| Deployed commit | `f3e45924fab49dc394f8eb698e88e08d6aecf059` | `fb0b5d9c44b9e68e10dc7d3f968dc256d11606a1` |
| Current worktree HEAD | `a50c6951861c054523004cd4a5955fac7f4530ed` (release report commit, on top of `f3e4592`) | `fb0b5d9c44b9e68e10dc7d3f968dc256d11606a1` (unchanged) |
| Upstream | none configured | none configured |
| Remote | `origin` = `https://github.com/Vinay13893/sociomonkey.ai.git` | same |
| Working tree | clean except untracked `handover/` | clean |
| Present on any remote branch (`git fetch` + `branch -r --contains`) | **No** — verified 25 July ~12:10 IST | **No** — verified 25 July ~12:10 IST |

Remote has no branch named `implementation/lms-v2-phase0-1-20260722`; only
`main`, `master`, `aseem/platform-lms-work` and
`frontend-static-recovery-baseline` exist on `origin`. Production was deployed
from local worktree source, not from a pushed branch. See
[10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md](10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md)
for the push-target decision this requires.

## Live Vercel evidence — VERIFIED, anomaly resolved

Re-verified independently by the takeover agent via `vercel inspect` at ~12:10 IST:

- `GET https://smk-backend-api.vercel.app/api/health` → HTTP 200.
- `HEAD https://lms.sociomonkey.com` → HTTP 200.
- `GET https://lms.sociomonkey.com/ganga-realty` (tenant login route) → HTTP 200.
- Backend alias `smk-backend-api.vercel.app` → deployment `dpl_CGnUbbL6o58Gy821jdY6SVomaDNw`, project `backend`, Ready, created 25 July 2026 10:50:50 IST.
- Frontend alias `lms.sociomonkey.com` → deployment `dpl_CKzUoFjbRqHAAjr1Wqx8f4QHup1H`, project `frontend_static` (correct project — the earlier `backend`-named mismatch is gone), Ready, created 25 July 2026 11:02:54 IST.
- The frontend deployment was produced by redeploying from an isolated directory explicitly linked to `frontend_static`, per the incident note in `../LMS_PRODUCTION_RELEASE_REPORT.md`.

## Required state matrix

| Question | State and evidence |
|---|---|
| What is definitely deployed? | **VERIFIED:** both canonical aliases point to Ready deployments in their correct respective projects (`backend`, `frontend_static`). |
| Current backend deployment | `dpl_CGnUbbL6o58Gy821jdY6SVomaDNw`, Ready, commit `f3e45924fab49dc394f8eb698e88e08d6aecf059`. |
| Current frontend deployment | `dpl_CKzUoFjbRqHAAjr1Wqx8f4QHup1H`, Ready, project `frontend_static`, commit `fb0b5d9c44b9e68e10dc7d3f968dc256d11606a1`. |
| Production aliases | Backend: `smk-backend-api.vercel.app`; frontend: `lms.sociomonkey.com`. Both correctly owned. Legacy aliases remain attached (decommission deferred, non-blocking). |
| Production commit hashes | **VERIFIED** per `LMS_PRODUCTION_RELEASE_REPORT.md` and matching worktree history. |
| Production migrations applied | **VERIFIED.** Additive V2 chain (Phase 1–9, 11) applied to canonical production database; second apply produced no further schema changes. |
| `FRONTEND_URL` corrected | **VERIFIED present/VALID** per environment certification in the release report; exact value not read (sensitive). |
| Meta OAuth reauthorized | **NOT DONE.** All four sources still return Graph `error 190 / subcode 460` as of this agent's independent re-check. This is the sole critical blocker. |
| Cron jobs / scheduler authority | **VERIFIED single-authority** per release report: Notification Drain (job `7720618`, 2 min) and Reminder Processor (job `7720616`, 5 min) active on cron-job.org; Meta Lead Poll (`7889113`) and Meta Report Sync (`7889135`) inactive; daily spend sync owned solely by Vercel. Live cron-job.org dashboard re-inspection needs browser access this agent does not have. |
| Authenticated smoke testing ran | Authenticated Admin navigation and production API traffic verified per release report. Non-Admin role QA and physical Android/iOS PWA push remain outstanding. |

## Update — 25 July, ~15:30 IST (post-takeover session)

A real bug was found and fixed: `/api/ingestion/meta/<token>` only accepted
`POST`, but Meta's Webhooks product sends its `GET` verification challenge to
the same registered Callback URL used for delivery — so the app-level webhook
subscription could never be saved (`405`), and webhook delivery had likely
been silent since 22 July for this reason, independent of the OAuth issue.
Fixed, tested (139/141 relevant tests pass; the 2 failures are a pre-existing
unrelated harness misdetection), and deployed as commit `417889d` to
`dpl_DJ9HgwTCGDtuyRJ4xE21z6V8n5A6`. Verified end-to-end: the app-level webhook
subscription now saves successfully, `leadgen` field is subscribed, and one
real test lead sent via Meta's own Lead Ads Testing Tool was received,
signature-validated, correctly routed by `page_id`, and logged with a correct
correlation ID (`ingested_lead_logs` id 4442).

That test lead still failed with `Lead payload missing name or contact
method` — expected, because Meta's webhook payload only carries IDs, and
fetching the full lead detail requires a valid Page token, which is still
dead. Two clean reconnect attempts during this session each produced a token
that worked for a moment then died again within minutes with the identical
`190/460` error; account compromise was ruled out (owner confirmed only their
own devices show active sessions). Continuing to retry immediately has not
helped and risks resetting whatever cooldown timer may be running — recommend
waiting several hours before the next attempt.

Also found and corrected: `LMS - Meta Lead Poll` and `LMS - Meta Report Sync`
were live on cron-job.org running every 5 minutes, contradicting the release
report's certification that both were inactive. Both were disabled by the
owner this session. Notification Drain and Reminder Processor were directly
observed healthy on the correct cadence.

## Release decision

**PRODUCTION BLOCKED — Meta only, narrower than before.** Deployment,
migration, scheduler and notification/reminder infrastructure are certified
healthy. The webhook delivery mechanism itself is now fixed and proven
working end-to-end. The only remaining blocker is the OAuth/Page access
token validity, which is an external Meta-side session issue, not an
application defect. Do not perform further Meta reauthorization attempts in
quick succession — wait a meaningful period, then retry once. Do not mark the
release successful until a real lead with full field data (name, phone, or
email) has been ingested end-to-end.
