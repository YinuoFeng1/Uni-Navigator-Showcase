import os
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "logs" / "uni_navigator.db"
DB_PATH = Path(os.environ.get("UNI_NAVIGATOR_DB_PATH", DEFAULT_DB_PATH))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    if not DATABASE_URL.startswith("sqlite:///"):
        return

    expected_columns_by_table = {
        "interactionlog": {
            "session_id": "VARCHAR",
            "participant_label": "VARCHAR",
            "participant_id": "VARCHAR",
            "task_id": "VARCHAR",
            "based_on": "VARCHAR",
            "full_answer": "TEXT",
            "limitations": "VARCHAR",
            "uncertainty": "VARCHAR",
            "escalation_guidance": "VARCHAR",
            "high_stakes_detected": "BOOLEAN",
            "escalation_category": "VARCHAR",
            "escalation_reasons_json": "TEXT",
            "retrieval_status": "VARCHAR",
            "citation_ids": "VARCHAR",
            "citations_json": "TEXT",
            "source_ids": "VARCHAR",
            "retrieved_chunk_ids": "VARCHAR",
            "retrieval_trace_json": "TEXT",
            "retrieved_context_count": "INTEGER",
            "escalation_guidance_present": "BOOLEAN",
            "sensitive_warning_shown": "BOOLEAN",
            "response_time_ms": "INTEGER",
            "error_type": "VARCHAR",
            "embedding_provider": "VARCHAR",
            "embedding_model": "VARCHAR",
            "embedding_dimension": "INTEGER",
            "vector_collection": "VARCHAR",
            "retrieval_partial_threshold": "FLOAT",
            "retrieval_grounded_threshold": "FLOAT",
            "retrieval_top_k": "INTEGER",
            "retrieval_mode": "VARCHAR",
            "scope_decision": "VARCHAR",
            "scope_registry_version": "VARCHAR",
            "scope_registry_fingerprint": "VARCHAR",
            "scope_matched_topics": "VARCHAR",
            "corpus_manifest_fingerprint": "VARCHAR",
            "ai_provider": "VARCHAR",
            "ai_model": "VARCHAR",
            "ai_model_requested": "VARCHAR",
            "provider_response_model": "VARCHAR",
            "provider_response_id": "VARCHAR",
            "input_tokens": "INTEGER",
            "output_tokens": "INTEGER",
            "total_tokens": "INTEGER",
            "token_usage_json": "TEXT",
            "answer_mode": "VARCHAR",
            "task_version": "VARCHAR",
            "app_version": "VARCHAR",
            "app_revision": "VARCHAR",
            "execution_context": "VARCHAR",
            "answer_strategy_version": "VARCHAR",
            "release_id": "VARCHAR",
            "release_version": "VARCHAR",
            "condition_id": "VARCHAR",
            "condition_version": "VARCHAR",
            "task_manifest_version": "VARCHAR",
            "runtime_config_fingerprint": "VARCHAR",
            "runtime_config_json": "TEXT",
            "prompt_template_version": "VARCHAR",
            "generation_temperature": "FLOAT",
            "generation_max_tokens": "INTEGER",
            "technical_run_id": "VARCHAR",
        },
        "studyeventlog": {
            "session_id": "VARCHAR",
            "participant_label": "VARCHAR",
            "interaction_id": "VARCHAR",
            "participant_id": "VARCHAR",
            "task_id": "VARCHAR",
            "condition": "VARCHAR",
            "schema_version": "VARCHAR",
            "occurred_at": "DATETIME",
            "recorded_at": "DATETIME",
            "release_id": "VARCHAR",
            "condition_id": "VARCHAR",
            "app_revision": "VARCHAR",
            "runtime_config_fingerprint": "VARCHAR",
            "idempotency_key": "VARCHAR",
            "payload_json": "VARCHAR",
        },
        "feedbacklog": {
            "session_id": "VARCHAR",
            "participant_label": "VARCHAR",
            "task_id": "VARCHAR",
        },
        "studysession": {
            "prototype_notice_acknowledged": "BOOLEAN",
            "prototype_notice_acknowledged_at": "DATETIME",
            "state": "VARCHAR",
            "release_id": "VARCHAR",
            "release_version": "VARCHAR",
            "condition_version": "VARCHAR",
            "runtime_config_fingerprint": "VARCHAR",
            "app_revision": "VARCHAR",
        },
    }

    with engine.begin() as connection:
        for table_name, expected_columns in expected_columns_by_table.items():
            existing_columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    f"PRAGMA table_info({table_name})"
                ).fetchall()
            }
            for column_name, column_type in expected_columns.items():
                if column_name not in existing_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )


def get_session():
    with Session(engine) as session:
        yield session
