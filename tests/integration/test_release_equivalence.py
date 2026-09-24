import mlflow
import numpy as np
import pandas as pd
import pytest

from fraud_risk.config import MLFLOW_TRACKING_URI, MODEL_URI
from fraud_risk.model_bundle import load_model_bundle
from fraud_risk.release_export import export_champion_release

pytestmark = pytest.mark.integration


NEGATIVE_SAMPLE = {
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

POSITIVE_SAMPLE = {
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


def test_exported_release_matches_mlflow_champion(tmp_path):
    release_path = export_champion_release(output_root=tmp_path)
    released_model = load_model_bundle(release_path.as_uri())

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    champion = mlflow.pyfunc.load_model(MODEL_URI)
    samples = pd.DataFrame([NEGATIVE_SAMPLE, POSITIVE_SAMPLE])

    released_probabilities = released_model.predict(samples)
    champion_probabilities = champion.predict(samples)

    np.testing.assert_allclose(
        released_probabilities,
        champion_probabilities,
        rtol=0.0,
        atol=1e-7,
    )
    assert released_probabilities[0] == pytest.approx(
        0.13046391308307648,
        abs=1e-7,
    )
    assert released_probabilities[1] == pytest.approx(
        0.9620176,
        abs=1e-6,
    )
