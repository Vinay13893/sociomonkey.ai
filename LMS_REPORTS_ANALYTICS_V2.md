# LMS V2 Reports and Analytics Contract

## Purpose

V2 analytics reads the existing LMS systems of record. It does not create a
reporting warehouse, summary table, materialized view or transactional copy.
The existing Management Overview and Dashboard contracts remain unchanged.

## API Contract

| Route | Capability | Purpose |
|---|---|---|
| `GET /api/reports/v2/filters` | `reports.view` | Return only filter options visible within the caller's resolved scope |
| `GET /api/reports/v2/{report}` | `reports.view` | Return a bounded interactive SQL aggregate |
| `GET /api/reports/v2/{report}/export` | `reports.export` | Download a separate aggregate-only XLSX |

Supported filters are `date_from`, `date_to`, `project_id`, `location_id`,
`user_id`, `organisation_unit_id` and `limit`.

- Dates use `YYYY-MM-DD`.
- The default period is the most recent 30 days.
- Interactive periods are limited to 366 days.
- Interactive responses are limited to 100 aggregate rows.
- Exports are limited to 5,000 aggregate rows.
- An out-of-scope user or organisation-unit filter is rejected.

## Report Families

| Key | System of record | Primary measures |
|---|---|---|
| `pipeline` | Leads, immutable Pipeline Transitions, status configuration | Active Leads, entries, exits, net movement, average stage hours, conversion |
| `leads` | Leads and status configuration | Leads, assignment, source outcomes, conversion |
| `organisations` | Organisation Units, memberships, Leads, Action Items | Users, Leads, Actions, completion |
| `users` | Users, Leads, Visits, Action Items | Workload, Visits, completed and overdue Actions |
| `projects` | Projects, Leads, Visits | Lead volume, Visit volume and completion |
| `locations` | Locations, Visits, Meeting Rooms | Visit activity, completion and room inventory |
| `visits` | Visits and Visit configuration | Type/status volume, visitors, duration and completion |
| `reception` | Visits and Locations | Arrivals, inside, walk-ins and no-shows |
| `meeting-rooms` | Meeting Rooms, Locations and Visits | Capacity, current status and Visit usage |
| `channel-partners` | Channel Partners, Leads and Visit Participants | Attributed Leads, Visits and engaged partners |
| `action-items` | Action Items | Workload, completion, overdue and priority |

Configured display labels are used where a configuration already exists.
Internal status keys and historical records remain unchanged.

## Scope and Permissions

The route decorator is the first authorization gate. The reporting service then
resolves the strongest permitted scope in this order:

1. Tenant
2. Team
3. Organisation Unit
4. Own

Every aggregate includes an explicit tenant predicate. Team and organisation
scopes also constrain the visible users and their related records. The backend
is authoritative; frontend controls do not grant access.

## Performance Contract

- Aggregation is performed in SQL.
- Transactional tables are not loaded into Python for aggregation.
- Independent per-entity aggregate subqueries prevent join multiplication.
- Only one report family is requested by the frontend at a time.
- Filter option lists are bounded to 200 rows per entity.
- Large transactional exports continue to use their existing dedicated
  workflows; the V2 export contains aggregates only.
- No speculative cache, index or reporting store was added.

Indexes should be added only after staging or production query evidence shows a
specific scan or latency problem.

## Frontend Contract

The Reports module now has two modes:

- Management Overview: the existing report workspace, unchanged.
- Operational Analytics: V2 filters, KPIs, one compact distribution chart,
  aggregate table, module drill-down and separate export.

The frontend displays generated timestamps in `Asia/Kolkata` and preserves the
existing API authentication and tenant context.

## Compatibility

- Existing Dashboard APIs and behavior are unchanged.
- Existing report routes and exports are unchanged.
- No Lead, Visit, Pipeline, Channel Partner or Action Item history was updated.
- No migration is required for V2-10.

