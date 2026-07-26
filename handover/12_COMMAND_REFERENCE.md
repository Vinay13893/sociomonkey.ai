# PowerShell Command Reference

All commands are non-destructive unless explicitly marked. Inspect output before sharing; redact sensitive identifiers.

```powershell
# READ ONLY — select worktrees
Set-Location -LiteralPath 'D:\AI\release_worktrees\backend-final-freeze'
Set-Location -LiteralPath 'D:\AI\release_worktrees\frontend-final-freeze'

# READ ONLY — Git identity/status/history/remotes/upstream
git status --short --branch
git log --oneline --decorate -30
git remote -v
git rev-parse HEAD
git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'

# LOCAL WRITE — tests may create caches only; no application/source changes.
# Current default Python 3.14 has no pytest. First recreate/activate the approved
# Python 3.11 test environment from requirements.txt without using production env.
python -m pytest -q --ignore=test_login.py --ignore=test_app.py
Get-ChildItem -File test_*_contract.js | ForEach-Object { node $_.FullName }
python -m compileall -q app migrations api
Get-ChildItem -Recurse -File -Include *.js | Where-Object { $_.FullName -notlike '*\node_modules\*' } | ForEach-Object { node --check $_.FullName }

# READ ONLY — whitespace, route duplication and migration help/check discovery
git diff --check
python -c "from app import create_app; a=create_app(); r=[(x.rule,tuple(sorted(x.methods-{'HEAD','OPTIONS'}))) for x in a.url_map.iter_rules()]; assert len(r)==len(set(r)); print(len(r),'unique route/method contracts')"
Get-ChildItem .\migrations\phase*.py | ForEach-Object { python $_.FullName --help }

# READ ONLY — credential-shaped scan; filenames/line numbers only
rg -l -i --hidden -g '!handover/**' -g '!.git/**' '(postgres(ql)?://|authorization\s*:|cookie\s*:|password\s*=|access[_-]?token\s*=|client[_-]?secret\s*=|private[_-]?key\s*=)' .

# READ ONLY — live health (no authenticated routes)
(Invoke-WebRequest -UseBasicParsing -Uri 'https://smk-backend-api.vercel.app/api/health' -TimeoutSec 20).StatusCode
(Invoke-WebRequest -UseBasicParsing -Uri 'https://lms.sociomonkey.com' -Method Head -TimeoutSec 20).StatusCode

# READ ONLY — Vercel deployment/alias inspection
vercel inspect https://smk-backend-api.vercel.app
vercel inspect https://lms.sociomonkey.com
vercel ls backend
vercel ls frontend_static

# READ ONLY — environment metadata only; do not use env pull or print values
vercel env ls production --project backend
vercel env ls production --project frontend_static

# READ ONLY — guarded migration interface; run --help before any check
python .\migrations\phase1_reliability_20260722.py --help
python .\migrations\phase11_notification_reliability_20260724.py --help
```

Migration `--check` may still connect to a database. It is READ ONLY only after the target is independently proven, a read-only role is used, and command help confirms check behavior. Do not place database URLs on the command line.

**PRODUCTION WRITE — not authorized by this handover.** Approved historical deployment commands are in `LMS_DEPLOYMENT_CHECKLIST.md` and `LMS_DEPLOYMENT_RUNBOOK.md`. Do not copy/run them until explicit target verification and owner approval. No Meta, cron, alias or database write command is included here.
