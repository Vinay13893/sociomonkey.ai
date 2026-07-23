# LMS V2 Phase 2 Results

## Status

Phase 2 organisation and permissions foundation is complete and independently deployable.
No production database, backend deployment, frontend deployment, cron job, or external
service was changed.

## Completed

- Added hierarchical organisation units and memberships.
- Added flexible, typed reporting relationships with effective dates.
- Added business roles and multiple role assignments per user.
- Added capability definitions, role grants, and user-level allow/deny overrides.
- Added scopes: Own, Team, Organisation Unit, Project, Tenant, and Platform.
- Added capability-authorised organisation administration APIs.
- Preserved legacy `User.role`, `manager_id`, and `assigned_manager_id` behavior.
- Migrated ambiguous `team_member` users to `LEGACY_TEAM_MEMBER`; no caller/RM guess was made.
- Added same-transaction activity logs for organisation and permission administration.

## Database Changes

Additive migration: `migrations/phase2_organisation_permissions_20260723.py`

New tables:

- `organisation_units`
- `organisation_unit_memberships`
- `business_roles`
- `user_business_roles`
- `reporting_relationships`
- `permission_definitions`
- `role_permissions`
- `user_permission_overrides`

The migration is host-guarded, confirmation-guarded, idempotent, and contains no
drop, truncate, delete, or legacy-table alteration.

## Recovery Branch Validation

Validated only against Neon branch `pre-lms-v2-phase1-20260722`.

| Check | Result |
|---|---|
| Pre-check | All eight Phase 2 tables absent |
| First apply | All eight tables created |
| Post-check | No tables missing |
| Second apply | Successful; aggregate counts unchanged |
| Tenant users without a role assignment | 0 |
| Cross-tenant reporting relationships | 0 |

Recovery snapshot aggregates after migration:

| Record | Count |
|---|---:|
| Organisation units | 2 |
| Business roles | 15 |
| Unit memberships | 37 |
| User role assignments | 43 |
| Reporting relationships | 16 |
| Permission definitions | 25 |
| Role grants | 141 |
| User overrides | 0 |

## API Surface

The `/api/organisation` blueprint provides bounded administration endpoints for:

- overview and organisation units
- unit memberships
- business roles and user role assignments
- reporting relationships
- permission definitions and role grants
- user permission overrides
- effective permission checks

Backend capability checks remain authoritative. Explicit user denies take precedence
over user allows and role grants. Resource-specific grants require a matching resource ID.

## Tests

- Backend contract checks: 60 passed.
- Frontend contract suites: 4 passed.
- Frontend JavaScript syntax checks: passed.
- Python compilation: passed.
- Flask blueprint registration: passed; 18 organisation routes registered.
- Git diff whitespace check: passed.

## Compatibility

- Existing login and legacy role decorators are unchanged.
- Existing manager relationships remain available to current workflows.
- Existing UI requires no Phase 2 response changes.
- The capability layer falls back to current legacy permissions while roles are migrated.

## Risks

- Role classification beyond known legacy roles requires an owner-approved user mapping.
- Production Meta credentials remain expired, as recorded in Phase 1.5; this blocks
  production readiness but does not block Phase 2 development.
- cron-job.org configuration remains unverified without authenticated API/browser access.
- The organisation administration UI is not part of this backend-foundation phase.

## Deployment Status

**Independently deployable, but production release remains NOT READY.**

Required release order when approved:

1. Apply the Phase 1 and Phase 2 migrations.
2. Deploy the backend.
3. Run capability, legacy-role, and tenant-isolation smoke tests.

Do not deploy until the Phase 1.5 production blockers are resolved.
