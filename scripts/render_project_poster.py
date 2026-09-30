"""Render a product poster from the verified app screenshot and real architecture."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media" / "webrag-project-poster.png"
LIVE = "https://webrag-assessment.vercel.app/"
W, H = 2400, 3200
INK = "#10272c"
MINT = "#a9e8c4"
GREEN = "#1b6751"
PALE = "#f5f8f5"


def face(size: int, *, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    files = (
        ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgia.ttf"]
        if serif
        else ["C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"]
    )
    files.append("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(next(file for file in files if Path(file).exists()), size)


def text_lines(
    draw: ImageDraw.ImageDraw,
    value: str,
    x: int,
    y: int,
    width: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
    line: int,
) -> int:
    for paragraph in value.split("\n"):
        current = ""
        for word in paragraph.split():
            next_line = (current + " " + word).strip()
            if current and draw.textlength(next_line, font=font) > width:
                draw.text((x, y), current, font=font, fill=fill)
                y += line
                current = word
            else:
                current = next_line
        draw.text((x, y), current, font=font, fill=fill)
        y += line
    return y


def arrow(
    draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = "#6bad92"
) -> None:
    draw.line((*start, *end), fill=color, width=7)
    x, y = end
    draw.polygon([(x, y), (x - 22, y - 14), (x - 22, y + 14)], fill=color)


def qr_image() -> Image.Image:
    encoder = cv2.QRCodeEncoder_create()
    raw = encoder.encode(LIVE)
    rgb = cv2.cvtColor(raw, cv2.COLOR_GRAY2RGB)
    qr = Image.fromarray(np.asarray(rgb))
    return ImageOps.expand(qr.resize((310, 310), Image.Resampling.NEAREST), border=17, fill="white")


def render() -> None:
    im = Image.new("RGB", (W, H), PALE)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 940), fill="#0a2526")
    d.ellipse((1740, -360, 2830, 730), fill="#103e35")
    d.ellipse((2020, 90, 2550, 620), fill="#17483a")
    d.ellipse((132, 105, 166, 139), fill=MINT)
    d.ellipse((106, 150, 140, 184), fill=MINT)
    d.ellipse((158, 150, 192, 184), fill=MINT)
    d.line((149, 131, 123, 163), fill=MINT, width=5)
    d.line((152, 131, 175, 163), fill=MINT, width=5)
    d.text((224, 102), "WebRAG", font=face(67, bold=True), fill="#f4faf5")
    d.text((130, 226), "WEBSITE-GROUNDED INTELLIGENCE", font=face(28, bold=True), fill=MINT)
    text_lines(
        d,
        "Every answer,\nrooted in a source.",
        120,
        295,
        1350,
        face(130, serif=True, bold=True),
        "#f2faf5",
        145,
    )
    text_lines(
        d,
        "Ask naturally. Verify every claim against the website passage that supports it.",
        132,
        634,
        1310,
        face(39),
        "#bad1c9",
        56,
    )
    d.rounded_rectangle(
        (1500, 238, 2300, 752), radius=28, fill="#294942", outline="#79bb96", width=4
    )
    capture = Image.open(ROOT / "docs" / "media" / "04-answer-trail.png").convert("RGB")
    capture = ImageOps.fit(capture, (766, 480), method=Image.Resampling.LANCZOS)
    im.paste(capture, (1517, 255))
    d.text((1500, 780), "REAL APP CAPTURE  /  CITED ANSWER", font=face(22, bold=True), fill=MINT)
    d.text(
        (130, 1006),
        "A working agent, not a confident guess",
        font=face(60, serif=True, bold=True),
        fill=INK,
    )
    metrics = [
        ("40", "public documentation pages"),
        ("1,597", "indexed passages"),
        ("8", "top evidence passages per query"),
    ]
    for i, (number, label) in enumerate(metrics):
        x = 130 + i * 730
        d.rounded_rectangle(
            (x, 1130, x + 670, 1365), radius=18, fill="#e2eee5", outline="#c1d8c9", width=3
        )
        d.text((x + 35, 1161), number, font=face(78, serif=True, bold=True), fill=GREEN)
        d.text((x + 38, 1274), label, font=face(27), fill="#446960")
    d.text(
        (130, 1470), "ONE WEBSITE IN. TRACEABLE ANSWERS OUT.", font=face(32, bold=True), fill=GREEN
    )
    d.rounded_rectangle((130, 1540, 2270, 2150), radius=29, fill="#102f2d")
    d.text((190, 1588), "OFFLINE  ·  BUILD THE KNOWLEDGE BASE", font=face(25, bold=True), fill=MINT)
    top = [("Scoped crawl", 190), ("Clean + chunk", 690), ("Embed", 1190), ("Chroma + BM25", 1690)]
    for label, x in top:
        d.rounded_rectangle(
            (x, 1660, x + 430, 1790), radius=17, fill="#1d4740", outline="#48886e", width=2
        )
        d.text((x + 25, 1695), label, font=face(34, bold=True), fill="#f3faf3")
    for i in range(3):
        arrow(d, (top[i][1] + 435, 1725), (top[i + 1][1] - 18, 1725))
    d.line((2030, 1790, 2030, 1900), fill="#6bad92", width=7)
    d.polygon([(2030, 1900), (2016, 1878), (2044, 1878)], fill="#6bad92")
    d.text((190, 1862), "LIVE  ·  ASK, RETRIEVE, VERIFY, CITE", font=face(25, bold=True), fill=MINT)
    bottom = [
        ("React workspace", 190),
        ("FastAPI + LangGraph", 690),
        ("Evidence checks", 1190),
        ("Answer / refusal", 1690),
    ]
    for label, x in bottom:
        d.rounded_rectangle(
            (x, 1933, x + 430, 2063), radius=17, fill="#1d4740", outline="#48886e", width=2
        )
        d.text((x + 23, 1969), label, font=face(30, bold=True), fill="#f3faf3")
    for i in range(3):
        arrow(d, (bottom[i][1] + 435, 1998), (bottom[i + 1][1] - 18, 1998))
    d.text((130, 2240), "Proof at the point of use", font=face(60, serif=True, bold=True), fill=INK)
    features = [
        ("01", "Exact evidence", "Each answer keeps the original source URL and passage."),
        ("02", "Honest refusal", "Unsupported questions receive no fabricated citation."),
        ("03", "Inspectable cost", "Tokens, timings, and estimated API cost are visible."),
    ]
    for i, (number, title, description) in enumerate(features):
        x = 130 + i * 730
        d.text((x, 2364), number, font=face(28, bold=True), fill=GREEN)
        d.text((x, 2420), title, font=face(38, bold=True), fill=INK)
        text_lines(d, description, x, 2494, 640, face(28), "#4f6c65", 40)
    d.line((130, 2695, 2270, 2695), fill="#c6d8cf", width=3)
    d.text(
        (130, 2765),
        "REACT  ·  FASTAPI  ·  LANGGRAPH  ·  CHROMA  ·  OPENAI",
        font=face(30, bold=True),
        fill=GREEN,
    )
    d.text(
        (130, 2845),
        "Live product and technical evidence",
        font=face(45, serif=True, bold=True),
        fill=INK,
    )
    d.text((130, 2920), "webrag-assessment.vercel.app", font=face(35), fill=GREEN)
    im.paste(qr_image(), (1900, 2770))
    d.text((1900, 3140), "SCAN TO TRY", font=face(24, bold=True), fill=GREEN)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT, optimize=True)
    im.crop((0, 0, W, 940)).save(OUT.parent / "webrag-readme-cover.png", optimize=True)
    print(OUT)


if __name__ == "__main__":
    render()
