from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

from fraud_risk.config import (
    MLFLOW_TRACKING_URI,
)
from fraud_risk.release_manifest import (
    MANIFEST_VERSION,
    MODEL_FILENAME,
    PREPROCESSOR_FILENAME,
    ArtifactFile,
    ModelReleaseManifest,
)
from fraud_risk.schemas import FraudPredictionRequest


MODEL_NAME = "fraud-risk-model"
CHAMPION_ALIAS = "champion"
PRODUCTION_THRESHOLD = 0.90


@dataclass(frozen=True)
class ResolvedModelVersion:
    model_name: str
    model_version: str
    mlflow_run_id: str | None
    mlflow_model_id: str | None
    source_uri: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_component(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(f"Unsafe release identifier: {value!r}")
    return value


def _release_name(resolved: ResolvedModelVersion) -> str:
    immutable_id = resolved.mlflow_model_id or resolved.mlflow_run_id
    if not immutable_id:
        raise ValueError(
            "The resolved MLflow model has no immutable model or run ID"
        )
    return (
        f"v{_release_component(resolved.model_version)}-"
        f"{_release_component(immutable_id)}"
    )


def build_release_bundle(
    *,
    resolved: ResolvedModelVersion,
    downloaded_model_path: Path,
    output_root: Path,
    source_git_commit: str,
    created_at: datetime,
) -> Path:
    downloaded_model_path = Path(downloaded_model_path)
    output_root = Path(output_root)
    release_path = output_root / _release_name(resolved)
    if release_path.exists():
        raise FileExistsError(
            f"Immutable release already exists: {release_path}"
        )

    source_artifacts = downloaded_model_path / "artifacts"
    source_paths = {
        PREPROCESSOR_FILENAME: source_artifacts / PREPROCESSOR_FILENAME,
        MODEL_FILENAME: source_artifacts / MODEL_FILENAME,
    }
    for name, source_path in source_paths.items():
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Downloaded MLflow model is missing {name}"
            )

    output_root.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(
        tempfile.mkdtemp(
            prefix=f".{release_path.name}-",
            dir=output_root,
        )
    )
    try:
        for name, source_path in source_paths.items():
            shutil.copy2(source_path, temporary_path / name)

        manifest = ModelReleaseManifest(
            manifest_version=MANIFEST_VERSION,
            model_name=resolved.model_name,
            model_version=resolved.model_version,
            mlflow_run_id=resolved.mlflow_run_id,
            mlflow_model_id=resolved.mlflow_model_id,
            threshold=PRODUCTION_THRESHOLD,
            features=list(FraudPredictionRequest.model_fields),
            source_git_commit=source_git_commit,
            created_at=created_at,
            files={
                name: ArtifactFile(sha256=_sha256(temporary_path / name))
                for name in sorted(source_paths)
            },
        )
        manifest_json = json.dumps(
            manifest.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        (temporary_path / "manifest.json").write_text(
            manifest_json + "\n",
            encoding="utf-8",
        )
        temporary_path.rename(release_path)
    finally:
        if temporary_path.exists():
            shutil.rmtree(temporary_path)

    return release_path


def _model_id_from_source(source_uri: str) -> str | None:
    parsed = urlparse(source_uri)
    candidates = [
        part
        for part in parsed.path.split("/")
        if part.startswith("m-")
    ]
    return candidates[-1] if candidates else None


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def export_champion_release(
    *,
    output_root: Path,
    tracking_uri: str = MLFLOW_TRACKING_URI,
) -> Path:
    try:
        import mlflow
        from mlflow import MlflowClient
    except ImportError as error:
        raise RuntimeError(
            "Install the release dependencies to export from MLflow"
        ) from error

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()
    model_version = client.get_model_version_by_alias(
        MODEL_NAME,
        CHAMPION_ALIAS,
    )
    resolved = ResolvedModelVersion(
        model_name=MODEL_NAME,
        model_version=str(model_version.version),
        mlflow_run_id=model_version.run_id,
        mlflow_model_id=_model_id_from_source(model_version.source),
        source_uri=model_version.source,
    )
    downloaded_path = Path(
        mlflow.artifacts.download_artifacts(
            artifact_uri=resolved.source_uri,
        )
    )
    return build_release_bundle(
        resolved=resolved,
        downloaded_model_path=downloaded_path,
        output_root=output_root,
        source_git_commit=_git_commit(),
        created_at=datetime.now(UTC),
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Export the MLflow champion as an immutable local release",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("dist/model-release"),
    )
    parser.add_argument(
        "--tracking-uri",
        default=MLFLOW_TRACKING_URI,
    )
    args = parser.parse_args()
    release_path = export_champion_release(
        output_root=args.output_root,
        tracking_uri=args.tracking_uri,
    )
    print(release_path)
