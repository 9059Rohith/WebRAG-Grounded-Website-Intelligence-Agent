"""Build the five separately packaged, credential-free assessment components."""

from __future__ import annotations

import hashlib
import json
import posixpath
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
SOURCE = "01_Source_Code"
README = "02_README"
ARCHITECTURE = "03_Architecture_Diagrams"
COST = "04_Cost_Analysis"
VIDEO = "05_Recorded_Walkthrough"
COMPONENTS = (SOURCE, README, ARCHITECTURE, COST, VIDEO)
VIDEO_BASENAME = "WebRAG-Live-Browser-Walkthrough"
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")

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


def rewrite_links(markdown: str, original_directory: str, output_directory: str,
                  special: dict[str, str] | None = None) -> str:
    """Keep local Markdown links valid after a document moves into its own folder."""
    special = special or {}

    def replace(match: re.Match[str]) -> str:
        target = match.group(2)
        if target.startswith(("https://", "http://", "#", "mailto:")):
            return match.group(0)
        path, marker, fragment = target.partition("#")
        if not path:
            return match.group(0)
        original = posixpath.normpath(posixpath.join(original_directory, path))
        destination = special.get(original, f"{SOURCE}/{original}")
        relative = posixpath.relpath(destination, output_directory)
        return f"{match.group(1)}{relative}{marker}{fragment}{match.group(3)}"

    return LINK.sub(replace, markdown)


def check_markdown_links(name: str, content: bytes, members: set[str]) -> None:
    markdown = content.decode("utf-8")
    links = [match[1] for match in LINK.findall(markdown)]
    missing = []
    folder = posixpath.dirname(name)
    for link in links:
        if link.startswith(("https://", "http://", "#", "mailto:")):
            continue
        target = link.split("#", 1)[0]
        resolved = posixpath.normpath(posixpath.join(folder, target))
        if target and resolved not in members and not any(p.startswith(resolved.rstrip("/") + "/") for p in members):
            missing.append(link)
    if missing:
        raise RuntimeError(f"Broken local links in {name}: {missing}")


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

    members: dict[str, bytes] = {}
    for name in paths:
        source = (ROOT / name).resolve()
        if ROOT.resolve() not in source.parents or not source.is_file():
            raise RuntimeError(f"Unsafe or missing tracked path: {name}")
        members[f"{SOURCE}/{name}"] = source.read_bytes()

    architecture_files = {
        "docs/architecture-showcase.png": f"{ARCHITECTURE}/architecture-showcase.png",
        "docs/architecture.svg": f"{ARCHITECTURE}/architecture.svg",
        "docs/langgraph.mmd": f"{ARCHITECTURE}/langgraph.mmd",
    }
    readme_special = {**architecture_files, "COST_ANALYSIS.md": f"{COST}/COST_ANALYSIS.md"}
    members[f"{README}/README.md"] = rewrite_links(
        (ROOT / "README.md").read_text(encoding="utf-8"), "", README, readme_special
    ).encode("utf-8")
    for source, destination in architecture_files.items():
        members[destination] = (ROOT / source).read_bytes()
    members[f"{ARCHITECTURE}/README.md"] = (
        "# Architecture diagrams\n\n"
        "Open [the presentation diagram](architecture-showcase.png) for the complete system flow, "
        "[the technical SVG](architecture.svg) for retrieval and verification branches, and "
        "[the LangGraph source](langgraph.mmd) for state transitions. "
        "[The annotated architecture notes](../01_Source_Code/docs/architecture.md) explain the boundaries and deployment.\n"
    ).encode("utf-8")
    members[f"{COST}/COST_ANALYSIS.md"] = rewrite_links(
        (ROOT / "COST_ANALYSIS.md").read_text(encoding="utf-8"), "", COST
    ).encode("utf-8")
    for extension in ("mp4", "srt"):
        filename = f"{VIDEO_BASENAME}.{extension}"
        members[f"{VIDEO}/{filename}"] = (ROOT / "docs" / "video" / filename).read_bytes()
    transcript = f"{VIDEO_BASENAME}-Transcript.md"
    members[f"{VIDEO}/{transcript}"] = (ROOT / "docs" / "video" / transcript).read_bytes()
    members[f"{VIDEO}/DEMO_LINK.md"] = (ROOT / "submission" / "05_DEMO_LINK.md").read_bytes()
    members["START_HERE.md"] = (ROOT / "submission" / "README.md").read_bytes()

    if DRIVE_URL.encode() not in members[f"{VIDEO}/DEMO_LINK.md"]:
        raise RuntimeError("Demo link changed or missing")
    recording = members[f"{VIDEO}/{VIDEO_BASENAME}.mp4"]
    if len(recording) < 20_000_000 or recording[4:8] != b"ftyp":
        raise RuntimeError("The MP4 walkthrough is missing or incomplete")
    all_names = set(members)
    for name in (f"{SOURCE}/README.md", f"{README}/README.md", f"{COST}/COST_ANALYSIS.md",
                 f"{ARCHITECTURE}/README.md", "START_HERE.md"):
        check_markdown_links(name, members[name], all_names)
    for name, content in members.items():
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise RuntimeError(f"Credential-like string detected in {name}")
    if not members[f"{SOURCE}/.env.example"].decode().split("OPENAI_API_KEY=", 1)[1].startswith("\n"):
        raise RuntimeError(".env.example contains a nonblank key")

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(ZIP_PATH, "w", compression=ZIP_DEFLATED, compresslevel=7) as archive:
        for name, content in sorted(members.items()):
            archive.writestr(clean_archive_info(name), content)
    with ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
        actual = {item.removeprefix(f"{PREFIX}/") for item in archive.namelist()}
        if actual != all_names:
            raise RuntimeError("Unexpected ZIP members")
        top_level = {name.split("/", 1)[0] for name in actual}
        if top_level != {"START_HERE.md", *COMPONENTS}:
            raise RuntimeError(f"Incorrect component folders: {top_level}")
        if hashlib.sha256(archive.read(f"{PREFIX}/{VIDEO}/{VIDEO_BASENAME}.mp4")).digest() != hashlib.sha256(recording).digest():
            raise RuntimeError("Archived recording differs from source")
    shutil.copy2(ZIP_PATH, DOWNLOAD)
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    if digest != hashlib.sha256(DOWNLOAD.read_bytes()).hexdigest():
        raise RuntimeError("Downloads ZIP does not match repository ZIP")
    result = {
        "archive": str(ZIP_PATH),
        "downloads_copy": str(DOWNLOAD),
        "bytes": ZIP_PATH.stat().st_size,
        "members": len(members),
        "sha256": digest,
        "components": list(COMPONENTS),
        "credential_scan": "passed",
        "readme_relative_links": "passed",
        "zip_integrity": "passed",
        "recording": "MP4, subtitles and transcript included",
    }
    (ROOT / "submission" / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
