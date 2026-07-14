# Local Secret Exposure Review

Date: 2026-07-14
Scope: Phase 1B-1 repository containment for the Sociomonkey LMS backend.

## Summary

This review covers local maintenance, diagnostic, cleanup, and migration scripts that can connect to a database. The goal is to prevent accidental production Neon access from local scripts without changing live LMS infrastructure.

No secrets are recorded in this document.

## Script Classification

| Script | Classification | Production-capable | Guard added |
|---|---|---:|---:|
| `check_leads.py` | read-only diagnostic | Yes | Yes |
| `dedup_leads.py` | destructive maintenance | Yes | Yes |
| `show_neon_schema.py` | read-only diagnostic | Yes | Yes |
| `migrate_to_neon.py` | destructive migration | Yes | Yes |
| `migrate_add_otp_codes.py` | migration | Yes | Yes |
| `migrations/rename_statuses_20260528.py` | destructive migration | Yes | Yes |
| `migrations/add_alternate_phone_to_leads_20260531.py` | migration | Yes | Yes |
| `migrations/google_foundation_phase1_20260613.py` | migration | Yes | Yes |
| `migrations/lead_sources_v2_20260612.py` | migration | Yes | Yes |
| `check_db.py` | local-only SQLite diagnostic | No | Not required |
| `_migrate_local.py` | local-only SQLite migration | No | Not required |
| `_seed_local.py` | local-only SQLite seed | No | Not required |

## Guards

Production-like database URLs are blocked unless:

```text
ALLOW_PRODUCTION_DB_OPERATION=true
```

Destructive operations are additionally blocked unless:

```text
CONFIRM_DESTRUCTIVE_DB_OPERATION=true
```

Production-like means a database URL using a Neon host, `APP_ENV=production`, `FLASK_ENV=production`, or `DATABASE_IS_PRODUCTION=true`.

## Credential Handling

Scripts now read database URLs from environment variables instead of hard-coded connection strings.

Scripts display only a masked database identity, for example:

```text
postgresql://user:***@*.neon.tech/database
```

They must not print the raw database URL, token, password, or connection string.

## Confirmed Removed Exposure

The previous hard-coded production Neon connection strings in:

- `dedup_leads.py`
- `check_leads.py`

were removed.

## Remaining Local Risk

Local `.env*` files may still contain credentials and are intentionally not inventoried here by value. They should be rotated and reviewed outside git if access to local command transcripts or workstations is not tightly controlled.

## Operational Note

These changes do not execute any production database operation. They only add local execution guards.
