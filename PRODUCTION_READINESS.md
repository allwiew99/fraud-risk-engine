# Production Readiness Evidence

Evidence captured on 2026-09-24. Status words have narrow meanings:
`VERIFIED LIVE` requires a remote serving/control-plane observation; `VERIFIED`
requires a reproducible local or CI check; `PARTIAL` means useful controls exist
but a required proof or capability is missing.

| Area | Status | Evidence and verification result | Remaining limitation |
|---|---|---|---|
| Application architecture | VERIFIED LIVE | `gcloud run services describe fraud-risk-api --project=fraud-risk-engine --region=europe-west1` showed revision `fraud-risk-api-00009-hiz` at 100%, using the dedicated runtime identity and immutable GCS release; deployment candidate and canonical checks returned 200 from `/health`, `/ready`, and `/predict`. | Single region and scale-to-zero cold starts. |
| Model evaluation | VERIFIED | Sanitized notebook records the 1,000,000-row chronological split and held-out XGBoost ROC-AUC `0.8918`, PR-AUC `0.1902`, threshold `0.90`. | Training dataset and generated state are intentionally not committed. |
| Model governance | VERIFIED LIVE | Live `MODEL_ARTIFACT_URI` is release `v2-3e65f5fd-88b81f0`; GCS manifest identifies registered version `2`, MLflow model ID `m-3e65f5fd985a4b6f929abc2057fc7a89`, and source commit `88b81f0017c8d90457e16ffeeebb02dbe1642e1b`. | A clean checkout cannot rerun MLflow integration tests without the approved local registry/artifact store. |
| Artifact integrity | VERIFIED LIVE | `gcloud storage ls --long gs://fraud-risk-engine-models/releases/v2-3e65f5fd-88b81f0/**` returned exactly manifest plus two artifacts. Startup code validates schema, exact filenames/features, and SHA-256 before deserialization; failure tests pass. | GCS object retention/lock is not configured as a repository-controlled policy. |
| Testing | VERIFIED | `PYTHONPATH=src:. python -m pytest -q` returned `86 passed`; failure cases cover unavailable model, bad manifest, missing artifact, hash mismatch, wrong features, load/prediction failures, readiness, and safe errors. CI and deployment reran the suite. | Real MLflow integration tests require local governed state. |
| Static analysis | VERIFIED | `python -m ruff check .`, `python -m mypy src scripts`, and `python -m compileall -q src scripts` pass locally; CI run `36019636821` ran Ruff/mypy successfully. | The historical notebook is excluded from Ruff; serving source, scripts, and tests are checked. |
| Containerization | VERIFIED | Local Docker build completed; CI run `36019636821` built the image; deployment run `36031500249` built and pushed linux/amd64 once. `.dockerignore` excludes credentials and non-runtime state. | Base image is a mutable Dockerfile reference resolved to a digest at build time, not pinned in source. |
| CI | VERIFIED | Main CI run `36019636821` passed static checks, 86 tests, and Docker build for commit `63f407827d3979d0345e899761a6755abb327c6a`. | GitHub runner image migration warnings are external and non-blocking. |
| CD | VERIFIED LIVE | Deployment run `36031500249` succeeded through WIF, zero-traffic candidate, exact runtime-spec verification, candidate smoke, promotion, canonical smoke, tag removal, and IAM recheck. | Workflow dispatch remains an authorized manual release action. |
| WIF / authentication | VERIFIED LIVE | Pool/provider are ACTIVE; provider condition pins numeric owner/repository IDs, `main`, and exact `deploy.yml`; successful run minted candidate and canonical identity tokens. | Local user credentials cannot mint the deployer identity token, so live access uses the Cloud Run proxy or GitHub OIDC. |
| Secrets | VERIFIED | Both service accounts have zero user-managed keys; Git tracked-file credential/key pattern scan returned no matches; `.env*` and `gha-creds-*.json` are ignored/excluded. | GitHub secret scanning is disabled for this public repository; the documented local scan is the available evidence. |
| IAM | VERIFIED LIVE | Deployer has WIF user on its service account, writer on one Artifact Registry repository, developer on one Cloud Run service, and runtime-SA user on the runtime identity. Runtime has object viewer on the model bucket. | Bucket retains Google-managed legacy project bindings in addition to the runtime binding. |
| Cloud Run privacy | VERIFIED LIVE | Service IAM has no `allUsers` or `allAuthenticatedUsers`; unauthenticated `/health` returned 403 on 2026-09-24. | Authorized callers still require `run.routes.invoke` through an appropriate identity. |
| Deployment safety | VERIFIED LIVE | Run `36031500249` deployed index digest `sha256:fbd2d8c5b81c788c75b093de6e64990f41c8f2e33ca018b28cafcdc03ad523fb` as revision `fraud-risk-api-00009-hiz` at zero traffic, verified identity/resources/scaling/model URI, then promoted explicitly. | Two stale zero-percent traffic tags from historical failed runs remain; they receive no ordinary traffic. |
| Smoke testing | VERIFIED LIVE | Candidate and canonical smoke steps both passed in run `36031500249`; known probabilities, classifications, threshold `0.9`, and tolerances were checked. | Direct local token minting is unavailable to the active user identity; private proxy is used locally. |
| Rollback | VERIFIED | Workflow records the prior explicit revision, reconciles ambiguous promotion state, and tests require exact 100% rollback traffic. | No deliberate live rollback was performed; hard runner termination cannot execute best-effort cleanup. |
| Structured logging | VERIFIED LIVE | Cloud Logging returned one `model_startup` event (release `v2-3e65f5fd-88b81f0`, version `2`, source commit, 2027.226 ms load) and fresh `prediction_completed` events from revision `fraud-risk-api-00009-hiz`; allowlist/redaction tests pass. | Application logs intentionally omit features, payloads, tokens, probabilities, and raw exception text. |
| Monitoring | VERIFIED LIVE | Policy `projects/fraud-risk-engine/alertPolicies/17997922764504296330` is enabled and matches 5xx/total >5% for 300 seconds in `europe-west1`; Cloud Run exposes request, latency, instance, CPU, and memory metrics. | No custom dashboard; built-in metrics are used. |
| Alerting | VERIFIED LIVE | Enabled email channel `projects/fraud-risk-engine/notificationChannels/7232674366703482783` exists and is attached to the enabled sustained-5xx policy. | Delivery is dependent on the configured external email system; no deliberate production incident was generated. |
| Failure handling | VERIFIED | API/model/release tests prove controlled 422/500/503 behavior and no raw exception text. Strict request models reject unknown and non-finite fields before inference. | Infrastructure-level timeouts are represented by Cloud Run responses rather than app-specific JSON. |
| Performance | VERIFIED LIVE | Warm private-proxy runs of 100 validated predictions measured 14.452, 104.809, 204.592, and 176.330 RPS at concurrency 1, 10, 25, and 50 with 0% errors; exact percentiles are in `LOAD_TEST_RESULTS.md`. | Short proxy-based tests are not capacity guarantees; concurrency 50 showed higher queueing and lower throughput. |
| Load testing | VERIFIED LIVE | `scripts/load_test.py` has deterministic tests and produced the recorded live matrix for revision `fraud-risk-api-00009-hiz`, release `v2-3e65f5fd-88b81f0`. | Longer, region-local soak testing is still needed for SLO/capacity decisions. |
| Security | VERIFIED LIVE | Private IAM, short-lived WIF, no user-managed SA keys, scoped runtime storage, safe logs, ignored env/credentials, and restricted Docker context were checked. | GitHub secret scanning is disabled and dependency vulnerability scanning is not configured. |
| Documentation | VERIFIED | README, `LOAD_TEST_RESULTS.md`, monitoring JSON, workflow, and this ledger agree on the audited live state and limitations. | Evidence is point-in-time and must be refreshed after future releases. |
| Reproducibility | VERIFIED | Python dependencies and actions are pinned; model release, threshold, feature order, smoke samples/tolerances, Make targets, Dockerfile, and monitoring JSON are tracked. | Governed MLflow/training state is intentionally external. |
| Production verification | VERIFIED LIVE | Revision `fraud-risk-api-00009-hiz` has exactly 100% ordinary traffic, index digest `sha256:fbd2d8c5b81c788c75b093de6e64990f41c8f2e33ca018b28cafcdc03ad523fb`, platform digest `sha256:deaea0658abfac04c7a9b43a1822b7d488e621780e6bfcd7001590f16a126ad3`, release `v2-3e65f5fd-88b81f0`, model version `2`, private IAM, fresh logs, and smoke/load evidence. | Evidence is point-in-time as of 2026-09-24. |

## Baseline command record

```text
PYTHONPATH=src:. python -m pytest -q
86 passed in 1.23s

python -m ruff check .
All checks passed!

python -m mypy src scripts
Success: no issues found in 13 source files

python -m compileall -q src scripts
exit 0

docker build -t fraud-risk-engine:production-readiness .
exit 0; manifest list sha256:2d50791376082fac41e748d8a3ec4f6b220daaeda882cc5f8d21d0d62b0c543d
```
