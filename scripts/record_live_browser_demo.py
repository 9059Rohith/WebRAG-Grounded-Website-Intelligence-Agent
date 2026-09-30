"""Record a reproducible, real-browser tour of the deployed product and README.

The resulting WebM files contain only genuine browser pixels. Narration/captions are
assembled separately so each scripted chapter can be checked against real actions.
"""

from __future__ import annotations

import json
import time
import wave
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "live_demo"
APP = "https://webrag-assessment.vercel.app/"
REPO = "https://github.com/9059Rohith/WebRAG-Grounded-Website-Intelligence-Agent"
SCENES = json.loads((ROOT / "scripts" / "live_demo_content.json").read_text(encoding="utf-8"))


def speech_seconds(index: int) -> float:
    with wave.open(str(OUT / f"{index:02d}.wav")) as sound:
        return sound.getnframes() / sound.getframerate()


def pause_for_chapter(page: Page, started: float, index: int) -> None:
    minimum = speech_seconds(index) + 1.0
    remaining = minimum - (time.monotonic() - started)
    if remaining > 0:
        page.wait_for_timeout(round(remaining * 1000))


def show(page: Page, selector: str) -> None:
    """Scroll on GitHub after its client-side tree has settled."""
    for attempt in range(5):
        try:
            page.locator(selector).wait_for(timeout=15_000)
            page.evaluate(
                "s => { const node = document.querySelector(s); if (!node) throw new Error(s); node.scrollIntoView({block: 'center', behavior: 'instant'}); }",
                selector,
            )
            return
        except Exception:
            if attempt == 4:
                raise
            page.wait_for_timeout(1_500)


def show_readme_top(page: Page) -> None:
    show(page, "article h1")
    page.wait_for_timeout(2_000)


def ask(page: Page, question: str, *, answerable: bool) -> None:
    page.locator("#question").fill(question)
    page.get_by_role("button", name="Ask question").click()
    page.locator(".answer-section").locator(".grounding-trail").wait_for(timeout=120_000)
    page.locator(".answer-result").wait_for(timeout=10_000)
    result = page.locator(".answer-result")
    if ("not-answerable" in (result.get_attribute("class") or "")) == answerable:
        raise RuntimeError(f"Unexpected answerability for {question!r}")
    if answerable and page.locator(".evidence-item").count() == 0:
        raise RuntimeError(f"No website evidence for {question!r}")
    result.scroll_into_view_if_needed()


def app_action(page: Page, action: str) -> None:
    if action == "entry":
        page.locator(".library-stats").get_by_text("40 pages").wait_for(timeout=30_000)
        page.locator(".intro-title").scroll_into_view_if_needed()
    elif action == "how":
        page.get_by_role("button", name="How it works").click()
        page.locator(".how-dialog").wait_for()
        page.wait_for_timeout(7_000)
        page.get_by_role("button", name="Close how it works").click()
        page.locator(".suggestions").scroll_into_view_if_needed()
    elif action == "ask_simple":
        ask(page, "What does list.append do in Python?", answerable=True)
    elif action == "citation":
        page.get_by_role("button", name="Read supporting passage 1").first.click()
        page.locator(".evidence-item.selected").wait_for()
        page.wait_for_timeout(4_000)
        source = page.locator(".evidence-item .view-source").first
        source.scroll_into_view_if_needed()
        # Use the actual rendered source URL and a same-tab visit for the capture.
        href = source.get_attribute("href")
        if href and href.startswith("https://docs.python.org/"):
            page.goto(href, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(5_000)
            page.go_back(wait_until="domcontentloaded", timeout=30_000)
            page.locator(".library-stats").get_by_text("40 pages").wait_for(timeout=30_000)
            ask(page, "What does list.append do in Python?", answerable=True)
    elif action == "trail":
        page.locator(".grounding-trail summary").click()
        page.locator(".trail-body").scroll_into_view_if_needed()
        page.wait_for_timeout(4_000)
        page.locator(".answer-meta summary").click()
        page.wait_for_timeout(3_000)
        page.get_by_role("button", name="Copy answer with sources").click()
        page.get_by_role("button", name="Copied with sources").wait_for()
    elif action == "comparison":
        ask(page, "How do Python lists and tuples differ?", answerable=True)
        page.locator(".evidence-item").first.scroll_into_view_if_needed()
    elif action == "misleading":
        ask(page, "A for-loop else clause runs after break terminates the loop, correct?", answerable=True)
        if "not executed" not in page.locator(".answer-result").inner_text().lower():
            raise RuntimeError("False-premise correction is absent")
    elif action == "refusal":
        ask(page, "What is today's weather in Paris?", answerable=False)
        page.get_by_text("No supporting evidence").wait_for()
    elif action == "history":
        items = page.locator(".history-item")
        if items.count() < 3:
            raise RuntimeError("Real query history is missing")
        items.last.click()
        page.locator(".answer-result").wait_for()
        page.get_by_role("button", name="New conversation").click()
        page.locator(".answer-empty").wait_for()
        page.get_by_role("button", name="Motion on").click()
        page.get_by_role("button", name="Motion off").wait_for()
        page.get_by_role("button", name="Motion off").click()
    elif action == "mobile":
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(2_000)
        ask(page, "What does list.append do in Python?", answerable=True)
        page.locator(".evidence-toggle").click()
        page.locator(".evidence-item").first.scroll_into_view_if_needed()
        page.wait_for_timeout(5_000)
        page.get_by_role("button", name="Open library").click()
        page.locator(".library-rail.is-open").wait_for()
        page.wait_for_timeout(5_000)
        page.locator(".library-rail .mobile-close").click()
    elif action == "app_close":
        page.set_viewport_size({"width": 1536, "height": 960})
        page.wait_for_timeout(2_000)
        page.locator(".answer-result").scroll_into_view_if_needed()
        page.locator(".grounding-trail summary").click()
    else:
        raise ValueError(action)


def readme_action(page: Page, action: str) -> None:
    if action == "readme_cover":
        show_readme_top(page)
        page.wait_for_timeout(11_000)
        show(page, "#user-content-watch-the-live-browser-demonstration")
        page.wait_for_timeout(9_000)
        show(page, "#user-content-what-is-working")
    elif action == "readme_poster":
        href = page.get_by_role("link", name="See the full project poster").first.get_attribute("href")
        page.goto(urljoin(REPO, href or ""), wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(8_000)
        page.goto(REPO, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2_000)
        show(page, "#user-content-see-the-product")
        page.wait_for_timeout(8_000)
    elif action == "readme_architecture":
        show(page, "#user-content-architecture-at-a-glance")
        page.wait_for_timeout(9_000)
        href = page.get_by_role("link", name="Detailed architecture and graph").first.get_attribute("href")
        page.goto(urljoin(REPO, href or ""), wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(6_000)
        page.goto(REPO, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2_000)
    elif action == "readme_results":
        show(page, "#user-content-what-is-working")
        page.wait_for_timeout(8_000)
        show(page, "#user-content-architecture-at-a-glance")
        page.wait_for_timeout(8_000)
        show(page, "#user-content-stack-and-repository-map")
        page.wait_for_timeout(8_000)
        href = page.get_by_role("link", name="Review measured costs").first.get_attribute("href")
        page.goto(urljoin(REPO, href or ""), wait_until="domcontentloaded", timeout=60_000)
        show(page, "#user-content-observed-provider-usage-extrapolation--scenario-not-invoice")
        page.evaluate("window.scrollBy(0, 170)")
        page.wait_for_timeout(6_000)
        page.goto(REPO, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2_000)
    elif action == "close":
        show_readme_top(page)
    else:
        raise ValueError(action)


def record(segment: str, start: int, end: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    timings: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1536, "height": 960},
            device_scale_factor=1,
            record_video_dir=str(OUT),
            record_video_size={"width": 1536, "height": 960},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        video_begin = time.monotonic()
        page.on("pageerror", lambda error: errors.append(str(error)))
        destination = APP if segment == "app" else REPO
        page.goto(destination, wait_until="domcontentloaded", timeout=60_000)
        (page.locator(".intro-title") if segment == "app" else page.locator("article").first).wait_for(timeout=60_000)
        if segment == "app":
            page.locator(".library-stats").get_by_text("40 pages").wait_for(timeout=60_000)
        page.wait_for_timeout(2_000)
        origin = time.monotonic()
        for index in range(start, end):
            scene = SCENES[index]
            began = time.monotonic()
            print(f"{segment}: {index + 1:02d} {scene['action']}", flush=True)
            if segment == "app":
                app_action(page, scene["action"])
            else:
                readme_action(page, scene["action"])
            pause_for_chapter(page, began, index)
            timings.append({"index": index, "action": scene["action"], "start": round(began - origin, 3), "end": round(time.monotonic() - origin, 3)})
        video = page.video
        context.close()
        video.save_as(str(OUT / f"{segment}-raw.webm"))
        browser.close()
    if errors:
        raise RuntimeError("Browser JavaScript errors: " + "; ".join(errors))
    (OUT / f"{segment}-timeline.json").write_text(json.dumps({"offset_seconds": round(origin - video_begin, 3), "scenes": timings}, indent=2), encoding="utf-8")
    print(f"{segment} complete: {timings[-1]['end']:.1f}s", flush=True)


if __name__ == "__main__":
    record("app", 0, 11)
    record("readme", 11, 16)
