import argparse
import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from app.services.escalation_service import (
    decide_escalation_category,
    escalation_guidance,
)
from app.services.rag_evidence_service import (
    NO_CITATION_STATUSES,
    citations_from_chunks,
)
from app.services.policy_safety import assess_policy_safety
from app.services.retrieval_service import (
    classify_retrieval_status,
    get_corpus_status,
    retrieve_policy_chunks,
)

SMOKE_QUESTIONS_PATH = PROJECT_ROOT / "data" / "evaluation" / "rag_smoke_questions.json"
TOP_K = 5


def load_smoke_questions(path: Path = SMOKE_QUESTIONS_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("RAG smoke questions file must contain a JSON list")
    return [item for item in payload if isinstance(item, dict)]


def run_rag_smoke_test(path: Path = SMOKE_QUESTIONS_PATH) -> dict[str, int]:
    settings = get_settings()
    questions = load_smoke_questions(path)
    pass_count = 0
    warn_count = 0

    print("Uni-Navigator RAG smoke test")
    print(f"questions: {len(questions)}")
    print(f"question_file: {path}")
    corpus_status = get_corpus_status()
    print(
        "vector_store: "
        f"requested={corpus_status.get('vectorStoreProviderRequested')} "
        f"active={corpus_status.get('vectorStoreProviderActive')} "
        f"fallback_used={corpus_status.get('fallbackUsed')}"
    )

    for question in questions:
        question_id = str(question.get("question_id") or "unknown_question")
        text = str(question.get("question") or "")
        expected_sources = {
            str(source_id)
            for source_id in question.get("expected_source_ids", [])
            if source_id
        }
        expected_status = str(question.get("expected_retrieval_status") or "")
        expected_type = _optional_text(question.get("expected_source_type"))
        expected_keywords = [
            str(keyword).lower()
            for keyword in question.get("expected_keywords", [])
            if keyword
        ]
        expected_escalation = question.get("expected_escalation")
        source_mode = _optional_text(question.get("source_mode"))

        results = retrieve_policy_chunks(
            text,
            top_k=TOP_K,
            source_mode=source_mode,
        )
        status = classify_retrieval_status(results, settings=settings)
        safety = assess_policy_safety(text)
        escalation_decision = decide_escalation_category(
            question=text,
            retrieval_status=status,
            scope_decision=None,
            high_stakes_detected=safety.high_stakes_detected,
            safety_categories=safety.categories,
        )
        escalation_recommended = escalation_decision.recommended
        guidance = escalation_guidance(escalation_decision)
        citations = (
            [] if status in NO_CITATION_STATUSES else citations_from_chunks(results)
        )
        retrieved_sources = {
            str(result.get("source_id"))
            for result in results
            if result.get("source_id")
        }
        matched_sources = expected_sources.intersection(retrieved_sources)
        matching_results = [
            result
            for result in results
            if not expected_sources or result.get("source_id") in expected_sources
        ]
        matching_text = " ".join(
            str(result.get("chunk_text") or "").lower()
            for result in matching_results
        )
        top_one_source = str(results[0].get("source_id") or "") if results else ""
        expected_top_one = bool(expected_sources and top_one_source in expected_sources)
        expected_in_top_k = bool(matched_sources)

        source_check_passed = (
            expected_in_top_k
            if expected_sources
            else status == "insufficient_evidence" and not citations
        )
        status_check_passed = not expected_status or status == expected_status
        type_check_passed = not expected_type or (
            bool(matching_results)
            and all(
                result.get("source_type") == expected_type
                for result in matching_results
            )
        )
        keywords_check_passed = all(
            keyword in matching_text for keyword in expected_keywords
        )
        escalation_check_passed = (
            not isinstance(expected_escalation, bool)
            or escalation_recommended is expected_escalation
        )
        official_citations = [
            citation
            for citation in citations
            if citation.sourceType
            in {"official_policy", "official_student_guidance"}
        ]
        citation_metadata_check_passed = all(
            citation.pageStart is not None
            and citation.pageEnd is not None
            and bool(citation.sourceUrl)
            for citation in official_citations
        )
        citation_labels_check_passed = [
            citation.label for citation in citations
        ] == [f"[{index}]" for index in range(1, len(citations) + 1)]

        checks = [
            source_check_passed,
            status_check_passed,
            type_check_passed,
            keywords_check_passed,
            escalation_check_passed,
            citation_metadata_check_passed,
            citation_labels_check_passed,
        ]
        outcome = "PASS" if all(checks) else "WARN"
        if outcome == "PASS":
            pass_count += 1
        else:
            warn_count += 1

        print("")
        print(f"{outcome} {question_id}")
        print(f"question: {text}")
        print(f"retrieval_status: {status}")
        print(f"source_mode: {source_mode or 'configured default'}")
        print(f"expected_sources: {sorted(expected_sources)}")
        print(f"matched_sources: {sorted(matched_sources)}")
        print(f"expected_source_type: {expected_type or 'not specified'}")
        print(f"expected_source_top_1: {expected_top_one}")
        print(f"expected_source_in_top_k: {expected_in_top_k}")
        print(f"expected_keywords_present: {keywords_check_passed}")
        print(f"escalation_recommended: {escalation_recommended}")
        print(f"escalation_category: {escalation_decision.category}")
        print(f"escalation_guidance_present: {bool(guidance)}")
        print(f"citation_metadata_complete: {citation_metadata_check_passed}")
        print(f"citation_labels_valid: {citation_labels_check_passed}")
        for index, result in enumerate(results[:TOP_K], start=1):
            score = result.get("score")
            score_text = f"{score:.3f}" if isinstance(score, int | float) else "n/a"
            passage = " ".join(str(result.get("chunk_text") or "").split())[:180]
            source_label = _source_label(str(result.get("source_type") or ""))
            print(
                f"  {index}. source={result.get('source_id')} "
                f"type={result.get('source_type')} label={source_label} "
                f"page={result.get('page_start')}-{result.get('page_end')} "
                f"chunk={result.get('chunk_id')} score={score_text}"
            )
            print(f"     source_url={result.get('source_url') or result.get('url')}")
            print(f"     passage={passage}")

    print("")
    print(f"summary: {pass_count} PASS, {warn_count} WARN")
    return {"questions": len(questions), "pass": pass_count, "warn": warn_count}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Uni-Navigator RAG smoke checks")
    parser.add_argument(
        "--question-file",
        type=Path,
        default=SMOKE_QUESTIONS_PATH,
        help="JSON question set to run (defaults to the prepared-corpus baseline).",
    )
    args = parser.parse_args()
    run_rag_smoke_test(args.question_file)


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _source_label(source_type: str) -> str:
    if source_type == "official_policy":
        return "Official policy"
    if source_type == "official_student_guidance":
        return "Official guidance"
    return "Prepared prototype"


if __name__ == "__main__":
    main()
