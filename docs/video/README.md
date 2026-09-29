# Recorded project walkthrough

[Play or download the walkthrough](WebRAG-Walkthrough.mp4) — **12 minutes 14 seconds**, H.264 video and AAC audio, 1920×1080. [Transcript](transcript.md).

![Opening slide](poster.png)

The video uses **disclosed synthetic narration**, real saved HTTP responses, and the final 38-question OpenAI evaluation, including 12 fresh independent holdout questions. It covers setup, architecture, crawl/chunk decisions, real embeddings, retrieval, grounding, queries, evaluation failures, costs, security, and deployment. It does not represent the candidate's voice or webcam presentation. A personal presentation can use [the prepared script](../VIDEO_SCRIPT.md).

[Verification metadata](../verification/video.json) records its source run, duration, SHA-256, codecs, and successful decoding at the beginning, middle, and end. Rendering sources are in `scripts/create_walkthrough.py`, `scripts/synthesize_walkthrough.ps1`, and `scripts/walkthrough_content.json`. Rendering uses optional Pillow and imageio-ffmpeg; these are not needed to run the RAG service.
