# Fraud Risk Engine

FastAPI service for the approved XGBoost fraud model. Production inference uses
an immutable, hash-verified model release bundle rather than a live MLflow
Registry connection. The decision threshold (`0.90`) is versioned with the
model in the bundle manifest.

## Local setup

Python 3.14 is required.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install --editable ".[dev]"
```

## Model release bundle

Each generated release contains exactly:

```text
manifest.json
xgb_preprocessor.joblib
xgb_champion.ubj
```

`manifest.json` records the immutable MLflow model version, run/model IDs,
feature order, threshold, source Git commit, timestamp, and artifact SHA-256
hashes. The runtime validates the manifest and both hashes before loading any
artifact.

Start the local MLflow server when exporting or running integration tests:

```bash
python -m mlflow server \
  --backend-store-uri sqlite:///notebooks/mlflow.db \
  --artifacts-destination ./notebooks/mlartifacts \
  --host 0.0.0.0 \
  --port 5000 \
  --allowed-hosts localhost:5000,127.0.0.1:5000,host.docker.internal:5000
```

Export the current approved champion to a local immutable directory:

```bash
make export-model-release
```

The exporter uses `fraud-risk-model@champion` only to resolve the immutable
registered model version. Generated releases are written under
`dist/model-release/`, are never overwritten, and are ignored by Git.

## Run locally

Point `MODEL_ARTIFACT_URI` at one exact release directory:

```bash
MODEL_ARTIFACT_URI="file://$PWD/dist/model-release/RELEASE_ID" \
  uvicorn fraud_risk.api:app --host 0.0.0.0 --port 8080
```

Endpoints:

- `GET /health`: process liveness
- `GET /ready`: verified model readiness
- `POST /predict`: fraud probability and manifest threshold

The model is verified and loaded during application startup. Predictions fail
with HTTP 503 while the model is not ready.

The future Cloud Run configuration will use an immutable GCS prefix such as
`gs://fraud-risk-engine-models/releases/RELEASE_ID`. No model is uploaded by
the local export command.

## Tests

The default and CI suite is service-independent:

```bash
make test
# or
PYTHONPATH=src python -m pytest -q
```

The integration suite requires the real local MLflow Registry and verifies
that an exported release matches the champion:

```bash
make test-integration
```

## Docker

Build normally for local/CI validation:

```bash
make docker-build
```

Build a Cloud Run-compatible local image without pushing it:

```bash
make docker-build-amd64
```

Run with one release mounted read-only:

```bash
MODEL_RELEASE_DIR="$PWD/dist/model-release/RELEASE_ID" make docker-run
```

The container honors `${PORT:-8080}` and does not need an MLflow server for
health, readiness, or prediction.

## Local artifacts

Raw datasets, notebook outputs, local MLflow state, exported model releases,
and generated model artifacts are intentionally local and not versioned.
