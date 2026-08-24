import importlib
from types import SimpleNamespace
import sys
import traceback

import pytest

from fraud_risk.schemas import FraudPredictionRequest


NEGATIVE_PAYLOAD = {
    "income": 0.9,
    "name_email_similarity": 0.6312595428642337,
    "prev_address_months_count": -1,
    "current_address_months_count": 35,
    "customer_age": 40,
    "days_since_request": 0.012314363321984,
    "intended_balcon_amount": -1.334989844562376,
    "payment_type": "AC",
    "zip_count_4w": 775,
    "velocity_6h": 3255.908260285335,
    "velocity_24h": 2391.592313290149,
    "velocity_4w": 3197.046015481273,
    "bank_branch_count_8w": 0,
    "date_of_birth_distinct_emails_4w": 4,
    "employment_status": "CA",
    "credit_risk_score": 169,
    "email_is_free": 0,
    "housing_status": "BA",
    "phone_home_valid": 1,
    "phone_mobile_valid": 1,
    "bank_months_count": -1,
    "has_other_cards": 1,
    "proposed_credit_limit": 1000.0,
    "foreign_request": 0,
    "source": "INTERNET",
    "session_length_in_minutes": 3.424853875036983,
    "device_os": "other",
    "keep_alive_session": 1,
    "device_distinct_emails_8w": 1,
    "device_fraud_count": 0,
}


def reset_model_state(model_service):
    model_service._model = None
    model_service._model_load_error = None


def test_import_does_not_load_model(monkeypatch):
    import fraud_risk.model_bundle as model_bundle

    calls = []

    def fake_load_model_bundle(uri):
        calls.append(uri)
        raise AssertionError("model must not load during module import")

    monkeypatch.setattr(
        model_bundle,
        "load_model_bundle",
        fake_load_model_bundle,
    )
    sys.modules.pop("fraud_risk.model_service", None)

    importlib.import_module("fraud_risk.model_service")

    assert calls == []


def test_initialize_model_loads_once(monkeypatch):
    import fraud_risk.model_service as model_service

    calls = []
    fake_model = SimpleNamespace(
        manifest=SimpleNamespace(
            model_version="3",
            source_git_commit="a" * 40,
        )
    )

    def fake_load_model_bundle(uri):
        calls.append(uri)
        return fake_model

    monkeypatch.setattr(
        model_service,
        "load_model_bundle",
        fake_load_model_bundle,
    )
    reset_model_state(model_service)

    assert model_service.initialize_model() is True
    assert model_service.initialize_model() is True
    assert model_service.get_model() is fake_model
    assert calls == [model_service.MODEL_ARTIFACT_URI]


def test_failed_initialization_leaves_model_unready(monkeypatch):
    import fraud_risk.model_service as model_service

    def fail_load(uri):
        raise RuntimeError("missing release")

    monkeypatch.setattr(model_service, "load_model_bundle", fail_load)
    reset_model_state(model_service)

    assert model_service.initialize_model() is False
    assert model_service.is_model_ready() is False
    assert isinstance(model_service.get_model_load_error(), RuntimeError)

    with pytest.raises(model_service.ModelNotReadyError):
        model_service.get_model()


def test_prediction_uses_threshold_from_verified_manifest(monkeypatch):
    import fraud_risk.model_service as model_service

    fake_model = SimpleNamespace(
        manifest=SimpleNamespace(
            model_version="3",
            threshold=0.9,
            features=list(NEGATIVE_PAYLOAD),
        ),
        predict=lambda frame: [0.91],
    )
    reset_model_state(model_service)
    model_service._model = fake_model

    response = model_service.predict_fraud(
        FraudPredictionRequest.model_validate(NEGATIVE_PAYLOAD)
    )

    assert response.fraud_probability == 0.91
    assert response.is_fraud is True
    assert response.threshold == 0.9


def test_prediction_failure_uses_fixed_exception_without_raw_context(
    monkeypatch,
):
    import fraud_risk.model_service as model_service

    raw_secret = "raw-model-secret-35b9a4"
    failed_events = []

    def fail_prediction(frame):
        raise ValueError(raw_secret)

    def capture_event(logger, level, event, message, **fields):
        failed_events.append((event, message, fields))

    fake_model = SimpleNamespace(
        manifest=SimpleNamespace(
            model_version="2",
            threshold=0.9,
            features=list(NEGATIVE_PAYLOAD),
        ),
        predict=fail_prediction,
    )
    reset_model_state(model_service)
    model_service._model = fake_model
    monkeypatch.setattr(model_service, "log_event", capture_event)

    with pytest.raises(RuntimeError) as raised:
        model_service.predict_fraud(
            FraudPredictionRequest.model_validate(NEGATIVE_PAYLOAD)
        )

    formatted_exception = "".join(
        traceback.format_exception(
            raised.type,
            raised.value,
            raised.tb,
        )
    )
    assert type(raised.value).__name__ == "PredictionFailedError"
    assert str(raised.value) == "Prediction failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert raised.value.__suppress_context__ is True
    assert raw_secret not in formatted_exception
    assert failed_events == [
        (
            "prediction_failed",
            "Prediction failed",
            {
                "exception_type": "ValueError",
                "error_message": "Prediction failed",
            },
        )
    ]
