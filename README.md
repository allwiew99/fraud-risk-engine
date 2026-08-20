# Fraud Risk Engine

FastAPI service that loads the MLflow registered model
`fraud-risk-model@champion` lazily and returns a fraud probability using a
decision threshold of `0.90`.

## Local setup

Python 3.14 is required.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install --editable ".[dev]"
```

`MLFLOW_TRACKING_URI` selects the MLflow tracking server. It defaults to
`http://127.0.0.1:5000` for local development and can be overridden at runtime.
The health endpoint does not load the model; the first prediction loads and
caches the champion model.

Run the API locally:

```bash
MLFLOW_TRACKING_URI=http://127.0.0.1:5000 \
  uvicorn fraud_risk.api:app --host 0.0.0.0 --port 8000
```

## Tests

The default and CI suites contain only the six fast tests. They use fakes and
do not require MLflow or model artifact downloads.

```bash
make test
# or
PYTHONPATH=src python -m pytest tests/test_api.py tests/test_model_service.py -q
```

The integration test is marked `integration` and intentionally uses the real
MLflow registry, champion alias, and model artifacts. Start the local server
from the repository root:

```bash
python -m mlflow server \
  --backend-store-uri sqlite:///notebooks/mlflow.db \
  --artifacts-destination ./notebooks/mlartifacts \
  --host 0.0.0.0 \
  --port 5000 \
  --allowed-hosts localhost:5000,127.0.0.1:5000,host.docker.internal:5000
```

Then run:

```bash
make test-integration
# or, for another server:
MLFLOW_TRACKING_URI=https://mlflow.example.com \
  PYTHONPATH=src python -m pytest -m integration \
  tests/integration/test_mlflow_serving.py -q
```

The integration test is not part of normal GitHub Actions CI.

## Docker

Build the image:

```bash
make docker-build
# CI-equivalent validation:
docker build -t fraud-risk-engine:ci .
```

On Docker Desktop for Mac, the Makefile defaults to the MLflow server running
on the host at `http://host.docker.internal:5000`:

```bash
make docker-run
```

Override either setting when needed:

```bash
MLFLOW_TRACKING_URI=https://mlflow.example.com \
  DOCKER_IMAGE=fraud-risk-engine:0.1.0 make docker-run
```

The container serves the API on `http://localhost:8000`.

## Local artifacts

Raw datasets under `data/raw/`, local MLflow state and artifacts, and generated
model artifacts are intentionally kept local and are not versioned. Restore
them locally before running notebook workflows or the real integration test.
