# Product and Architecture

Evidence labels: **VERIFIED** means repository/live evidence was inspected during handover; **REPORTED** means an existing release document says so; **UNVERIFIED** requires fresh external proof.

## System shape

- **Tenant model — VERIFIED:** tenant-scoped Flask APIs and frontend tenant context. Public route alias `ganga-realty` historically maps to data slug `ganga` (REPORTED).
- **Authentication — VERIFIED:** tenant password/OTP/JWT flows, middleware authorization, explicit production secrets, and capability checks. Platform Owner and tenant users are distinct scopes.
- **Organisation Units — VERIFIED:** hierarchical units, memberships, capability-backed roles, team scope, and workload/report filters.
- **Roles/capabilities — VERIFIED:** Platform Owner, tenant Admin, Sales Manager, and Team Member compatibility roles; APIs enforce granular capabilities such as reports and notification operations.
- **Configuration — VERIFIED:** tenant business configuration holds stable internal keys and editable labels/rules. Display renames must not mutate internal keys.
- **Locations/Meeting Rooms — VERIFIED:** normalized tenant Locations and Rooms, status/capacity/configuration, Visit and reporting relationships.
- **Visits — VERIFIED:** scheduled/actual physical interactions, status/type, visitors, Project/Lead/Location/Room relationships.
- **Gallery/Reception — VERIFIED:** arrivals, walk-ins, inside/no-show handling, reception operations, Visit handoffs.
- **Channel Partners — VERIFIED:** relationship profiles, attribution, assignment, arrivals/completion and engagement history.
- **Action Items — VERIFIED:** operational work with ownership, priority, due dates, lifecycle, correlated generation, and unified board.
- **Pipeline — VERIFIED:** current Lead state remains on Lead; immutable Pipeline transition events record lifecycle, rules, overrides, generated Actions and correlation.
- **Reports/Analytics — VERIFIED:** bounded, SQL-aggregated, read-only consumers across 11 report families; independent view/export capabilities.
- **NotificationEvent — VERIFIED:** sole outbound delivery queue with idempotency, claims, retry/backoff, dead-letter, immutable attempt history, replay/archive administration.
- **Meta ingestion — VERIFIED:** existing sources/forms/mappings feed signed webhook and manual-sync ingestion into durable raw events, deduplication, Lead creation, assignment, Pipeline, Actions and notifications.
- **Scheduler ownership — VERIFIED in code / UNVERIFIED live:** Vercel config owns only daily Meta/source-spend sync; cron-job.org is intended to own frequent Reminder Processor and Notification Drain.
- **Deployments — VERIFIED architecture / UNVERIFIED current parity:** Flask backend is a Vercel Python function via `api/index.py`; static/PWA frontend is a separate Vercel project with `/api` rewrite.
- **Neon — REPORTED:** production PostgreSQL plus an approved recovery branch used for migration rehearsal. Live branch identity and current production schema are UNVERIFIED.

## Ownership boundaries

- Leads own current Lead state.
- Pipeline owns immutable lifecycle history.
- Visits own physical interactions.
- Action Items own operational work.
- Channel Partners own relationship profiles.
- NotificationEvent owns delivery work.
- Reports remain read-only consumers.

Do not create parallel sources of truth or make reports write operational state.

## Explicit non-goals and deferred features

No new feature work is authorized during takeover. Deferred: first-class Customer/Customer Care; Booking, Inventory, Collections, Finance/Post Sales; document/media storage; meeting-room conflict calendar; QR/self-check-in and hardware visitor flows; advanced attribution/forecasting/AI recommendations; global search; public/versioned APIs; enterprise SSO; managed queue replacement; broad legacy cleanup. Legacy compatibility fields remain until an approved migration removes them.
