"""Render disclosed neural voice and exact word timings for the browser demo."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "live_demo"
VOICE = "en-US-AndrewNeural"


async def one(index: int, value: str) -> list[dict[str, object]]:
    for attempt in range(3):
        try:
            sound = bytearray()
            words: list[dict[str, object]] = []
            async for item in edge_tts.Communicate(value, VOICE, boundary="WordBoundary").stream():
                if item["type"] == "audio":
                    sound.extend(item["data"])
                elif item["type"] == "WordBoundary":
                    words.append(
                        {
                            "start": item["offset"] / 10_000_000,
                            "end": (item["offset"] + item["duration"]) / 10_000_000,
                            "text": item["text"],
                        }
                    )
            if not sound or not words:
                raise RuntimeError("Voice service returned no speech timing")
            path = OUT / f"{index:02d}.mp3"
            path.write_bytes(sound)
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-ar", "24000", "-ac", "1", str(OUT / f"{index:02d}.wav")],
                check=True,
            )
            print(f"Narration {index + 1:02d}: {len(words)} timed words", flush=True)
            return words
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    scenes = json.loads((ROOT / "scripts" / "live_demo_content.json").read_text(encoding="utf-8"))
    timings = []
    for index, scene in enumerate(scenes):
        timings.append(await one(index, scene["narration"]))
    (OUT / "word_boundaries.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    (OUT / "scenes.json").write_text(json.dumps(scenes, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
