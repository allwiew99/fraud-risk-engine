import pandas as pd

from fraud_risk.config import MODEL_ARTIFACT_URI
from fraud_risk.model_bundle import load_model_bundle
from fraud_risk.schemas import (
    FraudPredictionRequest,
    FraudPredictionResponse,
)


class ModelNotReadyError(RuntimeError):
    pass


_model = None
_model_load_error: Exception | None = None


def initialize_model() -> bool:
    global _model, _model_load_error

    if _model is not None:
        return True
    if _model_load_error is not None:
        return False

    try:
        _model = load_model_bundle(MODEL_ARTIFACT_URI)
    except Exception as error:
        _model_load_error = error
        return False

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
    model = get_model()
    input_df = pd.DataFrame(
        [request.model_dump()],
        columns=model.manifest.features,
    )
    fraud_probability = float(model.predict(input_df)[0])
    threshold = model.manifest.threshold
    is_fraud = fraud_probability >= threshold

    return FraudPredictionResponse(
        fraud_probability=fraud_probability,
        is_fraud=is_fraud,
        threshold=threshold,
    )
