"""Finish the actual-browser recording with narration, captions and a transcript."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "live_demo"
DEST = ROOT / "docs" / "video"
NAME = "WebRAG-Live-Browser-Walkthrough"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SCENES = json.loads((ROOT / "scripts" / "live_demo_content.json").read_text(encoding="utf-8"))
WORDS = json.loads((ART / "word_boundaries.json").read_text(encoding="utf-8"))


def run(*args: str) -> None:
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def stamp(seconds: float) -> str:
    milli = int(round(seconds * 1000))
    hour, milli = divmod(milli, 3_600_000)
    minute, milli = divmod(milli, 60_000)
    second, milli = divmod(milli, 1_000)
    return f"{hour:02d}:{minute:02d}:{second:02d},{milli:03d}"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    tracks = {
        part: json.loads((ART / f"{part}-timeline.json").read_text(encoding="utf-8"))
        for part in ("app", "readme")
    }
    timeline = tracks["app"]["scenes"] + tracks["readme"]["scenes"]
    if [scene["index"] for scene in timeline] != list(range(len(SCENES))):
        raise RuntimeError("Missing browser chapter")
    app_seconds = float(tracks["app"]["scenes"][-1]["end"])
    total_seconds = app_seconds + float(tracks["readme"]["scenes"][-1]["end"])
    if not 420 <= app_seconds <= 500 or not 600 <= total_seconds <= 900:
        raise RuntimeError(f"Unexpected runtimes: app {app_seconds:.1f}, total {total_seconds:.1f}")
    print(f"Browser capture: app {app_seconds:.1f}s, complete {total_seconds:.1f}s", flush=True)

    clips: list[Path] = []
    cues: list[str] = []
    cue = 1
    elapsed = 0.0
    for segment in timeline:
        index = int(segment["index"])
        part = "app" if index < 11 else "readme"
        offset = float(tracks[part]["offset_seconds"])
        start = float(segment["start"])
        duration = float(segment["end"]) - start
        if duration < float(WORDS[index][-1]["end"]) + 0.2:
            raise RuntimeError(f"Chapter {index + 1} cuts off narration")
        video = ART / f"{part}-raw.webm"
        audio = ART / f"{index:02d}.wav"
        clip = ART / f"browser-{index:02d}.mp4"
        if index == 9:
            # Playwright keeps the desktop-sized recording canvas on viewport resize.
            # Present the actual 390px-wide browser pixels as a centered phone view.
            vf = "crop=390:844:0:0,pad=1536:960:573:58:color=0x0b2522,format=yuv420p"
        else:
            vf = "format=yuv420p"
        run(
            "-ss", f"{offset + start:.3f}", "-i", str(video), "-i", str(audio),
            "-vf", vf, "-af", "apad", "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
            "-r", "25", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-ar", "48000", "-movflags", "+faststart", str(clip),
        )
        clips.append(clip)
        spoken = SCENES[index]["narration"].split()
        words = WORDS[index]
        display = spoken if len(spoken) == len(words) else [item["text"] for item in words]
        for first in range(0, len(words), 11):
            last = min(first + 11, len(words))
            begin = elapsed + float(words[first]["start"])
            end = elapsed + min(duration - 0.1, float(words[last - 1]["end"]) + 0.2)
            cues.append(f"{cue}\n{stamp(begin)} --> {stamp(end)}\n{' '.join(display[first:last])}\n")
            cue += 1
        elapsed += duration
        print(f"Rendered {index + 1:02d}/16: {SCENES[index]['title']}", flush=True)

    manifest = ART / "browser-concat.txt"
    manifest.write_text("\n".join(f"file '{clip.as_posix()}'" for clip in clips), encoding="utf-8")
    uncaptained = ART / "browser-combined.mp4"
    run("-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", "-movflags", "+faststart", str(uncaptained))
    srt = DEST / f"{NAME}.srt"
    srt.write_text("\n".join(cues), encoding="utf-8-sig")
    final = DEST / f"{NAME}.mp4"
    run(
        "-i", str(uncaptained), "-i", str(srt), "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
        "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
        "-disposition:s:0", "default", "-movflags", "+faststart", str(final),
    )
    transcript = DEST / f"{NAME}-Transcript.md"
    transcript.write_text(
        "# WebRAG live browser walkthrough transcript\n\n"
        "The candidate's webcam is damaged. The narration is disclosed synthetic speech. "
        "All application and repository visuals are genuine browser captures.\n\n"
        + "\n\n".join(
            f"## {index + 1:02d}. {scene['title']}\n\n{scene['narration']}"
            for index, scene in enumerate(SCENES)
        ) + "\n",
        encoding="utf-8",
    )
    poster = DEST / f"{NAME}-Poster.png"
    run("-ss", "3", "-i", str(final), "-frames:v", "1", str(poster))
    downloads = Path.home() / "Downloads"
    for path in (final, srt, transcript, poster):
        shutil.copy2(path, downloads / path.name)
    checksum = hashlib.sha256(final.read_bytes()).hexdigest()
    if checksum != hashlib.sha256((downloads / final.name).read_bytes()).hexdigest():
        raise RuntimeError("Downloads video hash mismatch")
    verification = {
        "live_app_seconds": app_seconds,
        "full_video_seconds": total_seconds,
        "chapters": len(SCENES),
        "caption_cues": len(cues),
        "source": "Real Playwright browser recording of the public Vercel app and GitHub README",
        "narration": "Disclosed synthetic neural voice",
        "webcam_note": "Candidate webcam damaged",
        "sha256": checksum,
        "bytes": final.stat().st_size,
        "downloads_copy": str(downloads / final.name),
    }
    (ROOT / "docs" / "verification" / "live-browser-video.json").write_text(
        json.dumps(verification, indent=2), encoding="utf-8"
    )
    print(json.dumps(verification, indent=2), flush=True)


if __name__ == "__main__":
    main()
