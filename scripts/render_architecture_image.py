"""Render the precise, presentation-ready architecture diagram in Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "docs" / "architecture-showcase.png"
W, H = 2400, 1350

BG = "#0b171c"
PANEL = "#12272d"
CARD = "#173239"
STROKE = "#2e5053"
WHITE = "#effbf4"
MUTED = "#a4beb8"
MINT = "#85e0ba"
TEAL = "#57b9bd"
CORAL = "#ffb493"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if bold
        else ("C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    size: int,
    fill: str,
    bold: bool = False,
) -> None:
    draw.text(xy, value, font=font(size, bold), fill=fill)


def pill(
    draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], label: str, fill: str, color: str
) -> None:
    draw.rounded_rectangle(xy, radius=26, fill=fill)
    bounds = draw.textbbox((0, 0), label, font=font(23, True))
    y = xy[1] + (xy[3] - xy[1] - (bounds[3] - bounds[1])) // 2 - 3
    text(draw, (xy[0] + 22, y), label, 23, color, True)


def card(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    number: str,
    heading: str,
    lines: tuple[str, ...],
    accent: str,
) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=25, fill=CARD, outline=STROKE, width=2)
    draw.rounded_rectangle((x1 + 25, y1 + 25, x1 + 86, y1 + 69), radius=16, fill="#24434a")
    text(draw, (x1 + 40, y1 + 30), number, 22, accent, True)
    text(draw, (x1 + 26, y1 + 75), heading, 31, WHITE, True)
    for idx, line in enumerate(lines):
        text(draw, (x1 + 27, y1 + 120 + idx * 28), line, 22, MUTED)


def arrow(draw: ImageDraw.ImageDraw, x1: int, x2: int, y: int, color: str) -> None:
    draw.line((x1, y, x2 - 14, y), fill=color, width=5)
    draw.polygon([(x2, y), (x2 - 18, y - 10), (x2 - 18, y + 10)], fill=color)


def main() -> None:
    image = Image.new("RGB", (W, H), BG)
    background = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = ImageDraw.Draw(background)
    glow.ellipse((-240, -310, 980, 650), fill=(48, 127, 110, 90))
    glow.ellipse((1550, 580, 2670, 1610), fill=(35, 109, 133, 75))
    image = Image.alpha_composite(
        image.convert("RGBA"), background.filter(ImageFilter.GaussianBlur(145))
    )
    draw = ImageDraw.Draw(image)

    # Subtle construction grid makes the two independent paths legible.
    for x in range(0, W, 120):
        draw.line((x, 0, x, H), fill="#15282b", width=1)
    for y in range(0, H, 120):
        draw.line((0, y, W, y), fill="#15282b", width=1)

    draw.rounded_rectangle((88, 64, 154, 76), radius=6, fill=MINT)
    text(draw, (88, 101), "WEBRAG  /  SYSTEM ARCHITECTURE", 29, MINT, True)
    text(draw, (88, 154), "Every answer, rooted in a source.", 66, WHITE, True)
    text(
        draw,
        (90, 241),
        "A traceable path from public documentation to a cited answer — or an honest refusal.",
        27,
        MUTED,
    )
    pill(draw, (1920, 83, 2306, 140), "LIVE ON VERCEL", "#1d4541", MINT)

    # Owner-operated indexing is deliberately separate from the live request path.
    draw.rounded_rectangle((78, 327, 2322, 650), radius=30, fill=PANEL, outline="#2b4a48", width=2)
    pill(draw, (110, 348, 425, 401), "01  OFFLINE INGESTION", "#245344", MINT)
    text(draw, (1680, 356), "40 pages  /  1,597 passages", 27, WHITE, True)
    top_y = 438
    top_x = (113, 671, 1229, 1787)
    top = (
        ("01", "Scoped crawl", ("robots.txt + relevant links", "SSRF-safe URL boundaries")),
        ("02", "Clean + chunk", ("main text + headings", "source URL on every passage")),
        ("03", "Embed content", ("text-embedding-3-small", "stable index identity")),
        ("04", "Searchable store", ("persistent Chroma vectors", "BM25 lexical companion")),
    )
    for idx, (num, title, lines) in enumerate(top):
        card(draw, (top_x[idx], top_y, top_x[idx] + 500, 619), num, title, lines, MINT)
        if idx < 3:
            arrow(draw, top_x[idx] + 505, top_x[idx + 1] - 7, 527, MINT)

    # The snapshot is built ahead of time and copied to writable storage on Vercel cold starts.
    draw.line((2040, 619, 2040, 693, 1048, 693, 1048, 728), fill=TEAL, width=4, joint="curve")
    draw.rounded_rectangle((1390, 667, 1935, 717), radius=22, fill="#1c3d43")
    text(draw, (1416, 676), "Bundled index copied to /tmp at cold start", 22, TEAL, True)

    draw.rounded_rectangle((78, 728, 2322, 1064), radius=30, fill=PANEL, outline="#2b4a48", width=2)
    pill(draw, (110, 750, 429, 803), "02  LIVE QUERY PATH", "#24515a", TEAL)
    text(draw, (1780, 757), "server-side provider calls", 25, MUTED)
    bottom_y = 837
    bottom_x = (111, 480, 849, 1218, 1587, 1956)
    bottom = (
        ("01", "React UI", ("ask + history", "source inspection")),
        ("02", "FastAPI", ("validate + cache", "LangGraph control")),
        ("03", "Hybrid search", ("Chroma + BM25", "RRF, top-eight")),
        ("04", "Synthesize", ("structured claims", "quote identifiers")),
        ("05", "Verify", ("exact evidence", "semantic check")),
        ("06", "Respond", ("cited answer", "or clear refusal")),
    )
    for idx, (num, title, lines) in enumerate(bottom):
        card(
            draw,
            (bottom_x[idx], bottom_y, bottom_x[idx] + 331, 1032),
            num,
            title,
            lines,
            TEAL if idx < 3 else CORAL,
        )
        if idx < 5:
            arrow(draw, bottom_x[idx] + 335, bottom_x[idx + 1] - 8, 931, TEAL if idx < 3 else CORAL)
    draw.line((1048, 728, 1048, 824), fill=TEAL, width=4)
    draw.polygon([(1048, 839), (1037, 818), (1059, 818)], fill=TEAL)

    # Trust contract: model text never becomes the authority for URLs or quotations.
    draw.rounded_rectangle(
        (78, 1103, 2322, 1268), radius=30, fill="#173136", outline="#2b4a48", width=2
    )
    labels = (
        ("EVIDENCE", "Exact quotes + server-owned source URLs"),
        ("CONTROL", "Bounded retry; refuse when support is missing"),
        ("ACCOUNTING", "Tokens, timings, and estimated API cost"),
    )
    for idx, (label, detail) in enumerate(labels):
        x = 112 + idx * 745
        if idx:
            draw.line((x - 32, 1128, x - 32, 1244), fill=STROKE, width=2)
        text(draw, (x, 1130), label, 22, MINT if idx == 0 else TEAL, True)
        text(draw, (x, 1174), detail, 25, WHITE)
    text(
        draw,
        (88, 1303),
        "Source: docs.python.org/3/tutorial  •  OpenAI calls stay server-side  •  Local embedding/excerpt mode is an optional fallback",
        22,
        MUTED,
    )
    image.convert("RGB").save(DESTINATION, optimize=True)
    print(DESTINATION)


if __name__ == "__main__":
    main()
