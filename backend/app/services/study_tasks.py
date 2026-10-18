import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

STUDY_TASKS_PATH = PROJECT_ROOT / "data" / "study_tasks.json"


def load_study_tasks(path: Path = STUDY_TASKS_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Study tasks file must contain a JSON list")
    return [task for task in payload if isinstance(task, dict)]


def active_study_tasks() -> list[dict[str, Any]]:
    return [task for task in load_study_tasks() if task.get("active") is True]


def get_study_task(task_id: str) -> dict[str, Any] | None:
    return next(
        (task for task in load_study_tasks() if task.get("task_id") == task_id),
        None,
    )


def study_tasks_by_id() -> dict[str, dict[str, Any]]:
    return {
        str(task.get("task_id")): task
        for task in load_study_tasks()
        if task.get("task_id")
    }
