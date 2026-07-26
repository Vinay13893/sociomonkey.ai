# Test and Validation Evidence

## Proven for the frozen release candidate

Phase 12 documentation records:

| Evidence | Result |
|---|---|
| Backend bounded regression | 138 passed |
| Frontend contract suites | 13 passed |
| Backend release-security contract | 5 passed |
| Python compilation | passed |
| JavaScript syntax | passed |
| Route duplication | 306 unique route/method contracts; no duplicates |
| Migration rehearsal | guard, apply twice, check and rollback-only workflow passed on recovery |
| Tenant isolation | contract/integration coverage passed across phases |
| Permission validation | capability/team-scope tests passed |
| Secret scan | runtime/test source passed |
| Worktrees before handover | both clean; no untracked files |

Phase 11 additionally records queue retry/dead-letter, immutable attempts, stale-claim recovery, cross-tenant denial, replay/archive permissions and zero synthetic recovery rows. Phase 10 records bounded analytics and independent view/export enforcement.

## Proven against the deployed production release (25 July, post-deployment)

Per `../LMS_PRODUCTION_RELEASE_REPORT.md` and independently re-verified by the
takeover agent where noted:

- Exact commit/artifact behind both production deployments — **VERIFIED** (backend `f3e4592`, frontend `fb0b5d9`).
- Correct frontend project/alias topology — **VERIFIED, re-checked independently** (`lms.sociomonkey.com` → `frontend_static`).
- Production migration state — **VERIFIED** (additive chain applied twice, second run made no further changes).
- `FRONTEND_URL`, CORS, VAPID, Meta app ID/secret, `CRON_SECRET` presence — **VERIFIED**.
- Scheduler ownership and consecutive successful runs — **VERIFIED** (see [08_SCHEDULERS_AND_NOTIFICATIONS.md](08_SCHEDULERS_AND_NOTIFICATIONS.md)); notification queue independently re-checked via DB: 0 pending/failed/dead-letter.
- Authenticated Admin browser navigation and production API traffic — **VERIFIED** per release report.

## Not yet proven

- Meta OAuth/webhook/form delivery — all four sources fail Graph validation (`190`/`460`), independently re-confirmed by the takeover agent. **This is the sole critical blocker.**
- Authenticated Manager/Caller/RM/Reception/Platform Owner QA against current deployments — Admin only was covered.
- Current Android/iOS installed-PWA push against the current deployment (historical 16 July success is stale evidence).
- Production-scale performance/Neon capacity under representative tenant load.
- cron-job.org dashboard itself has not been independently inspected by the current agent (no browser tool); backend-log evidence of successful runs is strong indirect proof but not a dashboard screenshot.
- Backend pytest in the current shell: default Python 3.14 reports `No module named pytest`; the 138-pass regression result is Phase 12 evidence, not re-run post-deployment. Recreate the approved Python 3.11 test environment before rerunning if fresh regression evidence is required.

## Must be retested once Meta is certified

Lead ingestion/dedup/assignment via live Meta webhook; Pipeline/Action
generation from a real Lead; non-Admin role navigation/capabilities; Android
and iOS PWA push; latency/error/queue/Neon metrics under real traffic.

## Exclusions and limitations

`test_login.py` is a manual localhost harness and is excluded from bounded
pytest. External authenticated Vercel/Neon/Meta/cron evidence is not
substituted with repository assertions. The current takeover agent has no
browser automation tool; any remaining browser-dependent verification requires
either the owner's authenticated session or a future session with browser
tooling.
