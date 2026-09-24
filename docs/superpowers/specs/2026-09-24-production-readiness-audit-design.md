# Production Readiness Audit Design

## Intent

Bring the existing fraud-risk engine to an evidence-backed small-production
state without changing its approved model, chronological evaluation, threshold,
private access model, or single-service architecture. Distinguish implemented,
locally tested, CI-verified, deployed, and live-verified claims throughout.

## Baseline findings

- `main` is clean at `a1615f6`; 76 default tests and compile sanity pass.
- CI and the WIF deployment for `a1615f6` succeeded on 2026-08-25.
- Cloud Run is private and serves revision `fraud-risk-api-00006-zaq` at 100%.
- The deployed index digest is
  `sha256:1ed0f5613452ddd3c83a396f5c2d4b3f3f1817a0882a1e2e4a72c5d85eae133c`;
  the imported linux/amd64 manifest digest is
  `sha256:f83c3f2f74e62a846ade5381b8049cc19b0c02e72444493700d70f4e3a9e3dcc`.
- WIF and scoped deployer bindings exist. The runtime identity has bucket-level
  object-viewer access.
- The 5xx ratio policy exists, but no notification channel is attached.
- The live revision reports `maxScale=20`, contrary to the workflow's intended
  maximum of 3.
- Ruff and mypy are not configured. Docker is available after starting its
  local engine.
- Current log retention contains request/audit evidence but no application event
  from the serving revision; a new rollout and smoke/load activity must create
  fresh evidence.

## Selected approach

Preserve the mature release, API, and deployment design and close only evidenced
gaps. Add useful static checks, strengthen schema boundaries, test deployment
configuration as a contract, add a dependency-free load harness, and make the
readiness documents source-backed. Deploy one new immutable revision through
the existing WIF workflow, then re-query Cloud Run, logs, IAM, monitoring, and
traffic. This avoids introducing infrastructure or retraining the model.

## Component changes

1. Quality gates: pin Ruff and mypy in the development extra, configure both,
   add Make targets, and run them in CI and deployment preflight.
2. Serving contracts: forbid unknown request/response fields and non-finite
   floating-point values; constrain probabilities and thresholds to `[0, 1]`.
3. Deployment safety: use unambiguous Cloud Run scaling flags and verify the
   candidate revision's runtime identity, immutable digest, resources, scaling,
   concurrency, timeout, model URI, and Ready status before smoke/promotion.
4. Performance: provide a standard-library concurrent load client that records
   RPS, p50/p95/p99, error rate, environment, revision, release, and sample count
   without logging tokens or request features.
5. Evidence: maintain `PRODUCTION_READINESS.md`; update README only after live
   validation. Create `LOAD_TEST_RESULTS.md` only from real measurements.

## Error and security behavior

Release verification continues to fail closed before deserialization. Startup
failure leaves readiness at 503; prediction failure remains a fixed 500 without
raw exception details. Load and smoke tooling accept credentials only through
environment variables and never serialize them. Cloud Run remains private; no
public IAM grant is introduced.

## Verification

Every behavior change is test-first. Final local gates are Ruff, mypy, compile,
the complete default suite, and Docker build. Remote gates are current-commit CI,
WIF deployment, zero-traffic candidate checks, authenticated candidate and
canonical smoke tests, explicit 100% traffic, digest/revision re-query, fresh
structured logs, alert-policy/channel inspection, and controlled load runs at
concurrency 1, 10, 25, and 50.

## Known boundary

Email notification verification may require the user. If no channel can be made
operational without that step, alerting remains `BLOCKED BY USER ACTION`; the
existing policy is not represented as operational external alerting.
