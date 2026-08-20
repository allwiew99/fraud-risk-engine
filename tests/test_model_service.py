import importlib
import sys

import mlflow.pyfunc


def test_import_does_not_load_model(monkeypatch):
    calls = []

    def fake_load_model(model_uri):
        calls.append(model_uri)
        raise AssertionError("Modelul nu trebuie incarcat la import")

    monkeypatch.setattr(
        mlflow.pyfunc,
        "load_model",
        fake_load_model,
    )

    sys.modules.pop("fraud_risk.model_service", None)

    importlib.import_module("fraud_risk.model_service")

    assert calls == []


def test_get_model_loads_once(monkeypatch):
    import fraud_risk.model_service as model_service

    calls = []
    fake_model = object()

    def fake_load_model(model_uri):
        calls.append(model_uri)
        return fake_model

    monkeypatch.setattr(
        model_service.mlflow.pyfunc,
        "load_model",
        fake_load_model,
    )

    model_service._model = None

    first_model = model_service.get_model()
    second_model = model_service.get_model()

    assert first_model is fake_model
    assert second_model is fake_model

    assert calls == [
        model_service.MODEL_URI
    ]