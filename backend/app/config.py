from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "Uni-Navigator Backend")
        self.app_env = os.getenv("APP_ENV", "development")
        self.app_version = os.getenv("APP_VERSION", "0.1.0")
        requested_study_mode = os.getenv("STUDY_MODE", "development").lower()
        self.study_mode = (
            requested_study_mode
            if requested_study_mode in {"development", "pilot"}
            else "development"
        )
        self.answer_mode = "live_llm"
        requested_execution_context = os.getenv(
            "EXECUTION_CONTEXT",
            "participant_study" if self.study_mode == "pilot" else "development",
        ).lower()
        self.execution_context = requested_execution_context
        self.app_revision = os.getenv("APP_REVISION", self.app_version)
        self.prompt_template_version = os.getenv(
            "PROMPT_TEMPLATE_VERSION", "grounded-v9"
        )
        self.generation_temperature = self._read_float(
            "GENERATION_TEMPERATURE", 0.0
        )
        self.generation_max_tokens = max(
            1, self._read_int("GENERATION_MAX_TOKENS", 400)
        )
        self.generation_reasoning_effort = os.getenv(
            "GENERATION_REASONING_EFFORT", "none"
        ).strip().lower()
        self.frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3001")
        self.database_url = os.getenv(
            "DATABASE_URL", "sqlite:///./data/logs/uni_navigator.db"
        )
        self.policy_dir = os.getenv("POLICY_DIR", "../data/policies")
        self.index_dir = os.getenv("INDEX_DIR", "../data/index")
        self.log_dir = os.getenv("LOG_DIR", "../data/logs")
        self.corpus_path = self._project_path(os.getenv("CORPUS_PATH", "data/corpus"))
        self.scope_registry_path = self._project_path(
            os.getenv("SCOPE_REGISTRY_PATH", "data/corpus/corpus_scope.json")
        )
        self.vector_store_path = self._project_path(
            os.getenv("VECTOR_STORE_PATH", "data/vector_store")
        )
        self.vector_store_provider = os.getenv("VECTOR_STORE_PROVIDER", "chroma").lower()
        self.vector_collection_name = os.getenv(
            "VECTOR_STORE_COLLECTION",
            os.getenv("VECTOR_COLLECTION_NAME", "uni_navigator_policy_chunks"),
        )
        self.vector_store_allow_fallback = (
            os.getenv("VECTOR_STORE_ALLOW_FALLBACK", "false").lower()
            not in {"0", "false", "no"}
        )
        requested_source_mode = os.getenv("RETRIEVAL_SOURCE_MODE", "official").lower()
        self.retrieval_source_mode = (
            requested_source_mode
            if requested_source_mode
            in {"all", "prepared", "official", "prefer_official"}
            else "official"
        )
        self.ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.ai_model = os.getenv(
            "AI_MODEL",
            os.getenv("OPENAI_MODEL", "gpt-5.4-mini-2026-03-17"),
        )
        self.openai_model = self.ai_model
        self.ai_timeout_seconds = self._read_float("AI_TIMEOUT_SECONDS", 30.0)
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.embedding_batch_size = max(
            1, self._read_int("EMBEDDING_BATCH_SIZE", 32)
        )
        self.embedding_batch_delay_seconds = max(
            0.0, self._read_float("EMBEDDING_BATCH_DELAY_SECONDS", 0.0)
        )
        self.embedding_timeout_seconds = max(
            1.0, self._read_float("EMBEDDING_TIMEOUT_SECONDS", 60.0)
        )
        self.embedding_max_retries = max(
            0, self._read_int("EMBEDDING_MAX_RETRIES", 3)
        )
        self.embedding_retry_base_seconds = max(
            0.0, self._read_float("EMBEDDING_RETRY_BASE_SECONDS", 1.0)
        )
        self.retrieval_partial_score_threshold = self._read_float(
            "RETRIEVAL_PARTIAL_SCORE_THRESHOLD", 0.15
        )
        self.retrieval_grounded_score_threshold = self._read_float(
            "RETRIEVAL_GROUNDED_SCORE_THRESHOLD", 0.35
        )
        self.retrieval_top_k = max(1, self._read_int("RETRIEVAL_TOP_K", 5))
        self.pilot_expected_embedding_provider = os.getenv(
            "PILOT_EXPECTED_EMBEDDING_PROVIDER", "openai"
        ).lower()
        self.pilot_expected_embedding_model = os.getenv(
            "PILOT_EXPECTED_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.pilot_expected_vector_provider = os.getenv(
            "PILOT_EXPECTED_VECTOR_PROVIDER", "chroma"
        ).lower()
        self.pilot_expected_vector_collection = os.getenv(
            "PILOT_EXPECTED_VECTOR_COLLECTION", self.vector_collection_name
        )
        self.pilot_expected_source_count = max(
            1, self._read_int("PILOT_EXPECTED_SOURCE_COUNT", 10)
        )
        self.pilot_expected_chunk_count = max(
            1, self._read_int("PILOT_EXPECTED_CHUNK_COUNT", 77)
        )
        self.pilot_allow_synthetic_sessions = (
            os.getenv("PILOT_ALLOW_SYNTHETIC_SESSIONS", "false").lower()
            in {"1", "true", "yes"}
        )
        self.condition_manifest_path = self._project_path(
            os.getenv(
                "CONDITION_MANIFEST_PATH", "data/study/experimental_conditions.json"
            )
        )
        self.pilot_release_manifest_path = self._project_path(
            os.getenv(
                "PILOT_RELEASE_MANIFEST_PATH",
                "data/study/pilot_release_manifest.json",
            )
        )
        self.active_pilot_release_path = self._project_path(
            os.getenv(
                "ACTIVE_PILOT_RELEASE_PATH",
                "data/study/active_pilot_release.json",
            )
        )
        self.task_manifest_version = os.getenv(
            "TASK_MANIFEST_VERSION", "study-tasks-2026-07-17.1"
        )
        self.technical_evaluation_output_path = self._project_path(
            os.getenv(
                "TECHNICAL_EVALUATION_OUTPUT_PATH",
                "data/evaluation/technical_runs.jsonl",
            )
        )
        self.cors_origins = self._build_cors_origins()

    def _project_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path

    def _read_float(self, key: str, default: float) -> float:
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default

    def _read_int(self, key: str, default: int) -> int:
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

    def _build_cors_origins(self) -> list[str]:
        origins = {
            self.frontend_origin,
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        }
        return sorted(origin for origin in origins if origin)


@lru_cache
def get_settings() -> Settings:
    return Settings()
