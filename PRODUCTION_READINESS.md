# Production Readiness Evidence

Evidence captured on 2026-09-24. Status words have narrow meanings:
`VERIFIED LIVE` requires a remote serving/control-plane observation; `VERIFIED`
requires a reproducible local or CI check; `PARTIAL` means useful controls exist
but a required proof or capability is missing.

| Area | Status | Evidence and verification result | Remaining limitation |
|---|---|---|---|
| Application architecture | VERIFIED LIVE | `gcloud run services describe fraud-risk-api --project=fraud-risk-engine --region=europe-west1` showed one private FastAPI service using the dedicated runtime identity and immutable GCS release; private proxy checks returned 200 from `/health`, `/ready`, and `/predict`. | Single region and scale-to-zero cold starts. |
| Model evaluation | VERIFIED | Sanitized notebook records the 1,000,000-row chronological split and held-out XGBoost ROC-AUC `0.8918`, PR-AUC `0.1902`, threshold `0.90`. | Training dataset and generated state are intentionally not committed. |
| Model governance | VERIFIED LIVE | Live `MODEL_ARTIFACT_URI` is release `v2-3e65f5fd-88b81f0`; GCS manifest identifies registered version `2`, MLflow model ID `m-3e65f5fd985a4b6f929abc2057fc7a89`, and source commit `88b81f0017c8d90457e16ffeeebb02dbe1642e1b`. | A clean checkout cannot rerun MLflow integration tests without the approved local registry/artifact store. |
| Artifact integrity | VERIFIED LIVE | `gcloud storage ls --long gs://fraud-risk-engine-models/releases/v2-3e65f5fd-88b81f0/**` returned exactly manifest plus two artifacts. Startup code validates schema, exact filenames/features, and SHA-256 before deserialization; failure tests pass. | GCS object retention/lock is not configured as a repository-controlled policy. |
| Testing | VERIFIED | `PYTHONPATH=src:. python -m pytest -q` returned `85 passed`; failure cases cover unavailable model, bad manifest, missing artifact, hash mismatch, wrong features, load/prediction failures, readiness, and safe errors. | Real MLflow integration tests require local governed state. |
| Static analysis | VERIFIED | `python -m ruff check .`, `python -m mypy src scripts`, and `python -m compileall -q src scripts` pass locally. | Current-commit CI evidence is pending branch integration. |
| Containerization | VERIFIED | `docker build -t fraud-risk-engine:production-readiness .` completed successfully on 2026-09-24. `.dockerignore` excludes Git, credentials, env files, data, tests, notebooks, MLflow state, and model artifacts. | Local build was arm64; deployment workflow builds linux/amd64. |
| CI | PARTIAL | Current `main` CI run `32854394673` passed at `a1615f6`; the workflow builds Docker. This branch adds Ruff and mypy gates. | New gates are not CI-verified until merged. |
| CD | VERIFIED LIVE | GitHub Actions deployment run `32854613397` succeeded through WIF, zero-traffic candidate, candidate smoke, promotion, canonical smoke, and IAM recheck. | The currently live revision predates this audit branch. |
| WIF / authentication | VERIFIED LIVE | Pool/provider are ACTIVE; provider condition pins numeric owner/repository IDs, `main`, and exact `deploy.yml`; successful run minted candidate and canonical identity tokens. | Local user credentials cannot mint the deployer identity token, so live access uses the Cloud Run proxy or GitHub OIDC. |
| Secrets | VERIFIED | Both service accounts have zero user-managed keys; Git tracked-file credential/key pattern scan returned no matches; `.env*` and `gha-creds-*.json` are ignored/excluded. | GitHub secret scanning is disabled for this public repository; the documented local scan is the available evidence. |
| IAM | VERIFIED LIVE | Deployer has WIF user on its service account, writer on one Artifact Registry repository, developer on one Cloud Run service, and runtime-SA user on the runtime identity. Runtime has object viewer on the model bucket. | Bucket retains Google-managed legacy project bindings in addition to the runtime binding. |
| Cloud Run privacy | VERIFIED LIVE | Service IAM has no `allUsers` or `allAuthenticatedUsers`; unauthenticated `/health` returned 403 on 2026-09-24. | Authorized callers still require `run.routes.invoke` through an appropriate identity. |
| Deployment safety | VERIFIED LIVE | Run `32854613397` deployed index digest `sha256:1ed0f5613452ddd3c83a396f5c2d4b3f3f1817a0882a1e2e4a72c5d85eae133c` as zero-traffic candidate before explicit promotion. | New candidate runtime-spec gate awaits deployment. |
| Smoke testing | VERIFIED LIVE | Candidate and canonical smoke steps both passed in run `32854613397`; known probabilities and threshold were checked. Private proxy repeated health/readiness/negative inference on 2026-09-24. | Direct local token minting is unavailable to the active user identity. |
| Rollback | VERIFIED | Workflow records the prior explicit revision, reconciles ambiguous promotion state, and tests require exact 100% rollback traffic. | No deliberate live rollback was performed; hard runner termination cannot execute best-effort cleanup. |
| Structured logging | PARTIAL | Allowlist logging and redaction tests pass. | Current retention contained request/audit logs but no application event from the serving revision; fresh live event evidence requires the new rollout. |
| Monitoring | VERIFIED LIVE | Policy `projects/fraud-risk-engine/alertPolicies/17997922764504296330` is enabled and matches 5xx/total >5% for 300 seconds in `europe-west1`; Cloud Run exposes request, latency, instance, CPU, and memory metrics. | No custom dashboard; built-in metrics are used. |
| Alerting | VERIFIED LIVE | Enabled email channel `projects/fraud-risk-engine/notificationChannels/7232674366703482783` exists and is attached to the enabled sustained-5xx policy. | Delivery is dependent on the configured external email system; no deliberate production incident was generated. |
| Failure handling | VERIFIED | API/model/release tests prove controlled 422/500/503 behavior and no raw exception text. Strict request models reject unknown and non-finite fields before inference. | Infrastructure-level timeouts are represented by Cloud Run responses rather than app-specific JSON. |
| Performance | NOT IMPLEMENTED | No production load measurements have yet been recorded for the audit revision. | Run the controlled private load matrix after deployment. |
| Load testing | VERIFIED | `scripts/load_test.py` and three deterministic unit tests cover percentile math, concurrency accounting, error rate, and safe output. | Harness exists; real results are pending, so `LOAD_TEST_RESULTS.md` does not yet exist. |
| Security | VERIFIED LIVE | Private IAM, short-lived WIF, no user-managed SA keys, scoped runtime storage, safe logs, ignored env/credentials, and restricted Docker context were checked. | GitHub secret scanning is disabled and dependency vulnerability scanning is not configured. |
| Documentation | PARTIAL | README and this evidence ledger identify exact live resources, monitoring channel, and limitations. | Final revision/digests/load/log state must be refreshed after the audit deployment. |
| Reproducibility | VERIFIED | Python dependencies and actions are pinned; model release, threshold, feature order, smoke samples/tolerances, Make targets, Dockerfile, and monitoring JSON are tracked. | Governed MLflow/training state is intentionally external. |
| Production verification | PARTIAL | Current live revision is `fraud-risk-api-00006-zaq`, 100% ordinary traffic, platform digest `sha256:f83c3f2f74e62a846ade5381b8049cc19b0c02e72444493700d70f4e3a9e3dcc`, release `v2-3e65f5fd-88b81f0`, model version `2`. | The audit branch is not deployed; structured log and load evidence remain pending. |

## Baseline command record

```text
PYTHONPATH=src:. python -m pytest -q
85 passed in 1.11s

python -m ruff check .
All checks passed!

python -m mypy src scripts
Success: no issues found in 13 source files

python -m compileall -q src scripts
exit 0

docker build -t fraud-risk-engine:production-readiness .
exit 0; manifest list sha256:2d50791376082fac41e748d8a3ec4f6b220daaeda882cc5f8d21d0d62b0c543d
```
