import hashlib
import json

import pytest

import fraud_risk.model_bundle as model_bundle_module
from fraud_risk.model_bundle import (
    ArtifactHashMismatchError,
    MalformedManifestError,
    MissingArtifactError,
    MissingManifestError,
    UnsupportedManifestVersionError,
    load_model_bundle,
    verify_model_bundle,
)

from tests.test_release_manifest import FEATURES, valid_manifest_data


def write_bundle(tmp_path):
    preprocessor = tmp_path / "xgb_preprocessor.joblib"
    model = tmp_path / "xgb_champion.ubj"
    preprocessor.write_bytes(b"preprocessor")
    model.write_bytes(b"model")

    data = valid_manifest_data()
    data["files"] = {
        preprocessor.name: {
            "sha256": hashlib.sha256(preprocessor.read_bytes()).hexdigest(),
        },
        model.name: {
            "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        },
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(data),
        encoding="utf-8",
    )
    return tmp_path


def test_valid_bundle_verifies_manifest_and_hashes(tmp_path):
    bundle = write_bundle(tmp_path)

    verified = verify_model_bundle(bundle)

    assert verified.manifest.model_version == "3"
    assert verified.manifest.features == FEATURES
    assert verified.preprocessor_path.name == "xgb_preprocessor.joblib"
    assert verified.model_path.name == "xgb_champion.ubj"


def test_missing_manifest_fails_closed(tmp_path):
    with pytest.raises(MissingManifestError, match="manifest.json"):
        verify_model_bundle(tmp_path)


def test_missing_artifact_fails_closed(tmp_path):
    bundle = write_bundle(tmp_path)
    (bundle / "xgb_champion.ubj").unlink()

    with pytest.raises(MissingArtifactError, match="xgb_champion.ubj"):
        verify_model_bundle(bundle)


def test_hash_mismatch_fails_closed(tmp_path):
    bundle = write_bundle(tmp_path)
    (bundle / "xgb_champion.ubj").write_bytes(b"tampered")

    with pytest.raises(ArtifactHashMismatchError, match="xgb_champion.ubj"):
        verify_model_bundle(bundle)


def test_unsupported_manifest_version_has_explicit_error(tmp_path):
    bundle = write_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["manifest_version"] = "2"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(UnsupportedManifestVersionError, match="2"):
        verify_model_bundle(bundle)


def test_malformed_manifest_has_explicit_error(tmp_path):
    (tmp_path / "manifest.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(MalformedManifestError, match="manifest.json"):
        verify_model_bundle(tmp_path)


def test_hashes_are_checked_before_deserialization(tmp_path, monkeypatch):
    bundle = write_bundle(tmp_path)
    (bundle / "xgb_preprocessor.joblib").write_bytes(b"tampered")
    deserialization_calls = []

    monkeypatch.setattr(
        "fraud_risk.model_bundle.joblib.load",
        lambda path: deserialization_calls.append(path),
    )

    with pytest.raises(ArtifactHashMismatchError):
        load_model_bundle(bundle.as_uri())

    assert deserialization_calls == []


def test_gcs_bundle_downloads_only_release_contract_without_credentials(
    tmp_path,
    monkeypatch,
):
    local_bundle = write_bundle(tmp_path)
    prefix = "releases/v3-model-id"
    objects = {
        f"{prefix}/{name}": (local_bundle / name).read_bytes()
        for name in (
            "manifest.json",
            "xgb_preprocessor.joblib",
            "xgb_champion.ubj",
        )
    }
    requested_objects = []

    class FakeBlob:
        def __init__(self, name):
            self.name = name

        def download_to_filename(self, filename):
            requested_objects.append(self.name)
            with open(filename, "wb") as destination:
                destination.write(objects[self.name])

    class FakeBucket:
        def blob(self, name):
            return FakeBlob(name)

    class FakeStorageClient:
        def bucket(self, name):
            assert name == "fraud-risk-engine-models"
            return FakeBucket()

    class FakePreprocessor:
        pass

    class FakeModel:
        def load_model(self, path):
            assert path.name == "xgb_champion.ubj"

    monkeypatch.setattr(
        model_bundle_module.joblib,
        "load",
        lambda path: FakePreprocessor(),
    )
    monkeypatch.setattr(
        model_bundle_module,
        "XGBClassifier",
        FakeModel,
    )

    loaded = load_model_bundle(
        "gs://fraud-risk-engine-models/releases/v3-model-id",
        storage_client=FakeStorageClient(),
    )

    assert loaded.manifest.model_version == "3"
    assert requested_objects == [
        f"{prefix}/manifest.json",
        f"{prefix}/xgb_preprocessor.joblib",
        f"{prefix}/xgb_champion.ubj",
    ]
