"""Persistent Chroma vectors and JSON chunk metadata; no pickle loading."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from rag_agent.config import Settings
from rag_agent.errors import IndexMismatchError
from rag_agent.schemas import Chunk


class VectorStore:
    """Keep vector IDs and the human-readable corpus in sync."""

    def __init__(self, settings: Settings, create: bool = False) -> None:
        self.settings = settings
        self.chunk_path = settings.data_dir / "chunks.json"
        self.stats_path = settings.data_dir / "stats.json"
        if not create and not self.stats_path.exists():
            raise FileNotFoundError("No index found. Run 'rag ingest' first.")
        self.info: dict[str, Any] = (
            json.loads(self.stats_path.read_text(encoding="utf-8"))
            if self.stats_path.exists()
            else {}
        )
        if self.info and self.info.get("embedding_id") != settings.embedding_id:
            raise IndexMismatchError(
                "Embedding model differs from the persisted index. Select the original provider or reingest to another DATA_DIR."
            )
        self.client = chromadb.PersistentClient(
            path=str(settings.data_dir / "chroma"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        name = str(
            self.info.get("collection_name")
            or "website_" + hashlib.sha256(settings.embedding_id.encode()).hexdigest()[:16]
        )
        self.collection = self.client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )
        # stats.json is the single atomic pointer to an immutable generation.
        snapshot_path = settings.data_dir / str(self.info.get("chunk_snapshot", "chunks.json"))
        self.chunks: list[Chunk] = (
            [Chunk.model_validate(c) for c in json.loads(snapshot_path.read_text(encoding="utf-8"))]
            if snapshot_path.exists()
            else []
        )
        self.by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        if not create and self.collection.count() != len(self.chunks):
            raise IndexMismatchError("Index snapshot is incomplete. Re-run ingestion to repair it.")

    def replace(
        self, chunks: list[Chunk], vectors: list[list[float]], info: dict[str, Any]
    ) -> dict[str, int]:
        """Build a new generation, then switch one pointer; failed builds leave readers intact."""
        previous = self.by_id
        current = {chunk.chunk_id: chunk for chunk in chunks}
        if len(chunks) != len(current) or len(chunks) != len(vectors):
            raise ValueError("Chunk IDs must be unique and match the vector batch")
        added = sum(cid not in previous for cid in current)
        updated = sum(
            cid in previous and previous[cid].content_hash != chunk.content_hash
            for cid, chunk in current.items()
        )
        unchanged = len(chunks) - added - updated
        generation = uuid.uuid4().hex
        name = (
            "website_"
            + hashlib.sha256(self.settings.embedding_id.encode()).hexdigest()[:16]
            + "_"
            + generation[:12]
        )
        replacement = self.client.create_collection(name=name, metadata={"hnsw:space": "cosine"})
        for start in range(0, len(chunks), 100):
            batch = chunks[start : start + 100]
            replacement.upsert(
                ids=[c.chunk_id for c in batch],
                embeddings=vectors[start : start + 100],
                documents=[c.text for c in batch],
                metadatas=[
                    {
                        "source_url": c.source_url,
                        "title": c.title,
                        "heading_path": c.heading_path,
                        "content_hash": c.content_hash,
                        "token_count": c.token_count,
                        "chunk_index": c.chunk_index,
                        "crawled_at": c.crawled_at,
                    }
                    for c in batch
                ],
            )
        stale = list(set(previous) - set(current))
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        snapshot = self.settings.data_dir / "snapshots" / f"{generation}.json"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps([c.model_dump() for c in chunks], ensure_ascii=False, indent=2)
        tmp = snapshot.with_suffix(".tmp")
        tmp.write_text(
            serialized,
            encoding="utf-8",
        )
        tmp.replace(snapshot)
        info["embedding_id"] = self.settings.embedding_id
        info["index_version"] = hashlib.sha256(
            (
                self.settings.embedding_id
                + "".join(c.chunk_id + c.content_hash + c.embedded_text for c in chunks)
            ).encode()
        ).hexdigest()
        info["chunks"] = len(chunks)
        info["collection_name"] = name
        info["chunk_snapshot"] = snapshot.relative_to(self.settings.data_dir).as_posix()
        tmp = self.stats_path.with_name(f"stats-{generation}.tmp")
        tmp.write_text(json.dumps(info, indent=2), encoding="utf-8")
        tmp.replace(self.stats_path)
        self.collection = replacement
        self.info, self.chunks, self.by_id = info, chunks, current
        # Convenience export for inspection/evaluation; query loads the immutable
        # snapshot named by stats, never this potentially interrupted export.
        tmp = self.chunk_path.with_suffix(".tmp")
        try:
            tmp.write_text(serialized, encoding="utf-8")
            tmp.replace(self.chunk_path)
        except OSError:
            logging.getLogger(__name__).warning(
                "Index committed; convenience chunk export unavailable"
            )
        return {"added": added, "updated": updated, "removed": len(stale), "unchanged": unchanged}

    def search(self, vector: list[float], k: int) -> list[tuple[Chunk, float]]:
        """Convert cosine distance to similarity while retaining metadata authority."""
        if not self.chunks:
            return []
        result = self.collection.query(
            query_embeddings=[vector], n_results=min(k, len(self.chunks)), include=["distances"]
        )
        ids = result["ids"][0]
        distances = result["distances"]
        if distances is None:
            return []
        return [
            (self.by_id[cid], max(0.0, 1 - float(distance)))
            for cid, distance in zip(ids, distances[0], strict=True)
            if cid in self.by_id
        ]
