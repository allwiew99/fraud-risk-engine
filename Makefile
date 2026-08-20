PYTHON ?= python
DOCKER_IMAGE ?= fraud-risk-engine:0.1.0
MLFLOW_TRACKING_URI ?= http://host.docker.internal:5000

.PHONY: test test-integration docker-build docker-run

test:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_api.py tests/test_model_service.py -q

test-integration:
	PYTHONPATH=src $(PYTHON) -m pytest -m integration tests/integration/test_mlflow_serving.py -q

docker-build:
	docker build -t $(DOCKER_IMAGE) .

docker-run:
	docker run --rm -p 8000:8000 \
		-e MLFLOW_TRACKING_URI="$(MLFLOW_TRACKING_URI)" \
		$(DOCKER_IMAGE)
