# Sociomonkey LMS Master Implementation Roadmap

Date: 24 July 2026
Status: Draft for owner review
Authority: Single source of truth after approval
Business timezone: `Asia/Kolkata` (IST)

## Purpose and Scope

This roadmap consolidates the historical LMS hardening program, the current
additive V2 foundation program, the remaining implementation sequence, and the
release gates for the first tenant release of the modernized LMS.

The live legacy LMS remains the production baseline. The V2 implementation
exists on isolated backend and frontend worktrees and has not been deployed.
The approved Neon recovery branch remains the database validation target.

This document uses two phase namespaces to prevent old and current phase
numbers from being confused:

- `H` phases are the historical optimization, stabilization, and production
  hardening program. They are retained for traceability only.
- `V2` phases are the authoritative implementation and release sequence going
  forward.

No future prompt should refer to an unqualified phase number.

### Status Definitions

| Status | Meaning |
|---|---|
| Complete | Implemented and passed the required phase gates |
| Validation Pending | Implementation exists, but a mandatory validation gate is open |
| Planned | Approved scope exists, but implementation has not started |
| Not Started | Identified work without an approved implementation start |

### Feature Status Definitions

| Status | Meaning |
|---|---|
| Complete | Implemented and locally/recovery validated for its approved scope |
| Partial | Implemented in part or awaiting operational certification |
| Planned | Required in the current release train but not yet implemented |
| Not Required | Deliberately represented by another shared entity or module |
| Future Version | Explicitly outside the first modernized tenant release |

## 1. Phase Inventory

### 1.1 Historical LMS Program

The historical program produced the clean production freeze from which the V2
worktrees were created. It is not the roadmap for new implementation.

| Phase | Name | Primary Objective | Major Features | Status |
|---|---|---|---|---|
| H0 | Safety and Infrastructure Baseline | Establish read-only investigation and rollback discipline | Repository inventory, deployment map, database safety, Neon transfer investigation | Complete |
| H1A | Infrastructure Containment | Identify production clients and scheduler ownership | Vercel, Railway, Neon, local/preview and cron inventory | Complete |
| H1B | Production Client Forensics | Determine who could reach production Neon | Deployment, environment, scheduler and connection evidence | Complete |
| H1C | Database and Traffic Evidence | Quantify read patterns and transfer risks | Table/query evidence, endpoint traffic assessment | Complete |
| H1D | Engineering Baselines | Define measurable budgets before optimization | Endpoint budgets, query inventory, cache strategy, realtime matrix, scalability and success metrics | Complete |
| H2 | Leads Optimization | Bound the highest-volume interactive dataset | Server pagination, SQL filters, search, sorting, delta retrieval | Complete |
| H3 | Dashboard and Action Board Optimization | Remove overlapping broad Lead reads | SQL aggregation, compact Action Board payloads, scoped filters | Complete |
| H4 | Notifications and Reminders Optimization | Separate browser reads from workers | Bounded bell history/delta, worker routes, polling controls | Complete |
| H5 | Lead Sources Optimization | Simplify source reporting and preserve ingestion | Source/form performance, daily spend direction, campaign report removal | Complete |
| H6 | Reports and Activity Optimization | Remove export-sized interactive reads | SQL aggregation, pagination, compact serializers, export separation | Complete |
| H7 | Production Readiness and Capacity | Model load and assess release hygiene | Capacity model, Neon transfer estimates, release risks | Complete |
| H8 | Release Preparation | Validate contracts without deploying | Runtime, API, query, repository and monitoring review | Complete |
| H9 | Release Reconstruction Gate | Reconstruct a clean deployable source state | Clean release branches, canonical path verification, NO-GO gate | Complete |
| H10 | Initial Controlled Deployment | Deploy reconstructed release | Backend release, failed frontend gate, rollback | Complete |
| H10A | Release Reconstruction | Correct the rolled-back release package | Clean backend/frontend reconstruction | Complete |
| H10B | Controlled Production Deployment | Deploy the approved release | Backend/frontend deployment and technical smoke tests | Complete |
| H10C | Scheduler Authority Review | Remove duplicate scheduler authority | Vercel daily spend ownership, inactive duplicate jobs | Complete |
| H11 | Notification and Scheduler Repair | Restore frequent notification/reminder execution | Worker route verification and cron-job.org configuration | Validation Pending |
| H12 | Callback Workflow Reconciliation | Centralize callback lifecycle and IST behavior | Create, reschedule, complete, cancel, reminder processing | Complete |
| H12C | Callback End-to-End Validation | Prove callback, bell and PWA delivery | Authenticated browser and physical push validation | Complete |
| H13 | Lead Count Reconciliation | Align Lead, Dashboard and Lead Source definitions | Submission, unique, processed, duplicate and active Lead semantics | Complete |
| H14 | Sales Operations Workflow | Improve allocation and management operations | Unassigned, stale, workload, Action Board and management health | Complete |
| H15 | Mobile Optimization | Harden changed operational pages for mobile | Responsive Allocation, reports and Action Board behavior | Complete |
| H16 | Code Audit and Cleanup | Remove release ambiguity without workflow changes | Canonical runtime paths and clean release reconstruction | Complete |
| H17 | Performance Hardening | Preserve bounded reads after workflow changes | Compact list fields and bounded operational endpoints | Complete |
| H17A | Timeline and Allocation Consistency | Standardize IST display and Allocation navigation | Activity timeline and filter/pager corrections | Complete |
| H17B | Workload and Recycle Completion | Complete manager workload movement | Cohort filters, bounded preview, transfer modes and eligibility | Complete |
| H-Freeze | Final Stabilization and Release Freeze | Establish the current production baseline | Clean commits, production deployment and technical health smoke | Complete |

Historical H11 owner-level scheduler evidence remains relevant as a current
release blocker, but its application behavior has since been hardened by V2
Phase 1.

### 1.2 Authoritative V2 Program

| Phase | Name | Primary Objective | Major Features | Status |
|---|---|---|---|---|
| V2-0 | Product Constitution and Safety | Fix architecture boundaries and rollback rules | Core entities, additive migration policy, recovery branch | Complete |
| V2-1 | Reliability Foundation | Harden ingestion, notifications and reminders | Durable raw ingestion, idempotency, retries, queue claims, diagnostics | Complete |
| V2-1.5 | Production Readiness Assessment | Verify external production prerequisites | Vercel targets, environment metadata, Meta, VAPID, cron and rollback review | Complete |
| V2-2 | Organisation and Permissions | Add flexible organization and capability foundations | Units, reporting relationships, multiple roles, scoped capabilities and overrides | Complete |
| V2-3 | Configuration Foundation | Remove hard-coded tenant display/business configuration | Lead statuses, sources, operational rules and configuration audit | Complete |
| V2-4 | Locations and Meeting Rooms | Add reusable physical-location entities | Locations, project relationships and lightweight rooms | Complete |
| V2-5 | Visits Foundation | Create one generic physical-interaction entity | Visit types, participants, lifecycle, locations, rooms and Lead/CP links | Complete |
| V2-6 | Gallery Operations | Build Reception operations on Visits | Expected visitors, walk-ins, queue, handoff, rooms and check-out | Complete |
| V2-7 | Channel Partners | Add reusable CP relationship foundation | Individuals, organizations, contacts, assignments, projects and Visits | Complete |
| V2-8 | Role-Specific Action Boards | Add one operational work model | Action Items, types, priorities, assignment, lifecycle and role workspaces | Complete |
| V2-9 | Unified Pipeline Engine | Orchestrate Lead lifecycle using existing foundations | Configured stages, immutable transitions, rules, Actions, Visits and ownership history | Complete |
| V2-10 | Reports and Analytics Foundation | Extend reporting across V2 entities | Pipeline, organization, location, Visit, CP and Action reporting | Planned |
| V2-11 | Notification Reliability Completion | Complete event-driven delivery operations | Queue health, retry, dead-letter, diagnostics, correlation and manual recovery | Planned |
| V2-12 | Staging, Release and Production Readiness | Validate and release the complete V2 train | Migration rehearsal, staging E2E, OAuth/cron certification, rollout and monitoring | Planned |

V2-9 implementation and recovery validation are complete. V2-10 is the next
planned phase and must not begin until the V2-9 completion report is approved.

## 2. Feature Inventory

### 2.1 Platform Foundation

| Feature | Status | Release Note |
|---|---|---|
| Tenant entity and tenant isolation | Complete | Backend tenant scope remains authoritative |
| Tenant slug routing | Complete | `ganga-realty` remains the current user-facing tenant route |
| Recovery-branch migration discipline | Complete | Required for every additive V2 migration |
| Canonical backend/frontend deployment targets | Complete | Deployment execution remains V2-12 work |
| Platform Owner role | Complete | Capability-backed in V2-2 |
| Tenant provisioning | Partial | Existing APIs exist; complete operational QA is deferred to release |
| Multi-brand hierarchy | Partial | Tenant/brand fields exist; advanced brand administration is not current scope |
| Independent Platform application dependency | Not Required | LMS release must not depend on a separate Platform runtime |

### 2.2 Authentication

| Feature | Status | Release Note |
|---|---|---|
| Email/password login | Complete | Legacy contract preserved |
| OTP login | Complete | Existing workflow retained |
| Session/token authentication | Complete | Existing frontend/backend contract retained |
| Keep-me-signed-in behavior | Complete | Existing UI behavior retained |
| Tenant-aware login and routing | Complete | Requires final staging/browser smoke |
| Authentication audit and brute-force hardening | Partial | Existing controls require security review before broader rollout |
| SSO/enterprise identity | Future Version | Not required for first tenant release |

### 2.3 Organisations, Roles and Permissions

| Feature | Status | Release Note |
|---|---|---|
| Organisation Units | Complete | Hierarchical and tenant scoped |
| Flexible reporting relationships | Complete | Effective-dated, non-hard-coded relationships |
| Multiple business roles per user | Complete | Legacy role fields preserved |
| Capability definitions | Complete | Backend authoritative |
| Role permission templates | Complete | Business roles supply defaults |
| User allow/deny overrides | Complete | Explicit deny precedence |
| OWN, TEAM, UNIT, PROJECT, TENANT and PLATFORM scopes | Complete | Resource scope supported |
| Admin permission UI | Partial | APIs complete; Administration coverage should receive staging QA |
| Permanent user-to-location ownership | Not Required | Users belong to organization; operations reference Locations |

### 2.4 Configuration

| Feature | Status | Release Note |
|---|---|---|
| Lead status display configuration | Complete | Internal keys remain immutable |
| Status order, color and visibility | Complete | Existing counts retain internal identifiers |
| Qualified, lost, terminal and success flags | Complete | Pipeline consumes configured outcomes |
| Lead source display configuration | Complete | Integration identities remain stable |
| Source reporting groups and ordering | Complete | Tenant scoped |
| Warm, hot, cold, SLA, escalation, callback and priority rules | Complete | Foundation and auditable definitions exist |
| Pipeline entry/exit rules | Complete | Validated by allowed, blocked and override transitions |
| Pipeline default Actions | Complete | Reuses idempotent Phase 8 Action Items |
| Configuration Activity Logs | Complete | Previous/new values and correlation IDs |
| Arbitrary tenant workflow builder | Future Version | Current declarative rules are intentionally bounded |

### 2.5 Locations and Meeting Rooms

| Feature | Status | Release Note |
|---|---|---|
| Generic Location entity | Complete | Tenant scoped and reusable outside LMS |
| Location types | Complete | Head office, gallery, site and other types |
| Project-to-multiple-location relationships | Complete | Legacy project location text remains compatible |
| Location administration | Complete | Create, edit, archive, restore, search and filter |
| Lightweight Meeting Room entity | Complete | Belongs to Location |
| Room status, capacity and type | Complete | Foundation only |
| Room allocation to Visit | Complete | Gallery operations reuse relationship |
| Room calendar and conflict engine | Future Version | Not required for first tenant release |
| Separate Sales Gallery entity/module | Not Required | A Sales Gallery is a Location type |

### 2.6 Leads, Allocation and Ownership

| Feature | Status | Release Note |
|---|---|---|
| Lead CRUD and detail timeline | Complete | Existing data model remains system of record |
| Bounded list pagination and SQL filters | Complete | No full interactive Lead dataset |
| Search, sorting and date filtering | Complete | Server-side |
| Status changes | Complete | Legacy behavior retained; V2 Pipeline records new movements |
| Notes, callbacks and call activity | Complete | Existing workflows retained |
| Bulk assignment and reassignment | Complete | Assignment history retained |
| Manager self-assignment | Complete | Existing manager workflow retained |
| Unassigned, stale, workload and recycle operations | Complete | Bounded and tenant scoped |
| Previous/current owner history | Complete | Existing history extended additively by V2-9 |
| Channel Partner attribution | Complete | Nullable relationship and transition attribution validated |
| Lead-to-Customer conversion | Future Version | Customer entity is deferred |
| Separate Pipeline Lead copy | Not Required | Pipeline references Lead and stores orchestration events only |

### 2.7 Lead Sources, Forms and Integrations

| Feature | Status | Release Note |
|---|---|---|
| Meta Integration | Partial | Ingestion is complete; production OAuth, tokens and scheduler evidence remain release gates |
| Configurable source records | Complete | Meta and Google integrations preserved |
| Source cards and connection details | Complete | Active/mapping state visible |
| Form discovery and mapping | Complete | Project and manager mapping retained |
| Refresh Forms | Complete | Manual operation retained |
| Manual Meta Sync | Complete | Existing operation retained |
| Future-only versus historical mapping update choice | Complete | Existing Lead updates remain explicit |
| Source/form performance reporting | Complete | Existing source definitions retained |
| Meta OAuth multi-tenant connection | Partial | Code exists; production tokens must be reauthorized and verified |
| Meta webhook ingestion | Complete | Durable raw events and idempotency in V2-1 |
| Meta duplicate delivery handling | Complete | Provider-event identity and Lead duplicate checks |
| Meta retry and reprocessing diagnostics | Complete | Manual retry and failure visibility |
| Meta spend synchronization | Partial | Daily path exists; credentials and scheduler require release validation |
| Google source integration | Partial | Existing implementation retained; final tenant workflow certification required |
| Meta polling as canonical ingestion | Not Required | Webhooks are canonical; legacy poll remains inactive |
| Duplicate Meta report scheduler | Not Required | Vercel daily job is the sole planned owner |

### 2.8 Uploads, Imports and Exports

| Feature | Status | Release Note |
|---|---|---|
| Single/manual Lead creation | Complete | Existing flow retained |
| Bulk Lead import | Complete | Bounded job workflow retained |
| Existing Lead bulk update | Complete | Pipeline-compatible status path implemented in V2-9 |
| Import validation and errors | Complete | Existing behavior retained |
| Export filters and full export generation | Complete | Separate from interactive lists |
| Background import/export jobs | Complete | Existing job model retained |
| Import templates and advanced mapping profiles | Future Version | Not required for first tenant |

### 2.9 Business Rules

| Feature | Status | Release Note |
|---|---|---|
| Tenant-scoped rule definitions | Complete | V2-3 |
| Version/audit history | Complete | Configuration changes logged |
| Declarative evaluation | Complete | Reused by V2-9 |
| Pipeline entry/exit evaluation | Complete | Rule evaluation and manager override validated |
| Automatic Visit-driven Pipeline movement | Not Required | Only configured rules may authorize movement |
| AI rule recommendations | Future Version | Pipeline event model is future-ready |

### 2.10 Visits, Gallery Operations and Reception

| Feature | Status | Release Note |
|---|---|---|
| Unified Visit entity | Complete | One physical-interaction model |
| Configurable Visit types and lifecycle | Complete | Scheduled, walk-in, site, CP and internal scenarios |
| Generic Visit participants | Complete | Future Customer support without schema redesign |
| Lead-linked and standalone Visits | Complete | No automatic Lead status change |
| Location, Project and Meeting Room links | Complete | Reusable relationships |
| Reception workspace | Complete | Driven by Visits |
| Expected arrivals and walk-ins | Complete | Walk-in creates a Visit |
| Check-in, waiting, called, in-meeting and check-out | Complete | No duplicate queue table |
| User handoff and notification event | Complete | Existing notification infrastructure reused |
| Room allocation/change/removal | Complete | No calendar conflicts |
| QR, token and self-check-in | Future Version | Schema is ready |
| Separate Reception visitor entity | Not Required | Visit is the source of truth |
| Separate workspace-usage module | Not Required | Workspace usage is a Visit type for current scope |

### 2.11 Channel Partners

| Feature | Status | Release Note |
|---|---|---|
| Individual and organization CP profiles | Complete | V2-7 |
| Multiple contacts | Complete | Contact can later evolve independently |
| Project associations | Complete | Preferred, active and historical |
| Sales Manager and RM assignment | Complete | Organization framework reused |
| CP Visits and workspace usage | Complete | Visit foundation reused |
| CP activity timeline | Complete | Visits, assignments, notes and logs |
| CP-originated Lead attribution | Complete | V2-9 relationship and tenant validation passed |
| Commission, payout and invoice workflows | Future Version | Financial logic deliberately excluded |
| Separate CP Pipeline | Not Required | Leads remain Pipeline-owned |

### 2.12 Action Boards and Tasks

| Feature | Status | Release Note |
|---|---|---|
| Unified Action Item entity | Complete | V2-8 |
| Configurable Action types, states and priorities | Complete | Stable internal keys |
| User and Organisation Unit assignment | Complete | Capability scoped |
| Due, waiting, overdue, completed and priority views | Complete | Operational workspace |
| Role-specific workspaces | Complete | Caller, manager, RM, Reception and Admin |
| Lead Queue compatibility view | Complete | Existing Action Board behavior preserved |
| Idempotent entity-generated Actions | Complete | Used by V2-9 instead of duplicate tasks |
| Scheduled due/overdue event generation | Partial | Event model ready; final worker behavior belongs to V2-11 |
| Separate Pipeline task table | Not Required | Pipeline reuses Action Items |

### 2.13 Pipeline

| Feature | Status | Release Note |
|---|---|---|
| Configuration-driven Lead stages | Complete | Stable keys and tenant configuration validated |
| Immutable stage-transition events | Complete | Application and PostgreSQL enforcement validated |
| Rule-gated transitions | Complete | Allowed and blocked transitions validated |
| Required completed Actions | Complete | Rule requirement integration validated |
| Manager override with audit | Complete | Permission, reason and audit behavior validated |
| Default Action generation | Complete | Reuses Phase 8 and rejects duplicate identities |
| Visit and CP attribution | Complete | Tenant-scoped relationships validated |
| Stage ageing and stalled Leads | Complete | Operational calculations validated |
| Conversion funnel and today's movement | Complete | Operational metrics validated |
| Pipeline history analytics | Planned | V2-10 |
| Multiple independent pipelines | Future Version | Current engine is reusable, but one Lead lifecycle is sufficient now |

### 2.14 Notifications and Reminders

| Feature | Status | Release Note |
|---|---|---|
| In-app bell history and unread count | Complete | Bounded history and delta behavior |
| Mark read and mark all read | Complete | Existing behavior retained |
| NotificationEvent queue | Complete | Durable delivery events |
| Push subscription registration | Complete | Existing PWA route |
| VAPID push delivery | Partial | Historical success exists; staging/device certification required |
| Assignment notifications | Complete | Existing flow retained |
| Callback warning and due reminders | Complete | Callback workflow centralized |
| Conditional queue claim and stale recovery | Complete | V2-1 |
| Retry, skip, dead-letter and manual retry diagnostics | Complete | V2-1 foundation |
| Current cron-job.org execution evidence | Partial | Owner/API validation remains mandatory |
| Correlation across all V2 event producers | Partial | Complete for V2 modules; consolidate in V2-11 |
| Managed event/delayed queue replacement | Future Version | Recommended after first release |
| Parallel notification system | Not Required | All modules use NotificationEvent |

### 2.15 Reports, Dashboards and Analytics

| Feature | Status | Release Note |
|---|---|---|
| Existing Lead reports | Complete | SQL aggregated and bounded |
| Existing team reports | Complete | SQL aggregated |
| Existing activity reports | Complete | Paginated |
| Existing Lead Source performance | Complete | Source/form semantics established |
| Existing operational Dashboard | Complete | Bounded current LMS metrics |
| Existing management health metrics | Complete | Allocation/callback/stale visibility |
| Pipeline history and time-in-stage reporting | Planned | V2-10 |
| Organization and role performance | Planned | V2-10 |
| Location and Gallery reporting | Planned | V2-10 |
| Visit and Meeting Room reporting | Planned | V2-10 |
| Channel Partner performance | Planned | V2-10 |
| Action Item productivity | Planned | V2-10 |
| Advanced forecasting and attribution analytics | Future Version | Not required for first tenant release |
| BI warehouse or separate analytics infrastructure | Future Version | Software/database optimization comes first |

### 2.16 Customer, Booking, Inventory, Documents and Media

| Feature | Status | Release Note |
|---|---|---|
| First-class Customer entity | Future Version | Leads and generic Visit participants cover current release |
| Booking entity and lifecycle | Future Version | Introduce with Inventory/Booking product scope |
| Inventory/unit management | Future Version | Not part of initial LMS release |
| Collections and finance | Future Version | Must reference future Booking/Customer foundations |
| Documentation workflow | Future Version | Current Documentation Visit and Action types are sufficient |
| Document storage | Future Version | Visit attachment foundation exists; storage is not implemented |
| Media library | Future Version | Not required for operational LMS |
| Customer Care/Post Sales | Future Version | Depends on Customer and Booking |
| Event entity | Future Version | Current event attendance is a Visit type |

### 2.17 Activity, Audit, Search, Settings and APIs

| Feature | Status | Release Note |
|---|---|---|
| Activity Logs | Complete | Existing and V2 mutations logged |
| Previous/new value audit | Complete | Configuration and V2 entity mutations |
| Correlation IDs | Complete | Present across new foundations; finalize coverage in V2-11 |
| Module-local search and filters | Complete | Bounded backend queries |
| Cross-module global search | Future Version | Requires dedicated permissions and indexing design |
| Tenant Administration / Settings | Complete | Configuration, Locations, Rooms, Visits, CP and Actions |
| Global Settings (platform scope) | Partial | Keep separate from tenant settings |
| REST APIs | Complete | Existing module APIs and capability enforcement |
| Public versioned API product | Future Version | Current internal API is not a public contract |
| Webhooks as an outbound product | Future Version | Meta inbound webhook is current scope |

## 3. Dependency Map

### 3.1 Foundation Dependency Graph

```text
Tenant + Authentication
        |
        v
Organisation + Roles + Capabilities
        |
        v
Tenant Configuration + Business Rules
        |
        +-----------------------------+
        |                             |
        v                             v
Locations + Meeting Rooms        Lead Sources + Ingestion
        |                             |
        v                             v
Unified Visits                    Leads + Ownership
        |                             |
        +-------------+---------------+
                      |
          +-----------+-----------+
          |                       |
          v                       v
Gallery Operations          Channel Partners
          |                       |
          +-----------+-----------+
                      |
                      v
              Unified Action Items
                      |
                      v
               Pipeline Engine
                      |
          +-----------+-----------+
          |                       |
          v                       v
Reports and Analytics       Notifications/Reminders
          |                       |
          +-----------+-----------+
                      |
                      v
             Staging and Release
```

### 3.2 Ownership Rules

- Leads own Lead identity, current status, assignment, notes and callbacks.
- Pipeline owns append-only lifecycle orchestration history, not Lead data.
- Action Items own operational work, regardless of originating module.
- Visits own physical interactions; Gallery Operations orchestrates Visits.
- Locations own physical place definitions; Sales Gallery is a Location type.
- Channel Partners own relationship profiles, not Leads or Pipeline stages.
- NotificationEvent owns delivery work; modules only emit events.
- Reports read systems of record and never become a transactional source.

### 3.3 Safest Remaining Order

1. Build V2-10 reports from stable V2-2 through V2-9 relationships.
2. Complete V2-11 event delivery and operational diagnostics.
3. Execute V2-12 migration rehearsal, staging E2E, release certification and
   production rollout.

This order is mandatory. Reporting requires finalized Pipeline history, and
release certification requires finalized notification behavior.

## 4. Remaining Phases

### V2-9 - Completed Recovery Gate

| Item | Definition |
|---|---|
| Objective | Prove the implemented Pipeline schema and workflows on the approved recovery branch |
| Deliverables | Guarded check/apply/reapply/check, schema/grant validation, rollback-only workflow, immutable event proof, final regressions, report and local commits |
| Dependencies | V2-1 through V2-8 and visible recovery environment variables |
| Complexity | Medium |
| Required before production | Satisfied |

The guarded check/apply/reapply/check, schema/grant validation, rollback-only
workflow, immutable-history proof, complete regressions and cleanup checks
passed on 24 July 2026.

### V2-10 - Reports and Analytics Foundation

| Item | Definition |
|---|---|
| Objective | Extend bounded reporting across all V2 foundations without creating a warehouse or duplicate aggregates |
| Deliverables | Pipeline history/time-in-stage, conversion, organization, user/team, Project, Location, Visit, CP and Action Item reporting; export parity; permission and tenant filters |
| Dependencies | Completed V2-9, V2-2 permissions, V2-3 configuration, V2-4 through V2-8 entities |
| Complexity | High |
| Required before production | Yes |

Implementation rules:

- Aggregate in SQL.
- Keep interactive responses bounded.
- Keep exports separate.
- Use immutable internal keys and configured display labels.
- Do not invent historical Pipeline or Visit events.

### V2-11 - Notification Reliability Completion

| Item | Definition |
|---|---|
| Objective | Certify one reliable event-delivery path for every operational module |
| Deliverables | Queue dashboard, retry/dead-letter/manual recovery, correlation trace, delivery status, expired subscription handling, worker cost checks and scheduler evidence |
| Dependencies | V2-1 queue, V2-6 Gallery, V2-7 CP, V2-8 Actions and completed V2-9 Pipeline |
| Complexity | Medium to High |
| Required before production | Yes |

The current cron-job.org jobs may remain for the first release if they are
proven healthy. A managed queue replacement is post-release architecture work,
not a reason to redesign V2-11.

### V2-12 - Staging, Release and Production Readiness

| Item | Definition |
|---|---|
| Objective | Produce and release one fully tested V2 release candidate |
| Deliverables | Migration bundle, clean commits, staging deployment, authenticated browser/device E2E, Meta OAuth/webhook validation, cron validation, load/capacity checks, rollback rehearsal, production rollout and monitoring |
| Dependencies | Completed V2-9, V2-10 and V2-11 |
| Complexity | High |
| Required before production | Yes |

Recommended internal gates:

| Gate | Scope |
|---|---|
| V2-12A | Release candidate freeze and migration rehearsal |
| V2-12B | Staging deployment and end-to-end tenant validation |
| V2-12C | Controlled production deployment and post-deployment monitoring |

These are gates inside V2-12, not parallel phases.

## 5. Release Checklist

### 5.1 Source and Database

- [x] V2-9 recovery validation passes.
- [ ] Every V2 migration passes check/apply/reapply/check on recovery.
- [ ] Migration order is documented and rehearsed.
- [ ] All migrations are additive and idempotent.
- [ ] No synthetic recovery/staging data remains.
- [ ] Backend and frontend release branches are clean.
- [ ] Release commits contain only approved phase changes.
- [ ] Production rollback deployment IDs are recorded.
- [ ] Neon recovery branch remains healthy and protected.

### 5.2 Staging Deployment

- [ ] Create or confirm isolated staging backend, frontend and database.
- [ ] Confirm staging never points at production Neon.
- [ ] Apply the complete migration chain to staging.
- [ ] Deploy backend, then validate health and schema.
- [ ] Deploy frontend, then validate asset/API contract versions.
- [ ] Confirm no Railway or legacy backend dependency.
- [ ] Confirm preview deployments cannot use production credentials.

### 5.3 Browser QA and Role Validation

- [ ] Admin login and navigation.
- [ ] Sales Manager visibility and assignment.
- [ ] Calling Manager team visibility.
- [ ] Caller OWN scope.
- [ ] Relationship Manager OWN/TEAM scope as configured.
- [ ] Reception Visit/Gallery scope.
- [ ] Platform Owner platform scope.
- [ ] Cross-tenant denial for every new module.
- [ ] Desktop responsive QA.
- [ ] Android installed-PWA QA.
- [ ] iOS installed-PWA QA.

### 5.4 Core Workflow Smoke Tests

- [ ] Create one manual Lead.
- [ ] Import a bounded Lead file.
- [ ] Receive one Meta test Lead.
- [ ] Redeliver the same Meta event and prove idempotency.
- [ ] Assign/reassign a Lead.
- [ ] Create, reschedule, complete and cancel a callback.
- [ ] Verify Action Board and Action Item behavior.
- [ ] Move a Lead through an allowed Pipeline transition.
- [ ] Prove a blocked rule and manager override.
- [ ] Generate a Pipeline Action Item once.
- [ ] Create a Visit and process Reception check-in/check-out.
- [ ] Create and assign a Channel Partner.
- [ ] Verify reports and exports.
- [ ] Verify activity and audit history.

### 5.5 OAuth, Webhooks and Cron Validation

- [ ] Reauthorize every active Meta source.
- [ ] Validate Meta App ID/secret metadata without exposing values.
- [ ] Validate callback URL and App Secret signature.
- [ ] Validate Page `leadgen` subscriptions.
- [ ] Validate forms and page access for each source.
- [ ] Validate daily source-spend sync at `29 18 * * *` UTC.
- [ ] Confirm Meta Lead Poll remains inactive.
- [ ] Confirm duplicate cron-job.org Meta Report Sync remains inactive.
- [ ] Confirm Notification Drain header and two successful runs.
- [ ] Confirm Reminder Processor header and two successful runs.
- [ ] Confirm no duplicate scheduler authority.

### 5.6 Notification and Device Smoke

- [ ] Active subscription exists for the test user.
- [ ] Assignment creates in-app and queued push events.
- [ ] Notification Drain sends assignment push.
- [ ] Callback warning/due events are idempotent.
- [ ] Callback push arrives on the physical device.
- [ ] Expired subscription is deactivated safely.
- [ ] Notification click opens the correct tenant context.
- [ ] Bell history, delta, unread count and mark-read work.

### 5.7 Capacity and Security

- [ ] Neon transfer baseline captured before staging load.
- [ ] Zero-work scheduler query cost measured.
- [ ] Largest endpoints stay within established budgets.
- [ ] Database connection count remains bounded.
- [ ] 12-user/10,000-monthly-Lead load test passes.
- [ ] Production secrets exist and match code variable names.
- [ ] Hard-coded demo/bootstrap passwords are removed.
- [ ] Legacy manual test credentials are removed.
- [ ] CORS and application secret production warnings are resolved.
- [ ] No credential-shaped values appear in the release diff.

### 5.8 Production Deployment

- [ ] Owner approves the staging report.
- [ ] Tenant maintenance window is active.
- [ ] Production snapshot/recovery timestamp is recorded.
- [ ] Apply migrations in rehearsed order.
- [ ] Deploy canonical backend project only.
- [ ] Run backend health, auth rejection and schema checks.
- [ ] Deploy canonical frontend project only.
- [ ] Run authenticated role and workflow smoke tests.
- [ ] Enable/confirm only approved schedulers.
- [ ] Restore tenant access after all success criteria pass.

### 5.9 Post-Deployment Verification

- [ ] Monitor Neon transfer, compute, storage and connections.
- [ ] Monitor endpoint latency, response size and error rate.
- [ ] Monitor ingestion lag and duplicate/error counts.
- [ ] Monitor queue pending age, failure and dead-letter counts.
- [ ] Monitor reminder due backlog.
- [ ] Monitor Pipeline transition and Action generation errors.
- [ ] Review at 1 hour, 24 hours, 7 days and 14 days.
- [ ] Roll back application aliases on any defined failure trigger.

## 6. Technical Debt

Technical debt is not automatically a release blocker. Items promoted to
release blockers are listed separately in Section 7.

### 6.1 Known Issues

- Inactive legacy `app/routes.py`, `app/routes_old.py` and `app/models.py`
  remain beside the active package implementation.
- Historical frontend Lead Source generations remain in the repository and
  require a clearly documented canonical path.
- Local SQLite integration startup emits a PostgreSQL `NOW()` warning.
- Existing documentation contains older `Asia/Calcutta` terminology; new work
  uses `Asia/Kolkata`.
- Mixed line-ending warnings remain on Windows worktrees.

### 6.2 Security Improvements

- Remove hard-coded demo/bootstrap password literals from `app/__init__.py`.
- Remove credentials from `test_login.py`; use environment-backed fixtures.
- Ensure demo/provisioning accounts require explicit non-production seeding.
- Resolve insecure fallback application-secret warnings.
- Restrict production CORS origins.
- Add an allowlisted secret scanner to CI.
- Review OTP throttling, account lockout and session revocation before broader
  multi-tenant rollout.

### 6.3 Reliability Improvements

- Replace external polling schedulers with a managed queue/delayed-job service
  after the first release.
- Add durable scheduler execution history independent of cron-job.org.
- Extend correlation trace views across ingestion, rules, Actions, Pipeline
  and delivery.
- Add automated cleanup/retention policies for large logs and raw payloads.

### 6.4 Performance Improvements

- Continue enforcing endpoint budgets and bounded list contracts.
- Add indexes only from production/staging query evidence.
- Monitor stage-ageing and report aggregation queries at larger Lead volumes.
- Add short-lived summary caching only after V2-10 query measurements.
- Reassess Neon plan before the tenant approaches the 5 GB transfer ceiling.

### 6.5 Deferred Features

- First-class Customer and Customer Care.
- Booking, Inventory, Collections and Finance.
- Document storage and Media library.
- Meeting Room calendar/conflict engine.
- QR/self-check-in and visitor token hardware workflows.
- Advanced Marketing attribution and forecasting.
- Global search.
- Public/versioned API product.
- Enterprise SSO.

### 6.6 Legacy Components

- Legacy role fields remain for backward compatibility until all users and
  endpoints consume capabilities.
- Legacy Project location text remains while normalized relationships mature.
- Existing Lead status and StatusHistory remain authoritative compatibility
  contracts alongside immutable Pipeline Transition events.
- cron-job.org remains the current frequent-worker owner until a managed
  replacement is approved.

## 7. Release Readiness

### 7.1 Completion Estimate

Estimated first modernized tenant release completion: **82%**.

This is a planning estimate, not a test metric. It reflects:

- V2-0 through V2-9 complete.
- V2-10 reporting not started.
- V2-11 final notification operations not started.
- V2-12 staging and release execution not started.

The underlying legacy LMS is already operational, so the percentage represents
the approved modernization and release train, not the existence of basic LMS
functionality.

### 7.2 Mandatory Before Tenant Deployment

1. Implement and approve V2-10.
2. Implement and approve V2-11.
3. Complete V2-12A migration/release rehearsal.
4. Pass V2-12B staging E2E for all roles and workflows.
5. Reauthorize and validate Meta sources/webhooks.
6. Validate cron-job.org jobs and eliminate duplicate scheduler authority.
7. Remove hard-coded bootstrap/manual-test credentials.
8. Pass capacity, tenant isolation, physical PWA push and rollback checks.
9. Execute V2-12C controlled production rollout.

### 7.3 Current Release Blockers

- V2-10 and V2-11 are not implemented.
- Canonical Vercel backend project-level `DATABASE_URL` is empty and must be
  restored and verified before deployment.
- Active production Meta credentials previously failed Graph validation and
  require reauthorization.
- Current cron-job.org configuration and consecutive successful executions
  require owner/API evidence.
- The complete V2 migration chain has not been rehearsed in staging.
- Authenticated, cross-role V2 browser QA has not run.
- Physical PWA push has not been certified against the final V2 release.
- Hard-coded bootstrap/manual-test credentials remain in the repository.

### 7.4 Can Wait Until a Future Version

- Customer, Booking, Inventory, Collections, Finance and Post Sales.
- Document storage and Media.
- Room calendar/conflict scheduling.
- QR/self-check-in.
- Global search.
- Managed queue replacement, provided current workers are certified.
- Advanced analytics, forecasting and AI recommendations.
- Public APIs and enterprise SSO.

### 7.5 Final Roadmap Decision

The architecture is sufficiently complete to continue implementation without
another discovery phase. The approved remaining sequence is:

```text
V2-10 Reports
    -> V2-11 Notification Reliability
    -> V2-12A Release Rehearsal
    -> V2-12B Staging E2E
    -> V2-12C Production Rollout
```

Do not add, remove, merge or reorder these phases without updating and
reapproving this document.
