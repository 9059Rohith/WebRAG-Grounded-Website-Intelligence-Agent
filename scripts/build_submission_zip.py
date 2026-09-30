"""Build a focused, credential-free assessment ZIP from the tracked project.

The archive keeps the normal repository layout so README links and setup commands
remain usable. Recorded media lives at the public Drive URL in 05_DEMO_LINK.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "WebRAG-Assessment-Submission"
ZIP_PATH = ROOT / "submission" / f"{PREFIX}.zip"
DOWNLOAD = Path.home() / "Downloads" / ZIP_PATH.name
DRIVE_URL = "https://drive.google.com/file/d/1KYgEdw04ZEYN9u-ptXm3PXSmMiI-nF47/view?usp=sharing"

SKIP_PREFIXES = ("docs/video/", "docs/superpowers/", "submission/")
SKIP_FILES = {
    "scripts/create_showcase_video.py",
    "scripts/create_walkthrough.py",
    "scripts/finish_live_browser_demo.py",
    "scripts/live_demo_content.json",
    "scripts/record_live_browser_demo.py",
    "scripts/showcase_content.json",
    "scripts/synthesize_live_demo.py",
    "scripts/synthesize_showcase.py",
    "scripts/synthesize_walkthrough.ps1",
    "scripts/walkthrough_content.json",
    "docs/verification/live-browser-video.json",
    "docs/verification/showcase-video.json",
    "docs/verification/video.json",
}
SECRET_PATTERNS = (
    re.compile(rb"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
)


def tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    selected = []
    for value in output.decode("utf-8").split("\0"):
        if not value or value in SKIP_FILES or value.startswith(SKIP_PREFIXES):
            continue
        if value == ".env" or value.startswith(".env.") and value != ".env.example":
            raise RuntimeError(f"Private environment file would be included: {value}")
        selected.append(value)
    return sorted(selected)


def local_readme_links_are_packaged(paths: set[str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", readme)
    missing = []
    for link in links:
        if link.startswith(("https://", "http://", "#", "mailto:")):
            continue
        target = link.split("#", 1)[0]
        if target and target not in paths and not any(p.startswith(target.rstrip("/") + "/") for p in paths):
            missing.append(link)
    if missing:
        raise RuntimeError(f"README links omitted from ZIP: {missing}")


def clean_archive_info(name: str) -> ZipInfo:
    info = ZipInfo(f"{PREFIX}/{name}", date_time=(2026, 9, 30, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def main() -> None:
    paths = tracked_files()
    required = {
        "README.md", ".env.example", "LICENSE", "COST_ANALYSIS.md",
        "docs/architecture-showcase.png", "docs/architecture.svg",
        "docs/architecture.md", "docs/langgraph.mmd",
        "src/rag_agent/api.py", "web/package.json", "evaluation/submission_questions.json",
    }
    if not required.issubset(paths):
        raise RuntimeError(f"Missing required submission files: {sorted(required - set(paths))}")
    if not any(p.startswith("tests/") for p in paths):
        raise RuntimeError("Tests are missing from the submission")
    local_readme_links_are_packaged(set(paths))
    extra = {
        "SUBMISSION_INDEX.md": (ROOT / "submission" / "README.md").read_bytes(),
        "05_DEMO_LINK.md": (ROOT / "submission" / "05_DEMO_LINK.md").read_bytes(),
    }
    if DRIVE_URL.encode() not in extra["05_DEMO_LINK.md"]:
        raise RuntimeError("Demo link changed or missing")
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with ZipFile(ZIP_PATH, "w", compression=ZIP_DEFLATED, compresslevel=7) as archive:
        for name in paths:
            source = (ROOT / name).resolve()
            if ROOT.resolve() not in source.parents or not source.is_file():
                raise RuntimeError(f"Unsafe or missing tracked path: {name}")
            content = source.read_bytes()
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                raise RuntimeError(f"Credential-like string detected in {name}")
            archive.writestr(clean_archive_info(name), content, compress_type=ZIP_DEFLATED, compresslevel=7)
            count += 1
        for name, content in sorted(extra.items()):
            archive.writestr(clean_archive_info(name), content, compress_type=ZIP_DEFLATED, compresslevel=7)
            count += 1
    with ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
        names = archive.namelist()
        if len(names) != count or any("/docs/video/" in item or item.endswith("/.env") for item in names):
            raise RuntimeError("Unexpected ZIP members")
        if not archive.read(f"{PREFIX}/.env.example").decode().split("OPENAI_API_KEY=", 1)[1].startswith("\n"):
            raise RuntimeError(".env.example contains a nonblank key")
    shutil.copy2(ZIP_PATH, DOWNLOAD)
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    if digest != hashlib.sha256(DOWNLOAD.read_bytes()).hexdigest():
        raise RuntimeError("Downloads ZIP does not match repository ZIP")
    result = {
        "archive": str(ZIP_PATH),
        "downloads_copy": str(DOWNLOAD),
        "bytes": ZIP_PATH.stat().st_size,
        "members": count,
        "sha256": digest,
        "components": ["source", "README", "architecture diagrams", "cost analysis", "Drive demo link"],
        "credential_scan": "passed",
        "readme_relative_links": "passed",
        "zip_integrity": "passed",
    }
    (ROOT / "submission" / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
