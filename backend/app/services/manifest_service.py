from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any


def manifest_checksum(payload: dict[str, Any]) -> str:
    canonical = deepcopy(payload)
    canonical.pop("manifest_checksum", None)
    serialized = json.dumps(
        canonical,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"
