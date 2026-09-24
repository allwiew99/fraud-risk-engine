PYTHON ?= python
DOCKER_IMAGE ?= fraud-risk-engine:0.1.0
PORT ?= 8080
MODEL_RELEASE_DIR ?=
MLFLOW_TRACKING_URI ?= http://127.0.0.1:5000

.PHONY: check lint typecheck test test-integration export-model-release docker-build docker-build-amd64 docker-run load-test

check: lint typecheck test

lint:
	PYTHONPATH=src $(PYTHON) -m ruff check .

typecheck:
	PYTHONPATH=src $(PYTHON) -m mypy src scripts

test:
	PYTHONPATH=src $(PYTHON) -m pytest -q

test-integration:
	MLFLOW_TRACKING_URI="$(MLFLOW_TRACKING_URI)" PYTHONPATH=src \
		$(PYTHON) -m pytest -m integration tests/integration -q

export-model-release:
	MLFLOW_TRACKING_URI="$(MLFLOW_TRACKING_URI)" PYTHONPATH=src \
		$(PYTHON) scripts/export_model_release.py

docker-build:
	docker build -t $(DOCKER_IMAGE) .

docker-build-amd64:
	docker buildx build --platform linux/amd64 --load -t $(DOCKER_IMAGE) .

docker-run:
	@test -n "$(MODEL_RELEASE_DIR)" || \
		(echo "MODEL_RELEASE_DIR must point to one immutable release directory"; exit 1)
	docker run --rm -p $(PORT):$(PORT) \
		-v "$(abspath $(MODEL_RELEASE_DIR)):/model-release:ro" \
		-e MODEL_ARTIFACT_URI="file:///model-release" \
		-e PORT="$(PORT)" \
		$(DOCKER_IMAGE)

load-test:
	@test -n "$(SERVICE_URL)" || (echo "SERVICE_URL is required"; exit 1)
	@test -n "$(REVISION)" || (echo "REVISION is required"; exit 1)
	PYTHONPATH=. $(PYTHON) scripts/load_test.py \
		--service-url="$(SERVICE_URL)" \
		--concurrency="$${CONCURRENCY:-10}" \
		--requests="$${REQUESTS:-100}" \
		--environment="$${ENVIRONMENT:-production-private-proxy}" \
		--revision="$(REVISION)" \
		--model-release="$${MODEL_RELEASE:-v2-3e65f5fd-88b81f0}" \
		--instance-config="$${INSTANCE_CONFIG:-1 CPU, 1Gi, concurrency 4}"
