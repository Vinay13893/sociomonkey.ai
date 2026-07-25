# LMS Reception and Site Visit Workflow Stabilization

Date: 25 July 2026 (Asia/Kolkata)

Status: Production stabilization and UX correction initiative, not a new
product phase. All items are additive; no destructive migrations were
required (no schema changes at all — every gap closed by reusing existing
columns/tables).

Backend commit: `641bd00` (on top of the `417889d` production release,
which itself sits on `f3e4592`)

Frontend commit: `1c5d36d` (on top of `fb0b5d9`)

## 1. Original Problems and What the Audit Actually Found

The initiative was requested from screenshots of the live Reception module
that appeared to show several gaps. A read-only audit against the actual
backend/frontend code (not the screenshots alone) found the module
healthier than it looked:

| Screenshot-suggested problem | Audit finding |
|---|---|
| Reception has no direct per-row actions, only tabs + "Register walk-in" | **Not a real gap.** `receptionRowActions()` already renders state-gated buttons (Check In, No Show, Waiting, Call, Start Meeting, Assign, Room, Check Out). The screenshotted visit was `Completed`, which correctly shows "No action required" — that's correct behavior, not a missing feature. |
| Reception search only filters already-rendered rows | **Not a real gap.** Search was already backend-driven (`GET /gallery-operations/visits?search=`, ilike against `Visit.purpose/source` and `Lead.name`). |
| Register Walk-in doesn't create Visit+Lead+notification atomically | **Not a real gap** for what existed (Visit + participant + audit + notification was already one transaction). The real gap was narrower: it didn't yet support creating a *new* Lead in that same transaction (see §3). |
| Visit state transitions aren't validated | **Not a real gap.** `_transition()` already enforces an explicit allowed-from table, tested by existing contract/integration tests. |

The confirmed, real gaps — the actual scope of this initiative — were:

1. Reception's date filter used a native `<input type="date">`, inconsistent with the rest of the app's shared date-picker component.
2. The walk-in modal had no way to search for or associate an existing Lead by name/phone (only a raw numeric "Lead ID" field), no duplicate-phone protection when creating a new Lead, and no path for an *unregistered* Channel Partner.
3. The Project reference list in the walk-in form wasn't filtered to active projects (inconsistent with Location/Room/User/Channel Partner in the same endpoint).
4. Changing a Lead's status to "Site Visit Planned" only updated the status field — it never created an actual Visit, reception queue entry, or optional callback.
5. `Lead.assigned_to` and `Visit.assigned_user_id` were separate, unsynced fields with no code path connecting them.

## 2. Decisions Made With the Owner

Two things had no existing code to reuse and needed an explicit decision
before implementation:

- **Auto-allocation engine**: no rules-based auto-assignment exists anywhere
  in the codebase today (all Lead and Visit assignment is manual). Building
  one is a genuinely large, separate initiative. **Decision: skip it for
  this pass.** The walk-in and Site Visit Planned dialogs offer manual
  "Select Responsible User" and an explicit "Assign later" option — no
  "Auto Assign" button was added.
- **Lead ↔ Visit ownership**: **Decision: a Visit defaults to the Lead's
  current `assigned_to` at the moment the Visit is created, but this is a
  one-time default, not continuous syncing.** If the Lead is reassigned
  later, existing Visits do not silently change. An explicit
  `assigned_user_id` in the walk-in/planning form always overrides the
  default.

## 3. What Changed

All work reused existing validation, notification, callback, and audit
machinery. The one structural change was extracting Visit-payload
validation out of `visits.py` into a new shared module so other routes
could reuse it without importing another routes file.

### `app/services/visit_builder.py` (new)

Extracted from `app/routes/visits.py`: `validate_visit_payload`,
`validate_reference`, `validate_user`, `validate_configuration`,
`parse_datetime` — same logic, now parameterized by `tenant_id` explicitly
instead of reading `request.current_user` internally, so `pipeline.py` and
`gallery_operations.py` can call them directly. `visits.py` now calls these
via same-named thin wrappers; verified zero behavior change against the
full existing test suite.

Also added here (new logic, not extracted): `find_duplicate_lead_by_phone`
and `create_lead_row` (mirroring `leads.py`'s `create_lead()` duplicate
check and `Lead(...)` construction exactly — no phone normalization added,
preserving existing matching behavior against live tenant data),
`default_visit_assigned_user` (the inherit-with-override rule from §2), and
`active_planned_visit_for_lead` (duplicate-planned-visit detection).

### `app/routes/gallery_operations.py`

- `references()`: Project list now filters `is_active=True`, matching
  Location/Room/User/Channel Partner in the same endpoint.
- `create_walk_in()`:
  - Accepts a `new_lead` dict (`name`, `phone`, `alternate_phone`, `email`,
    `source`) when no `lead_id` is supplied. Runs the duplicate-phone check
    first and returns `409 {'error':'duplicate_phone','existing_lead':{...}}`
    immediately if found — matching `create_lead()`'s existing contract
    exactly. Otherwise creates the Lead, flushes to get its id, and
    continues into the existing participant/Visit branch unchanged. Same
    single commit as before — Lead + Visit + participant + audit + push
    notification remain one atomic transaction.
  - `Visit.assigned_user_id` now defaults to the Lead's `assigned_to`
    (existing or newly-created Lead) via `default_visit_assigned_user` when
    no explicit value is supplied.
  - Channel Partner walk-ins with no registered-partner reference are now
    accepted (previously raised "Channel Partner is required"), falling
    through to the same free-text `display_name` path
    OTHER/VENDOR/INTERNAL_VISITOR already use, tagged
    `participant_metadata.unregistered = True`.
  - Response includes `'lead'` when a new one was created.

### `app/routes/pipeline.py`

`move_pipeline_lead()` (`POST /api/pipeline/leads/<id>/move`) gains optional
`visit_payload` and `callback_payload`. When `to_status ==
'site_visit_planned'` and no `visit_id` is supplied but `visit_payload` is:

1. Checks `active_planned_visit_for_lead()` first — returns `409
   {'error':'active_planned_visit_exists','visit':{...}}` unless the caller
   passes `force_new_visit: true`, instead of silently creating a duplicate.
2. Builds the Visit via `validate_visit_payload` (status forced to
   `SCHEDULED`, `lead_id` forced to this Lead), with `assigned_user_id`
   defaulted per §2 unless explicit.
3. Passes the Visit into the existing `transition_lead(visit=...)` call —
   unchanged from before this initiative, which already accepted `visit=`.
4. Optionally creates a callback via the existing
   `create_callback_for_lead()` when `callback_payload` is present.

All of this happens inside the endpoint's existing try/except and single
final commit — one atomic transaction for status change + Visit + callback.
A plain `to_status` move without `visit_payload` (bulk updates, manager
overrides, an explicit pre-existing `visit_id`) is completely unaffected —
verified by a dedicated regression test.

New `GET /api/pipeline/leads/<id>/planned-visit` lets the frontend check for
an existing planned Visit before opening the dialog.

### Frontend (`frontend-final-freeze`)

- **`reception.js`**: walk-in modal's raw "Lead ID" input replaced with a
  debounced (300ms) search box against `GET /api/leads?search=` (reusing
  the existing endpoint and its tenant-scoped visibility rules rather than
  building a parallel lookup); selecting a result sets the Lead to use.
  When no Lead is selected and a phone number is entered, the payload
  includes `new_lead` so the backend creates one atomically. Also: native
  date input replaced with a small shared-style single-date picker.
- **`leads.js`**: new `openSiteVisitPlanningDialog(leadId, onDone)` — checks
  for an existing planned Visit first (offers to view it instead of
  duplicating), then collects date/time, visit type, location, project,
  responsible user (with "Assign later"), visitor count, room, Channel
  Partner, notes, and an optional callback sub-section, submitting
  everything in one call to the pipeline move endpoint. Wired into both the
  inline status `<select>` and the detail-panel "Update Status" form; only
  the `site_visit_planned` target is intercepted, every other status
  transition is untouched. Cancel never calls the API.
- **`action-board.js`**: same interception on its inline status `<select>`.
- **`single-date-picker.js`** (new): a small single-date component (Today/
  Yesterday presets + a month grid) reusing the existing app-wide date-
  picker's visual classes, not a retrofit of its range-only state machine.

## 4. State Transition Map (Visit lifecycle — unchanged, documented for reference)

```
SCHEDULED ──check-in──> CHECKED_IN ──┬─waiting──> WAITING ─call──> CALLED
                                      │                              │
                                      ├──────────in-meeting──────────┤
                                      │                              ▼
                                      └─────────────────────────> IN_MEETING ──check-out──> COMPLETED
SCHEDULED ──no-show──> NO_SHOW
```

Enforced by `_transition()` in `gallery_operations.py` (unchanged by this
initiative — the state machine was already correct; this document exists to
make it explicit for anyone extending Reception next).

## 5. API Contracts Added or Changed

| Endpoint | Change |
|---|---|
| `GET /api/gallery-operations/references` | `projects` now excludes inactive projects |
| `POST /api/gallery-operations/walk-ins` | Accepts `new_lead` (creates Lead atomically, dup-phone protected); `participant.type=CHANNEL_PARTNER` no longer requires `reference_id`; response includes `lead` when one is created |
| `POST /api/pipeline/leads/<id>/move` | Accepts optional `visit_payload` and `callback_payload`; when `to_status=site_visit_planned`, builds a Visit and optional callback atomically with the transition; response includes `visit` |
| `GET /api/pipeline/leads/<id>/planned-visit` | New — returns the Lead's current active planned Visit, if any |

## 6. Permissions

No new capabilities were introduced. All new/changed behavior sits behind
the same capability checks the surrounding endpoints already enforced:
`gallery.check_in` for walk-ins, `pipeline.move` for the guided planning
flow (including the new `planned-visit` lookup). Cross-tenant references
(Location, Project, Lead, Channel Partner, User) continue to be validated
tenant-scoped by the shared `validate_reference` helper.

## 7. Testing Evidence

See [LMS_RECEPTION_STABILIZATION_RESULTS.md](LMS_RECEPTION_STABILIZATION_RESULTS.md)
for full results. Summary: 146 backend tests passed (139 pre-existing + 7
new), all frontend contract suites passed (12 pre-existing + 3 new), Python
compilation clean, 301 unique route/method contracts with zero duplicates,
secret-pattern scan clean.

## 8. Deployment and Rollback Notes

Not yet deployed as of this document's creation. Both backend (`641bd00`)
and frontend (`1c5d36d`) worktrees are clean and locally committed, not yet
pushed to any remote branch (consistent with the rest of this release
train — see `LMS_PRODUCTION_RELEASE_REPORT.md`).

No schema/migration changes were required for any part of this initiative —
every gap was closed using existing columns and tables. Rollback, if ever
needed, is a plain Vercel alias reassignment to the prior deployment; there
is no database rollback concern specific to this work.
