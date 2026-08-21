from fastapi.testclient import TestClient

import fraud_risk.api as api
from fraud_risk.api import app
from fraud_risk.schemas import FraudPredictionResponse


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_503_before_model_is_loaded(monkeypatch):
    monkeypatch.setattr(api, "is_model_ready", lambda: False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_ready_returns_200_after_model_is_loaded(monkeypatch):
    monkeypatch.setattr(api, "is_model_ready", lambda: True)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_predict(monkeypatch):
    def fake_predict_fraud(request):
        return FraudPredictionResponse(
            fraud_probability=0.13046391308307648,
            is_fraud=False,
            threshold=0.9,
        )

    monkeypatch.setattr(
        api,
        "predict_fraud",
        fake_predict_fraud,
    )

    payload = {
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

    response = client.post("/predict", json=payload)

    assert response.status_code == 200

    body = response.json()

    assert body["is_fraud"] is False
    assert body["threshold"] == 0.9
    assert abs(
        body["fraud_probability"] - 0.13046391308307648
    ) < 1e-6


def test_predict_missing_required_field():
    payload = {
        "income": 0.9,
        "name_email_similarity": 0.6312595428642337,
    }

    response = client.post("/predict", json=payload)

    assert response.status_code == 422


def test_predict_fraud_true(monkeypatch):
    def fake_predict_fraud(request):
        return FraudPredictionResponse(
            fraud_probability=0.9620176,
            is_fraud=True,
            threshold=0.9,
        )

    monkeypatch.setattr(
        api,
        "predict_fraud",
        fake_predict_fraud,
    )

    payload = {
        "income": 0.6000000000000001,
        "name_email_similarity": 0.0552121590907224,
        "prev_address_months_count": -1,
        "current_address_months_count": 75,
        "customer_age": 30,
        "days_since_request": 0.0048924491272589,
        "intended_balcon_amount": -0.4304898848409637,
        "payment_type": "AD",
        "zip_count_4w": 852,
        "velocity_6h": 3613.136025251703,
        "velocity_24h": 1926.3003380033435,
        "velocity_4w": 3079.2487331451725,
        "bank_branch_count_8w": 2,
        "date_of_birth_distinct_emails_4w": 3,
        "employment_status": "CA",
        "credit_risk_score": 96,
        "email_is_free": 1,
        "housing_status": "BA",
        "phone_home_valid": 0,
        "phone_mobile_valid": 1,
        "bank_months_count": 30,
        "has_other_cards": 0,
        "proposed_credit_limit": 200.0,
        "foreign_request": 0,
        "source": "INTERNET",
        "session_length_in_minutes": 4.6506036418338015,
        "device_os": "windows",
        "keep_alive_session": 0,
        "device_distinct_emails_8w": 1,
        "device_fraud_count": 0,
    }

    response = client.post("/predict", json=payload)

    assert response.status_code == 200

    body = response.json()

    assert body["is_fraud"] is True
    assert body["threshold"] == 0.9
    assert abs(
        body["fraud_probability"] - 0.9620176
    ) < 1e-6
