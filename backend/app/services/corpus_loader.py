import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError


PREPARED_SOURCE_TYPE = "prepared_policy"
OFFICIAL_SOURCE_TYPES = {"official_policy", "official_student_guidance"}
SUPPORTED_PREPARED_SUFFIXES = {".md", ".txt", ".json"}
SourceSelection = Literal["prepared", "official", "all"]
MIN_EXTRACTED_PAGE_CHARS = 20
logger = logging.getLogger(__name__)


class CorpusValidationError(ValueError):
    pass


class PdfExtractionError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PolicyPage:
    page_number: int
    text: str
    section: str


@dataclass(frozen=True)
class PdfExtractionResult:
    pages: tuple[PolicyPage, ...]
    page_count: int
    empty_pages: tuple[int, ...]
    ocr_required: bool
    image_only: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PolicyDocument:
    source_id: str
    title: str
    document_name: str
    section: str
    url: str
    source_type: str
    updated_at: str
    access_date: str
    prototype_only: bool
    text: str
    path: str
    institution: str = ""
    active: bool = True
    version: str = ""
    effective_date: str = ""
    superseded_date: str = ""
    notes: str = ""
    document_checksum: str = ""
    pages: tuple[PolicyPage, ...] = ()
    ocr_required: bool = False
    empty_pages: tuple[int, ...] = ()

    @property
    def source_url(self) -> str:
        return self.url


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    source_id: str
    title: str
    document_name: str
    section: str
    url: str
    source_type: str
    updated_at: str
    access_date: str
    prototype_only: bool
    chunk_index: int
    chunk_text: str
    institution: str = ""
    active: bool = True
    version: str = ""
    effective_date: str = ""
    superseded_date: str = ""
    document_checksum: str = ""
    page_start: int | None = None
    page_end: int | None = None

    def metadata(self) -> dict[str, str | int | float | bool]:
        metadata: dict[str, str | int | float | bool] = {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "title": self.title,
            "document_name": self.document_name,
            "section": self.section,
            "url": self.url,
            "source_url": self.url,
            "source_type": self.source_type,
            "prototype_only": self.prototype_only,
            "active": self.active,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "document_checksum": self.document_checksum,
        }
        optional: dict[str, str | int | None] = {
            "institution": self.institution,
            "updated_at": self.updated_at,
            "access_date": self.access_date,
            "version": self.version,
            "effective_date": self.effective_date,
            "superseded_date": self.superseded_date,
            "page_start": self.page_start,
            "page_end": self.page_end,
        }
        metadata.update(
            {key: value for key, value in optional.items() if value not in {None, ""}}
        )
        return metadata


@dataclass
class CorpusLoadReport:
    files_discovered: int = 0
    metadata_files_validated: int = 0
    pdfs_extracted: int = 0
    pages_extracted: int = 0
    pdfs_requiring_ocr: int = 0
    invalid_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    inactive_sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorpusLoadResult:
    documents: list[PolicyDocument]
    report: CorpusLoadReport


def ensure_corpus_structure(corpus_path: str | Path) -> dict[str, Path]:
    root = Path(corpus_path)
    paths = {
        "root": root,
        "prepared": root / "prepared",
        "official": root / "official",
        "metadata": root / "metadata",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def load_corpus(
    corpus_path: str | Path,
    source_type: SourceSelection = "all",
) -> list[PolicyDocument]:
    result = load_corpus_with_report(corpus_path, source_type=source_type)
    for message in result.report.invalid_files:
        logger.warning("Skipping invalid corpus file: %s", message)
    for message in result.report.warnings:
        logger.warning("Corpus warning: %s", message)
    return result.documents


def load_corpus_with_report(
    corpus_path: str | Path,
    source_type: SourceSelection = "all",
) -> CorpusLoadResult:
    if source_type not in {"prepared", "official", "all"}:
        raise ValueError(f"Unsupported source selection: {source_type}")

    paths = ensure_corpus_structure(corpus_path)
    report = CorpusLoadReport()
    documents: list[PolicyDocument] = []

    if source_type in {"prepared", "all"}:
        for file_path in _discover_prepared_files(paths):
            report.files_discovered += 1
            try:
                document = load_policy_document(file_path)
                if document.source_type != PREPARED_SOURCE_TYPE:
                    raise CorpusValidationError(
                        f"prepared source must use source_type={PREPARED_SOURCE_TYPE}"
                    )
                if document.text.strip():
                    documents.append(document)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                report.invalid_files.append(f"{file_path}: {exc}")

    if source_type in {"official", "all"}:
        official_pdfs = sorted(paths["official"].rglob("*.pdf"))
        expected_metadata_paths: set[Path] = set()
        for pdf_path in official_pdfs:
            report.files_discovered += 1
            relative = pdf_path.relative_to(paths["official"])
            metadata_path = (paths["metadata"] / relative).with_suffix(".json")
            expected_metadata_paths.add(metadata_path)
            try:
                metadata = load_official_metadata(metadata_path)
                report.metadata_files_validated += 1
                extraction = extract_pdf(pdf_path)
                report.pdfs_extracted += 1
                report.pages_extracted += extraction.page_count
                report.warnings.extend(extraction.warnings)
                if extraction.ocr_required:
                    report.pdfs_requiring_ocr += 1
                document = _official_document(
                    pdf_path=pdf_path,
                    metadata=metadata,
                    extraction=extraction,
                )
                if not document.active:
                    report.inactive_sources.append(document.source_id)
                documents.append(document)
            except (OSError, ValueError, json.JSONDecodeError, PdfReadError) as exc:
                report.invalid_files.append(f"{pdf_path}: {exc}")
        orphan_metadata = sorted(
            path
            for path in paths["metadata"].rglob("*.json")
            if path not in expected_metadata_paths
        )
        report.invalid_files.extend(
            f"{path}: metadata sidecar has no matching official PDF"
            for path in orphan_metadata
        )

    _reject_duplicate_source_ids(documents, report)
    return CorpusLoadResult(documents=documents, report=report)


def load_policy_document(path: str | Path) -> PolicyDocument:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        return _load_json_document(file_path)
    if suffix == ".md":
        return _load_markdown_document(file_path)
    if suffix == ".txt":
        return _load_text_document(file_path)

    raise ValueError(f"Unsupported corpus file type: {suffix}")


def load_official_metadata(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)
    if not metadata_path.exists():
        raise CorpusValidationError(
            f"missing metadata sidecar {metadata_path.name}"
        )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CorpusValidationError("metadata sidecar must contain a JSON object")
    return validate_official_metadata(payload)


def validate_official_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "source_id",
        "title",
        "document_name",
        "institution",
        "source_url",
        "access_date",
        "source_type",
        "prototype_only",
        "active",
    }
    missing = sorted(
        key
        for key in required
        if key not in payload or payload[key] is None or payload[key] == ""
    )
    if missing:
        raise CorpusValidationError(
            f"metadata is missing required field(s): {', '.join(missing)}"
        )
    for key in ("source_id", "title", "document_name", "institution"):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise CorpusValidationError(f"{key} must be a non-empty string")
    if payload["source_type"] not in OFFICIAL_SOURCE_TYPES:
        raise CorpusValidationError(
            "source_type must be official_policy or official_student_guidance"
        )
    if payload["prototype_only"] is not False:
        raise CorpusValidationError("official metadata prototype_only must be false")
    if not isinstance(payload["active"], bool):
        raise CorpusValidationError("official metadata active must be a boolean")
    parsed_url = urlparse(str(payload["source_url"]))
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise CorpusValidationError("source_url must be an absolute http(s) URL")
    _validate_iso_date(str(payload["access_date"]), "access_date")
    for key in ("effective_date", "superseded_date"):
        if payload.get(key):
            _validate_iso_date(str(payload[key]), key)

    normalized = dict(payload)
    for key in required | {
        "version",
        "effective_date",
        "superseded_date",
        "notes",
    }:
        if key in normalized and isinstance(normalized[key], str):
            normalized[key] = normalized[key].strip()
    return normalized


def extract_pdf(path: str | Path) -> PdfExtractionResult:
    pdf_path = Path(path)
    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise PdfExtractionError(
                    "password-protected PDF cannot be extracted", "password_protected"
                ) from exc
            if not unlocked:
                raise PdfExtractionError(
                    "password-protected PDF cannot be extracted", "password_protected"
                )
    except FileNotDecryptedError as exc:
        raise PdfExtractionError(
            "password-protected PDF cannot be extracted", "password_protected"
        ) from exc
    except PdfReadError as exc:
        raise PdfExtractionError(f"invalid PDF: {exc}", "invalid_pdf") from exc

    pages: list[PolicyPage] = []
    empty_pages: list[int] = []
    warnings: list[str] = []
    image_pages = 0
    last_section = "General"

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = _normalize_pdf_text(page.extract_text() or "")
        except FileNotDecryptedError as exc:
            raise PdfExtractionError(
                "password-protected PDF cannot be extracted", "password_protected"
            ) from exc
        try:
            if list(page.images):
                image_pages += 1
        except Exception:
            pass

        if len(text) < MIN_EXTRACTED_PAGE_CHARS:
            empty_pages.append(index)
            warnings.append(f"{pdf_path.name}: page {index} has no extractable text")
        section = _detect_pdf_heading(text) or last_section
        if section:
            last_section = section
        pages.append(PolicyPage(page_number=index, text=text, section=last_section))

    meaningful_pages = [
        page for page in pages if len(page.text) >= MIN_EXTRACTED_PAGE_CHARS
    ]
    ocr_required = not meaningful_pages
    image_only = ocr_required and image_pages > 0
    if ocr_required:
        reason = "image-only" if image_only else "empty"
        warnings.append(
            f"{pdf_path.name}: {reason} PDF requires OCR; OCR was not run"
        )

    return PdfExtractionResult(
        pages=tuple(pages),
        page_count=len(pages),
        empty_pages=tuple(empty_pages),
        ocr_required=ocr_required,
        image_only=image_only,
        warnings=tuple(warnings),
    )


def chunk_policy_documents(
    documents: list[PolicyDocument],
    target_chars: int | None = None,
    overlap_chars: int = 300,
    min_chars: int = 120,
    target_tokens: int = 700,
    overlap_tokens: int = 80,
) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []

    for document in documents:
        if not document.active or document.ocr_required or not document.text.strip():
            continue
        if document.pages:
            chunk_parts = _chunk_pdf_pages(
                document.pages,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
            )
        else:
            char_target = target_chars or target_tokens * 5
            chunk_parts = [
                (text, None, None, _section_for_chunk(text, document.section))
                for text in _chunk_text(
                    document.text,
                    target_chars=char_target,
                    overlap_chars=overlap_chars,
                    min_chars=min_chars,
                )
            ]

        for index, (chunk_text, page_start, page_end, section) in enumerate(
            chunk_parts
        ):
            chunks.append(
                PolicyChunk(
                    chunk_id=f"{_slug(document.source_id)}_chunk_{index:04d}",
                    source_id=document.source_id,
                    title=document.title,
                    document_name=document.document_name,
                    section=section,
                    url=document.url,
                    source_type=document.source_type,
                    updated_at=document.updated_at,
                    access_date=document.access_date,
                    prototype_only=document.prototype_only,
                    chunk_index=index,
                    chunk_text=chunk_text,
                    institution=document.institution,
                    active=document.active,
                    version=document.version,
                    effective_date=document.effective_date,
                    superseded_date=document.superseded_date,
                    document_checksum=document.document_checksum,
                    page_start=page_start,
                    page_end=page_end,
                )
            )

    return chunks


def document_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _discover_prepared_files(paths: dict[str, Path]) -> list[Path]:
    legacy = [
        item
        for item in paths["root"].iterdir()
        if item.is_file()
        and item.name != "corpus_scope.json"
        and item.suffix.lower() in SUPPORTED_PREPARED_SUFFIXES
    ]
    nested = [
        item
        for item in paths["prepared"].rglob("*")
        if item.is_file() and item.suffix.lower() in SUPPORTED_PREPARED_SUFFIXES
    ]
    return sorted({*legacy, *nested})


def _load_json_document(file_path: Path) -> PolicyDocument:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON corpus file must contain an object")

    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("JSON corpus file is missing text")

    return _document_from_metadata(payload, text=text, file_path=file_path)


def _load_markdown_document(file_path: Path) -> PolicyDocument:
    raw_text = file_path.read_text(encoding="utf-8")
    metadata, text = _split_front_matter(raw_text)
    return _document_from_metadata(metadata, text=text.strip(), file_path=file_path)


def _load_text_document(file_path: Path) -> PolicyDocument:
    text = file_path.read_text(encoding="utf-8").strip()
    metadata = {
        "source_id": file_path.stem,
        "title": file_path.stem.replace("_", " ").replace("-", " ").title(),
        "document_name": file_path.name,
        "section": _first_heading(text) or "General",
        "source_type": PREPARED_SOURCE_TYPE,
        "prototype_only": True,
    }
    return _document_from_metadata(metadata, text=text, file_path=file_path)


def _document_from_metadata(
    metadata: dict[str, Any],
    text: str,
    file_path: Path,
) -> PolicyDocument:
    source_id = str(metadata.get("source_id") or file_path.stem)
    title = str(metadata.get("title") or source_id)
    return PolicyDocument(
        source_id=source_id,
        title=title,
        document_name=str(metadata.get("document_name") or title),
        section=str(metadata.get("section") or _first_heading(text) or "General"),
        url=str(metadata.get("source_url") or metadata.get("url") or ""),
        source_type=str(metadata.get("source_type") or PREPARED_SOURCE_TYPE),
        updated_at=str(metadata.get("updated_at") or ""),
        access_date=str(metadata.get("access_date") or ""),
        prototype_only=_as_bool(metadata.get("prototype_only"), default=True),
        text=text,
        path=str(file_path),
        institution=str(metadata.get("institution") or ""),
        active=_as_bool(metadata.get("active"), default=True),
        version=str(metadata.get("version") or ""),
        effective_date=str(metadata.get("effective_date") or ""),
        superseded_date=str(metadata.get("superseded_date") or ""),
        notes=str(metadata.get("notes") or ""),
        document_checksum=document_checksum(file_path),
    )


def _official_document(
    pdf_path: Path,
    metadata: dict[str, Any],
    extraction: PdfExtractionResult,
) -> PolicyDocument:
    active = bool(metadata["active"]) and not bool(metadata.get("superseded_date"))
    text = "\n\n".join(page.text for page in extraction.pages if page.text)
    section = next(
        (page.section for page in extraction.pages if page.section), "General"
    )
    return PolicyDocument(
        source_id=str(metadata["source_id"]),
        title=str(metadata["title"]),
        document_name=str(metadata["document_name"]),
        section=section,
        url=str(metadata["source_url"]),
        source_type=str(metadata["source_type"]),
        updated_at="",
        access_date=str(metadata["access_date"]),
        prototype_only=False,
        text=text,
        path=str(pdf_path),
        institution=str(metadata["institution"]),
        active=active,
        version=str(metadata.get("version") or ""),
        effective_date=str(metadata.get("effective_date") or ""),
        superseded_date=str(metadata.get("superseded_date") or ""),
        notes=str(metadata.get("notes") or ""),
        document_checksum=document_checksum(pdf_path),
        pages=extraction.pages,
        ocr_required=extraction.ocr_required,
        empty_pages=extraction.empty_pages,
    )


def _reject_duplicate_source_ids(
    documents: list[PolicyDocument], report: CorpusLoadReport
) -> None:
    by_source: dict[str, list[PolicyDocument]] = {}
    for document in documents:
        by_source.setdefault(document.source_id, []).append(document)
    duplicates = {key: values for key, values in by_source.items() if len(values) > 1}
    if not duplicates:
        return
    duplicate_documents = {id(item) for values in duplicates.values() for item in values}
    documents[:] = [item for item in documents if id(item) not in duplicate_documents]
    for source_id, values in sorted(duplicates.items()):
        paths = ", ".join(item.path for item in values)
        report.invalid_files.append(
            f"duplicate source_id {source_id!r} used by: {paths}"
        )


def _chunk_pdf_pages(
    pages: tuple[PolicyPage, ...],
    target_tokens: int,
    overlap_tokens: int,
) -> list[tuple[str, int, int, str]]:
    units: list[tuple[str, int, str]] = []
    for page in pages:
        if len(page.text) < MIN_EXTRACTED_PAGE_CHARS:
            continue
        for block in _split_for_token_target(page.text, target_tokens):
            units.append((block, page.page_number, page.section))

    chunks: list[tuple[str, int, int, str]] = []
    current: list[tuple[str, int, str]] = []
    current_tokens = 0

    for unit in units:
        unit_tokens = _token_count(unit[0])
        if current and current_tokens + unit_tokens > target_tokens:
            chunks.append(_pdf_chunk_tuple(current))
            current = _overlap_units(current, overlap_tokens)
            current_tokens = sum(_token_count(item[0]) for item in current)
        current.append(unit)
        current_tokens += unit_tokens

    if current:
        chunks.append(_pdf_chunk_tuple(current))
    return chunks


def _split_for_token_target(text: str, target_tokens: int) -> list[str]:
    paragraphs = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    output: list[str] = []
    for paragraph in paragraphs:
        if _token_count(paragraph) <= target_tokens:
            output.append(paragraph)
            continue
        words = paragraph.split()
        for start in range(0, len(words), target_tokens):
            output.append(" ".join(words[start : start + target_tokens]))
    return output


def _pdf_chunk_tuple(
    units: list[tuple[str, int, str]],
) -> tuple[str, int, int, str]:
    return (
        "\n\n".join(unit[0] for unit in units).strip(),
        min(unit[1] for unit in units),
        max(unit[1] for unit in units),
        next((unit[2] for unit in units if unit[2]), "General"),
    )


def _overlap_units(
    units: list[tuple[str, int, str]], overlap_tokens: int
) -> list[tuple[str, int, str]]:
    if overlap_tokens <= 0:
        return []
    selected: list[tuple[str, int, str]] = []
    total = 0
    for unit in reversed(units):
        count = _token_count(unit[0])
        if not selected and count > overlap_tokens:
            break
        if selected and total + count > overlap_tokens:
            break
        selected.append(unit)
        total += count
        if total >= overlap_tokens:
            break
    return list(reversed(selected))


def _chunk_text(
    text: str,
    target_chars: int,
    overlap_chars: int,
    min_chars: int,
) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[str] = []
    current = ""

    for block in blocks:
        if current and len(current) + len(block) + 2 > target_chars:
            if len(current) >= min_chars:
                chunks.append(current.strip())
            overlap = current[-overlap_chars:].strip() if overlap_chars else ""
            current = f"{overlap}\n\n{block}".strip() if overlap else block
        else:
            current = f"{current}\n\n{block}".strip() if current else block

    if current.strip() and len(current.strip()) >= min_chars:
        chunks.append(current.strip())

    if not chunks and text.strip():
        chunks.append(text.strip())

    return chunks


def _split_front_matter(raw_text: str) -> tuple[dict[str, str], str]:
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw_text

    metadata: dict[str, str] = {}
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    if end_index is None:
        return {}, raw_text

    return metadata, "\n".join(lines[end_index + 1 :])


def _normalize_pdf_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _detect_pdf_heading(text: str) -> str | None:
    for line in [item.strip() for item in text.splitlines()[:12] if item.strip()]:
        if len(line) > 120 or line.endswith(('.', '?', '!')):
            continue
        if re.match(r"^(?:\d+(?:\.\d+)*|[A-Z])(?:\s+|[.:])", line):
            return line
        words = line.split()
        if 1 <= len(words) <= 14 and (line.isupper() or line.istitle()):
            return line
    return None


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def _section_for_chunk(chunk_text: str, fallback: str) -> str:
    return _first_heading(chunk_text) or fallback


def _token_count(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() in {"true", "1", "yes"}:
            return True
        if value.strip().lower() in {"false", "0", "no"}:
            return False
    return default


def _validate_iso_date(value: str, field_name: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise CorpusValidationError(
            f"{field_name} must use ISO date format YYYY-MM-DD"
        ) from exc


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "source"
