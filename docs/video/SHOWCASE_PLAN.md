# Current application walkthrough — editorial plan

The candidate's webcam is damaged. This video is a screen presentation with disclosed **synthetic neural narration**, actual captures from the public application, a published architecture image, and saved evaluation/cost records. It does not impersonate the candidate's voice or claim that illustrations are live screen recordings.

The assessment asks for 10–15 minutes, so the narration is paced for that range. The structure follows [Vidyard's demo guidance](https://www.vidyard.com/blog/demo-videos/) to establish the problem, demonstrate the workflow, and show a concrete outcome without constant screen movement. Selectable English captions, an `.srt` file, and a full transcript follow [W3C media accessibility guidance](https://www.w3.org/WAI/media/av/). The script names important visual content in the narration.

| Chapter | Focus | Visual evidence |
|---|---|---|
| 01 | Assessment goal and immediate product result | Public desktop answer capture |
| 02 | Full architecture, beginning within two minutes | Newly generated and already-published `architecture-showcase.png` |
| 03 | Grounded answer and adjacent evidence | Public desktop answer capture |
| 04–06 | Crawl, chunk, embed, hybrid retrieval, LangGraph | Labeled explanatory flow graphics derived from source code and reports |
| 07 | Exact citation provenance | Crop of public source-evidence rail |
| 08 | Misleading-question correction | Public corrected-answer capture |
| 09 | Clear refusal when support is absent | Public refusal capture with zero supporting passages |
| 10 | History, How it works, keyboard, copying, usage, motion | Public How it works dialog capture and verified UI behavior |
| 11 | Responsive answer and source inspection | Public mobile answer and evidence captures |
| 12 | Baseline and follow-up evaluation, including failures | Recorded evaluation numbers with the regression caveat |
| 13 | Observed usage and scaled cost scenarios | `COST_ANALYSIS.md` values |
| 14–15 | Deployment, limitations, where to inspect | Repository and deployed app links |

The source images are in `docs/video/assets/`. The renderer is `scripts/create_showcase_video.py`, the exact spoken text and chapter metadata are in `scripts/showcase_content.json`, and the voice generator is `scripts/synthesize_showcase.py`. The architecture image's own source is `scripts/render_architecture_image.py`. The captioned video should be checked for 10–15-minute duration, video/audio/subtitle streams, architecture visibility within 120 seconds, non-silent audio, successful decoding across the runtime, and a matching copy in Downloads.

The walkthrough deliberately distinguishes the original fresh independent 12-question baseline from the later 38-question **inspected** regression. Exact quote matching checks provenance, not semantic entailment. GitHub Actions currently cannot run jobs because the owner's account is billing-locked; local checks and the live deployment are separate evidence.
