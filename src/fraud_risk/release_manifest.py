from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

MANIFEST_VERSION: Literal["1"] = "1"
PREPROCESSOR_FILENAME = "xgb_preprocessor.joblib"
MODEL_FILENAME = "xgb_champion.ubj"
REQUIRED_ARTIFACTS = frozenset(
    {PREPROCESSOR_FILENAME, MODEL_FILENAME}
)

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GitCommit = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
ModelVersion = Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]


class ArtifactFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sha256: Sha256


class ModelReleaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: Literal["1"]
    model_name: str = Field(min_length=1)
    model_version: ModelVersion
    mlflow_run_id: str | None = None
    mlflow_model_id: str | None = None
    threshold: float = Field(ge=0.0, le=1.0)
    features: list[str] = Field(min_length=1)
    source_git_commit: GitCommit
    created_at: AwareDatetime
    files: dict[str, ArtifactFile]

    @model_validator(mode="after")
    def require_exact_artifacts(self):
        if set(self.files) != REQUIRED_ARTIFACTS:
            raise ValueError(
                "files must contain exactly: "
                + ", ".join(sorted(REQUIRED_ARTIFACTS))
            )
        return self
