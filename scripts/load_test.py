"""Small, dependency-free load client for the private prediction endpoint."""

import argparse
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.smoke_cloud_run import (
    EXPECTED_NEGATIVE_PROBABILITY,
    NEGATIVE_SAMPLE,
)


def nearest_rank_percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be between 1 and 100")
    ordered = sorted(values)
    rank = math.ceil((percentile / 100) * len(ordered))
    return ordered[rank - 1]


def _prediction_is_valid(body: object) -> bool:
    if not isinstance(body, dict):
        return False
    probability = body.get("fraud_probability")
    return (
        isinstance(probability, (int, float))
        and not isinstance(probability, bool)
        and math.isfinite(probability)
        and abs(probability - EXPECTED_NEGATIVE_PROBABILITY) <= 1e-7
        and body.get("is_fraud") is False
        and body.get("threshold") == 0.9
    )


def _one_prediction(
    service_url: str,
    identity_token: str | None,
    opener,
) -> tuple[float, bool]:
    headers = {"Content-Type": "application/json"}
    request = Request(
        f"{service_url.rstrip('/')}/predict",
        data=json.dumps(NEGATIVE_SAMPLE).encode(),
        headers=headers,
    )
    if identity_token:
        request.add_unredirected_header(
            "Authorization",
            f"Bearer {identity_token}",
        )

    started_at = perf_counter()
    try:
        with opener(request, timeout=30) as response:
            raw_body = response.read()
            body = json.loads(raw_body.decode("utf-8"))
            success = response.status == 200 and _prediction_is_valid(body)
    except Exception:
        success = False
    latency_ms = (perf_counter() - started_at) * 1000
    return latency_ms, success


def run_load_test(
    service_url: str,
    *,
    concurrency: int,
    request_count: int,
    identity_token: str | None = None,
    opener=urlopen,
) -> dict[str, int | float]:
    parsed = urlsplit(service_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("service URL must use HTTP or HTTPS")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    if request_count < 1:
        raise ValueError("request count must be at least 1")

    started_at = perf_counter()
    with ThreadPoolExecutor(
        max_workers=min(concurrency, request_count)
    ) as executor:
        measurements = list(
            executor.map(
                lambda _: _one_prediction(
                    service_url,
                    identity_token,
                    opener,
                ),
                range(request_count),
            )
        )
    duration_seconds = perf_counter() - started_at
    latencies = [latency for latency, _ in measurements]
    successful = sum(success for _, success in measurements)
    failed = request_count - successful

    return {
        "concurrency": concurrency,
        "requests": request_count,
        "successful_requests": successful,
        "failed_requests": failed,
        "error_rate": failed / request_count,
        "duration_seconds": round(duration_seconds, 6),
        "rps": round(request_count / duration_seconds, 3),
        "p50_latency_ms": round(nearest_rank_percentile(latencies, 50), 3),
        "p95_latency_ms": round(nearest_rank_percentile(latencies, 95), 3),
        "p99_latency_ms": round(nearest_rank_percentile(latencies, 99), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--requests", type=int, required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--model-release", required=True)
    parser.add_argument("--instance-config", required=True)
    args = parser.parse_args()

    result = run_load_test(
        args.service_url,
        concurrency=args.concurrency,
        request_count=args.requests,
        identity_token=os.environ.get("CLOUD_RUN_ID_TOKEN"),
    )
    output = {
        "environment": args.environment,
        "revision": args.revision,
        "model_release": args.model_release,
        "instance_config": args.instance_config,
        **result,
    }
    print(json.dumps(output, sort_keys=True))
    return 0 if result["failed_requests"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
