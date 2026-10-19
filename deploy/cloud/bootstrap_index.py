"""Build a Chroma index from approved existing vectors; never calls an API."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import chromadb


def bootstrap(bundle: Path, output: Path):
    payload = json.loads(gzip.decompress(bundle.read_bytes()))
    rows = payload["records"]
    if not rows or any(row["metadata"]["source_type"] != "official_policy" for row in rows):
        raise ValueError("Demo index must contain official policy passages only")
    client = chromadb.PersistentClient(path=str(output))
    collection = client.get_or_create_collection(
        payload["collection"], embedding_function=None,
        metadata={"hnsw:space": "cosine", **payload["index_metadata"]},
    )
    collection.upsert(
        ids=[row["id"] for row in rows],
        embeddings=[row["embedding"] for row in rows],
        documents=[row["document"] for row in rows],
        metadatas=[row["metadata"] for row in rows],
    )
    if collection.count() != len(rows):
        raise ValueError("Demo index count mismatch")
    manifest = payload["manifest"]
    (output / f"ingestion_manifest.{payload['collection']}.json").write_text(json.dumps(manifest), encoding="utf-8")
    print(json.dumps({
        "provider": "chroma", "fallback": False,
        "sources": manifest["source_count"], "chunks": collection.count(),
        "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=Path(__file__).with_name("policy_index.json.gz"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bootstrap(args.bundle, args.output)
