import json
import logging
from types import SimpleNamespace

from fraud_risk.observability import JsonFormatter, release_name_from_uri
from fraud_risk.schemas import FraudPredictionRequest


PRODUCTION_MODEL_ARTIFACT_URI = (
    "gs://fraud-risk-model-releases/v2-3e65f5fd-88b81f0/"
)
SOURCE_GIT_COMMIT = "88b81f0017c8d90457e16ffeeebb02dbe1642e1b"
PREDICTION_PAYLOAD = {
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


def _event_from_log_call(level, event, message, **fields):
    record = logging.LogRecord(
        name="fraud_risk",
        level=level,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.event = event
    for key, value in fields.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter().format(record))


def _reset_model_state(model_service):
    model_service._model = None
    model_service._model_load_error = None


def test_json_formatter_emits_whitelisted_startup_fields():
    record = logging.LogRecord(
        name="fraud_risk",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="Verified model release loaded",
        args=(),
        exc_info=None,
    )
    record.event = "model_startup"
    record.model_version = "2"
    record.model_release = "v2-3e65f5fd-88b81f0"
    record.source_git_commit = SOURCE_GIT_COMMIT
    record.model_load_duration_ms = 12.345

    event = json.loads(JsonFormatter().format(record))

    assert event == {
        "severity": "INFO",
        "message": "Verified model release loaded",
        "event": "model_startup",
        "model_version": "2",
        "model_release": "v2-3e65f5fd-88b81f0",
        "source_git_commit": SOURCE_GIT_COMMIT,
        "model_load_duration_ms": 12.345,
    }


def test_json_formatter_omits_request_payload_and_unknown_fields():
    record = logging.LogRecord(
        name="fraud_risk",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="Prediction completed",
        args=(),
        exc_info=None,
    )
    record.event = "prediction_completed"
    record.request_payload = {"income": 0.9}
    record.income = 0.9
    record.token = "token-value"

    event = json.loads(JsonFormatter().format(record))

    assert event == {
        "severity": "INFO",
        "message": "Prediction completed",
        "event": "prediction_completed",
    }
    assert "request_payload" not in event
    assert "income" not in event
    assert "token" not in event


def test_release_name_from_uri_handles_gcs_trailing_slash():
    assert release_name_from_uri(PRODUCTION_MODEL_ARTIFACT_URI) == (
        "v2-3e65f5fd-88b81f0"
    )


def test_initialize_model_logs_verified_manifest_identity_once(monkeypatch):
    import fraud_risk.model_service as model_service

    load_calls = []
    loaded_events = []
    fake_model = SimpleNamespace(
        manifest=SimpleNamespace(
            model_version="2",
            source_git_commit=SOURCE_GIT_COMMIT,
        )
    )

    def fake_load_model_bundle(uri):
        load_calls.append(uri)
        assert uri == PRODUCTION_MODEL_ARTIFACT_URI
        return fake_model

    def capture_event(logger, level, event, message, **fields):
        loaded_events.append(
            _event_from_log_call(level, event, message, **fields)
        )

    monkeypatch.setattr(
        model_service,
        "MODEL_ARTIFACT_URI",
        PRODUCTION_MODEL_ARTIFACT_URI,
    )
    monkeypatch.setattr(
        model_service,
        "load_model_bundle",
        fake_load_model_bundle,
    )
    monkeypatch.setattr(model_service, "log_event", capture_event)
    _reset_model_state(model_service)

    assert model_service.initialize_model() is True
    assert model_service.initialize_model() is True

    assert loaded_events[0]["event"] == "model_startup"
    assert loaded_events[0]["model_version"] == "2"
    assert loaded_events[0]["model_release"] == "v2-3e65f5fd-88b81f0"
    assert loaded_events[0]["source_git_commit"] == SOURCE_GIT_COMMIT
    assert loaded_events[0]["model_load_duration_ms"] >= 0
    assert load_calls == [PRODUCTION_MODEL_ARTIFACT_URI]
    assert len(loaded_events) == 1


def test_initialize_model_failure_logs_type_without_exception_message(
    monkeypatch,
):
    import fraud_risk.model_service as model_service

    failed_events = []

    def fail_load_model_bundle(uri):
        raise RuntimeError("raw-secret-value")

    def capture_event(logger, level, event, message, **fields):
        failed_events.append(
            _event_from_log_call(level, event, message, **fields)
        )

    monkeypatch.setattr(
        model_service,
        "MODEL_ARTIFACT_URI",
        PRODUCTION_MODEL_ARTIFACT_URI,
    )
    monkeypatch.setattr(
        model_service,
        "load_model_bundle",
        fail_load_model_bundle,
    )
    monkeypatch.setattr(model_service, "log_event", capture_event)
    _reset_model_state(model_service)

    assert model_service.initialize_model() is False

    event = failed_events[0]
    assert event["event"] == "model_startup_failed"
    assert event["exception_type"] == "RuntimeError"
    assert event["error_message"] == "Model release initialization failed"
    assert "raw-secret-value" not in json.dumps(event)
    assert len(failed_events) == 1


def test_prediction_logs_model_version_latency_and_classification_only(
    monkeypatch,
):
    import fraud_risk.model_service as model_service

    prediction_events = []
    fake_model = SimpleNamespace(
        manifest=SimpleNamespace(
            model_version="2",
            threshold=0.9,
            features=list(PREDICTION_PAYLOAD),
        ),
        predict=lambda frame: [0.91],
    )

    def capture_event(logger, level, event, message, **fields):
        prediction_events.append(
            _event_from_log_call(level, event, message, **fields)
        )

    monkeypatch.setattr(model_service, "log_event", capture_event)
    _reset_model_state(model_service)
    model_service._model = fake_model

    response = model_service.predict_fraud(
        FraudPredictionRequest.model_validate(PREDICTION_PAYLOAD)
    )

    event = prediction_events[0]
    assert response.fraud_probability == 0.91
    assert event["event"] == "prediction_completed"
    assert event["model_version"] == "2"
    assert event["latency_ms"] >= 0
    assert event["is_fraud"] is True
    assert "income" not in event
    assert "fraud_probability" not in event
