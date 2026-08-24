"""Authenticated, deterministic smoke verification for a private Cloud Run API."""

import argparse
import json
import math
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


class SmokeCheckError(RuntimeError):
    """Raised when the deployed service differs from the expected contract."""


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

EXPECTED_NEGATIVE_PROBABILITY = 0.13046391308307648
EXPECTED_POSITIVE_PROBABILITY = 0.9620175957679749


def _read_response(response, endpoint):
    try:
        body = response.read()
        return json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SmokeCheckError(f"{endpoint} returned malformed response") from error


def _request(service_url, path, token, opener, payload=None, parse_body=True):
    headers = {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{service_url.rstrip('/')}{path}", data=data, headers=headers)
    if token:
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        response = opener(request)
    except HTTPError as error:
        return error.code, None
    except URLError as error:
        raise SmokeCheckError(f"{path} request failed") from error
    with response:
        return response.status, _read_response(response, path) if parse_body else None


def _require_response(status, body, expected_status, expected_body, endpoint):
    if status != expected_status:
        raise SmokeCheckError(
            f"{endpoint} returned status {status}; expected {expected_status}"
        )
    if not isinstance(body, dict):
        raise SmokeCheckError(f"{endpoint} returned malformed response")
    if body != expected_body:
        raise SmokeCheckError(f"{endpoint} returned an unexpected response body")


def _is_finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _verify_prediction(body, expected_probability, expected_classification, tolerance, label):
    if not isinstance(body, dict):
        raise SmokeCheckError(f"{label} returned malformed response")
    threshold = body.get("threshold")
    if not _is_finite_number(threshold) or threshold != 0.9:
        raise SmokeCheckError("prediction returned an unexpected threshold")
    if body.get("is_fraud") is not expected_classification:
        raise SmokeCheckError("prediction returned an unexpected classification")
    probability = body.get("fraud_probability")
    if not _is_finite_number(probability):
        raise SmokeCheckError("prediction returned an invalid probability")
    difference = abs(probability - expected_probability)
    if difference > tolerance:
        raise SmokeCheckError("prediction probability difference exceeds tolerance")
    return probability, difference


def run_smoke_tests(service_url: str, identity_token: str, opener=urlopen) -> dict:
    """Check the private service health, readiness, and two stable predictions."""
    parsed_service_url = urlsplit(service_url)
    if parsed_service_url.scheme != "https" or not parsed_service_url.netloc:
        raise SmokeCheckError("service URL must use HTTPS")

    status, _ = _request(service_url, "/health", None, opener, parse_body=False)
    if status != 403:
        raise SmokeCheckError(
            f"unauthenticated /health returned status {status}; expected 403"
        )

    health_status, health_body = _request(service_url, "/health", identity_token, opener)
    _require_response(health_status, health_body, 200, {"status": "ok"}, "/health")

    ready_status, ready_body = _request(service_url, "/ready", identity_token, opener)
    _require_response(ready_status, ready_body, 200, {"status": "ready"}, "/ready")

    negative_status, negative_body = _request(
        service_url, "/predict", identity_token, opener, NEGATIVE_SAMPLE
    )
    if negative_status != 200:
        raise SmokeCheckError(f"negative prediction returned status {negative_status}")
    negative_probability, negative_difference = _verify_prediction(
        negative_body, EXPECTED_NEGATIVE_PROBABILITY, False, 1e-7, "negative prediction"
    )

    positive_status, positive_body = _request(
        service_url, "/predict", identity_token, opener, POSITIVE_SAMPLE
    )
    if positive_status != 200:
        raise SmokeCheckError(f"positive prediction returned status {positive_status}")
    positive_probability, positive_difference = _verify_prediction(
        positive_body, EXPECTED_POSITIVE_PROBABILITY, True, 1e-6, "positive prediction"
    )

    return {
        "health": health_status,
        "ready": ready_status,
        "negative_probability": negative_probability,
        "negative_absolute_difference": negative_difference,
        "positive_probability": positive_probability,
        "positive_absolute_difference": positive_difference,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-url", required=True)
    args = parser.parse_args()
    identity_token = os.environ.get("CLOUD_RUN_ID_TOKEN")
    if not identity_token:
        parser.error("CLOUD_RUN_ID_TOKEN must be set")
    try:
        result = run_smoke_tests(args.service_url, identity_token)
    except SmokeCheckError:
        print("Cloud Run smoke verification failed", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
