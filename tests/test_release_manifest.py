import pytest
from pydantic import ValidationError

from fraud_risk.release_manifest import ModelReleaseManifest


FEATURES = [
    "income",
    "name_email_similarity",
    "prev_address_months_count",
    "current_address_months_count",
    "customer_age",
    "days_since_request",
    "intended_balcon_amount",
    "payment_type",
    "zip_count_4w",
    "velocity_6h",
    "velocity_24h",
    "velocity_4w",
    "bank_branch_count_8w",
    "date_of_birth_distinct_emails_4w",
    "employment_status",
    "credit_risk_score",
    "email_is_free",
    "housing_status",
    "phone_home_valid",
    "phone_mobile_valid",
    "bank_months_count",
    "has_other_cards",
    "proposed_credit_limit",
    "foreign_request",
    "source",
    "session_length_in_minutes",
    "device_os",
    "keep_alive_session",
    "device_distinct_emails_8w",
    "device_fraud_count",
]


def valid_manifest_data() -> dict:
    return {
        "manifest_version": "1",
        "model_name": "fraud-risk-model",
        "model_version": "3",
        "mlflow_run_id": "15e72c463980489e94b6823d17edcd75",
        "mlflow_model_id": "m-3e65f5fd985a4b6f929abc2057fc7a89",
        "threshold": 0.9,
        "features": FEATURES,
        "source_git_commit": "a" * 40,
        "created_at": "2026-08-21T10:00:00Z",
        "files": {
            "xgb_preprocessor.joblib": {"sha256": "b" * 64},
            "xgb_champion.ubj": {"sha256": "c" * 64},
        },
    }


def test_valid_manifest_accepts_exact_release_contract():
    manifest = ModelReleaseManifest.model_validate(valid_manifest_data())

    assert manifest.manifest_version == "1"
    assert manifest.threshold == 0.9
    assert manifest.features == FEATURES
    assert set(manifest.files) == {
        "xgb_preprocessor.joblib",
        "xgb_champion.ubj",
    }


def test_manifest_rejects_unsupported_version():
    data = valid_manifest_data()
    data["manifest_version"] = "2"

    with pytest.raises(ValidationError, match="manifest_version"):
        ModelReleaseManifest.model_validate(data)


def test_manifest_rejects_mutable_model_alias_as_version():
    data = valid_manifest_data()
    data["model_version"] = "champion"

    with pytest.raises(ValidationError, match="model_version"):
        ModelReleaseManifest.model_validate(data)


def test_manifest_rejects_timestamp_without_timezone():
    data = valid_manifest_data()
    data["created_at"] = "2026-08-21T10:00:00"

    with pytest.raises(ValidationError, match="created_at"):
        ModelReleaseManifest.model_validate(data)


def test_manifest_rejects_missing_required_field():
    data = valid_manifest_data()
    del data["threshold"]

    with pytest.raises(ValidationError, match="threshold"):
        ModelReleaseManifest.model_validate(data)


def test_manifest_rejects_unexpected_artifact_name():
    data = valid_manifest_data()
    data["files"]["extra.pkl"] = {"sha256": "d" * 64}

    with pytest.raises(ValidationError, match="files"):
        ModelReleaseManifest.model_validate(data)


def test_manifest_rejects_unknown_fields():
    data = valid_manifest_data()
    data["mutable_alias"] = "champion"

    with pytest.raises(ValidationError, match="mutable_alias"):
        ModelReleaseManifest.model_validate(data)
