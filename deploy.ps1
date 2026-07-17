# Deploy frontend_static -> lms.sociomonkey.com (prj_A6b6jLRXwpf5axKz1MNEqpr9j0Vl)
# Run THIS file to deploy frontend. Never run vercel deploy from backend directory for frontend.
Set-Location "d:\AI\Scripts\sociomonkey.ai\mvp\frontend_static"
# Deploy frontend_static -> lms.sociomonkey.com (prj_A6b6jLRXwpf5axKz1MNEqpr9j0Vl)
# This script is the only approved frontend deploy path.

$projectLockPath = Join-Path $PSScriptRoot 'deploy-target.json'
if (-not (Test-Path $projectLockPath)) {
	throw "Missing deploy lock file: $projectLockPath"
}

$projectLock = Get-Content $projectLockPath -Raw | ConvertFrom-Json
if ($projectLock.projectId -ne 'prj_A6b6jLRXwpf5axKz1MNEqpr9j0Vl' -or $projectLock.projectName -ne 'frontend_static') {
	throw "Deploy lock mismatch. Expected frontend_static project prj_A6b6jLRXwpf5axKz1MNEqpr9j0Vl."
}

vercel deploy --prod --yes --scope vinay13893s-projects --cwd $PSScriptRoot --project $projectLock.projectId
