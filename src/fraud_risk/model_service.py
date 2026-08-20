import mlflow
import pandas as pd

from fraud_risk.config import (
    MLFLOW_TRACKING_URI,
    MODEL_URI,
    THRESHOLD,
)
from fraud_risk.schemas import (
    FraudPredictionRequest,
    FraudPredictionResponse,
)

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

_model = None


def get_model():
    global _model

    if _model is None:
        _model = mlflow.pyfunc.load_model(MODEL_URI)

    return _model


def predict_fraud(
    request: FraudPredictionRequest,
) -> FraudPredictionResponse:
    input_df = pd.DataFrame(
        [request.model_dump()]
    )

    model = get_model()

    fraud_probability = float(
        model.predict(input_df)[0]
    )

    is_fraud = fraud_probability >= THRESHOLD

    return FraudPredictionResponse(
        fraud_probability=fraud_probability,
        is_fraud=is_fraud,
        threshold=THRESHOLD,
    )
