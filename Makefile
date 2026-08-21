PYTHON ?= python
DOCKER_IMAGE ?= fraud-risk-engine:0.1.0
PORT ?= 8080
MODEL_RELEASE_DIR ?=
MLFLOW_TRACKING_URI ?= http://127.0.0.1:5000

.PHONY: test test-integration export-model-release docker-build docker-build-amd64 docker-run

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
