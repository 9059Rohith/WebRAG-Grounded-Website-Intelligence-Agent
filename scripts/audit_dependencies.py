"""Audit pinned upstream releases; explicitly explain the CPU local-version mapping."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

# These advisories require Chroma server HTTP/auth routes. This application uses
# an embedded PersistentClient, supplied vectors and trust_remote_code=False.
# They are still disclosed in SECURITY.md; deploying a Chroma server changes scope.
SERVER_ONLY_ADVISORIES = ["PYSEC-2026-311", "PYSEC-2026-3814", "PYSEC-2026-3815", "PYSEC-2026-3813"]


def main() -> int:
    """Audit the CPU build's corresponding upstream torch version, not skip it."""
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    requirements = re.sub(r"(?m)^(torch==\d+\.\d+\.\d+)\+cpu$", r"\1", requirements)
    with tempfile.TemporaryDirectory(prefix="webrag-audit-") as directory:
        target = Path(directory) / "audit-requirements.txt"
        target.write_text(requirements, encoding="utf-8")
        args = [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            str(target),
            "--no-deps",
            "--disable-pip",
            "--progress-spinner",
            "off",
        ]
        for advisory in SERVER_ONLY_ADVISORIES:
            args.extend(["--ignore-vuln", advisory])
        print(
            "Auditing upstream PyTorch release for the official +cpu build; four server-only Chroma exceptions are documented.",
            flush=True,
        )
        return subprocess.run(args, check=False).returncode  # noqa: S603 -- fixed interpreter/module, no shell.


if __name__ == "__main__":
    raise SystemExit(main())
