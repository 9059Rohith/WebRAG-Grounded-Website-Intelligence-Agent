"""Copy the bundled public index into instance-local writable storage once."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from filelock import FileLock


def prepare_runtime_index(seed_dir: Path, temp_root: Path | None = None) -> Path:
    """Serialize cold-start copies and recover safely from an interrupted copy.

    Vercel's function bundle is immutable. Chroma and the embedding/query cache
    need writable storage; /tmp is instance-local and is never a durable store.
    The versioned bundled index remains the authority across cold starts.
    """
    seed_dir = seed_dir.resolve()
    manifest_path = seed_dir / "bundle_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not manifest.get("index_version") or not (seed_dir / "stats.json").is_file():
        raise ValueError("The bundled index is incomplete; run prepare_vercel.py")
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    temp_root = (temp_root or Path(tempfile.gettempdir())).resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    destination = temp_root / ("webrag-" + digest[:24])
    complete = destination / ".bundle-complete"
    with FileLock(str(temp_root / (destination.name + ".lock")), timeout=120):
        if complete.is_file() and complete.read_text(encoding="ascii") == digest:
            return destination
        # The path is fixed under the selected temporary root, never a caller's
        # DATA_DIR or the read-only seed. An incomplete copy has no valid marker.
        if destination.parent != temp_root or destination == seed_dir:
            raise ValueError("Unsafe temporary index destination")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(seed_dir, destination)
        marker = destination / ".bundle-complete.tmp"
        marker.write_text(digest, encoding="ascii")
        marker.replace(complete)
    return destination


def serverless_settings(data_dir: Path) -> Any:
    """Use remote environment secrets and force the shipped embedding provider."""
    from rag_agent.config import Settings

    # Do not load a dotenv file in a production function. DATA_DIR and PROVIDER
    # cannot redirect this deployment to a local model or read-only bundle.
    os.environ.setdefault("XDG_CACHE_HOME", str(data_dir / "runtime_cache"))
    return Settings(_env_file=None, provider="openai", data_dir=data_dir)
