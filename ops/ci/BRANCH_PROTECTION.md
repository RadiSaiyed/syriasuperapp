Required Status Checks (Supply Chain)

Goal
- Block merges unless the supply-chain scanning job passes.

Check name
- Workflow: `Payments CI` (file `.github/workflows/payments-ci.yml`)
- Job ID: `supply-chain`
- In GitHub UI, the status check typically shows as: `Payments CI / supply-chain`.

Enable required status
1) Go to GitHub → Settings → Branches → Branch protection rules.
2) Edit your main rule (or create one) and enable “Require status checks to pass”.
3) Add `Payments CI / supply-chain` (or select from the list after it has run once).
4) Save.

Notes
- The job runs on push/PR when files in `apps/payments/**`, `libs/superapp_shared/**`, `tools/**`, or the workflow file change.
- Artifacts include CycloneDX SBOM, pip-audit results, and a licenses report.

