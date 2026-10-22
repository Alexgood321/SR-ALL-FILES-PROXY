# Mini Plan 6 HAPP — clean GitHub release review

Base: `26ef272b0ff3bdcf59b40289e1f6647e9dc85353`; confirmed by read-only
`git ls-remote origin refs/heads/main` on 2026-10-22. Source implementation:
`ad200ec9dbade3ff2d4128108cff95b39485bd70`. No source branch history is required.

## Exact scope

- `.github/workflows/sync-incy-routing.yml`: HAPP step in the existing writer;
  original INCY steps and concurrency compare equal to base.
- `.github/workflows/validate-incy-routing.yml`: independent HAPP validation.
- `scripts/generate_happ_xray_policy.py`: adapter of unchanged INCY converter.
- `tests/test_happ_xray_policy.py`: existing five HAPP regression tests.
- `happ/xray-policy.json`, `happ/xray-conversion-report.md`: generated artifacts.
- This report: release and TDD evidence, not runtime functionality.

Owner finalization: `AGENTS.md` is excluded from the release diff and equals
the base file. Instructions in the original local repository are untouched.
No generator, artifact, workflow or test changed during this finalization.

No changes to canonical config/modules, INCY scripts/artifacts, requirements or
other workflows. No IR, v2 namespaces, manifests, bootstrap fixture/probe, Docker
publication step or new dependencies. Generated JSON was rebuilt with the
existing adapter after a transfer hash mismatch; the final bytes equal both
the original approved HAPP artifact and the unchanged INCY policy. SHA256:
`bb01f2d65f6403e97ddb77e8bf6349943dca481cf844479ef14783e6d16fe701`.

## Checks

- `python -m pytest tests/test_happ_xray_policy.py tests/test_incy_xray_policy.py`:
  **29 PASS**. HAPP-only RED on clean base: **5 failed**, missing implementation;
  then the same target became GREEN. RED checkpoint `b7b02cc`, implementation
  checkpoint `c6716c8`; complete regenerated artifact `18b7170`.
- `python -m coverage run --source=generate_happ_xray_policy -m pytest ...`:
  adapter **97%** (entrypoint exercised separately by CLI test).
- Canonical validator: PASS, errors=0/warnings=0.
- Both generators' `--check`: PASS. HAPP/INCY policy byte parity: PASS.
- Workflow YAML, every shell run block (`bash -n`), Python AST, imports and
  `git diff --check`: PASS. No new package or network test infrastructure.
- Evidence kept locally at root
  `output/mini-plan6-clean-release-20261022/{github-red.xml,github-green.xml}`.

Checkpoint commits are preserved on `codex/mini-plan6-happ-github-release`.
The final candidate is one commit directly on the stated base. Its functional
files are identical to the verified checkpoint tree; only AGENTS exclusion
and this scope note differ. This preserves TDD evidence without publishing
the historical development/Phase 2 branch.

READY_FOR_GITHUB_GO=YES for this exact scope only. No push or activation occurred.
Actual GitHub Actions / `xray run -test` execution remains NOT_TESTED locally
(available binary is Linux ELF on macOS); the workflow must pass before READY.
Device tunnel/refresh behavior is not established by this repository review.
PRODUCTION_CHANGED=NO; CANONICAL_CHANGED=NO.
