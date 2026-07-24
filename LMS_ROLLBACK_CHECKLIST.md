# LMS V2 Rollback Checklist

## Rollback Triggers

- Migration error or schema mismatch.
- Tenant-isolation or permission regression.
- Login/OTP failure for existing users.
- Lead ingestion loss or uncontrolled duplicates.
- Pipeline/history mutation defect.
- Notification/reminder retry storm.
- Sustained 5xx rate, database saturation or critical PWA failure.

## Application Rollback

1. Keep tenant access disabled.
2. Disable only newly enabled scheduler execution; preserve job definitions.
3. Reassign the backend alias to the recorded prior deployment.
4. Reassign the frontend alias to the recorded prior deployment.
5. Verify health, login and read-only tenant access.

## Database Rollback

The V2 migrations are additive. Prefer application rollback while leaving
additive schema in place. Do not run ad hoc destructive reverse migrations.

If data/schema recovery is required:

1. Stop application writes.
2. Confirm rollback authority and incident timestamp.
3. Use the recorded Neon recovery branch/snapshot.
4. Validate recovered schema and tenant aggregates before reconnecting services.
5. Record all lost-write implications and obtain owner approval.

Never expose connection strings or copy production data into an unapproved
environment.
