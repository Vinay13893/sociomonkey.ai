# Claude Code Takeover Prompt

You are taking over the Sociomonkey LMS controlled production release. You
have no reliable prior chat context. **Production is already deployed** — do
not restart the release from scratch or re-run migration/deployment steps
unless live evidence contradicts this package.

Read every file in `D:\AI\release_worktrees\backend-final-freeze\handover`,
beginning with `00_START_HERE.md`, in its stated order, plus
`../LMS_PRODUCTION_RELEASE_REPORT.md`. Use only:

- backend `D:\AI\release_worktrees\backend-final-freeze`
- frontend `D:\AI\release_worktrees\frontend-final-freeze`

Never work or deploy from `D:\AI`; parent Vercel state previously caused
project/root confusion (now resolved, but stay out of `D:\AI` regardless).

**Check for a browser automation tool before assuming you don't have one** —
search thoroughly (Playwright/Puppeteer/computer-use/screenshot/click
keywords). As of this writing no such tool exists in this environment; if that
is still true for you, you cannot drive interactive Meta OAuth, inspect the
cron-job.org dashboard, or perform authenticated browser QA yourself. Guide
the owner through the exact click path one step at a time instead, and verify
each result afterward via read-only Graph API and database queries (see
`../release_prod_observability.py` and `../release_prod_guard.py` at
`D:\AI` for the established read-only query pattern using
`PRODUCTION_DATABASE_URL`).

Start with a read-only re-verification of Git, Vercel, live LMS health and
Meta source status — this package's evidence should still hold, but re-check
rather than assume. Do not deploy, promote aliases, re-migrate, edit
environment/configuration, alter cron jobs, push, commit, or create features
until any conflicting evidence is resolved and explicit authorization is
given for the specific write in question. Never expose credentials, URLs
containing secrets, tokens, passwords, cookies or authorization headers.

**The only known critical blocker: all four Meta source tokens (IDs 11, 12,
13, 14) return Graph OAuth error 190 / subcode 460.** Everything else —
deployment, migrations, schedulers, notification/reminder queue — is
certified healthy as of this package's last refresh. Do not re-litigate those
unless live evidence disagrees.

**Also open:** neither backend nor frontend release commits exist on any
remote Git branch, and the local branch has no remote counterpart. Do not
push without the owner picking one precise target branch.

Preserve existing sources, mappings, Leads and ownership boundaries. No new
features or broad cleanup. Continue only the controlled release gates in the
documented order.

Pause immediately if a project/alias/build root/commit, Neon branch,
environment metadata, external account, scheduler authority, rollback target,
tenant-safe test record, or git push target cannot be proven; if a secret
would be printed; if schema differs unexpectedly; if migration/health/auth/
tenant-isolation fails; or if requested work exceeds the release scope.

At completion update `../LMS_PRODUCTION_RELEASE_REPORT.md` with final Meta
certification evidence, writes performed with approval, deployment IDs/
commits, QA and rollback state, and state exactly one of: Production Ready /
Production Ready with Minor Issues / Production Blocked. Never claim success
for an unverified gate, and never mark Meta complete without genuine live
ingestion evidence.
