from __future__ import annotations

import json

from app.config import get_settings
from app.services.experimental_condition_service import ExperimentalConditionService
from app.services.manifest_service import manifest_checksum
from app.services.pilot_release_service import PilotReleaseService


def main() -> int:
    settings = get_settings()
    conditions = ExperimentalConditionService(
        settings.condition_manifest_path
    ).load_manifest()
    service = PilotReleaseService(
        settings.pilot_release_manifest_path,
        settings.active_pilot_release_path,
    )
    report = service.validate(
        condition_manifest_checksum=manifest_checksum(conditions),
    )
    release = service.load_manifest()
    payload = {
        "valid": report.valid,
        "releaseId": release.get("release_id"),
        "releaseVersion": release.get("release_version"),
        "releaseStatus": release.get("release_status"),
        "answerMode": release.get("selected_answer_mode"),
        "aiProvider": release.get("ai_provider"),
        "aiModel": release.get("ai_model"),
        "errors": report.errors,
        "warnings": report.warnings,
        "releaseModified": False,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
