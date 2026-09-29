"""Render a disclosed synthetic walkthrough from actual saved results and TTS audio."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "walkthrough"


def prepare() -> None:
    """Fill metric placeholders only from the final persisted run and test output."""
    OUT.mkdir(parents=True, exist_ok=True)
    report = json.loads((ROOT / "evaluation/results/results.json").read_text(encoding="utf-8"))
    holdout = report["by_split"].get(
        "independent_holdout", report["by_split"].get("holdout", report["overall"])
    )
    tests = (ROOT / "artifacts/tests-final.txt").read_text(encoding="utf-8")
    count = re.search(r"(\d+) passed", tests)
    coverage = re.search(r"Total coverage: ([\d.]+)%", tests)
    metrics = {
        "provider": report["provider"],
        "answer_mode": "structured synthesis"
        if report["provider"] == "openai"
        else "extractive quotations",
        "pages": str(report["corpus"]["pages"]),
        "chunks": str(report["corpus"]["chunks"]),
        "holdout_keypoint_pct": f"{holdout['keypoint_coverage'] * 100:.1f}",
        "correct_refusal_pct": f"{holdout['unanswerable_refusal']['rate'] * 100:.1f}",
        "false_answer_pct": f"{holdout['false_answer']['rate'] * 100:.1f}",
        "test_count": count.group(1) if count else "unverified",
        "coverage_pct": coverage.group(1) if coverage else "unverified",
        "mean_api_usd": f"{sum(row['raw_answer']['usage']['estimated_usd'] for row in report['questions']) / len(report['questions']):.6f}",
        "p95_ms": f"{report['overall']['p95_wall_ms']:.1f}",
    }
    slides = json.loads((ROOT / "scripts/walkthrough_content.json").read_text(encoding="utf-8"))
    for slide in slides:
        for key in ("title", "narration"):
            slide[key] = slide[key].format(**metrics)
        slide["bullets"] = [line.format(**metrics) for line in slide["bullets"]]
    (OUT / "slides.json").write_text(
        json.dumps(slides, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    transcript = "\n\n".join(
        f"## {index + 1}. {slide['title']}\n\n{slide['narration']}"
        for index, slide in enumerate(slides)
    )
    (OUT / "transcript.md").write_text(
        "# Automated walkthrough — synthetic narration\n\n" + transcript + "\n",
        encoding="utf-8",
    )


def font(size: int, mono: bool = False) -> Any:
    """Use available system fonts, retaining a portable fallback."""
    candidates = (
        ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
        if mono
        else ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def wrapped(
    draw: Any,
    text: str,
    x: int,
    y: int,
    width: int,
    size: int = 31,
    color: str = "#d4e1df",
    mono: bool = False,
    max_lines: int = 18,
) -> int:
    """Wrap readable text into a bounded slide panel."""
    face = font(size, mono)
    lines: list[str] = []
    for paragraph in text.replace("\r", "").split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if draw.textlength(candidate, font=face) > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    for line in lines[:max_lines]:
        draw.text((x, y), line, font=face, fill=color)
        y += int(size * 1.35)
    return y


def evidence_panel(slide: dict[str, Any], index: int) -> str:
    """Display real output excerpts and concrete commands beside the narration."""
    report = json.loads((ROOT / "evaluation/results/results.json").read_text(encoding="utf-8"))
    kind = slide["kind"]
    if kind == "demo":
        saved = json.loads((ROOT / "artifacts/http-smoke.json").read_text(encoding="utf-8"))
        rows = saved["questions"][:3] if index == 8 else saved["questions"][3:]
        excerpts = []
        for row in rows:
            excerpt = row["answer"][:105].replace("\n", " ")
            source = (
                row["sources"][0]["url"] if row["sources"] else "No supporting website evidence."
            )
            excerpts.append(
                f"{row['question']}\nanswerable: {row['answerable']}\n{excerpt}\n{source}"
            )
        return "ACTUAL HTTP RESPONSES (excerpts)\n\n" + "\n\n".join(excerpts)
    if kind == "evaluation":
        h = report["by_split"].get(
            "independent_holdout", report["by_split"].get("holdout", report["overall"])
        )
        return f"FINAL HOLDOUT — {h['count']} QUESTIONS\n\nKeypoint coverage: {h['keypoint_coverage']:.1%}\nRetrieval Hit@{report['top_k']}: {h['hit_at_k']['successes']}/{h['hit_at_k']['trials']}\nRefusal: {h['unanswerable_refusal']['successes']}/{h['unanswerable_refusal']['trials']}\nFalse answers: {h['false_answer']['successes']}/{h['false_answer']['trials']}\n\nQuote support checks provenance.\nRegex coverage is not a human quality score.\n\nSee EVALUATION.md and raw results."
    if kind == "cost":
        mean_cost = sum(row["usage"].get("estimated_usd", 0) for row in report["questions"]) / len(
            report["questions"]
        )
        example = next(row for row in report["questions"] if row["id"] == "s1")
        usage = example["usage"]
        return (
            f"OBSERVED API USAGE ESTIMATES\n\nMean query: ${mean_cost:.6f}\n"
            f"100 queries: ${mean_cost * 100:.4f}\n"
            f"1,000 queries: ${mean_cost * 1000:.4f}\n"
            f"10,000 queries: ${mean_cost * 10000:.4f}\n\n"
            f"Example: What does list.append do?\n"
            f"Input / output tokens: {usage['input_tokens']:,} / {usage['output_tokens']:,}\n"
            f"Query estimate: ${usage['estimated_usd']:.6f}\n\n"
            "Includes returned synthesis + verification\nand bounded retry usage.\n"
            "Embedding tokens remain text estimates.\n"
            "Small-sample scenario, not an invoice.\nSee COST_ANALYSIS.md."
        )
    if kind == "architecture":
        return "INGESTION\nScoped URL + robots\nPublic IP / redirect validation\nMain content + sections\nToken chunks + source metadata\nReal embeddings → Chroma\nJSON documents → BM25\n\nQUERY\nValidate → hybrid retrieve → gate\nQuote/synthesize → verify\nBounded retry or refusal\nAnswer + URLs + usage"
    if kind == "code":
        return 'RUN FROM THE REPOSITORY\n\nrag doctor\nrag ingest\nrag stats\nrag ask "What does list.append do?" --json\nrag eval --questions evaluation/submission_questions.json\nrag cost-report\n\npython -m uvicorn rag_agent.api:create_app --factory\n\npython -m pytest --cov=rag_agent\npython scripts/audit_dependencies.py'
    return (
        f"Website-grounded RAG assessment\n\n{report['corpus']['pages']} real public documentation pages\n"
        "Persistent vector and lexical search\nExplicit LangGraph branches\n"
        "Exact source evidence\nMeasured evaluation and costs\nCLI + HTTP API + Docker\n\n"
        f"Measured provider: {report['provider']}\n"
        "OpenAI structured synthesis + semantic check\nLocal embedding/excerpt fallback available\n\n"
        "Synthetic narration is disclosed."
    )


def render() -> None:
    """Combine generated speech with labeled slides; enforce a 10–15 minute runtime."""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    slides = json.loads((OUT / "slides.json").read_text(encoding="utf-8"))
    durations = []
    for index in range(len(slides)):
        with wave.open(str(OUT / f"{index:02d}.wav"), "rb") as speech:
            durations.append(speech.getnframes() / speech.getframerate())
    speech_total = sum(durations)
    speed = max(0.75, min(1.5, speech_total / 720))
    clips = []
    for index, slide in enumerate(slides):
        frame = Image.new("RGB", (1920, 1080), "#101f29")
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle((48, 38, 1872, 92), radius=18, fill="#193643")
        draw.text((72, 47), "WEBRAG  /  MYADVICE ASSESSMENT", font=font(27), fill="#85d3bc")
        draw.text((1190, 47), "AUTOMATED NARRATION · REAL OUTPUTS", font=font(24), fill="#d0dad8")
        wrapped(draw, slide["title"], 72, 130, 1720, 51, "#f6faf6", max_lines=2)
        y = 285
        for bullet in slide["bullets"]:
            draw.ellipse((78, y + 14, 90, y + 26), fill="#85d3bc")
            y = wrapped(draw, bullet, 112, y, 790, 38, max_lines=3) + 25
        draw.rounded_rectangle((970, 275, 1850, 960), radius=24, fill="#20333d")
        panel_size = 23 if slide["kind"] == "demo" else 27
        panel_lines = 22 if slide["kind"] == "demo" else 18
        wrapped(
            draw,
            evidence_panel(slide, index),
            1000,
            307,
            810,
            panel_size,
            "#dae4dd",
            True,
            panel_lines,
        )
        draw.text(
            (72, 1020),
            "Source code, evidence, test logs and evaluation results are included in the submission.",
            font=font(25),
            fill="#a1b7b3",
        )
        draw.text(
            (1690, 1020), f"{index + 1:02d} / {len(slides):02d}", font=font(27), fill="#85d3bc"
        )
        path = OUT / f"{index:02d}.png"
        frame.save(path)
        duration = durations[index] / speed + 1
        clip = OUT / f"{index:02d}.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-framerate",
                "1",
                "-i",
                str(path),
                "-i",
                str(OUT / f"{index:02d}.wav"),
                "-vf",
                "fps=12,format=yuv420p",
                "-af",
                f"atempo={speed:.5f},apad=pad_dur=1",
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-tune",
                "stillimage",
                "-crf",
                "25",
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-movflags",
                "+faststart",
                str(clip),
            ],
            check=True,
        )
        clips.append(clip)
    manifest = OUT / "concat.txt"
    manifest.write_text("\n".join("file '" + p.as_posix() + "'" for p in clips), encoding="utf-8")
    destination = ROOT / "artifacts/WebRAG-Walkthrough.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        check=True,
    )
    total = sum(d / speed + 1 for d in durations)
    if not 600 <= total <= 900:
        raise ValueError(f"Walkthrough duration {total:.1f}s outside 10–15 minutes")
    (ROOT / "artifacts/video-verification.json").write_text(
        json.dumps(
            {
                "path": str(destination),
                "duration_seconds": total,
                "speech_seconds": speech_total,
                "speed_factor": speed,
                "slides": len(slides),
                "narration": "Windows synthetic TTS, explicitly disclosed",
                "source_results": report_id(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "video": str(destination),
                "duration_seconds": total,
                "bytes": destination.stat().st_size,
            }
        )
    )


def report_id() -> str:
    return str(
        json.loads((ROOT / "evaluation/results/results.json").read_text(encoding="utf-8"))["run_id"]
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "render"])
    args = parser.parse_args()
    prepare() if args.phase == "prepare" else render()
