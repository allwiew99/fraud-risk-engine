import logging
from time import perf_counter

import pandas as pd

from fraud_risk.config import MODEL_ARTIFACT_URI
from fraud_risk.model_bundle import load_model_bundle
from fraud_risk.observability import log_event, release_name_from_uri
from fraud_risk.schemas import (
    FraudPredictionRequest,
    FraudPredictionResponse,
)


class ModelNotReadyError(RuntimeError):
    pass


_model = None
_model_load_error: Exception | None = None
logger = logging.getLogger(__name__)


def initialize_model() -> bool:
    global _model, _model_load_error

    if _model is not None:
        return True
    if _model_load_error is not None:
        return False

    started_at = perf_counter()
    try:
        _model = load_model_bundle(MODEL_ARTIFACT_URI)
    except Exception as error:
        _model_load_error = error
        log_event(
            logger,
            logging.ERROR,
            "model_startup_failed",
            "Model release initialization failed",
            model_release=release_name_from_uri(MODEL_ARTIFACT_URI),
            model_load_duration_ms=round(
                (perf_counter() - started_at) * 1000,
                3,
            ),
            exception_type=type(error).__name__,
            error_message="Model release initialization failed",
        )
        return False

    log_event(
        logger,
        logging.INFO,
        "model_startup",
        "Verified model release loaded",
        model_version=_model.manifest.model_version,
        model_release=release_name_from_uri(MODEL_ARTIFACT_URI),
        source_git_commit=_model.manifest.source_git_commit,
        model_load_duration_ms=round(
            (perf_counter() - started_at) * 1000,
            3,
        ),
    )
    return True


def is_model_ready() -> bool:
    return _model is not None


def get_model_load_error() -> Exception | None:
    return _model_load_error


def get_model():
    if _model is None:
        raise ModelNotReadyError(
            "The verified model release is not loaded"
        )
    return _model


def predict_fraud(
    request: FraudPredictionRequest,
) -> FraudPredictionResponse:
    started_at = perf_counter()
    try:
        model = get_model()
        input_df = pd.DataFrame(
            [request.model_dump()],
            columns=model.manifest.features,
        )
        fraud_probability = float(model.predict(input_df)[0])
        threshold = model.manifest.threshold
        is_fraud = fraud_probability >= threshold
        response = FraudPredictionResponse(
            fraud_probability=fraud_probability,
            is_fraud=is_fraud,
            threshold=threshold,
        )
    except Exception as error:
        log_event(
            logger,
            logging.ERROR,
            "prediction_failed",
            "Prediction failed",
            exception_type=type(error).__name__,
            error_message="Prediction failed",
        )
        raise

    log_event(
        logger,
        logging.INFO,
        "prediction_completed",
        "Prediction completed",
        model_version=model.manifest.model_version,
        latency_ms=round((perf_counter() - started_at) * 1000, 3),
        is_fraud=is_fraud,
    )
    return response
