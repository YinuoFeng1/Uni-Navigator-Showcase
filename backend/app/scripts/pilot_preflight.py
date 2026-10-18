import json
import argparse

from app.config import get_settings
from app.services.pilot_preflight_service import run_pilot_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate participant pilot readiness.")
    parser.add_argument(
        "--no-session-scan",
        action="store_true",
        help="Do not read existing session labels; use for privacy-safe release checks.",
    )
    args = parser.parse_args()
    report = run_pilot_preflight(
        get_settings(), session_labels=[] if args.no_session_scan else None
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
