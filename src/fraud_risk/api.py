from fastapi import FastAPI

from fraud_risk.model_service import predict_fraud
from fraud_risk.schemas import (
    FraudPredictionRequest,
    FraudPredictionResponse,
)


app = FastAPI(
    title="Fraud Risk Engine",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/predict",
    response_model=FraudPredictionResponse,
)
def predict(
    request: FraudPredictionRequest,
) -> FraudPredictionResponse:
    return predict_fraud(request)