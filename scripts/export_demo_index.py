"""Copy only approved public policy fields from a snapshot of a local index."""

import argparse
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.parse import urlparse

import chromadb

FIELDS = {
    "chunk_id", "source_id", "title", "document_name", "section", "url",
    "source_type", "chunk_text", "page_start", "page_end", "source_url",
    "version", "effective_date", "document_checksum", "active", "prototype_only",
}


def export(source: Path, destination: Path):
    name = "uni_navigator_policy_chunks_openai"
    manifest = json.loads((source / f"ingestion_manifest.{name}.json").read_text())
    with tempfile.TemporaryDirectory(prefix="uni-demo-export-") as temporary:
        snapshot = Path(temporary) / "chroma"
        shutil.copytree(source, snapshot)
        # SQLite backup handles an active WAL without touching the source DB.
        with sqlite3.connect(f"file:{source / 'chroma.sqlite3'}?mode=ro", uri=True) as original:
            with sqlite3.connect(snapshot / "chroma.sqlite3") as target:
                original.backup(target)
        client = chromadb.PersistentClient(path=str(snapshot))
        collection = client.get_collection(name, embedding_function=None)
        data = collection.get(include=["documents", "metadatas", "embeddings"])
        records = []
        for id_, document, metadata, vector in zip(data["ids"], data["documents"], data["metadatas"], data["embeddings"]):
            if metadata.get("source_type") != "official_policy" or not metadata.get("active", True):
                continue
            safe = {key: value for key, value in metadata.items() if key in FIELDS}
            for key in ("url", "source_url"):
                if safe.get(key):
                    url = urlparse(safe[key])
                    if url.scheme != "https" or not (url.hostname or "").endswith(".uq.edu.au"):
                        raise ValueError("Only official HTTPS UQ links may be published")
            records.append({"id": id_, "document": document, "metadata": safe, "embedding": vector.tolist()})
        index_metadata = {
            key: value for key, value in (collection.metadata or {}).items()
            if key in {"embedding_provider", "embedding_model", "embedding_dimension", "index_built_at"}
        }
    ids = {row["metadata"]["source_id"] for row in records}
    safe_manifest = {
        key: manifest[key] for key in (
            "collection_name", "embedding_provider", "embedding_model", "embedding_dimension",
            "index_built_at", "latest_ingestion_at", "source_selection",
        ) if key in manifest
    }
    safe_manifest.update({
        "source_count": len(ids), "chunk_count": len(records),
        "sources": {id_: {key: value for key, value in manifest["sources"][id_].items() if key in FIELDS} for id_ in sorted(ids)},
    })
    payload = {"collection": name, "records": sorted(records, key=lambda row: row["id"]),
               "index_metadata": index_metadata, "manifest": safe_manifest}
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    if b"/Users/" in encoded or b"sk-proj-" in encoded:
        raise ValueError("Private local path or credential found in index export")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(encoded, mtime=0))
    print(f"Exported {len(records)} official passages from {len(ids)} sources; no PDFs or research records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.source.resolve(), args.output.resolve())
