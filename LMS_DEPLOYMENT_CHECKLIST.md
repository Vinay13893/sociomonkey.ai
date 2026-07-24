# LMS V2 Deployment Checklist

## Before Staging

- [ ] Verify Vercel project IDs, branches and aliases.
- [ ] Verify staging `DATABASE_URL` points only to the approved staging/recovery
      branch; do not print it.
- [ ] Verify required application, OAuth, VAPID and cron variables by presence.
- [ ] Record current rollback deployments.

## Staging Order

1. Freeze the release commit set.
2. Apply migrations in the order documented in `LMS_PHASE12_RESULTS.md`.
3. Deploy backend.
4. Verify health, unauthenticated rejection, schema and capability seeds.
5. Deploy frontend.
6. Execute browser, integration, scheduler, PWA and capacity certification.

## Production Order

1. Obtain UAT and owner approval.
2. Record a fresh Neon recovery branch and current Vercel deployment IDs.
3. Start the maintenance window.
4. Apply the rehearsed additive migration chain.
5. Deploy the canonical `backend` project.
6. Run backend health/auth/worker smoke checks.
7. Deploy `frontend_static`.
8. Run tenant login and role/workflow smoke checks.
9. Confirm scheduler ownership and first successful executions.
10. Restore tenant access and begin monitoring.

Stop immediately on migration failure, health failure, authentication regression,
tenant-isolation failure, ingestion failure or sustained queue backlog.
