"""FastAPI entrypoint discovered by Vercel's Python framework preset."""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOYMENT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOYMENT_ROOT))
sys.path.insert(0, str(DEPLOYMENT_ROOT / "runtime"))

from runtime_bootstrap import prepare_runtime_index, serverless_settings  # noqa: E402

from rag_agent.api import create_app  # noqa: E402

data_dir = prepare_runtime_index(DEPLOYMENT_ROOT / "seed_index")
app = create_app(
    serverless_settings(data_dir),
    static_dir=DEPLOYMENT_ROOT / "static",
)
