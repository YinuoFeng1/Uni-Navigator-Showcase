from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.technical_evaluation import summarize_manual_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize a completed Uni-Navigator manual answer review CSV."
    )
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = summarize_manual_review(args.review_csv)
    output = args.output or args.review_csv.with_name(
        f"{args.review_csv.stem}_summary.json"
    )
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"summary_file: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
