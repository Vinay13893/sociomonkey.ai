# Database and Migrations

## Neon topology

- Production database: Neon PostgreSQL used by canonical backend (**REPORTED**, live identity **UNVERIFIED**).
- Production branch role: live tenant system of record; never use for rehearsal.
- Recovery branch role: approved non-production schema rehearsal and rollback evidence.
- Recovery branch name: `pre-lms-v2-phase1-20260722` (**REPORTED**). Confirm in Neon before use.
- Neon project name/ID and complete hostnames: deliberately omitted; obtain read-only from owner dashboard and compare masked identifiers.

## V2 migration order

1. `migrations/phase1_reliability_20260722.py`
2. `migrations/phase2_organisation_permissions_20260723.py`
3. `migrations/phase3_business_configuration_20260723.py`
4. `migrations/phase4_locations_rooms_20260723.py`
5. `migrations/phase5_visits_20260723.py`
6. `migrations/phase6_gallery_operations_20260723.py`
7. `migrations/phase7_channel_partners_20260723.py`
8. `migrations/phase8_action_items_20260723.py`
9. `migrations/phase9_pipeline_engine_20260724.py`
10. `migrations/phase11_notification_reliability_20260724.py`

Phase 10 and Phase 12 add no schema migration. Older migrations (`rename_statuses_20260528.py`, `add_alternate_phone_to_leads_20260531.py`, `lead_sources_v2_20260612.py`, `google_foundation_phase1_20260613.py`) predate this V2 chain; verify baseline rather than blindly reapplying.

## Guards and evidence

`db_safety.py` validates database intent and requires production confirmation for guarded access. Migration scripts expose check/apply behavior and are additive/idempotent by design. Phase 12 **VERIFIED in documentation**: guarded recovery preflight, full first apply, identical second apply, final check, destructive-statement scan, rollback-only workflow and zero synthetic residue. This is not proof of production apply.

Required variable names include `DATABASE_URL`, `APP_ENV` and any script-specific expected-host/confirmation variables shown by `--help`. Never paste or log their values.

Current production migration state: **STATUS: UNVERIFIED**.

## Safe schema verification

Use the Neon dashboard or a read-only database role. Record only project/branch labels, migration presence booleans, table/column/index/capability counts and masked host fingerprint. Do not print connection strings, usernames, passwords, query parameters or full hostnames.

## Before any production database write

- [ ] Prove the canonical Vercel backend project and deployed commit.
- [ ] Prove the Neon project and exact production branch using two independent identifiers.
- [ ] Confirm a current recovery point and owner-approved maintenance window.
- [ ] Confirm tenant access/workers are handled per runbook.
- [ ] Run all migration `--help` and read-only checks first.
- [ ] Compare production schema to expected V2 state; do not infer missing/applied.
- [ ] Confirm recovery rehearsal evidence still matches the exact Git commit.
- [ ] Confirm migration order and expected locks.
- [ ] Obtain explicit owner authorization for the production write.
- [ ] Stop on target ambiguity, guard mismatch, unexpected schema, destructive SQL, or first migration error.
