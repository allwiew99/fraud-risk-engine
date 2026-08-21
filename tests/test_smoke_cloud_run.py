import json

import pytest

from scripts.smoke_cloud_run import SmokeCheckError, run_smoke_tests


NEGATIVE_PREDICTION = {
    "fraud_probability": 0.13046391308307648,
    "is_fraud": False,
    "threshold": 0.9,
}
POSITIVE_PREDICTION = {
    "fraud_probability": 0.9620175957679749,
    "is_fraud": True,
    "threshold": 0.9,
}


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return json.dumps(self._body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeOpener:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []

    def __call__(self, request):
        self.calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "has_authorization": request.has_header("Authorization"),
            }
        )
        status, body = next(self._responses)
        return FakeResponse(status, body)


def successful_responses():
    return [
        (403, {"detail": "Forbidden"}),
        (200, {"status": "ok"}),
        (200, {"status": "ready"}),
        (200, NEGATIVE_PREDICTION),
        (200, POSITIVE_PREDICTION),
    ]


def test_smoke_requires_unauthenticated_health_to_be_403():
    # A publicly accessible health endpoint must fail this private-service check.
    opener = FakeOpener([(200, {"status": "ok"})])

    with pytest.raises(SmokeCheckError):
        run_smoke_tests("https://service.example", "test-token", opener)

    assert opener.calls == [
        {
            "url": "https://service.example/health",
            "method": "GET",
            "has_authorization": False,
        }
    ]


def test_smoke_accepts_expected_health_and_readiness():
    # A changed health or readiness contract must fail this smoke verification.
    opener = FakeOpener(successful_responses())

    result = run_smoke_tests("https://service.example", "test-token", opener)

    assert result["health"] == 200
    assert result["ready"] == 200
    assert opener.calls[:3] == [
        {
            "url": "https://service.example/health",
            "method": "GET",
            "has_authorization": False,
        },
        {
            "url": "https://service.example/health",
            "method": "GET",
            "has_authorization": True,
        },
        {
            "url": "https://service.example/ready",
            "method": "GET",
            "has_authorization": True,
        },
    ]


def test_smoke_accepts_both_known_prediction_contracts():
    # Incorrect expected predictions or request authentication must fail this check.
    opener = FakeOpener(successful_responses())

    result = run_smoke_tests("https://service.example", "test-token", opener)

    assert result["negative_probability"] == 0.13046391308307648
    assert result["negative_absolute_difference"] == 0.0
    assert result["positive_probability"] == 0.9620175957679749
    assert result["positive_absolute_difference"] == 0.0
    assert opener.calls[3:] == [
        {
            "url": "https://service.example/predict",
            "method": "POST",
            "has_authorization": True,
        },
        {
            "url": "https://service.example/predict",
            "method": "POST",
            "has_authorization": True,
        },
    ]
    serialized_result = json.dumps(result, sort_keys=True)
    assert "test-token" not in serialized_result
    assert "income" not in serialized_result


def test_smoke_rejects_probability_or_classification_mismatch():
    # A production classification that disagrees with the known positive case must fail.
    responses = successful_responses()
    responses[-1] = (
        200,
        {
            "fraud_probability": 0.9620175957679749,
            "is_fraud": False,
            "threshold": 0.9,
        },
    )
    opener = FakeOpener(responses)

    with pytest.raises(SmokeCheckError):
        run_smoke_tests("https://service.example", "test-token", opener)
