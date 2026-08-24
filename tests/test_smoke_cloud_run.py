import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler

import pytest

import scripts.smoke_cloud_run as smoke_cloud_run
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


class RawFakeResponse(FakeResponse):
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body


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
                "has_unredirected_authorization": (
                    "Authorization" in request.unredirected_hdrs
                ),
                "has_regular_authorization": "Authorization" in request.headers,
            }
        )
        response = next(self._responses)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, FakeResponse):
            return response
        status, body = response
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
            "has_unredirected_authorization": False,
            "has_regular_authorization": False,
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
            "has_unredirected_authorization": False,
            "has_regular_authorization": False,
        },
        {
            "url": "https://service.example/health",
            "method": "GET",
            "has_authorization": True,
            "has_unredirected_authorization": True,
            "has_regular_authorization": False,
        },
        {
            "url": "https://service.example/ready",
            "method": "GET",
            "has_authorization": True,
            "has_unredirected_authorization": True,
            "has_regular_authorization": False,
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
            "has_unredirected_authorization": True,
            "has_regular_authorization": False,
        },
        {
            "url": "https://service.example/predict",
            "method": "POST",
            "has_authorization": True,
            "has_unredirected_authorization": True,
            "has_regular_authorization": False,
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


def test_smoke_continues_after_plain_text_unauthenticated_http_error():
    # Parsing a gateway's plain-text denial must not mask its required 403 status.
    denial = HTTPError(
        "https://service.example/health",
        403,
        "Forbidden",
        None,
        io.BytesIO(b"access denied"),
    )
    opener = FakeOpener([denial, *successful_responses()[1:]])

    result = run_smoke_tests("https://service.example", "test-token", opener)

    assert result["health"] == 200
    assert result["ready"] == 200


def test_smoke_rejects_unexpected_unauthenticated_http_error():
    # HTTP failures other than the expected private-service denial are not success.
    failure = HTTPError(
        "https://service.example/health",
        500,
        "Internal Server Error",
        None,
        io.BytesIO(b"untrusted response"),
    )
    opener = FakeOpener([failure])

    with pytest.raises(SmokeCheckError):
        run_smoke_tests("https://service.example", "test-token", opener)


def test_smoke_requires_an_https_service_url():
    # A caller selecting cleartext transport must fail before any HTTP request.
    opener = FakeOpener([])

    with pytest.raises(SmokeCheckError):
        run_smoke_tests("http://service.example", "test-token", opener)

    assert opener.calls == []


def test_smoke_does_not_send_authorization_on_cross_origin_redirect():
    # Replacing an unredirected header with a regular header would leak it here.
    class RedirectInspectingOpener(FakeOpener):
        def __init__(self, responses):
            super().__init__(responses)
            self.redirected_request = None

        def __call__(self, request):
            response = super().__call__(request)
            if request.has_header("Authorization") and self.redirected_request is None:
                self.redirected_request = HTTPRedirectHandler().redirect_request(
                    request,
                    response,
                    302,
                    "Found",
                    {"Location": "https://other.example/redirected"},
                    "https://other.example/redirected",
                )
            return response

    opener = RedirectInspectingOpener(successful_responses())

    run_smoke_tests("https://service.example", "test-token", opener)

    assert opener.redirected_request is not None
    assert opener.redirected_request.full_url == "https://other.example/redirected"
    assert not opener.redirected_request.has_header("Authorization")


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), float("-inf"), True])
def test_smoke_rejects_non_finite_or_boolean_probability(invalid_value):
    # Non-finite and boolean values are not valid measured probabilities.
    responses = successful_responses()
    responses[3] = (
        200,
        {"fraud_probability": invalid_value, "is_fraud": False, "threshold": 0.9},
    )
    opener = FakeOpener(responses)

    with pytest.raises(SmokeCheckError):
        run_smoke_tests("https://service.example", "test-token", opener)


def test_smoke_rejects_out_of_tolerance_probability():
    # A finite prediction beyond tolerance must not be accepted as equivalent.
    responses = successful_responses()
    responses[3] = (
        200,
        {
            "fraud_probability": 0.13047391308307648,
            "is_fraud": False,
            "threshold": 0.9,
        },
    )
    opener = FakeOpener(responses)

    with pytest.raises(SmokeCheckError):
        run_smoke_tests("https://service.example", "test-token", opener)


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), float("-inf"), True])
def test_smoke_rejects_non_finite_or_boolean_threshold(invalid_value):
    # Threshold validation must use the same real finite-number rule.
    responses = successful_responses()
    responses[3] = (
        200,
        {
            "fraud_probability": NEGATIVE_PREDICTION["fraud_probability"],
            "is_fraud": False,
            "threshold": invalid_value,
        },
    )
    opener = FakeOpener(responses)

    with pytest.raises(SmokeCheckError):
        run_smoke_tests("https://service.example", "test-token", opener)


@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (RawFakeResponse(200, b"<html>untrusted response</html>"), "/health returned malformed response"),
        (RawFakeResponse(200, b"\xff"), "/health returned malformed response"),
        ((200, ["untrusted response"]), "negative prediction returned malformed response"),
    ],
)
def test_smoke_normalizes_malformed_bodies_to_safe_errors(response, expected_message):
    # Raw response data and request details must never escape in error messages.
    responses = successful_responses()
    if isinstance(response, tuple):
        responses[3] = response
    else:
        responses[1] = response
    opener = FakeOpener(responses)

    with pytest.raises(SmokeCheckError) as error:
        run_smoke_tests("https://service.example", "test-token", opener)

    assert str(error.value) == expected_message
    assert "untrusted response" not in str(error.value)
    assert "test-token" not in str(error.value)
    assert "income" not in str(error.value)


@pytest.mark.parametrize(
    "failure_kind",
    ("malformed", "transport", "semantic"),
)
def test_main_emits_one_fixed_safe_line_for_smoke_failures(
    monkeypatch,
    capsys,
    failure_kind,
):
    token = "cli-token-secret-428af9"
    raw_response = "raw-response-secret-17a20c"
    feature_detail = "income=0.987654"
    transport_detail = f"{Path.cwd()}/transport-secret"
    decoder_detail = "decoder-secret-50d4a1"

    def fail_smoke(service_url, identity_token):
        assert service_url == "https://service.example"
        assert identity_token == token
        if failure_kind == "malformed":
            try:
                raise UnicodeDecodeError(
                    "utf-8",
                    b"\xff",
                    0,
                    1,
                    decoder_detail,
                )
            except UnicodeDecodeError as error:
                raise SmokeCheckError(
                    f"malformed response: {raw_response}"
                ) from error
        if failure_kind == "transport":
            raise SmokeCheckError(
                f"transport failure at {transport_detail}"
            )
        raise SmokeCheckError(
            f"semantic mismatch for {feature_detail}"
        )

    monkeypatch.setattr(smoke_cloud_run, "run_smoke_tests", fail_smoke)
    monkeypatch.setattr(
        sys,
        "argv",
        ["smoke_cloud_run.py", "--service-url=https://service.example"],
    )
    monkeypatch.setenv("CLOUD_RUN_ID_TOKEN", token)

    exit_code = smoke_cloud_run.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Cloud Run smoke verification failed\n"
    for unsafe_value in (
        token,
        raw_response,
        feature_detail,
        "income",
        "0.987654",
        transport_detail,
        decoder_detail,
        "UnicodeDecodeError",
        "SmokeCheckError",
        "Traceback",
    ):
        assert unsafe_value not in captured.err


def test_main_preserves_success_json_output(monkeypatch, capsys):
    result = {
        "health": 200,
        "ready": 200,
        "negative_probability": 0.13046391308307648,
        "negative_absolute_difference": 0.0,
        "positive_probability": 0.9620175957679749,
        "positive_absolute_difference": 0.0,
    }
    monkeypatch.setattr(
        smoke_cloud_run,
        "run_smoke_tests",
        lambda service_url, identity_token: result,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["smoke_cloud_run.py", "--service-url=https://service.example"],
    )
    monkeypatch.setenv("CLOUD_RUN_ID_TOKEN", "success-token-secret")

    exit_code = smoke_cloud_run.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == f"{json.dumps(result, sort_keys=True)}\n"
    assert captured.err == ""
    assert "success-token-secret" not in captured.out
