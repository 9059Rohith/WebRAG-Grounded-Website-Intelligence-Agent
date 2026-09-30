# Product media

These captures come from the working same-origin React/FastAPI application at a desktop viewport of 1536 × 960 or a mobile viewport of 390 × 844. They use real query responses from the Python documentation index. The screenshots contain no credentials. UI transitions were allowed to finish before final capture.

| File | What the reviewer can verify |
|---|---|
| [`01-workspace.png`](01-workspace.png) | Initial product identity, source library, question composer, suggestions, and empty evidence state |
| [`02-how-it-works.png`](02-how-it-works.png) | Built-in explanation and keyboard guidance |
| [`03-grounded-answer.png`](03-grounded-answer.png) | Natural-language question, answer, citations, and source rail |
| [`04-answer-trail.png`](04-answer-trail.png) | Search/evidence/decision inspector with measured stage timing |
| [`05-citation-focus.png`](05-citation-focus.png) | Citation selection focuses a supporting passage |
| [`06-honest-refusal.png`](06-honest-refusal.png) | Unsupported weather request refuses with zero cited passages |
| [`07-mobile-answer.png`](07-mobile-answer.png) | Responsive answer view |
| [`08-mobile-evidence.png`](08-mobile-evidence.png) | Source links and quotations remain available on mobile |
| [`webrag-readme-cover.png`](webrag-readme-cover.png) | README opening visual |
| [`webrag-project-poster.png`](webrag-project-poster.png) | Product identity, architecture, measured corpus scale, and scannable live-app QR code |

The [poster renderer](../../scripts/render_project_poster.py) takes a real application screenshot as input. The QR code was decoded back to the live deployment URL during validation. The architecture image in the README is generated separately by [`scripts/render_architecture_image.py`](../../scripts/render_architecture_image.py).
