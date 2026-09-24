import os

DEFAULT_MLFLOW_TRACKING_URI = "http://127.0.0.1:5000"
MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    DEFAULT_MLFLOW_TRACKING_URI,
)

MODEL_URI = "models:/fraud-risk-model@champion"

DEFAULT_MODEL_ARTIFACT_URI = "file:///app/model-release"
MODEL_ARTIFACT_URI = os.getenv(
    "MODEL_ARTIFACT_URI",
    DEFAULT_MODEL_ARTIFACT_URI,
)
