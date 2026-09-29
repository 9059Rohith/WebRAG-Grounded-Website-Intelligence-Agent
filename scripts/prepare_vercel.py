"""Build an allowlisted, secret-free Vercel input directory without API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STATS_FIELDS = {
    "pages",
    "start_url",
    "allowed_prefix",
    "provider",
    "chunk_tokens",
    "chunk_overlap_tokens",
    "created_at",
    "embedding_id",
    "index_version",
    "chunks",
    "collection_name",
    "chunk_snapshot",
}
HNSW_FILES = {
    "header.bin",
    "data_level0.bin",
    "length.bin",
    "link_lists.bin",
    "index_metadata.pickle",
}
BLOCKED_NAMES = {".env", "embedding_cache", "raw", "__pycache__", ".git"}


def public_python_url(value: str) -> bool:
    """The distributable demonstration package is restricted to public Python docs."""
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "docs.python.org"
        and parsed.path.startswith("/3/")
        and not parsed.username
        and not parsed.password
    )


def safe_child(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("Index snapshot escapes the source directory")
    return path


def validate_index(source: Path) -> tuple[dict, Path]:
    stats = json.loads((source / "stats.json").read_text(encoding="utf-8"))
    if set(stats) - STATS_FIELDS:
        raise ValueError("Unexpected metadata fields in the public index")
    if stats.get("embedding_id") != "openai:text-embedding-3-small":
        raise ValueError("Vercel requires the existing OpenAI embedding index")
    if stats.get("provider") != "openai" or not stats.get("index_version"):
        raise ValueError("OpenAI index metadata is incomplete")
    if not all(
        public_python_url(str(stats.get(field, ""))) for field in ("start_url", "allowed_prefix")
    ):
        raise ValueError("Only the public Python documentation corpus may be bundled")
    snapshot = safe_child(source, str(stats["chunk_snapshot"]))
    chunks = json.loads(snapshot.read_text(encoding="utf-8"))
    if not chunks or len(chunks) != stats["chunks"]:
        raise ValueError("Active chunk snapshot does not match index metadata")
    if any(not public_python_url(str(chunk.get("source_url", ""))) for chunk in chunks):
        raise ValueError("A chunk points outside the public demonstration corpus")
    if len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise ValueError("Active chunk IDs are not unique")
    if any(path.is_symlink() for path in source.rglob("*") if path.parent.name == "chroma"):
        raise ValueError("Symlinks are not allowed in the index package")
    return stats, snapshot


def copy_chroma(source: Path, target: Path, stats: dict) -> None:
    """Copy a consistent SQLite backup and only the active HNSW segment."""
    target.mkdir(parents=True)
    uri = (source / "chroma.sqlite3").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        row = database.execute(
            "SELECT id, dimension FROM collections WHERE name = ?",
            (stats["collection_name"],),
        ).fetchone()
        if row is None or row[1] != 1536:
            raise ValueError("Active Chroma collection or embedding dimension is invalid")
        collection_id = row[0]
        count = database.execute(
            "SELECT count(*) FROM embeddings e JOIN segments s ON s.id = e.segment_id WHERE s.collection = ?",
            (collection_id,),
        ).fetchone()[0]
        other_count = database.execute(
            "SELECT count(*) FROM embeddings e JOIN segments s ON s.id = e.segment_id WHERE s.collection != ?",
            (collection_id,),
        ).fetchone()[0]
        if count != stats["chunks"] or other_count:
            raise ValueError("Chroma contains an incomplete or additional non-public collection")
        segments = database.execute(
            "SELECT id FROM segments WHERE collection = ? AND scope = 'VECTOR'", (collection_id,)
        ).fetchall()
        with closing(sqlite3.connect(target / "chroma.sqlite3")) as backup:
            database.backup(backup)
            # Rebuild pages so deleted SQLite cells and free pages are not shipped.
            backup.execute("VACUUM")
    for (segment_id,) in segments:
        segment_source = safe_child(source, segment_id)
        if not segment_source.is_dir():
            raise ValueError("Active Chroma HNSW segment is missing")
        segment_target = target / segment_id
        segment_target.mkdir()
        for name in HNSW_FILES:
            file = segment_source / name
            if file.is_symlink():
                raise ValueError("Symlinks are not allowed in the index package")
            if file.is_file():
                shutil.copy2(file, segment_target / name)
        if not (segment_target / "data_level0.bin").is_file():
            raise ValueError("Active Chroma HNSW vectors are missing")


def replace_generated(staging: Path, destination: Path, output: Path) -> None:
    """Replace only a known generated subtree inside the selected output folder."""
    if destination.resolve().parent != output.resolve() or destination.name not in {
        "runtime",
        "seed_index",
        "static",
    }:
        raise ValueError("Unsafe generated-package destination")
    if destination.is_symlink():
        raise ValueError("Generated-package destinations must not be symlinks")
    if destination.exists():
        shutil.rmtree(destination)
    staging.replace(destination)


def prepare(
    source_index: Path = REPOSITORY_ROOT / "data_openai",
    output: Path = REPOSITORY_ROOT / "deployment",
    frontend_dist: Path | None = REPOSITORY_ROOT / "web" / "dist",
    *,
    require_frontend: bool = False,
) -> dict:
    source_index, output = source_index.resolve(), output.resolve()
    stats, snapshot = validate_index(source_index)
    if require_frontend and (frontend_dist is None or not (frontend_dist / "index.html").is_file()):
        raise ValueError("Build web/dist before preparing the production deployment")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output) as temporary:
        staging = Path(temporary)
        runtime = staging / "runtime" / "rag_agent"
        runtime.mkdir(parents=True)
        for file in sorted((REPOSITORY_ROOT / "src" / "rag_agent").rglob("*.py")):
            if file.is_symlink() or any(part in BLOCKED_NAMES for part in file.parts):
                raise ValueError("Only ordinary Python source files may be packaged")
            destination = runtime / file.relative_to(REPOSITORY_ROOT / "src" / "rag_agent")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
        seed = staging / "seed_index"
        seed.mkdir()
        (seed / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
        copied_snapshot = seed / snapshot.relative_to(source_index)
        copied_snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot, copied_snapshot)
        copy_chroma(source_index / "chroma", seed / "chroma", stats)
        files = {
            file.relative_to(seed).as_posix(): {
                "bytes": file.stat().st_size,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            }
            for file in sorted(seed.rglob("*"))
            if file.is_file()
        }
        (seed / "bundle_manifest.json").write_text(
            json.dumps({"index_version": stats["index_version"], "files": files}, indent=2) + "\n",
            encoding="utf-8",
        )
        if frontend_dist is not None and (frontend_dist / "index.html").is_file():
            for file in frontend_dist.rglob("*"):
                if file.is_symlink() or file.name.startswith(".env"):
                    raise ValueError("Private files or symlinks cannot be frontend assets")
            shutil.copytree(frontend_dist, staging / "static")
        for name in ("runtime", "seed_index", "static"):
            if (staging / name).exists():
                replace_generated(staging / name, output / name, output)
    shutil.copy2(REPOSITORY_ROOT / "requirements-vercel.txt", output / "requirements.txt")
    shutil.copy2(REPOSITORY_ROOT / "LICENSE", output / "LICENSE")
    package_files = [
        file
        for folder in (output / "runtime", output / "seed_index", output / "static")
        if folder.exists()
        for file in folder.rglob("*")
        if file.is_file()
    ]
    summary = {
        "pages": stats["pages"],
        "chunks": stats["chunks"],
        "embedding_dimensions": 1536,
        "index_version": stats["index_version"],
        "generated_files": len(package_files),
        "generated_bytes": sum(file.stat().st_size for file in package_files),
        "frontend_included": (output / "static" / "index.html").is_file(),
    }
    (output / "package_manifest.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-index", type=Path, default=REPOSITORY_ROOT / "data_openai")
    parser.add_argument("--output", type=Path, default=REPOSITORY_ROOT / "deployment")
    parser.add_argument("--frontend-dist", type=Path, default=REPOSITORY_ROOT / "web" / "dist")
    parser.add_argument("--require-frontend", action="store_true")
    options = parser.parse_args()
    summary = prepare(
        options.source_index,
        options.output,
        options.frontend_dist,
        require_frontend=options.require_frontend,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
