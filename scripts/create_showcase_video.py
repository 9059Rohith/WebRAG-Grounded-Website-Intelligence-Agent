"""Build a captioned assessment video from real captures and disclosed Windows TTS.

Run `prepare`, then `powershell -File scripts/synthesize_walkthrough.ps1
-Directory artifacts/showcase`, then `render`. The architecture image must already be
published before recording; this script only reads that image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "showcase"
ASSETS = ROOT / "docs" / "video" / "assets"
SIZE = (1920, 1080)
BG = "#071718"
INK = "#eef7ef"
MINT = "#9fe9c5"
MUTED = "#acc5bc"
YELLOW = "#f5cb83"


def font(size: int, bold: bool = False, serif: bool = False) -> Any:
    names = (
        ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgia.ttf"]
        if serif
        else ["C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"]
    )
    names.extend(["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def lines(draw: ImageDraw.ImageDraw, value: str, width: int, face: Any) -> list[str]:
    result: list[str] = []
    current = ""
    for word in value.split():
        candidate = (current + " " + word).strip()
        if current and draw.textlength(candidate, font=face) > width:
            result.append(current)
            current = word
        else:
            current = candidate
    if current:
        result.append(current)
    return result


def paragraph(
    draw: ImageDraw.ImageDraw,
    value: str,
    xy: tuple[int, int],
    width: int,
    face: Any,
    fill: str = MUTED,
    leading: int | None = None,
) -> int:
    x, y = xy
    dy = leading or int(face.size * 1.36)
    for line in lines(draw, value, width, face):
        draw.text((x, y), line, font=face, fill=fill)
        y += dy
    return y


def base(index: int, total: int, slide: dict[str, Any]) -> tuple[Image.Image, Any]:
    im = Image.new("RGB", SIZE, BG)
    glow = Image.new("RGBA", SIZE)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((1190, -370, 2350, 790), fill=(67, 167, 130, 32))
    gd.ellipse((-540, 500, 560, 1600), fill=(89, 137, 177, 22))
    im = Image.alpha_composite(im.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(125)))
    draw = ImageDraw.Draw(im)
    draw.ellipse((83, 62, 105, 84), fill=MINT)
    draw.text((120, 51), "WebRAG", font=font(34, True), fill=MINT)
    draw.text((1490, 57), "MYADVICE  /  AI ENGINEER I", font=font(22, True), fill=MUTED)
    draw.line((82, 115, 1838, 115), fill="#31534c", width=2)
    draw.text((84, 148), slide["eyebrow"], font=font(22, True), fill=YELLOW)
    draw.text(
        (82, 1019),
        "Real captures • recorded evaluation • synthetic narration",
        font=font(21),
        fill="#81a499",
    )
    draw.text((1745, 1019), f"{index + 1:02d} / {total:02d}", font=font(22, True), fill=MINT)
    draw.rounded_rectangle((80, 1060, 1840, 1067), radius=3, fill="#25433d")
    draw.rounded_rectangle(
        (80, 1060, 80 + int(1760 * (index + 1) / total), 1067), radius=3, fill=MINT
    )
    return im, draw


def points(
    draw: Any, slide: dict[str, Any], *, x: int = 90, y: int = 400, width: int = 720
) -> None:
    for i, point in enumerate(slide["points"]):
        draw.rounded_rectangle(
            (x, y, x + width, y + 112), radius=19, fill="#122b29", outline="#31534c", width=2
        )
        draw.ellipse((x + 25, y + 33, x + 70, y + 78), fill="#244940")
        draw.text((x + 39, y + 40), str(i + 1), font=font(22, True), fill=MINT)
        paragraph(draw, point, (x + 88, y + 25), width - 112, font(29, True), INK, 37)
        y += 135


def image_card(
    im: Image.Image, path: Path, box: tuple[int, int, int, int], *, crop: bool = False
) -> None:
    x1, y1, x2, y2 = box
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x1 - 12, y1 - 12, x2 + 12, y2 + 12), radius=23, fill="#29413c")
    source = Image.open(path).convert("RGB")
    if path.name == "repaired-answer.png":
        source = source.crop((0, 0, 905, 640))
    if path.name == "how-it-works.png":
        source = source.crop((170, 175, 1360, 925))
    target = (x2 - x1, y2 - y1)
    source = (
        ImageOps.fit(source, target, method=Image.Resampling.LANCZOS)
        if crop
        else ImageOps.contain(source, target, method=Image.Resampling.LANCZOS)
    )
    canvas = Image.new("RGB", target, "#0a1a1e" if "architecture" in path.name else "#f5f9f5")
    canvas.paste(source, ((target[0] - source.width) // 2, (target[1] - source.height) // 2))
    im.paste(canvas, (x1, y1))


def render_frame(index: int, total: int, slide: dict[str, Any]) -> Path:
    im, draw = base(index, total, slide)
    kind = slide["kind"]
    title = slide["title"]
    if kind == "architecture":
        draw.text((85, 185), title, font=font(52, True, True), fill=INK)
        image_card(im, ROOT / "docs" / "architecture-showcase.png", (175, 270, 1745, 965))
        draw.text((1475, 972), "SOURCE: docs/architecture-showcase.png", font=font(17), fill=MUTED)
    else:
        paragraph(draw, title, (83, 200), 1670, font(62, True, True), INK, 75)
        if kind in {"hero", "screenshot", "evidence", "mobile"}:
            points(draw, slide, y=430 if kind == "hero" else 410, width=690)
            if kind == "evidence":
                source = Image.open(ASSETS / slide["asset"]).convert("RGB")
                source = source.crop((int(source.width * 0.69), 0, source.width, source.height))
                temp = OUT / "evidence-crop.png"
                source.save(temp)
                image_card(im, temp, (890, 320, 1780, 905))
            elif kind == "mobile":
                image_card(im, ASSETS / slide["asset"], (910, 320, 1280, 960))
                image_card(im, ASSETS / slide["asset2"], (1370, 320, 1740, 960))
            else:
                image_card(
                    im, ASSETS / (slide.get("asset") or "desktop-answer.png"), (860, 320, 1810, 920)
                )
            draw.text(
                (910, 948), "CAPTURED FROM THE PUBLIC APPLICATION", font=font(19, True), fill=MUTED
            )
        elif kind == "pipeline":
            points(draw, slide, y=385, width=730)
            labels = (
                [
                    "URL scope + robots",
                    "Extract useful content",
                    "Heading-aware chunks",
                    "OpenAI embeddings",
                    "Chroma + BM25",
                ]
                if index == 3
                else [
                    "Question embedding",
                    "Dense + lexical search",
                    "RRF + facet coverage",
                    "Top 8 passages",
                    "Grounding gate",
                ]
                if index == 4
                else [
                    "Validate",
                    "Retrieve + gate",
                    "Generate source IDs",
                    "Restore + verify",
                    "Answer / retry / refuse",
                ]
            )
            y = 326
            for n, label in enumerate(labels):
                draw.rounded_rectangle(
                    (930, y, 1760, y + 94), radius=18, fill="#14352f", outline="#38745d", width=2
                )
                draw.text((960, y + 22), f"{n + 1:02d}", font=font(29, True), fill=MINT)
                draw.text((1040, y + 21), label, font=font(30, True), fill=INK)
                if n < len(labels) - 1:
                    draw.text((1320, y + 88), "↓", font=font(25, True), fill=MINT)
                y += 122
        elif kind == "refusal":
            points(draw, slide, y=390, width=750)
            image_card(im, ASSETS / "refusal-live.png", (900, 320, 1810, 910))
            draw.text(
                (910, 948), "CAPTURED FROM THE PUBLIC APPLICATION", font=font(19, True), fill=MUTED
            )
        elif kind == "metrics":
            points(draw, slide, y=400, width=780)
            for n, (number, label) in enumerate(
                [
                    ("40", "pages"),
                    ("1,597", "chunks"),
                    ("37 / 38", "follow-up answerability"),
                    ("1", "remaining false refusal"),
                ]
            ):
                x = 970 + (n % 2) * 410
                y = 365 + (n // 2) * 260
                draw.rounded_rectangle(
                    (x, y, x + 370, y + 220), radius=22, fill="#14352f", outline="#38745d", width=2
                )
                draw.text((x + 27, y + 28), number, font=font(57, True, True), fill=MINT)
                paragraph(draw, label, (x + 28, y + 120), 315, font(26), INK)
        elif kind == "cost":
            points(draw, slide, y=397, width=780)
            for n, (volume, amount) in enumerate(
                [
                    ("100 queries", "$0.1559"),
                    ("1,000 queries", "$1.5585"),
                    ("10,000 queries", "$15.5851"),
                ]
            ):
                y = 400 + n * 156
                draw.rounded_rectangle(
                    (960, y, 1770, y + 125), radius=22, fill="#14352f", outline="#38745d", width=2
                )
                draw.text((995, y + 28), volume, font=font(32, True), fill=INK)
                draw.text((1500, y + 28), amount, font=font(36, True), fill=MINT)
            draw.text(
                (1040, 905),
                "Observed mix extrapolation · excludes hosting",
                font=font(24),
                fill=MUTED,
            )
        else:
            points(draw, slide, y=400, width=930)
            if kind == "deployment":
                right = [
                    "PUBLIC DEPLOYMENT",
                    "webrag-assessment.vercel.app",
                    "SOURCE + REPORTS",
                    "github.com/9059Rohith",
                    "CI STATUS",
                    "Blocked before jobs by account billing",
                ]
            else:
                right = [
                    "TRY THE PUBLIC APP",
                    "webrag-assessment.vercel.app",
                    "READ THE IMPLEMENTATION",
                    "GitHub / WebRAG",
                    "VERIFY THE CLAIMS",
                    "Raw results · costs · architecture",
                ]
            draw.rounded_rectangle(
                (1090, 365, 1800, 860), radius=26, fill="#14352f", outline="#38745d", width=2
            )
            y = 413
            for n in range(0, 6, 2):
                draw.text((1130, y), right[n], font=font(22, True), fill=YELLOW)
                paragraph(draw, right[n + 1], (1130, y + 43), 620, font(29, True), INK)
                y += 148
    target = OUT / f"{index:02d}.png"
    im.convert("RGB").save(target, optimize=True)
    return target


def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    slides = json.loads((ROOT / "scripts" / "showcase_content.json").read_text(encoding="utf-8"))
    (OUT / "slides.json").write_text(
        json.dumps(slides, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    transcript = "# WebRAG assessment walkthrough\n\nSynthetic narration; the candidate's webcam is damaged. UI captures and evaluation records are real.\n\n"
    transcript += (
        "\n\n".join(
            f"## {i + 1:02d}. {slide['title']}\n\n{slide['narration']}"
            for i, slide in enumerate(slides)
        )
        + "\n"
    )
    (OUT / "transcript.md").write_text(transcript, encoding="utf-8")
    for i, slide in enumerate(slides):
        render_frame(i, len(slides), slide)
    print(f"Prepared {len(slides)} frames and narration scripts in {OUT}")


def timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def captions(slides: list[dict[str, Any]], durations: list[float], speed: float) -> str:
    lines_out: list[str] = []
    at = 0.0
    cue = 1
    boundary_path = OUT / "word_boundaries.json"
    boundaries = (
        json.loads(boundary_path.read_text(encoding="utf-8")) if boundary_path.exists() else None
    )
    for index, (slide, duration) in enumerate(zip(slides, durations, strict=True)):
        if boundaries and boundaries[index]:
            words = boundaries[index]
            source_words = slide["narration"].split()
            # The TTS service may tokenize punctuation differently. Preserve exact
            # transcript punctuation when counts align; otherwise use timed words.
            if len(source_words) == len(words):
                display_words = source_words
            else:
                display_words = [word["text"] for word in words]
            for start in range(0, len(words), 11):
                stop = min(len(words), start + 11)
                first = words[start]
                last = words[stop - 1]
                begin = at + float(first["start"]) / speed
                end = at + min(duration - 0.1, float(last["end"]) / speed + 0.2)
                caption = " ".join(display_words[start:stop])
                lines_out.append(f"{cue}\n{timestamp(begin)} --> {timestamp(end)}\n{caption}\n")
                cue += 1
        else:
            sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", slide["narration"])
            sentence_words = [max(1, len(s.split())) for s in sentences]
            available = max(0.1, duration - 1.0)
            cursor = at
            for sentence, count in zip(sentences, sentence_words, strict=True):
                segment = available * count / sum(sentence_words)
                lines_out.append(
                    f"{cue}\n{timestamp(cursor)} --> {timestamp(cursor + segment)}\n{sentence.strip()}\n"
                )
                cue += 1
                cursor += segment
        at += duration
    return "\n".join(lines_out)


def render() -> None:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    slides = json.loads((OUT / "slides.json").read_text(encoding="utf-8"))
    speech: list[float] = []
    for i in range(len(slides)):
        with wave.open(str(OUT / f"{i:02d}.wav"), "rb") as audio:
            speech.append(audio.getnframes() / audio.getframerate())
    speech_total = sum(speech)
    # Keep natural voice speed whenever the required 10–15 minute range allows.
    speed = (
        1.0
        if 600 <= speech_total + len(slides) <= 900
        else min(1.15, max(0.85, speech_total / 840))
    )
    durations = [d / speed + 1.0 for d in speech]
    total_duration = sum(durations)
    if not 600 <= total_duration <= 900:
        raise RuntimeError(f"Narration would run {total_duration:.1f}s; revise script")
    if durations[0] >= 120:
        raise RuntimeError("Architecture would not appear in the first two minutes")
    clips: list[Path] = []
    for i, duration in enumerate(durations):
        clip = OUT / f"{i:02d}.mp4"
        fade_out = max(0.0, duration - 0.35)
        vf = (
            f"zoompan=z='min(zoom+0.000035,1.03)':d=1:s=1920x1080:fps=15,"
            f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.3f}:d=0.3,format=yuv420p"
        )
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
                "15",
                "-i",
                str(OUT / f"{i:02d}.png"),
                "-i",
                str(OUT / f"{i:02d}.wav"),
                "-vf",
                vf,
                "-af",
                f"atempo={speed:.6f},apad=pad_dur=1",
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "24",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-pix_fmt",
                "yuv420p",
                str(clip),
            ],
            check=True,
        )
        clips.append(clip)
        print(f"Rendered {i + 1:02d}/{len(slides)}: {slides[i]['title']}", flush=True)
    manifest = OUT / "concat.txt"
    manifest.write_text("\n".join("file '" + p.as_posix() + "'" for p in clips), encoding="utf-8")
    video = ROOT / "docs" / "video" / "WebRAG-Assessment-Showcase.mp4"
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
            str(video),
        ],
        check=True,
    )
    srt = ROOT / "docs" / "video" / "WebRAG-Assessment-Showcase.srt"
    srt.write_text(captions(slides, durations, speed), encoding="utf-8-sig")
    captioned = OUT / "captioned.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-i",
            str(srt),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-map",
            "1:0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-disposition:s:0",
            "default",
            "-movflags",
            "+faststart",
            str(captioned),
        ],
        check=True,
    )
    captioned.replace(video)
    transcript = ROOT / "docs" / "video" / "WebRAG-Assessment-Showcase-Transcript.md"
    shutil.copy2(OUT / "transcript.md", transcript)
    poster = ROOT / "docs" / "video" / "WebRAG-Assessment-Showcase-Poster.png"
    shutil.copy2(OUT / "00.png", poster)
    download = Path.home() / "Downloads" / video.name
    shutil.copy2(video, download)
    shutil.copy2(srt, download.with_suffix(".srt"))
    shutil.copy2(transcript, download.with_name(transcript.name))
    verification = {
        "video": str(video),
        "downloads_copy": str(download),
        "seconds_approx": total_duration,
        "architecture_appears_at_seconds": durations[0],
        "slides": len(slides),
        "speech_seconds": speech_total,
        "speed_factor": speed,
        "bytes": video.stat().st_size,
        "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "narration": "synthetic neural TTS, disclosed in opening, footer and transcript",
    }
    (OUT / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "render"])
    args = parser.parse_args()
    prepare() if args.phase == "prepare" else render()
