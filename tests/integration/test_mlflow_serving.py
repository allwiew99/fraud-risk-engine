import mlflow
import pandas as pd
import pytest

from fraud_risk.config import MLFLOW_TRACKING_URI, MODEL_URI

pytestmark = pytest.mark.integration


def test_champion_model_predicts_known_sample():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    model = mlflow.pyfunc.load_model(MODEL_URI)

    sample = pd.DataFrame(
        [
            {
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
        ]
    )

    probability = float(model.predict(sample)[0])

    assert abs(
        probability - 0.13046391308307648
    ) < 1e-6
