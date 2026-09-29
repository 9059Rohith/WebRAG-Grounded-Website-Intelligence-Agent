# WebRAG interface

Accepted concept: `C:/Users/BhaviChasvi/.codex/generated_images/01a0ed2c-7938-7483-8462-27cb0d362feb/exec-aa3251c0-cb70-4846-bf6c-12cf1c2ad948.png`.

The interface is a working research workspace: library/history rail, central question and answer, and an adjacent evidence rail. The content uses API responses; the example answer, evidence, history, and numbers in the concept are never seeded into the product.

## Research and decisions

- [Geist](https://vercel.com/geist/introduction) provides a useful developer-tool reference for restrained typography, accessible contrasts, simple controls, and consistent icon treatment. The final visual language follows the accepted concept: a pale mint surface, charcoal text, fine borders, Fraunces headings, and DM Sans controls.
- [He and Liu, Seeing to Think?](https://arxiv.org/abs/2601.14611) studied four citation presentations with 372 participants. Their aligned sidebar supported critical engagement under denser citations. This motivates the evidence rail and claim-level source selection; it does not establish a universal best layout or a confidence score.
- [W3C animation guidance](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) recommends disabling nonessential interaction motion. Text enters with a brief opacity/translation reveal; the graph has small pointer parallax. OS reduced motion and the saved Motion toggle disable both.

## Design system

- Background `#f5f8f5`; text `#10272c`; muted `#607b80`; border `#d8e2df`; accent `#1b6751`; selected library `#e1eee4`.
- Desktop: 68 px header, 270 px library, flexible center, 448 px evidence rail. Fine dividing rules establish the container system. The composer is the primary bordered container.
- Fraunces Variable medium editorial headline; DM Sans Variable for answers and all controls. Both fonts are bundled locally.
- Lucide outline icons use 1.5–2 px strokes and sizes appropriate to their function. Brand/source graph are faithful code-native vector elements.
- At tablet sizes evidence moves below the answer; at phone sizes library becomes a drawer and evidence becomes an expandable section.

## Functional behavior

Same-origin `/v1/stats` supplies index counts; `/v1/ask` supplies answers, passages, timings, cache and usage. Suggested questions fill the composer. Numeric citations focus and highlight their evidence. Copy confirms success. Recent questions alone persist on the device; their answer can be reopened during the current session. New conversation cancels pending work and clears the current view. Errors and unsupported questions remain readable and recoverable. Ctrl/Command + Enter submits.

## Intentional concept adaptations

The initial screen has an empty answer, empty evidence rail, and no fabricated history. The website label and counts are populated only after the API returns. Runtime answer/evidence and usage can differ from the concept's sample. The graph uses accessible lightweight SVG geometry because it is a functional website-source diagram. Mobile interactions extend the same design system. The How it works dialog and usage disclosure provide necessary behavior for the concept's controls.

## Fidelity and QA

The final TypeScript check and production build pass (`npm run build`). The final bundle is approximately 244 kB JavaScript (77 kB gzip) plus 21 kB CSS (5.5 kB gzip). Fonts load locally.

The in-app browser was used throughout: a visible tab is unsupported for a subagent, so validation used a background tab. No Playwright fallback was used. First pass used Vite at `http://127.0.0.1:5173`; final API/CSP checks used the built application through the same-origin Python server at `http://127.0.0.1:8007`.

The final accepted concept and the latest desktop and mobile screenshots were inspected with `view_image` in the same comparison pass. Desktop was checked at the concept's native 1536 × 1024 viewport. Responsive checks also covered 390 × 844, 320 × 720, and 768 × 1024. All checked widths had no horizontal document overflow; viewport overrides were reset afterward.

| Comparison | Concept evidence | Render evidence / resolution |
|---|---|---|
| Layout | 68 px header, narrow library, central composer, adjacent evidence | 68 px measured header; shared rail rules; correct desktop columns; evidence moves below the answer on phones/tablets |
| Typography | Large two-line editorial title; readable sans UI | Local Fraunces/DM Sans; deliberate heading/control/quote scales; no browser-default controls; phone line breaks checked |
| Palette | Pale mint/off-white, charcoal, muted green, fine borders | Explicit locked tokens; matching light green source treatment and dark green primary action |
| Composer | Spacious textarea, source note, right-aligned Ask question | Same framing and control order; suggested questions populate editable input; mobile header crowding repaired |
| Evidence | Numbered titles, meaningful URLs, quoted passages, View source | Exact real API evidence; safe URLs; numeric claim buttons select/focus/highlight their passage; phone disclosure opens on citation selection |
| Motion | Quiet source graph and editorial text | Brief text reveals, bounded pointer transform parallax, manual switch persists; switch yields computed animation `none` |
| Container model | Open central workspace and two rails, one framed composer | No card grid or nested dashboard wrappers; real quote borders match the concept |

Above-the-fold copy was checked against the concept: WebRAG, Workspace, How it works, GitHub, Motion on/off, Your library, Python documentation, Recent questions, New conversation, Every answer/rooted in a source, supporting sentence, Website sources only, Ask question, all three suggestion labels, Answer/Copy, Website evidence/View source are preserved. Runtime data, a blank-question placeholder, and explicit empty states are the intentional adaptations listed above. The mobile header omits the redundant Workspace tab to avoid overflow; the main workspace remains the active surface.

Core interaction path verified: load real 40-page/1,597-passage library → fill question / Ctrl+Enter → truthful elapsed loading → real append answer with two passages → select source → verify selected class and focused article → open View source URLs → Copy / Copied with matching actual clipboard content → new conversation → reopen the same-session answer from recent questions. Usage disclosure showed actual API tokens and estimated cost. Reload preserved questions and motion preference but did not seed stored answers.

Other verified states: all-whitespace submit disabled; 500-character input bound; actual API validation failure displays a recoverable error and Try again; out-of-corpus weather question returns the actual refusal, zero passages, and no fabricated sources. How it works opens/closes; mobile library opens, traps focus, and closes with Escape; closed drawer is excluded from accessibility/tab order. Console checks were clean for the normal API/CSP interaction path. The OS reduced-motion branch is present in both CSS and the media-query listener; the browser capability does not offer OS media emulation, so that branch was audited rather than externally emulated.

The interface was faithfully verified against the accepted design. No material layout or functional mismatches remain in the checked views. The content differences are actual API data and the explicit adaptations above.

Screenshot evidence (outside the repository):

- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-desktop-empty.png`
- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-desktop-answer.png`
- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-mobile-empty.png`
- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-mobile-evidence.png`

## Public deployment verification

The deployed [WebRAG workspace](https://webrag-assessment.vercel.app/) was verified in the in-app browser at 1536 × 1024 and 390 × 844. Its script is the final `index-CR5NOpXb.js`. Title, meaningful rendered content, actual 40-page/1,597-passage stats, same-origin API and local fonts all worked, with no framework overlay or relevant console warnings/errors.

The public keyboard-submitted append question returned an actual answer and two exact passages in 9.3 seconds. Claim/source selection, focused highlighted evidence, correct clipboard answer content, and the phone evidence disclosure worked. The saved Motion off preference survived reload and computed heading animation remained `none`. Both public widths had no horizontal overflow. Temporary viewport overrides were reset.

The concept and final public desktop/phone/evidence screenshots were inspected together with `view_image`. The five-plus comparison points above remain satisfied by the public build, and no material visual mismatches remain beyond the explicitly listed content/responsive adaptations.

Public screenshot evidence:

- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-public-desktop.png`
- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-public-mobile.png`
- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-public-mobile-empty.png`
- `C:/Users/BhaviChasvi/.codex/visualizations/2026/09/29/01a0ed2c-7938-7483-8462-27cb0d362feb/webrag-public-mobile-evidence.png`

Root public motion check: text animation was `text-in`; a real pointer move changed graph CSS offsets from `(1.3125px, 0.9667px)` to `(-0.5531px, 0px)`. Motion off removed the offsets and changed text animation to `none`. Motion was restored on after the check. The public false-premise correction was verified with exact website quotations in 5.4 seconds.
