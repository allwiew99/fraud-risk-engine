import json
from pathlib import Path

POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "monitoring"
    / "cloud-run-5xx-rate-policy.json"
)
CHANNEL = (
    "projects/fraud-risk-engine/notificationChannels/7232674366703482783"
)


def test_sustained_5xx_policy_has_exact_ratio_and_notification_channel():
    policy = json.loads(POLICY_PATH.read_text())
    threshold = policy["conditions"][0]["conditionThreshold"]

    assert policy["enabled"] is True
    assert policy["notificationChannels"] == [CHANNEL]
    assert threshold["comparison"] == "COMPARISON_GT"
    assert threshold["thresholdValue"] == 0.05
    assert threshold["duration"] == "300s"
    assert 'metric.label.response_code_class="5xx"' in threshold["filter"]
    assert "metric.label.response_code_class" not in threshold[
        "denominatorFilter"
    ]
    for monitored_filter in (
        threshold["filter"],
        threshold["denominatorFilter"],
    ):
        assert 'resource.label.service_name="fraud-risk-api"' in monitored_filter
        assert 'resource.label.location="europe-west1"' in monitored_filter
