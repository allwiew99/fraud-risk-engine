import json
import logging
import sys
from urllib.parse import urlparse

SAFE_EVENT_FIELDS = (
    "event",
    "model_version",
    "model_release",
    "source_git_commit",
    "model_load_duration_ms",
    "latency_ms",
    "is_fraud",
    "exception_type",
    "error_message",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        for field in SAFE_EVENT_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_application_logging() -> logging.Logger:
    logger = logging.getLogger("fraud_risk")
    if not any(
        getattr(handler, "_fraud_risk_json", False)
        for handler in logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler._fraud_risk_json = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    **fields,
) -> None:
    safe_fields = {
        key: value
        for key, value in fields.items()
        if key in SAFE_EVENT_FIELDS and key != "event"
    }
    logger.log(level, message, extra={"event": event, **safe_fields})


def release_name_from_uri(uri: str) -> str:
    path = urlparse(uri).path.rstrip("/")
    return path.rsplit("/", 1)[-1]
