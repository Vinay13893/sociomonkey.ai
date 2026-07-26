# Sociomonkey LMS Production Release Handover

Generated 25 July 2026 (Asia/Kolkata). Refreshed 25 July 2026 ~12:15 IST after
production deployment and certification completed. This package lets Claude
Code continue the controlled release without prior chat context.

## Current status

**STATUS: PRODUCTION DEPLOYED / BLOCKED ON META ONLY.** The V2 release
candidate is deployed to both canonical Vercel aliases, the additive migration
chain is applied to the canonical production database, and core health,
notification and reminder workers are certified healthy. The earlier
`NO-GO — production reconstruction required` status and the alias/project
mismatch it described (`lms.sociomonkey.com` resolving to a deployment named
`backend`) are **resolved and superseded**. Do not use that earlier status as
current truth; it is retained in file history only for traceability.

The sole remaining release-blocking gate is Meta: all four production Meta
Page sources fail Graph API validation with OAuth error `190` / subcode `460`
(invalidated session). See [10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md](10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md).

Authoritative worktrees:

- Backend: `D:\AI\release_worktrees\backend-final-freeze` (HEAD `a50c695`, only untracked `handover/`)
- Frontend: `D:\AI\release_worktrees\frontend-final-freeze` (HEAD `fb0b5d9`, clean)

Authoritative evidence, in order of precedence:

1. Current live production evidence (Vercel/Neon/Graph reads)
2. `../LMS_PRODUCTION_RELEASE_REPORT.md`
3. Current Git history and deployment metadata
4. `../LMS_PHASE12_RESULTS.md` and other Phase results
5. This handover package

Do **not** work from `D:\AI`; it has parent Vercel state and unrelated/legacy
trees. Do **not** expose credentials, tokens, cookies, authorization headers,
database URLs, or decrypted environment values. Do **not** assume any
outstanding item completed because an earlier agent intended or started it —
re-verify against live evidence.

## Known limitation for the current takeover agent

No browser automation tool (Playwright/Puppeteer/computer-use) is available in
this Claude Code session. Read-only Vercel/Neon/Graph API checks, git
operations and file edits proceed normally. Interactive Meta OAuth
reauthorization, cron-job.org dashboard inspection, and authenticated browser
QA require a human (or a session with browser tooling) to drive the click
path; this agent can only verify results afterward via API/DB reads and give
step-by-step guidance.

## Read in this order

1. [03_CURRENT_RELEASE_STATE.md](03_CURRENT_RELEASE_STATE.md)
2. [10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md](10_OPEN_BLOCKERS_AND_NEXT_ACTIONS.md)
3. [01_PRODUCT_AND_ARCHITECTURE.md](01_PRODUCT_AND_ARCHITECTURE.md)
4. [02_PHASE_HISTORY.md](02_PHASE_HISTORY.md)
5. [04_REPOSITORY_MAP.md](04_REPOSITORY_MAP.md)
6. [05_DATABASE_AND_MIGRATIONS.md](05_DATABASE_AND_MIGRATIONS.md)
7. [06_DEPLOYMENT_AND_ENVIRONMENTS.md](06_DEPLOYMENT_AND_ENVIRONMENTS.md)
8. [07_META_AND_LEAD_INGESTION.md](07_META_AND_LEAD_INGESTION.md)
9. [08_SCHEDULERS_AND_NOTIFICATIONS.md](08_SCHEDULERS_AND_NOTIFICATIONS.md)
10. [09_TEST_AND_VALIDATION_EVIDENCE.md](09_TEST_AND_VALIDATION_EVIDENCE.md)
11. [12_COMMAND_REFERENCE.md](12_COMMAND_REFERENCE.md)
12. [13_FILE_INDEX.md](13_FILE_INDEX.md)
13. [11_CLAUDE_CODE_TAKEOVER_PROMPT.md](11_CLAUDE_CODE_TAKEOVER_PROMPT.md)

The next action is a single owner-authenticated Meta authorization session
that refreshes all four existing Pages without duplicating sources, followed
by direct Graph/webhook/form validation and one controlled test Lead. See
[07_META_AND_LEAD_INGESTION.md](07_META_AND_LEAD_INGESTION.md) for the exact
preserved-identity requirements.

Production state must be proven independently before any further write.
Pause if a target, project, database branch, credential scope, scheduler
owner, or rollback target cannot be proven, or if source-control branch
ownership for pushing the release commits remotely is ambiguous.

> Deployment is done. Remaining work is Meta reauthorization and certification,
> then final role/device QA. Do not repeat migration or deployment steps
> unless live evidence contradicts this file.
