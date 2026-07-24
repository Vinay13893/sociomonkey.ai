# LMS V2 Release Checklist

## Release Candidate

- [x] V2-0 through V2-11 implementation approved.
- [x] Phase 12 security blockers corrected locally.
- [x] Backend and frontend regression suites pass.
- [x] Complete migration chain rehearsed twice on the recovery branch.
- [x] Rollback-only database workflow leaves no synthetic data.
- [x] Secret-pattern scan passes.
- [ ] Confirm staging database is isolated from production.
- [ ] Create immutable backend/frontend release tags or record commit hashes.

## Staging Certification

- [ ] Deploy backend to the canonical staging project.
- [ ] Apply migrations in the rehearsed order.
- [ ] Deploy frontend to the canonical staging project.
- [ ] Run authenticated desktop/responsive QA for every role.
- [ ] Validate Meta OAuth, webhook signature and one controlled lead.
- [ ] Validate notification drain and reminder processor twice.
- [ ] Validate Android and iOS push and deep links.
- [ ] Measure endpoint budgets, DB connections and Neon usage.
- [ ] Obtain tenant UAT sign-off.

## Production Gate

- [ ] Record production branch/deployment IDs and fresh Neon rollback point.
- [ ] Confirm production environment variable presence and owner validation.
- [ ] Confirm only approved schedulers are enabled.
- [ ] Approve maintenance window and rollback authority.
- [ ] Apply migrations, backend, frontend in that order.
- [ ] Run smoke tests before restoring tenant access.
- [ ] Monitor at 1 hour, 24 hours, 7 days and 14 days.
