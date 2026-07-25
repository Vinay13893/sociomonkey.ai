# LMS Reception Workflow Stabilization — Results

Date: 25 July 2026 (Asia/Kolkata)

See [LMS_RECEPTION_WORKFLOW_STABILIZATION.md](LMS_RECEPTION_WORKFLOW_STABILIZATION.md)
for the full architecture/decisions writeup. This file records the
verification evidence.

## Backend

| Check | Result |
|---|---|
| Full bounded pytest suite | **146 passed**, 0 failed (139 pre-existing + 7 new) |
| Python compilation (`app`, `migrations`, `api`) | Clean, 0 failures |
| Duplicate route/method registration | 0 (301 unique route/method contracts, up from 300: +1 for the new `planned-visit` GET) |
| Secret-pattern scan | Passed — no new/modified file in this initiative matched |
| `visits.py` regression after `visit_builder.py` extraction | 14/14 visit tests passed, confirming zero behavior change from the refactor |

New backend test files:

- `test_reception_walkin_stabilization.py` (3 tests): Project active-filter,
  unregistered Channel Partner walk-in (plus the still-required-name
  rejection), atomic new-Lead walk-in with duplicate-phone rejection and
  assignment-defaults-to-lead-owner.
- `test_pipeline_site_visit_planning.py` (4 tests): Visit creation +
  transition linkage, duplicate active-planned-visit rejection,
  callback_payload atomicity, plain-move regression guard (no
  `visit_payload` ⇒ completely unaffected, zero Visits created).

One pre-existing static contract test
(`test_phase5_visits_contract.py::test_every_reference_is_tenant_validated_and_room_matches_location`)
needed updating after the extraction, since it asserted the validation
logic's literal presence in `visits.py` specifically. Updated to check the
new location (`app/services/visit_builder.py`) — the invariant it verifies
(every reference is tenant-validated, room must match the visit's location)
is unchanged, confirmed still true.

## Frontend

| Check | Result |
|---|---|
| All contract test suites | **15 passed**, 0 failed (12 pre-existing + 3 new) |
| JS syntax sweep (all files under `src/`) | Clean, 0 failures |

New frontend test files:

- `test_site_visit_planning_dialog_contract.js`: dialog exists and checks
  for an existing planned visit first; drives the flow through the pipeline
  move endpoint with `visit_payload`/`callback_payload` (not a bare status
  PUT); cancel never calls the API (verified by source-order assertion, not
  just presence); both inline-status entry points (Leads table, Action
  Board) intercept `site_visit_planned` before firing the plain move.
- `test_single_date_picker_contract.js`: the picker is genuinely single-date
  (no `draftTo`/`in-range` range-machinery leaked in from a copy-paste),
  mounts on the existing `#receptionDate` id, and is loaded from `index.html`.

One pre-existing contract test
(`test_gallery_operations_phase6_contract.js`) needed updating: it asserted
the literal string `"Lead ID (optional)"` — the raw numeric input that was
intentionally replaced by the search-first lookup. Updated to check for the
new lookup UI's markers instead; the invariant (walk-in can associate an
existing Lead) is unchanged.

## Deployment

Deployed 25 July 2026 ~18:25 IST.

- Backend: `dpl_48krSjoPfGHci6x1spNXSms1iFt6`, project `backend`, commit `641bd00`. Deployed directly from `D:\AI\release_worktrees\backend-final-freeze` (same directory that worked cleanly for the earlier webhook fix).
- Frontend: `dpl_BdQeJQWMXfMhwhiM5nLbXGzmpvbW`, project `frontend_static`, commit `1c5d36d`.

### Deployment incident (second occurrence) and fix

Deploying the frontend directly from `frontend-final-freeze` sent the build
to the **`backend`** Vercel project again, despite that directory's own
`.vercel/project.json` correctly specifying `frontend_static` — the exact
incident already documented in `LMS_PRODUCTION_RELEASE_REPORT.md` from the
original release. Root cause identified this time: **`D:\AI\.vercel\project.json`
is linked to the `backend` project**, and something in Vercel CLI's project
resolution prefers that parent-directory link over the correct one in the
worktree. `lms.sociomonkey.com` was briefly aliased to a `backend`-project
deployment (which happened to still be serving correct frontend HTML
content, so there was no user-facing outage, but the project association
was wrong).

Fix applied: immediately reassigned the alias back to the last-known-good
`frontend_static` deployment, then deployed the actual new frontend build
from a fully isolated directory outside `D:\AI` (`git archive` of the
frontend worktree's HEAD into a scratch directory, linked via `vercel link
--project=frontend_static` rather than hand-copying config), matching the
same fix already used once before. Verified after redeploy: `vercel
inspect` confirms project `frontend_static`; `reception.js` and `leads.js`
served from the live domain contain the new code (`Find existing lead`,
`openSiteVisitPlanningDialog`); health, root, and tenant login route all
return HTTP 200.

**Standing infrastructure risk, not yet resolved:** `D:\AI\.vercel` should
not exist, or should not be linked to `backend` — its presence is what
causes this incident to recur. Recommend either deleting
`D:\AI\.vercel` entirely (nothing should ever deploy from the `D:\AI` root)
or relinking it to a project that can't be mistaken for a real target.
Until that's done, **any future frontend deployment must use the same
isolated-directory approach**, not a direct deploy from
`frontend-final-freeze`, even though that directory's own link file is
correct.

## Manual Production Verification Checklist (deployment complete; functional checklist below still pending)

Per the stabilization document's rollout plan, before/after deploying:

- [ ] Create one guided Site Visit Planned Lead; confirm a `SCHEDULED` Visit
      appears in Reception's Expected queue for the right date/location.
- [ ] Attempt a second Site Visit Planned on the same Lead; confirm the
      "existing visit" prompt appears instead of a silent duplicate.
- [ ] Walk-in with an existing Lead found via the new search box; confirm
      no duplicate Lead is created and the Visit links to the found Lead.
- [ ] Walk-in creating a brand-new Lead (name + phone, no existing match);
      confirm exactly one Lead and one Visit are created, and the Lead
      appears in the Leads list.
- [ ] Repeat the same new-Lead walk-in with the same phone number; confirm
      a `409 duplicate_phone` is returned and no second Lead is created.
- [ ] Unregistered Channel Partner walk-in; confirm it saves with a
      free-text name and no `ChannelPartner` reference is created.
- [ ] Verify via direct DB read (not UI alone) that Lead/Visit/ActivityLog/
      NotificationEvent rows look correct for each scenario above and no
      duplicates exist.

## Summary

All code-level verification (tests, compilation, route integrity, secret
scan) is complete and green. Deployment and the manual production checklist
above remain outstanding — see the "Deployment and Rollback Notes" section
of the stabilization document.
