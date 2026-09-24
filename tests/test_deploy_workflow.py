import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github/workflows/deploy.yml"
)
CI_WORKFLOW_PATH = WORKFLOW_PATH.with_name("ci.yml")
PROJECT_PATH = WORKFLOW_PATH.parents[2] / "pyproject.toml"
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


def _embedded_step_python(step_name: str, next_step_name: str) -> str:
    workflow = WORKFLOW_PATH.read_text()
    step = workflow.split(f"      - name: {step_name}\n", 1)[1].split(
        f"      - name: {next_step_name}\n",
        1,
    )[0]
    embedded_python = step.split("python - <<'PY'\n", 1)[1].split(
        "\n          PY\n",
        1,
    )[0]
    return textwrap.dedent(embedded_python)


def _run_promotion_check(
    script: str,
    state: dict,
    candidate_revision: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SERVICE_STATE_JSON"] = json.dumps(state)
    environment["CANDIDATE_REVISION"] = candidate_revision
    return subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _promotion_reconciliation_parser() -> str:
    return _embedded_step_python(
        "Promote candidate revision to 100 percent",
        "Fail ambiguous promotion reconciliation",
    )


def _promoted_traffic_verifier() -> str:
    return _embedded_step_python(
        "Verify promoted traffic",
        "Mint canonical route identity token",
    )


def test_cloud_run_identity_tokens_are_minted_by_pinned_wif_action():
    workflow = WORKFLOW_PATH.read_text()

    assert "gcloud auth print-identity-token" not in workflow
    assert workflow.count("token_format: id_token") == 2
    assert (
        workflow.count(
            "id_token_audience: "
            "${{ steps.service_preflight.outputs.service_url }}"
        )
        == 2
    )
    assert workflow.count("create_credentials_file: false") == 2
    assert workflow.count("export_environment_variables: false") == 2
    assert "id: candidate_auth" in workflow
    assert "id: canonical_auth" in workflow


def test_ci_and_deploy_run_static_quality_gates():
    ci_workflow = CI_WORKFLOW_PATH.read_text()
    deploy_workflow = WORKFLOW_PATH.read_text()
    project = PROJECT_PATH.read_text()

    assert '"ruff==' in project
    assert '"mypy==' in project
    assert "python -m ruff check ." in ci_workflow
    assert "python -m mypy src scripts" in ci_workflow
    assert "python -m ruff check ." in deploy_workflow
    assert "python -m mypy src scripts" in deploy_workflow


def test_identity_token_flow_preserves_wif_and_never_logs_credentials():
    workflow = WORKFLOW_PATH.read_text()

    assert "id-token: write" in workflow
    assert workflow.count("${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}") == 3
    assert (
        workflow.count(
            "service_account: ${{ env.GCP_DEPLOYER_SERVICE_ACCOUNT }}"
        )
        == 3
    )
    assert "credentials_json:" not in workflow
    assert "${{ secrets." not in workflow
    assert "IDENTITY_TOKEN=" not in workflow
    assert "CLOUD_RUN_ID_TOKEN=" not in workflow
    assert (
        "CLOUD_RUN_ID_TOKEN: ${{ steps.candidate_auth.outputs.id_token }}"
        in workflow
    )
    assert (
        "CLOUD_RUN_ID_TOKEN: ${{ steps.canonical_auth.outputs.id_token }}"
        in workflow
    )
    assert "--service-url=\"$CANDIDATE_URL\"" in workflow
    assert "--service-url=\"$SERVICE_URL\"" in workflow


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


@pytest.mark.parametrize(
    ("script_factory", "expected_stdout"),
    [
        (_promotion_reconciliation_parser, "candidate-100\n"),
        (_promoted_traffic_verifier, ""),
    ],
    ids=("reconciliation", "post-promotion-verification"),
)
def test_promotion_checks_accept_tagged_candidate_as_sole_positive_traffic(
    script_factory,
    expected_stdout,
):
    candidate_revision = "fraud-risk-api-00003-liv"
    state = _service_state(
        latest=candidate_revision,
        traffic=[
            {
                "revisionName": candidate_revision,
                "percent": 100,
                "tag": "candidate-32840376805-1",
            }
        ],
    )

    result = _run_promotion_check(
        script_factory(), state, candidate_revision
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == expected_stdout


@pytest.mark.parametrize(
    "traffic",
    [
        [
            {"revisionName": "fraud-risk-api-00003-liv", "percent": 50},
            {"revisionName": "fraud-risk-api-00001-l7q", "percent": 50},
        ],
        [
            {
                "revisionName": "fraud-risk-api-00003-liv",
                "percent": 50,
                "tag": "candidate-32840376805-1",
            }
        ],
        [
            {
                "revisionName": "fraud-risk-api-00003-liv",
                "percent": 0,
                "tag": "candidate-32840376805-1",
            }
        ],
        [{"revisionName": "fraud-risk-api-00001-l7q", "percent": 100}],
    ],
    ids=(
        "two-positive-revisions",
        "candidate-below-100",
        "no-positive-revision",
        "different-revision-at-100",
    ),
)
def test_promotion_checks_reject_ambiguous_positive_traffic(traffic):
    candidate_revision = "fraud-risk-api-00003-liv"
    state = _service_state(latest=candidate_revision, traffic=traffic)

    reconciliation = _run_promotion_check(
        _promotion_reconciliation_parser(),
        state,
        candidate_revision,
    )
    verification = _run_promotion_check(
        _promoted_traffic_verifier(),
        state,
        candidate_revision,
    )

    assert reconciliation.returncode == 0, reconciliation.stderr
    assert reconciliation.stdout == "ambiguous\n"
    assert verification.returncode != 0
