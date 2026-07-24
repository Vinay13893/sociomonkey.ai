# LMS V2 Tenant UAT Checklist

Run only on isolated staging with approved synthetic or owner-approved test data.

| Role | Required UAT |
|---|---|
| Admin | Users, permissions, configuration, allocation, reports, notification operations |
| Sales Manager | Team visibility, assignment, workload, pipeline, reports |
| Calling Manager | Caller workload, reassignment, escalations, Action Board |
| Caller | Lead actions, notes, callbacks, statuses, own Action Board |
| Relationship Manager | Assigned work, Visits, Channel Partners, Pipeline |
| Reception | Expected visits, walk-ins, check-in, queue, handoff, room, checkout |
| Platform Owner | Tenant/platform access boundaries and diagnostics |

For every role:

- [ ] Navigation contains only authorised modules.
- [ ] Create/edit/archive actions match capabilities.
- [ ] Cross-tenant access is rejected.
- [ ] Desktop layout is usable.
- [ ] Mobile/responsive layout is usable.
- [ ] Activity and notification history is correct.

Owner sign-off must include Meta ingestion, assignment push, callback reminder,
report reconciliation and rollback awareness.
