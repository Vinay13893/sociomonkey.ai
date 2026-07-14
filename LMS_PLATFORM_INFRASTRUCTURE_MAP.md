# LMS / Platform Infrastructure Map

Date: 2026-07-14
Scope: Phase 1 infrastructure containment.

No secrets are recorded in this document.

## Canonical LMS Assets

| Asset | Canonical value |
|---|---|
| LMS frontend | `https://lms.sociomonkey.com` |
| LMS frontend Vercel project | `frontend_static` |
| LMS backend API | `https://smk-backend-api.vercel.app` |
| LMS backend Vercel project | `backend` |
| LMS production database | Neon PostgreSQL, masked identity only |

## Canonical Platform Assets

| Asset | Canonical value |
|---|---|
| Platform frontend | `https://app.sociomonkey.com` |
| Platform frontend Vercel project | `sociomonkey-platform-web` |
| Platform API | `https://sociomonkey-platform-api.vercel.app` |
| Platform API Vercel project | `sociomonkey-platform-api` |

## Legacy Railway LMS Assets

| Asset | Value |
|---|---|
| Railway project | `sociomonkey-backend` |
| Production public URL | `https://sociomonkey-backend-production.up.railway.app` |
| Staging public URL | `https://sociomonkey-backend-staging.up.railway.app` |
| Repository root | `backend` |
| Status before Phase 1B-2 | Legacy fallback, not yet decommissioned |

## Backend Staging

| Asset | Value |
|---|---|
| Vercel project | `backend-staging` |
| Domain | `https://backend-staging-phi.vercel.app` |
| Risk | Staging project has production Neon database access and must be isolated in a later phase. |

## Legacy Aliases

| Alias | Status |
|---|---|
| `backend-nu-nine-20.vercel.app` | Legacy LMS backend alias/reference; needs callback and scheduler verification before cleanup. |
| `sociomonkey-ai.vercel.app` | Legacy/frontend alias/reference; needs callback and scheduler verification before cleanup. |
| Vercel project aliases | Must not be removed until external callbacks and schedulers are verified. |

## Scheduler Status

| Scheduler | Status |
|---|---|
| Vercel crons in `backend/vercel.json` | Configured and intentionally unchanged in Phase 1. |
| cron-job.org | Not yet verified; dashboard/API access required before changes. |
| Railway cron | No active cron configured in the inspected Railway LMS environments. |
| GitHub Actions | No root backend workflow evidence found. |
| Windows Scheduled Tasks | No matching local scheduled tasks found. |

## Shared Database Boundary

The LMS database contains LMS tables and platform/control-plane-looking tables in the same database/schema. Until this boundary is fully separated, Platform database credentials must not be removed as part of LMS-only cleanup.

## Ownership Uncertainties

The following require explicit verification before cleanup:

- Meta webhook URLs and retry history.
- Google OAuth and lead-form callback URLs.
- cron-job.org active job inventory.
- Whether Platform intentionally shares the LMS Neon database.
- Whether legacy Vercel aliases are still referenced by external systems.
