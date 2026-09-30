"""Create neural synthetic narration with timing metadata for selectable captions."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "showcase"
VOICE = "en-US-AndrewNeural"


async def synthesize_one(index: int, narration: str) -> list[dict[str, object]]:
    mp3 = OUT / f"{index:02d}.mp3"
    boundaries: list[dict[str, object]] = []
    for attempt in range(3):
        try:
            audio = bytearray()
            talk = edge_tts.Communicate(narration, VOICE, boundary="WordBoundary")
            async for chunk in talk.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    boundaries.append(
                        {
                            "start": chunk["offset"] / 10_000_000,
                            "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                            "text": chunk["text"],
                        }
                    )
            if not audio or not boundaries:
                raise RuntimeError("No audio or word timing was returned")
            mp3.write_bytes(audio)
            break
        except Exception:
            boundaries.clear()
            if attempt == 2:
                raise
            await asyncio.sleep(2 * (attempt + 1))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(mp3),
            "-ar",
            "24000",
            "-ac",
            "1",
            str(OUT / f"{index:02d}.wav"),
        ],
        check=True,
    )
    print(f"Neural narration {index + 1:02d}: {len(boundaries)} timed words", flush=True)
    return boundaries


async def main() -> None:
    slides = json.loads((OUT / "slides.json").read_text(encoding="utf-8"))
    all_boundaries = []
    for index, slide in enumerate(slides):
        all_boundaries.append(await synthesize_one(index, slide["narration"]))
    (OUT / "word_boundaries.json").write_text(
        json.dumps(all_boundaries, indent=2), encoding="utf-8"
    )
    (OUT / "narration.json").write_text(
        json.dumps(
            {
                "type": "synthetic neural TTS",
                "voice": VOICE,
                "caption_timing": "provider word boundaries",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
