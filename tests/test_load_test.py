import json
import threading
import time

from scripts.load_test import nearest_rank_percentile, run_load_test


class FakeResponse:
    status = 200

    def read(self):
        return json.dumps(
            {
                "fraud_probability": 0.13046391308307648,
                "is_fraud": False,
                "threshold": 0.9,
            }
        ).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_nearest_rank_percentiles_are_deterministic():
    values = [10.0, 20.0, 30.0, 40.0]

    assert nearest_rank_percentile(values, 50) == 20.0
    assert nearest_rank_percentile(values, 95) == 40.0
    assert nearest_rank_percentile(values, 99) == 40.0


def test_load_test_accounts_for_all_requests_and_bounds_concurrency():
    lock = threading.Lock()
    active = 0
    maximum_active = 0

    def opener(request, timeout):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.005)
        with lock:
            active -= 1
        return FakeResponse()

    result = run_load_test(
        "http://127.0.0.1:9090",
        concurrency=3,
        request_count=12,
        identity_token="private-token",
        opener=opener,
    )

    assert result["requests"] == 12
    assert result["successful_requests"] == 12
    assert result["failed_requests"] == 0
    assert result["error_rate"] == 0.0
    assert result["concurrency"] == 3
    assert result["rps"] > 0
    assert result["p50_latency_ms"] >= 0
    assert result["p95_latency_ms"] >= result["p50_latency_ms"]
    assert result["p99_latency_ms"] >= result["p95_latency_ms"]
    assert 1 < maximum_active <= 3
    serialized = json.dumps(result)
    assert "private-token" not in serialized
    assert "income" not in serialized


def test_load_test_counts_transport_failures_without_exposing_details():
    raw_secret = "upstream-secret-response"

    def opener(request, timeout):
        raise RuntimeError(raw_secret)

    result = run_load_test(
        "https://service.example",
        concurrency=2,
        request_count=4,
        identity_token="private-token",
        opener=opener,
    )

    assert result["successful_requests"] == 0
    assert result["failed_requests"] == 4
    assert result["error_rate"] == 1.0
    assert raw_secret not in json.dumps(result)
    assert "private-token" not in json.dumps(result)
