import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github/workflows/deploy.yml"
)
SERVICE_URL = "https://fraud-risk-api.example.run.app"


def _service_preflight_parser() -> str:
    workflow = WORKFLOW_PATH.read_text()
    service_step = workflow.split(
        "      - name: Verify existing private service\n",
        1,
    )[1].split(
        "      - name: Configure Docker authentication for regional registry\n",
        1,
    )[0]
    embedded_python = service_step.split(
        "            SERVICE_STATE_JSON=\"$SERVICE_STATE_JSON\" python - <<'PY'\n",
        1,
    )[1].split("\n          PY\n", 1)[0]
    return textwrap.dedent(embedded_python)


def _run_service_preflight(state: dict) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SERVICE_STATE_JSON"] = json.dumps(state)
    return subprocess.run(
        [sys.executable, "-c", _service_preflight_parser()],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _service_state(*, latest: str, traffic: object) -> dict:
    return {
        "status": {
            "latestReadyRevisionName": latest,
            "url": SERVICE_URL,
            "traffic": traffic,
        }
    }


def test_preflight_selects_sole_ordinary_serving_revision_not_failed_latest():
    state = _service_state(
        latest="rev-failed",
        traffic=[
            {
                "tag": "candidate-failed",
                "revisionName": "rev-failed",
                "percent": 0,
                "url": "https://candidate-failed.example.run.app",
            },
            {"revisionName": "rev-serving", "percent": 100},
        ],
    )

    result = _run_service_preflight(state)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"rev-serving\t{SERVICE_URL}\n"


def test_preflight_accepts_one_explicit_ordinary_serving_revision():
    state = _service_state(
        latest="rev-serving",
        traffic=[{"revisionName": "rev-serving", "percent": 100}],
    )

    result = _run_service_preflight(state)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"rev-serving\t{SERVICE_URL}\n"


@pytest.mark.parametrize(
    "traffic",
    [
        [
            {"revisionName": "rev-a", "percent": 50},
            {"revisionName": "rev-b", "percent": 50},
        ],
        [
            {"revisionName": "rev-a", "percent": 100},
            {"revisionName": "rev-b", "percent": 100},
        ],
        [
            {
                "tag": "candidate-only",
                "revisionName": "rev-latest",
                "percent": 0,
            }
        ],
        [],
        [{"latestRevision": True, "percent": 100}],
        {"revisionName": "rev-serving", "percent": 100},
        [{"tag": 0, "revisionName": "rev-serving", "percent": 100}],
    ],
    ids=(
        "split-traffic",
        "multiple-ordinary-revisions",
        "tag-only",
        "zero-traffic-entries",
        "latest-only",
        "malformed-traffic-state",
        "malformed-tag",
    ),
)
def test_preflight_fails_closed_without_one_explicit_ordinary_100_revision(
    traffic,
):
    state = _service_state(latest="rev-latest", traffic=traffic)

    result = _run_service_preflight(state)

    assert result.returncode != 0
    assert result.stdout == ""
