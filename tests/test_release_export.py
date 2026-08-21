from datetime import UTC, datetime
import json

import pytest

from fraud_risk.release_export import (
    ResolvedModelVersion,
    build_release_bundle,
)

from tests.test_release_manifest import FEATURES


def downloaded_mlflow_model(tmp_path):
    model_directory = tmp_path / "downloaded-model"
    artifacts = model_directory / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "xgb_preprocessor.joblib").write_bytes(
        b"approved-preprocessor"
    )
    (artifacts / "xgb_champion.ubj").write_bytes(b"approved-model")
    (model_directory / "MLmodel").write_text(
        "model_id: m-model-id\n",
        encoding="utf-8",
    )
    (model_directory / "python_model.pkl").write_bytes(b"do-not-export")
    return model_directory


def resolved_version():
    return ResolvedModelVersion(
        model_name="fraud-risk-model",
        model_version="3",
        mlflow_run_id="15e72c463980489e94b6823d17edcd75",
        mlflow_model_id="m-model-id",
        source_uri="models:/m-model-id",
    )


def test_build_release_exports_only_approved_artifacts_and_manifest(tmp_path):
    downloaded = downloaded_mlflow_model(tmp_path)
    output_root = tmp_path / "releases"

    release_path = build_release_bundle(
        resolved=resolved_version(),
        downloaded_model_path=downloaded,
        output_root=output_root,
        source_git_commit="a" * 40,
        created_at=datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
    )

    assert release_path.name == "v3-m-model-id"
    assert sorted(path.name for path in release_path.iterdir()) == [
        "manifest.json",
        "xgb_champion.ubj",
        "xgb_preprocessor.joblib",
    ]

    manifest = json.loads(
        (release_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["manifest_version"] == "1"
    assert manifest["model_name"] == "fraud-risk-model"
    assert manifest["model_version"] == "3"
    assert manifest["mlflow_run_id"] == (
        "15e72c463980489e94b6823d17edcd75"
    )
    assert manifest["mlflow_model_id"] == "m-model-id"
    assert manifest["threshold"] == 0.9
    assert manifest["features"] == FEATURES
    assert manifest["source_git_commit"] == "a" * 40
    assert manifest["created_at"] == "2026-08-21T10:00:00Z"
    assert len(
        manifest["files"]["xgb_preprocessor.joblib"]["sha256"]
    ) == 64
    assert len(manifest["files"]["xgb_champion.ubj"]["sha256"]) == 64


def test_build_release_refuses_to_overwrite_existing_release(tmp_path):
    output_root = tmp_path / "releases"
    existing = output_root / "v3-m-model-id"
    existing.mkdir(parents=True)
    marker = existing / "keep.txt"
    marker.write_text("unchanged", encoding="utf-8")

    with pytest.raises(FileExistsError, match="v3-m-model-id"):
        build_release_bundle(
            resolved=resolved_version(),
            downloaded_model_path=downloaded_mlflow_model(tmp_path),
            output_root=output_root,
            source_git_commit="a" * 40,
            created_at=datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
        )

    assert marker.read_text(encoding="utf-8") == "unchanged"
