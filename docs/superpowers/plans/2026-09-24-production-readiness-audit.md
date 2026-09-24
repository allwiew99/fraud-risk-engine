# Production Readiness Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close verified production-readiness gaps and produce current local, CI, deployment, performance, monitoring, and live evidence.

**Architecture:** Preserve the single private FastAPI/Cloud Run service and immutable GCS model release. Add contract checks around existing boundaries and a small standalone load client; use the existing WIF deployment path for the final rollout.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, pytest, Ruff, mypy, Docker, GitHub Actions, Google Cloud Run, Artifact Registry, GCS, Cloud Logging, Cloud Monitoring.

**Spec:** `docs/superpowers/specs/2026-09-24-production-readiness-audit-design.md`

## Global Constraints

- Work only in `allwiew99/fraud-risk-engine`.
- Preserve model version `2`, release `v2-3e65f5fd-88b81f0`, and threshold `0.90`.
- Keep Cloud Run private and use no service-account JSON key.
- Do not regenerate or overwrite the approved model release.
- Separate local, CI, configured, deployed, and verified-live evidence.

## Review Focus

- Unknown or non-finite prediction fields must fail with 422 and never reach inference.
- A candidate with wrong scaling, runtime identity, digest, or model URI must not be promoted.
- Load failures must count as errors without exposing response bodies, tokens, or features.
- Tagged zero-percent revisions must not be mistaken for ordinary traffic allocations.
- Documentation must not claim a notification path or live log event without remote evidence.

---

### Task 1: Static analysis and API boundary contracts

**Files:**
- Modify: `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`
- Modify: `src/fraud_risk/schemas.py`
- Test: `tests/test_api.py`, `tests/test_deploy_workflow.py`

**Interfaces:**
- Produces: deterministic `make check` and strict Pydantic request/response contracts.

- [ ] Write API and workflow contract tests for unknown/non-finite fields and static gates.
- [ ] Run the focused tests and confirm they fail for missing behavior.
- [ ] Configure Ruff/mypy, strengthen schemas, and wire the gates into Make/CI/deploy.
- [ ] Run focused and full tests, Ruff, mypy, and compile sanity.
- [ ] Commit `chore: strengthen quality and API contracts`.

### Task 2: Candidate runtime verification

**Files:**
- Modify: `.github/workflows/deploy.yml`
- Test: `tests/test_deploy_workflow.py`

**Interfaces:**
- Consumes: immutable digest and candidate revision from the existing workflow.
- Produces: promotion gate requiring exact Ready/runtime/scaling/resource configuration.

- [ ] Write tests that require explicit `--min-instances=0`, `--max-instances=3`, and candidate spec validation.
- [ ] Run the focused test and confirm failure.
- [ ] Implement the candidate revision verifier without exposing environment secrets.
- [ ] Run focused and complete gates.
- [ ] Commit `ops: verify candidate runtime configuration`.

### Task 3: Reproducible load harness

**Files:**
- Create: `scripts/load_test.py`
- Create: `tests/test_load_test.py`
- Modify: `pyproject.toml`, `Makefile`

**Interfaces:**
- Produces: `run_load_test(url, concurrency, requests, opener)` returning measured aggregate results and a safe CLI JSON document.

- [ ] Write tests for percentile calculation, concurrency accounting, HTTP failures, and safe output.
- [ ] Run focused tests and confirm failure because the harness is absent.
- [ ] Implement the minimal standard-library load client.
- [ ] Run focused and complete gates.
- [ ] Commit `perf: add reproducible private load test`.

### Task 4: Evidence documents

**Files:**
- Create: `PRODUCTION_READINESS.md`
- Modify: `README.md`
- Create after measurement only: `LOAD_TEST_RESULTS.md`

**Interfaces:**
- Consumes: local outputs, CI/deploy run URLs, Cloud Run/IAM/logging/monitoring queries, and measured load JSON.
- Produces: an evidence table using only the allowed readiness statuses.

- [ ] Record baseline and verification commands with exact limitations.
- [ ] Update stale README production claims.
- [ ] Validate all links/identifiers and scan for unsupported claims.
- [ ] Commit `docs: record verified production state`.

### Task 5: CI, deploy, and live verification

**Files:**
- Update evidence documents only when remote results differ from planned values.

**Interfaces:**
- Consumes: merged `main`, GitHub OIDC/WIF, the immutable model release, and the existing private service.
- Produces: current CI run, immutable image index and platform digests, candidate/canonical smoke evidence, final revision, fresh logs, and load results.

- [ ] Run all local gates and build the Docker image.
- [ ] Push the branch, open/merge a PR, and verify current-commit CI.
- [ ] Dispatch deployment with release `v2-3e65f5fd-88b81f0`, version `2`.
- [ ] Re-query traffic, revision spec, IAM, digest, fresh logs, monitoring, and notification channels.
- [ ] Run private load tests at concurrency 1, 10, 25, and 50 and record real results.
- [ ] Attach or create a notification channel if it can be verified without user-only action; otherwise document the exact blocker.
- [ ] Commit any final evidence corrections and re-run CI as needed.
