from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlparse

import joblib
import pandas as pd
from pydantic import ValidationError
from xgboost import XGBClassifier

from fraud_risk.release_manifest import (
    MANIFEST_VERSION,
    MODEL_FILENAME,
    PREPROCESSOR_FILENAME,
    ModelReleaseManifest,
)
from fraud_risk.schemas import FraudPredictionRequest


class ModelBundleError(RuntimeError):
    """Base error for an unusable model release bundle."""


class MissingManifestError(ModelBundleError):
    pass


class MissingArtifactError(ModelBundleError):
    pass


class MalformedManifestError(ModelBundleError):
    pass


class UnsupportedManifestVersionError(ModelBundleError):
    pass


class ArtifactHashMismatchError(ModelBundleError):
    pass


class FeatureContractMismatchError(ModelBundleError):
    pass


class ModelBundleDownloadError(ModelBundleError):
    pass


@dataclass(frozen=True)
class VerifiedModelBundle:
    manifest: ModelReleaseManifest
    preprocessor_path: Path
    model_path: Path


@dataclass(frozen=True)
class LoadedModelBundle:
    manifest: ModelReleaseManifest
    preprocessor: object
    model: XGBClassifier

    def predict(self, model_input: pd.DataFrame):
        transformed = self.preprocessor.transform(model_input)
        return self.model.predict_proba(transformed)[:, 1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> ModelReleaseManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MalformedManifestError(
            f"Unable to parse manifest.json: {error}"
        ) from error

    if not isinstance(data, dict):
        raise MalformedManifestError(
            "manifest.json must contain a JSON object"
        )

    version = data.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise UnsupportedManifestVersionError(
            f"Unsupported manifest version: {version!r}"
        )

    try:
        return ModelReleaseManifest.model_validate(data)
    except ValidationError as error:
        raise MalformedManifestError(
            f"Invalid manifest.json: {error}"
        ) from error


def verify_model_bundle(bundle_path: Path) -> VerifiedModelBundle:
    bundle_path = Path(bundle_path)
    manifest_path = bundle_path / "manifest.json"
    if not manifest_path.is_file():
        raise MissingManifestError(
            f"Missing manifest.json in {bundle_path}"
        )

    manifest = _load_manifest(manifest_path)
    expected_features = list(FraudPredictionRequest.model_fields)
    if manifest.features != expected_features:
        raise FeatureContractMismatchError(
            "Manifest features do not match the API feature contract"
        )

    artifact_paths = {
        name: bundle_path / name
        for name in manifest.files
    }
    for name, artifact_path in artifact_paths.items():
        if not artifact_path.is_file():
            raise MissingArtifactError(f"Missing artifact: {name}")

        expected_hash = manifest.files[name].sha256
        actual_hash = _sha256(artifact_path)
        if actual_hash != expected_hash:
            raise ArtifactHashMismatchError(
                f"SHA-256 mismatch for {name}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    return VerifiedModelBundle(
        manifest=manifest,
        preprocessor_path=artifact_paths[PREPROCESSOR_FILENAME],
        model_path=artifact_paths[MODEL_FILENAME],
    )


def _local_bundle_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ModelBundleError(
            f"Unsupported model artifact URI scheme: {parsed.scheme!r}"
        )
    return Path(unquote(parsed.path))


def _storage_client():
    try:
        from google.cloud import storage
    except ImportError as error:
        raise ModelBundleDownloadError(
            "google-cloud-storage is required for gs:// model bundles"
        ) from error
    return storage.Client()


@contextmanager
def _materialized_bundle(uri: str, storage_client=None):
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        yield _local_bundle_path(uri)
        return

    if parsed.scheme != "gs":
        raise ModelBundleError(
            f"Unsupported model artifact URI scheme: {parsed.scheme!r}"
        )

    bucket_name = parsed.netloc
    prefix = parsed.path.strip("/")
    if not bucket_name or not prefix:
        raise ModelBundleDownloadError(
            "GCS model artifact URI must include a bucket and release prefix"
        )

    client = storage_client or _storage_client()
    bucket = client.bucket(bucket_name)
    filenames = (
        "manifest.json",
        PREPROCESSOR_FILENAME,
        MODEL_FILENAME,
    )

    with TemporaryDirectory(prefix="fraud-risk-model-") as directory:
        bundle_path = Path(directory)
        try:
            for filename in filenames:
                object_name = f"{prefix}/{filename}"
                bucket.blob(object_name).download_to_filename(
                    bundle_path / filename
                )
        except Exception as error:
            raise ModelBundleDownloadError(
                f"Unable to download model release from {uri}: {error}"
            ) from error
        yield bundle_path


def load_model_bundle(
    uri: str,
    *,
    storage_client=None,
) -> LoadedModelBundle:
    with _materialized_bundle(uri, storage_client) as bundle_path:
        verified = verify_model_bundle(bundle_path)
        preprocessor = joblib.load(verified.preprocessor_path)
        model = XGBClassifier()
        model.load_model(verified.model_path)
        return LoadedModelBundle(
            manifest=verified.manifest,
            preprocessor=preprocessor,
            model=model,
        )
