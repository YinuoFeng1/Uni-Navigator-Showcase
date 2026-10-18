from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from app.config import Settings
from app.services.experimental_condition_service import ExperimentalConditionService
from app.services.interaction_provenance import (
    corpus_manifest_fingerprint,
    scope_registry_fingerprint,
)
from app.services.manifest_service import manifest_checksum
from app.services.pilot_preflight_service import run_pilot_preflight
from app.services.pilot_release_service import PilotReleaseService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_DIR = PROJECT_ROOT / "data" / "study"
COLLECTION = "uni_navigator_policy_chunks_openai"


class _FixtureVectorStore:
    def __init__(self, source_count: int, chunk_count: int):
        self.source_count = source_count
        self.chunk_count = chunk_count
        self.query_count = 0

    def status(self):
        from types import SimpleNamespace

        return SimpleNamespace(
            active_provider="chroma",
            fallback_used=False,
            collection_name=COLLECTION,
            source_count=self.source_count,
            chunk_count=self.chunk_count,
            embedding_dimension=1536,
            collection_metadata={
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
            },
        )

    def query(self, query_embedding, top_k=1):
        self.query_count += 1
        return []


def test_complete_temporary_frozen_release_fixture_passes_preflight(
    tmp_path: Path,
) -> None:
    # Exercise the release boundary with a synthetic manifest, not a local index.
    vector_path = tmp_path / "vectors"
    vector_path.mkdir()
    current_manifest = {
        "latest_ingestion_at": "2026-08-27T00:00:00Z",
        "collection_name": COLLECTION,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": 1536,
        "source_count": 1,
        "chunk_count": 1,
        "sources": {"fixture-policy": {"source_type": "official_policy", "active": True}},
    }
    (vector_path / f"ingestion_manifest.{COLLECTION}.json").write_text(
        json.dumps(current_manifest), encoding="utf-8"
    )
    reference_settings = Settings()
    reference_settings.vector_store_path = vector_path
    reference_settings.vector_collection_name = COLLECTION
    current_fingerprint = corpus_manifest_fingerprint(reference_settings)
    scope_version = json.loads(
        (PROJECT_ROOT / "data" / "corpus" / "corpus_scope.json").read_text()
    )["registry_version"]

    condition_manifest = deepcopy(
        json.loads((STUDY_DIR / "experimental_conditions.json").read_text())
    )
    condition_path = tmp_path / "conditions.json"
    condition_path.write_text(json.dumps(condition_manifest), encoding="utf-8")

    release = deepcopy(
        json.loads((STUDY_DIR / "pilot_release_manifest.json").read_text())
    )
    release["corpus_fingerprint"] = current_fingerprint
    release["corpus_manifest_version"] = current_manifest["latest_ingestion_at"]
    release["scope_registry_version"] = scope_version
    release["scope_registry_fingerprint"] = scope_registry_fingerprint(
        PROJECT_ROOT / "data" / "corpus" / "corpus_scope.json"
    )
    release["release_status"] = "frozen"
    release["reviewed_by"] = "fixture-reviewer"
    release["reviewed_at"] = "2026-08-27T00:00:00Z"
    release["reviewer_notes"] = "Temporary complete system configuration fixture."
    release["app_revision"] = "0123456789abcdef0123456789abcdef01234567"
    release["condition_manifest_checksum"] = manifest_checksum(condition_manifest)
    release["manifest_checksum"] = manifest_checksum(release)
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(release), encoding="utf-8")
    pointer_path = tmp_path / "pointer.json"
    pointer_path.write_text(
        json.dumps(
            {
                "active_release_id": release["release_id"],
                "active_release_version": release["release_version"],
            }
        ),
        encoding="utf-8",
    )

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    store = _FixtureVectorStore(
        source_count=int(current_manifest["source_count"]),
        chunk_count=int(current_manifest["chunk_count"]),
    )

    settings = Settings()
    settings.study_mode = "pilot"
    settings.execution_context = "participant_study"
    settings.answer_mode = "live_llm"
    settings.ai_provider = "openai"
    settings.openai_api_key = "test-key"
    settings.ai_model = release["ai_model"]
    settings.prompt_template_version = release["prompt_template_version"]
    settings.generation_temperature = release["generation_temperature"]
    settings.generation_max_tokens = release["generation_max_tokens"]
    settings.generation_reasoning_effort = release[
        "generation_reasoning_effort"
    ]
    settings.embedding_provider = "openai"
    settings.embedding_model = "text-embedding-3-small"
    settings.vector_store_provider = "chroma"
    settings.vector_store_allow_fallback = False
    settings.retrieval_partial_score_threshold = release[
        "retrieval_partial_threshold"
    ]
    settings.retrieval_grounded_score_threshold = release[
        "retrieval_grounded_threshold"
    ]
    settings.retrieval_top_k = release["retrieval_top_k"]
    settings.retrieval_source_mode = release["retrieval_source_mode"]
    settings.vector_store_path = vector_path
    settings.vector_collection_name = COLLECTION
    settings.pilot_expected_vector_collection = COLLECTION
    settings.pilot_expected_vector_provider = "chroma"
    settings.pilot_expected_embedding_provider = "openai"
    settings.pilot_expected_embedding_model = "text-embedding-3-small"
    settings.pilot_expected_source_count = int(current_manifest["source_count"])
    settings.pilot_expected_chunk_count = int(current_manifest["chunk_count"])
    settings.condition_manifest_path = condition_path
    settings.pilot_release_manifest_path = release_path
    settings.active_pilot_release_path = pointer_path
    settings.scope_registry_path = PROJECT_ROOT / "data" / "corpus" / "corpus_scope.json"
    settings.task_manifest_version = release["task_manifest_version"]
    settings.app_revision = release["app_revision"]

    report = run_pilot_preflight(
        settings,
        vector_store=store,
        database_path=log_dir / "fixture.db",
        session_labels=[],
        condition_service=ExperimentalConditionService(condition_path),
        release_service=PilotReleaseService(release_path, pointer_path),
    )

    assert report.ok is True, [check for check in report.to_dict()["checks"] if check["status"] == "FAIL"]
    assert store.query_count >= 1
