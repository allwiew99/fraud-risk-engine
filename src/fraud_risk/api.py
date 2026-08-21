from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fraud_risk.model_service import (
    ModelNotReadyError,
    initialize_model,
    is_model_ready,
    predict_fraud,
)
from fraud_risk.observability import configure_application_logging
from fraud_risk.schemas import (
    FraudPredictionRequest,
    FraudPredictionResponse,
)

configure_application_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_model()
    yield


app = FastAPI(
    title="Fraud Risk Engine",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(ModelNotReadyError)
def model_not_ready_handler(
    request: Request,
    error: ModelNotReadyError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Model is not ready"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    model_ready = is_model_ready()
    status = "ready" if model_ready else "not_ready"
    status_code = 200 if model_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": status},
    )


@app.post(
    "/predict",
    response_model=FraudPredictionResponse,
)
def predict(
    request: FraudPredictionRequest,
) -> FraudPredictionResponse:
    return predict_fraud(request)
