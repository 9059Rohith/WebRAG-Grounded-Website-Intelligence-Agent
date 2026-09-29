# CI workflow preserved for owner activation

[ci.yml](ci.yml) preserves the full assessment workflow. It checks Python 3.11/3.12, Ruff and formatting, strict application/evaluation types, Bandit, the documented dependency audit, offline tests with an 85% coverage threshold, a Node 22 frontend build and dependency audit, Docker configuration, image build, and empty-index health/readiness behavior.

The publication credential could not modify `.github/workflows/ci.yml` because its workflow permission was missing. The workflow is kept here so the source submission can be published without that restricted path. **It is currently inactive:** GitHub only discovers this workflow after it is restored under `.github/workflows/`. Moving the file is a publication fallback, not evidence that remote CI passed.

The repository owner can activate it using an authenticated GitHub identity authorized to modify workflow files, or create the file through the repository's web editor while signed in as an authorized owner. For a local activation in PowerShell:

```powershell
New-Item -ItemType Directory -Force .github/workflows | Out-Null
Copy-Item -LiteralPath docs/ci/ci.yml -Destination .github/workflows/ci.yml
```

Remove the `.github/workflows/ci.yml` entry from `.gitignore`, then review and commit the restored file using the owner's normal Git workflow. Keep the preserved documentation copy or remove it in that owner-reviewed change. Do not copy credentials into either file. Push through an authorized identity; the currently configured publication token must not be assumed to have gained workflow permission.

After restoration, inspect the repository's Actions page for the first actual run. Review the lint/type/security/audit results, both Python test matrices, uploaded coverage reports, and the Docker job. Resolve any platform-specific failure before labeling CI as passing. A successful local test run or prepared workflow is separate from a successful hosted Actions run. Paid provider evaluation is not part of this offline workflow and must remain separately budgeted and recorded.

The follow-up checked the stored owner credential: scopes were `repo`, `gist`, and `read:org`, without `workflow`. The connected GitHub integration could not access this repository, and an existing-credential SSH test returned `Permission denied (publickey)`. No token was printed, committed, or exposed. Sign in as the repository owner with workflow access (for example `gh auth login --scopes workflow`, then `gh auth setup-git`) or create the preserved file through the authorized GitHub web editor. Only an actual hosted run can establish Actions success.
