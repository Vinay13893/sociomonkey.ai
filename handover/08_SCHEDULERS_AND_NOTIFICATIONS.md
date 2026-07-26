# Schedulers and Notifications

## Expected authority

| Job | Owner | Expected schedule | Route |
|---|---|---|---|
| Notification Drain | cron-job.org | every 2 minutes | `/api/cron/drain-notifications` |
| Reminder Processor | cron-job.org | every 5 minutes | `/api/internal/reminders/process` |
| Daily Meta/source-spend sync | Vercel Cron | `29 18 * * *` UTC (23:59 IST) | `/api/cron/meta-report-sync` |
| Legacy Meta Lead Poll | none/inactive | inactive | legacy polling route |
| Duplicate cron-job.org Meta Report Sync | none/inactive | inactive | duplicate report route |

Worker requests require the server-defined cron authentication mechanism using the matching secret. Do not print the header name/value from external dashboards in handover evidence.

## NotificationEvent design

`NotificationEvent` is the only outbound delivery queue. Producers attach stable idempotency and correlation/origin metadata. The drain conditionally claims bounded work, recovers stale claims, dispatches push, records immutable attempts, and returns sanitized counts. Retry backoff is 2, 5, 15, 30 and 60 minutes; maximum attempts enter dead-letter. Missing/expired subscriptions are skipped/deactivated safely. The Reminder Processor creates due events but does not deliver push inline.

Push subscriptions are tenant/user scoped with active/deactivated/failure metadata. Operations APIs under `/api/push/operations/` provide summary, paginated events, detail/attempt history, replay and bounded soft archive. Required capabilities: `notifications.view`, `notifications.retry`, `notifications.manage`. The frontend administration workspace is `src/products/lms/notification-operations.js`.

## Current state — VERIFIED against the 25 July production deployment

Per `../LMS_PRODUCTION_RELEASE_REPORT.md`:

| Job | Authority | Schedule | State |
|---|---|---|---|
| Notification Drain, job `7720618` | cron-job.org | Every 2 minutes, Asia/Kolkata | Active |
| Reminder Processor, job `7720616` | cron-job.org | Every 5 minutes, Asia/Kolkata | Active |
| Meta Lead Poll, job `7889113` | cron-job.org | N/A | Inactive (confirmed) |
| Meta Report Sync, job `7889135` | cron-job.org | N/A | Inactive (confirmed, no duplicate authority) |
| Daily Meta report/source spend | Vercel | `29 18 * * *` UTC (11:59 PM IST) | Configured |

Consecutive production executions were verified from backend logs: Notification
Drain at 06:02:02, 06:04:02, 06:06:02 UTC (HTTP 200 each); Reminder Processor at
05:55:03, 06:00:19, 06:05:03 UTC (HTTP 200 each). Zero-work drain runs
completed in 10–31 ms with no overlap or retry storm.

Independently re-verified by the takeover agent via direct DB read (not
browser): production `notification_events` table shows 2,593 sent, 55 skipped,
**zero pending, zero failed, zero dead-letter** — consistent with a healthy,
singly-owned queue.

## Update — 25 July, ~15:20 IST: drift found and corrected

The owner directly inspected the live cron-job.org console (not backend-log
inference) and found **`LMS - Meta Lead Poll` and `LMS - Meta Report Sync`
were both active**, running every 5 minutes with real successful executions —
directly contradicting the release report's claim that both were inactive.
This mattered: both jobs hit the Meta Graph API using the same Page tokens the
app already relies on, every 5 minutes, which was a plausible contributor to
the repeated OAuth session invalidation being investigated the same session.

The owner disabled both jobs in the console. Current confirmed state (direct
console observation, not inference):

| Job | Status | Last execution |
|---|---|---|
| Sociomonkey - Drain Notifications | Active, green | Successful, 2-min cadence confirmed |
| Reminder Process | Active, green | Successful, 5-min cadence confirmed |
| LMS - Meta Lead Poll | **Inactive** (corrected this session) | — |
| LMS - Meta Report Sync | **Inactive** (corrected this session) | — |

This now matches the intended architecture. Re-verify this state has not
drifted again before any future release sign-off — it drifted once already
without anyone noticing until direct inspection.
