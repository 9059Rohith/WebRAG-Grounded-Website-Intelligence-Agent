# Live browser walkthrough — recording plan

This is a continuous presentation of the **public Vercel product first**, followed by the **published GitHub repository**. All screen pixels in the recording come from Playwright-controlled Chromium visiting those live URLs. The voice is clearly disclosed synthetic narration because the candidate's webcam is damaged. The separate script `scripts/live_demo_content.json` contains the exact narration; `scripts/record_live_browser_demo.py` contains the browser actions, and `scripts/finish_live_browser_demo.py` adds audio, captions, and transcript.

The assessment requests a 10–15 minute walkthrough, while the owner requested an approximately 7–8 minute live product demo. The combined recording satisfies both by devoting the first ~7:45 to the actual app and the remaining ~3:40 to the README. A separate technical video remains available for deeper architecture explanation.

| Sequence | Product/browser action | Evidence the reviewer sees |
|---|---|---|
| 01 | Open public app and indexed library | Value proposition, 40 pages, 1,597 passages, primary question input |
| 02 | Open and close How it works | Grounding promise, source navigation, local history, keyboard shortcut |
| 03 | Ask `What does list.append do in Python?` | Real request, processing state, answer, citations, exact evidence |
| 04 | Select citation 1 and visit its original URL | Highlighted stored passage and the official Python website |
| 05 | Open answer trail and Usage; copy answer with sources | Retrieval/verification timings, decision, measured token/cost estimate, clipboard action |
| 06 | Ask `How do Python lists and tuples differ?` | Multi-passage comparison grounded in docs |
| 07 | Ask false-premise loop-else question | Corrects the premise with citations |
| 08 | Ask today's Paris weather | Honest refusal with no supporting passages |
| 09 | Restore recent question, start new conversation, toggle motion | Session behavior, clear/reset, restrained motion control |
| 10 | Resize to phone and ask again; open evidence and library drawer | Responsive answer and original evidence links |
| 11 | Return to desktop | Final product outcome before repository transition |
| 12 | Open the actual GitHub README | Cover, primary links, tested capability matrix |
| 13 | Open full poster, then real product screenshots | Consistent visual identity and captured UI proof |
| 14 | Show architecture image and detail page | Offline crawl/index and online LangGraph query path |
| 15 | Review evaluation, cost, stack, setup | Measured results, caveats, 100/1,000/10,000 scenario costs |
| 16 | Return to README cover | Source, live product, video, and technical evidence links |

The narration differentiates the original fresh 12-question holdout from the later inspected regression. Exact quote matching establishes provenance only; it does not certify semantic correctness. Hosted GitHub CI remains blocked before jobs by the owner's GitHub billing state and is disclosed in the README. The demo never presents fabricated answers, credentials, or an invented human voice.

## Media acceptance checks

- App chapter is 7–8 minutes; full walkthrough is 10–15 minutes.
- Recorded URLs are the public Vercel app and the published GitHub repository.
- Video decodes from start to end; audio is audible; selectable English captions, SRT, and transcript exist.
- Opening app, grounded answer, exact source, refusal, mobile evidence, README poster, architecture, and cost pages are legible in representative frames.
- No browser JavaScript error or failed required action occurred during recording.
- Final repository and Downloads MP4 copies have the same SHA-256 digest.
