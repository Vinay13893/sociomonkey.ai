# Meta and Lead Ingestion

## Architecture

Tenant Lead Sources contain Page identity, credentials, webhook verification state, forms and field mappings. Signed webhooks and manual sync enter the durable ingestion engine, which persists raw events, deduplicates provider identities, resolves mappings, creates/updates the Lead under existing-source identity, assigns according to rules, creates Pipeline history/Actions, and emits correlated NotificationEvents.

Page Sources and mappings are existing records. `Refresh Forms` updates forms inside an existing source; it must not create a replacement source. Manual sync is a controlled recovery path, not a substitute scheduler. Duplicate provider delivery is protected by ingestion idempotency and must create at most one Lead. Reports consume results but do not own ingestion.

## Current state

- **VERIFIED (DB read):** four active Meta Page sources exist — IDs 11, 12, 13, 14 — with historical forms/mappings intact (12, 1, 6, 6 forms respectively).
- **VERIFIED (Deployed):** backend `f3e4592` (preserves source identity on reauthorization) and frontend `fb0b5d9` (preserves OAuth callback session during route normalization) are both live in the current production deployment.
- **VERIFIED (live Graph API re-check by takeover agent, post-deployment):** all four sources still return `HTTP 401`, `code 190`, `subcode 460` on direct Page read. Stored Page IDs and tokens remain present in the database; only the tokens themselves are invalid (invalidated Facebook session, not data loss).
- Source 13's `last_test_result` shows `pass` from 25 July 05:53 UTC — this is stale relative to the current 401 evidence and must not be treated as current token evidence.
- Source 14 already shows `permission_status: error` / `last_test_result: fail`.
- Interactive OAuth restart/completion, Page subscribed-app state, webhook signature delivery and one controlled test Lead: **NOT YET DONE.** This is the sole critical release blocker.

## Owner-authenticated browser work still required

The current takeover agent has no browser automation tool and cannot drive
this itself. It can verify each result afterward via the Graph API and direct
database reads without ever printing a token. Steps, to be performed by the
owner in their own authenticated session:

1. Confirm current production frontend/backend artifacts first (already done — see [03_CURRENT_RELEASE_STATE.md](03_CURRENT_RELEASE_STATE.md)).
2. Sign in to the correct tenant (`ganga-realty`) and the Meta business owner account.
3. Reauthorize each existing source (11, 12, 13, 14) in place through the existing LMS OAuth wizard; do not add duplicates.
4. Confirm Page selection, existing mappings and historical Lead counts remain unchanged for each source.
5. Refresh forms within each existing source; confirm form counts stay at or above the current known counts (12, 1, 6, 6).
6. Verify app `leadgen` and Page subscribed-app state for each Page.
7. Send one controlled test Lead; trace raw event -> dedup -> Lead -> assignment -> Pipeline/Action -> NotificationEvent -> report update.
8. Redeliver the same event and prove no second Lead is created.

**Critical procedural constraint:** perform all four Page reauthorizations in
one continuous authorization session. A later login can invalidate credentials
saved by an earlier login within the same Meta app, so reauthorizing sources
one at a time across separate sessions risks re-breaking an already-fixed
source.

Stop if OAuth chooses the wrong business/Page, source identity changes,
mappings disappear, historical Leads move, webhook verification fails, or any
credential would be exposed. Never include tokens in screenshots, logs or
reports. Report token state only as VALID / INVALID / UNVERIFIABLE.

## Update — 25 July, ~15:30 IST: webhook bug found, fixed, and proven; OAuth remains open

**Webhook delivery — FIXED.** `/api/ingestion/meta/<token>` only accepted
`POST`. Meta's Webhooks product always sends its `GET` verification challenge
to the same Callback URL registered for delivery, not a separate path, so the
app-level webhook subscription could never be saved — every attempt failed
with `HTTP 405` before Meta could validate it. This is very likely why
webhook delivery had been completely silent since 22 July, independent of the
OAuth token problem. Fixed in commit `417889d`, deployed to
`dpl_DJ9HgwTCGDtuyRJ4xE21z6V8n5A6`, and verified end-to-end:

1. App Dashboard → Webhooks (Page object) → Callback URL + Verify token for
   source 12 saved successfully (previously failed with "could not be
   validated").
2. `leadgen` field subscribed successfully.
3. One real test lead sent via Meta's own Lead Ads Testing Tool (Page
   `1119764314564515`, form `1082765517417316`) was received, signature
   validated, correctly routed to source 12 by `page_id` via
   `_resolve_meta_target_source`, and logged in `ingested_lead_logs` (id 4442)
   with a correct correlation ID and idempotency key.

The fix is app-level (the Callback URL registration and `leadgen`
subscription apply to the whole app, not per source), so it should not need
to be repeated per Page — all four sources' Page-level `/subscribed_apps`
registrations were already established during the OAuth reconnect attempts
below.

**OAuth/Page tokens — still INVALID.** That same test lead failed
ingestion with `Lead payload missing name or contact method` — expected,
since Meta's webhook payload only ever carries IDs (`leadgen_id`, `page_id`,
`form_id`); fetching the actual name/phone/email requires a follow-up Graph
API call using the Page access token, which is still dead.

Two clean, full reconnect passes were completed this session (all four
sources, single Facebook login each time, ~13:49 and ~14:19 IST). Both times,
every source's token worked for a moment — successfully re-subscribing the
Page's webhook via `/subscribed_apps` during save — then died again within
minutes with the identical `Error validating access token... session has
been invalidated because the user changed their password or Facebook has
changed the session for security reasons` (`code 190 / subcode 460`).

Investigated and ruled out:
- Account compromise: owner confirmed "Where You're Logged In" shows only
  their own devices, and the password-change timestamp matches their own
  action.
- Chrome/Google Password Manager auto-change: owner confirmed no such prompt
  appeared.
- App-level restriction: Meta App Dashboard "Required actions" is clear, no
  blocking Alert Inbox items, app is Published/live mode.
- My own diagnostic script causing cross-IP flagging: ruled out once the
  LMS's own backend-originated "Test" button (single consistent IP) showed
  the identical error.
- A discovered contributing factor (separate from root cause): two duplicate
  cron-job.org jobs were hammering the Graph API with these same tokens every
  5 minutes — see [08_SCHEDULERS_AND_NOTIFICATIONS.md](08_SCHEDULERS_AND_NOTIFICATIONS.md).
  Now disabled; may reduce recurrence on the next attempt.

Leading theory: a Meta-side post-password-change security cooldown that
specifically invalidates third-party app tokens shortly after issuance while
leaving the web login session intact (consistent with every piece of
evidence gathered). **Recommendation: do not retry immediately again.** Wait
several hours, ideally until the next day, then attempt one clean
reconnect and re-test with a single test lead before declaring Meta
certified.
