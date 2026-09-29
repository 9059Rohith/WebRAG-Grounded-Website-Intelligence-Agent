"""Offline checks for the public bundle boundary and serverless startup."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from deployment.runtime_bootstrap import prepare_runtime_index, serverless_settings
from scripts.prepare_vercel import prepare, validate_index


def fixture_index(root: Path) -> Path:
    root.mkdir()
    snapshot = root / "snapshots" / "active.json"
    snapshot.parent.mkdir()
    snapshot.write_text(
        json.dumps(
            [
                {
                    "chunk_id": "chunk-a",
                    "source_url": "https://docs.python.org/3/tutorial/",
                    "text": "A list holds items.",
                }
            ]
        ),
        encoding="utf-8",
    )
    stats = {
        "pages": 1,
        "chunks": 1,
        "provider": "openai",
        "embedding_id": "openai:text-embedding-3-small",
        "index_version": "public-version",
        "chunk_snapshot": "snapshots/active.json",
        "collection_name": "public",
        "start_url": "https://docs.python.org/3/tutorial/index.html",
        "allowed_prefix": "https://docs.python.org/3/",
    }
    (root / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    chroma = root / "chroma"
    chroma.mkdir()
    connection = sqlite3.connect(chroma / "chroma.sqlite3")
    try:
        connection.executescript("""
            CREATE TABLE collections (id TEXT, name TEXT, dimension INTEGER);
            CREATE TABLE segments (id TEXT, scope TEXT, collection TEXT);
            CREATE TABLE embeddings (id TEXT, segment_id TEXT);
            INSERT INTO collections VALUES ('collection-a', 'public', 1536);
            INSERT INTO segments VALUES ('vector-a', 'VECTOR', 'collection-a');
            INSERT INTO segments VALUES ('metadata-a', 'METADATA', 'collection-a');
            INSERT INTO embeddings VALUES ('chunk-a', 'metadata-a');
        """)
        connection.commit()
    finally:
        connection.close()
    segment = chroma / "vector-a"
    segment.mkdir()
    (segment / "data_level0.bin").write_bytes(b"public-vector-fixture")
    (segment / "private-log.txt").write_text("excluded", encoding="utf-8")
    (root / ".env").write_text("FAKE_PRIVATE_MARKER=excluded", encoding="utf-8")
    (root / "embedding_cache").mkdir()
    (root / "embedding_cache" / "query.json").write_text("excluded", encoding="utf-8")
    return root


def test_prepare_only_copies_active_public_index_and_python_source(tmp_path: Path) -> None:
    source = fixture_index(tmp_path / "index")
    output = tmp_path / "deployment"
    summary = prepare(source, output, frontend_dist=None)
    assert summary["chunks"] == 1
    assert summary["embedding_dimensions"] == 1536
    assert (output / "runtime" / "rag_agent" / "graph.py").is_file()
    assert (output / "runtime" / "rag_agent" / "crawler.py").is_file()
    assert (output / "seed_index" / "snapshots" / "active.json").is_file()
    assert not list(output.rglob(".env"))
    assert not list(output.rglob("embedding_cache"))
    assert not list(output.rglob("private-log.txt"))
    manifest = json.loads((output / "seed_index" / "bundle_manifest.json").read_text())
    for relative, expected in manifest["files"].items():
        copied = output / "seed_index" / relative
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == expected["sha256"]
    # A second run also checks that no SQLite handles prevent replacement on Windows.
    assert prepare(source, output, frontend_dist=None)["chunks"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("chunk_snapshot", "../private.json"),
        ("start_url", "http://127.0.0.1/private"),
        ("embedding_id", "local:sentence-transformers/all-MiniLM-L6-v2"),
        ("unexpected_secret_field", "excluded"),
    ],
)
def test_prepare_rejects_non_public_or_incompatible_metadata(
    tmp_path: Path, field: str, value: str
) -> None:
    source = fixture_index(tmp_path / "index")
    stats_path = source / "stats.json"
    stats = json.loads(stats_path.read_text())
    stats[field] = value
    stats_path.write_text(json.dumps(stats), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_index(source)


def test_prepare_requires_built_frontend_when_requested(tmp_path: Path) -> None:
    source = fixture_index(tmp_path / "index")
    with pytest.raises(ValueError, match="Build web/dist"):
        prepare(source, tmp_path / "deployment", tmp_path / "missing", require_frontend=True)


def test_runtime_copy_is_serialized_and_warm_cache_is_retained(tmp_path: Path) -> None:
    source = fixture_index(tmp_path / "index")
    output = tmp_path / "deployment"
    prepare(source, output, frontend_dist=None)
    seed = output / "seed_index"
    with ThreadPoolExecutor(max_workers=8) as executor:
        destinations = list(
            executor.map(lambda _: prepare_runtime_index(seed, tmp_path / "tmp"), range(8))
        )
    assert len(set(destinations)) == 1
    destination = destinations[0]
    assert (destination / ".bundle-complete").is_file()
    (destination / "embedding_cache").mkdir()
    cache_file = destination / "embedding_cache" / "cached-query.json"
    cache_file.write_text("warm-cache", encoding="utf-8")
    assert prepare_runtime_index(seed, tmp_path / "tmp") == destination
    assert cache_file.read_text() == "warm-cache"
    # A missing completion marker signals an interrupted copy; seed is restored.
    (destination / ".bundle-complete").unlink()
    (destination / "stats.json").write_text("interrupted", encoding="utf-8")
    prepare_runtime_index(seed, tmp_path / "tmp")
    assert json.loads((destination / "stats.json").read_text())["chunks"] == 1
    assert not cache_file.exists()


def test_serverless_settings_force_remote_provider_and_writable_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-only")
    monkeypatch.setenv("PROVIDER", "local")
    monkeypatch.setenv("DATA_DIR", "read-only-bundle")
    configuration = serverless_settings(tmp_path)
    assert configuration.provider == "openai"
    assert configuration.data_dir == tmp_path
    assert configuration.embedding_id == "openai:text-embedding-3-small"


def test_serverless_settings_never_load_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=offline-dotenv-marker", encoding="utf-8")
    with pytest.raises(ValidationError, match="Set OPENAI_API_KEY"):
        serverless_settings(tmp_path)
