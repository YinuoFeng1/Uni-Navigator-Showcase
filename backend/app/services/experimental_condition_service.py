from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from app.core.errors import ApplicationError
from app.services.manifest_service import manifest_checksum


@dataclass(frozen=True)
class ConditionValidationReport:
    valid: bool
    errors: list[str]
    warnings: list[str]


class ExperimentalConditionService:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_manifest(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="experimental condition manifest unavailable",
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("conditions"), list
        ):
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="experimental condition schema invalid",
            )
        return payload

    def validate(self) -> ConditionValidationReport:
        manifest = self.load_manifest()
        errors: list[str] = []
        warnings: list[str] = []
        if manifest.get("manifest_checksum") != manifest_checksum(manifest):
            errors.append("condition manifest checksum mismatch")
        conditions = manifest["conditions"]
        ids = [item.get("condition_id") for item in conditions]
        if len(ids) != len(set(ids)):
            errors.append("duplicate condition IDs")
        for condition in conditions:
            if condition.get("answer_mode") != "live_llm":
                errors.append(
                    f"{condition.get('condition_id')}: participant condition must use live_llm"
                )
            if not condition.get("active"):
                warnings.append(f"{condition.get('condition_id')}: inactive condition")
        return ConditionValidationReport(not errors, errors, warnings)

    def get_condition(self, condition_id: str) -> dict[str, Any]:
        for condition in self.load_manifest()["conditions"]:
            if condition.get("condition_id") == condition_id:
                return condition
        raise ApplicationError(
            "client_context_mismatch",
            researcher_safe_detail="condition does not exist in server manifest",
        )
