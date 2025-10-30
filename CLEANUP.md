Repository Cleanup (2025-10-30)

This repository has been streamlined to focus on the single unified end‑user app and the backend services that power it.

What changed
- Removed per‑service Flutter demo clients and portals. The only end‑user client is now `clients/superapp_flutter`.
- Kept shared Flutter packages: `clients/shared_core` and `clients/shared_ui`.
- Kept `clients/ops_admin_flutter` for operator/ops workflows.
- Removed local build artifacts: `build/`, `dist/`, and `.pytest_cache/`.

Archive
- The removed client projects were moved to `archive/<timestamp>/clients/` for safekeeping.
- To restore any archived folder, move it back to its original path.

Why
- The Super‑App experience is now unified behind the BFF (`apps/bff`) and a single Flutter client (`clients/superapp_flutter`). Keeping only these reduces maintenance and avoids confusion.

Notes
- CI workflows referencing removed client paths may need to be updated.
- Documentation and READMEs have been adjusted to reflect the unified client.
