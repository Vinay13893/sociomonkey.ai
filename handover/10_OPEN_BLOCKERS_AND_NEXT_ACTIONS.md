# Open Blockers and Next Actions

Superseded: the deployment-state, migration-state, `FRONTEND_URL`/redeploy,
scheduler-duplicate and two-consecutive-worker-run blockers listed in the
prior version of this file are **RESOLVED** — see
[03_CURRENT_RELEASE_STATE.md](03_CURRENT_RELEASE_STATE.md) and
[08_SCHEDULERS_AND_NOTIFICATIONS.md](08_SCHEDULERS_AND_NOTIFICATIONS.md) for
the verifying evidence. Updated again 25 July ~15:30 IST: the webhook
delivery mechanism bug is now also fixed and proven end-to-end (see
[07_META_AND_LEAD_INGESTION.md](07_META_AND_LEAD_INGESTION.md)); the
cron-job.org duplicate-job drift found mid-session is corrected. This file
lists only what remains open.

| Class | Blocker | Evidence / risk | Exact next action and access | Stop / success |
|---|---|---|---|---|
| Critical | Meta OAuth error 190 | All four source tokens (11, 12, 13, 14) re-confirmed invalid twice more this session, immediately after two clean full reconnects; account compromise ruled out; likely a Meta-side post-password-change cooldown | Wait several hours (not immediate retry), then one owner-authenticated in-place reauthorization session covering all four Pages | Stop on duplicate/wrong source or lost mapping; succeed with existing source IDs preserved, Graph checks returning 200, AND a real test lead capturing full name/phone data |
| Resolved this session | Webhook delivery mechanism | `/api/ingestion/meta/<token>` rejected Meta's GET verification challenge (405), so the app-level webhook subscription could never be saved | Fixed in commit `417889d`, deployed, verified end-to-end with a real test lead reaching `ingested_lead_logs` with correct routing/correlation | Done — no further action |
| Major | Meta test-Lead full-data certification | Test lead now reaches ingestion successfully but fails with "missing name or contact method" because enrichment needs the still-dead Page token | After the OAuth fix above: redeliver a test lead, confirm full field data captured, redeliver same event, prove exactly-once ingestion | Stop on mapping/history change; succeed end-to-end with one Lead containing real name/phone and proven dedup |
| Major | Meta spend/manual sync | Cannot retrieve fresh data while tokens are invalid | After reauth: Refresh Forms + Manual Meta Sync per source | Stop on duplicate source creation; succeed with existing mappings intact |
| Major | Non-Admin authenticated browser QA | Only Admin navigation was covered by the release report | Manager, Caller, RM, Reception, Platform Owner browser QA with internal data | Stop on cross-tenant/permission/5xx; succeed checklist |
| Major | Android push | Not certified against the current (25 July) deployment | Installed PWA controlled notification | Stop if wrong user/data; succeed receipt/deep link |
| Major | iOS push | Not certified against the current (25 July) deployment | Installed PWA controlled notification | Same |
| Major | Production performance | No representative-load baseline yet | Read-only latency, errors, queue age, compute/transfer/storage/connections under real traffic | Stop on degradation; succeed within approved budgets |
| Major | Source-control remote parity | Neither backend (`a50c695`/`f3e4592`) nor frontend (`fb0b5d9`) commits exist on any remote branch; `implementation/lms-v2-phase0-1-20260722` has no remote counterpart | Owner decides target branch (new remote branch of the same name vs. an existing branch); then push only that decision, no force-push, no history rewrite | **Stop — ambiguous, requires one precise owner decision before any push** |
| Environment limitation | No browser automation tool available to the current takeover agent | Meta reauth, cron-job.org dashboard inspection, and browser QA all need an authenticated interactive session | Owner drives the browser directly, following step-by-step instructions from this agent; agent verifies each result afterward via API/DB reads | Not a blocker to fix — a standing constraint of this session to route around |
| External owner action | Meta/cron-job.org dashboard/device access | Authenticated owner surfaces required | Owner opens sessions directly (no browser tool available to hand off to) | Never request secrets in chat |
| Verification only | Final report update | `LMS_PRODUCTION_RELEASE_REPORT.md` exists and is current through deployment/migration/scheduler; Meta section still reflects the open blocker | Update after Meta certification completes | Do not label release successful with Meta still failing |
| Minor | Legacy aliases/files | Cleanup could break callbacks | Inventory only; defer cleanup until after a successful release window | Success is documented dependency, not deletion |
| Minor | Legacy `app/models.py`, manual Flask harnesses | Inherited technical debt, non-blocking | Defer to a separately tested cleanup phase | No change in this release |

## Ordered execution plan (remaining)

1. Owner decides the push target for the three unpushed commits (see the
   Source-control row above); push only that decision.
2. Owner performs one Meta authorization session covering all four Pages,
   guided step-by-step by this agent; agent verifies via Graph API/DB reads
   after each step, never printing tokens.
3. Send one controlled test Lead; verify exactly-once ingestion, assignment,
   Pipeline entry, Action Item, notification, report update, and Activity Log
   via DB/API reads.
4. Validate Refresh Forms, Manual Meta Sync and daily spend sync.
5. Owner (or a session with browser tooling) completes non-Admin role QA and
   Android/iOS PWA push certification.
6. Owner independently confirms cron-job.org dashboard state if stricter
   certification than backend-log evidence is required.
7. Update `LMS_PRODUCTION_RELEASE_REPORT.md`, `LMS_MASTER_IMPLEMENTATION_ROADMAP.md`,
   `LMS_RELEASE_CHECKLIST.md` and this handover package with final evidence.
8. Classify the release as exactly one of: Production Ready / Production Ready
   with Minor Issues / Production Blocked. Do not mark successful while Meta
   ingestion is uncertified.
