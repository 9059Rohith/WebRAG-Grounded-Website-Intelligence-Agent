# WebRAG live browser walkthrough transcript

The candidate's webcam is damaged. The narration is disclosed synthetic speech. All application and repository visuals are genuine browser captures.

## 01. Open the live product

Hello, I’m Rohith. My webcam is damaged, so this screen recording uses disclosed synthetic narration. Every product interaction you see runs against the public deployment; the answers are not prefilled demo data. This is WebRAG. It answers questions from a bounded snapshot of the official Python documentation and places the supporting website passages beside the answer. The first screen explains the value immediately: every answer is rooted in a source. The left rail identifies the indexed library and its forty pages and fifteen hundred ninety-seven passages. The center invites a natural-language question, and the right side is reserved for exact website evidence. I’ll use the product first, then open the GitHub README and technical proof.

## 02. Orient the reviewer

Before asking, the How it works panel makes the workflow explicit: ask naturally, read a grounded answer, and follow it back to the original source. It also explains that recent questions are stored on this device and that Control or Command plus Enter submits. The three suggested questions offer useful starting paths without placing fake answers on the screen. The interface is intentionally a workspace: the question, answer, and evidence stay in one view so a reviewer can compare them. The source-graph motion is restrained and can be switched off, including by a reduced-motion device preference. Now I’ll take the main path from a real input to a real answer.

## 03. Ask the first real question

I’m typing a straightforward question: what does list dot append do in Python? Watch the processing state rather than assuming the answer is hard-coded. The browser sends the question to the same-origin FastAPI endpoint. LangGraph retrieves relevant chunks from the saved documentation index, combines semantic and lexical search, checks whether the evidence is strong enough, and returns either a supported answer or a refusal. Here the result explains that append adds a new item to the end of a list. Citation numbers are attached to the statements; the rail simultaneously shows their original Python documentation pages and exact excerpts. The useful outcome is not simply a sentence about a method. It is a sentence that can be checked against the website the user selected.

## 04. Follow the answer back to the site

I select a citation in the answer. The matching passage receives focus in the evidence rail, so the connection between claim and source is visible. Each source card includes the original page title, a clickable docs dot python dot org URL, and a quotation restored from the stored chunk. I can follow the View source link to the official documentation, then return to the workspace. These URLs are not composed by the language model; the server takes them from index metadata attached during ingestion. The quote text must occur in the retrieved chunk. That establishes provenance, although a real quote alone cannot prove every inference made from it. This is why the agent also runs a separate support-and-completeness check before finalizing a synthesized answer.

## 05. Inspect the result and its cost

The new answer trail gives a reviewer a compact account of what happened. It shows how many distinct website pages were retrieved, how many exact passages support this answer, whether the agent answered or refused, and the measured time spent in retrieval, generation, and verification. The Usage disclosure shows token count and estimated new API cost. I can copy the answer together with its titles, source URLs, and excerpts for an audit note. That is more useful than copying a bare paragraph with citation numbers that have lost their meaning. The timing and cost values are real response data from the backend, but they are estimates and diagnostics, not a billing invoice or a proof of semantic correctness.

## 06. Ask across more than one passage

Now I use a comparison question: how do Python lists and tuples differ? This tests more than a single matching keyword. The retriever gathers semantic and B M twenty-five candidates, fuses the ranks, and reserves evidence for comparison facets before selecting up to eight context passages. The answer should distinguish mutable lists from immutable tuples and cite the documentation that supports those points. The source cards make it possible to inspect whether both halves are represented. The application shows a loading state while the API works, then replaces it with the returned answer. If the needed evidence had not been in the indexed snapshot, the correct behavior would have been to refuse rather than fill the gap from model memory.

## 07. Correct a misleading premise

A grounded assistant also needs to challenge a false premise. Here I ask whether a for-loop else clause runs after break terminates the loop. The website supports a correction: the else clause is not executed when the loop exits through break, and it runs when the loop completes without that break. The answer cites the Python tutorial instead of echoing the incorrect premise or refusing the entire question. This case matters because early evaluation found some answerable questions were refused too conservatively. The visible result comes from the repaired deployed agent. Later in the README I’ll show both the original independent baseline and the follow-up regression, with a clear distinction between fresh and previously inspected questions.

## 08. See an honest refusal

Now I ask for today’s weather in Paris. The Python documentation snapshot cannot establish a live weather report. The agent responds that it could not find enough information on the selected website, and the evidence rail explicitly says there is no supporting evidence. Notice the zero supporting passages. This is an intentional product outcome, not an error screen. The same rule applies to private facts, off-site knowledge, or instructions asking the model to ignore the grounding contract. The benchmark recorded ten of ten unknown-question refusals in the inspected follow-up set, while still leaving one false refusal on a question that was actually answerable. Both sides of that tradeoff are documented.

## 09. Review the rest of the workspace

The library rail now shows the questions I actually asked. Selecting a recent question restores its answer within this browser session; only question text persists on this device. New conversation clears the current view and focuses the composer. I can toggle interface motion without changing the retrieval or grounding behavior. Copy and usage controls remain attached to each answer, and the How it works panel is available from navigation. These sound like small details, but they matter during review: the app gives feedback for loading, success, unsupported questions, and request errors rather than leaving a blank surface. On mobile, the same evidence remains reachable.

## 10. Keep the evidence on a phone

Here is the same public app at a narrow phone width. The navigation becomes compact, the library opens as a drawer, and the question and answer remain readable without horizontal scrolling. After submitting the list question, the supporting passages move below the answer as an expandable evidence section. I open that section to show that the original page links and exact quotations have not disappeared for the sake of responsive design. Selecting an inline citation can also open and focus the corresponding mobile evidence. The phone layout preserves the same grounding semantics as desktop. I’ll return to the desktop view for the final product result, then move to the repository.

## 11. The product outcome

The working flow is now complete: a website snapshot becomes a searchable knowledge base, a user asks naturally, and the agent either provides a cited answer or clearly refuses. The answer trail makes the path and cost inspectable. That is the product outcome. The remaining minutes are in GitHub, where the poster, architecture, code, raw evaluation, setup, and limitations make these claims reviewable rather than merely presentable.

## 12. Open the GitHub product story

This is the actual GitHub README. It opens with the same WebRAG identity as the application and poster, and links directly to the live product, browser walkthrough, architecture, and cost analysis. The product screenshots below are real captures of the working interface. The feature table distinguishes verified capabilities from the one hosted CI issue: GitHub Actions is configured, but GitHub reports the owner account billing lock before any job starts. The README does not pretend that a local test pass is a green hosted workflow. It also labels the follow-up benchmark as an inspected regression, not a new independent holdout.

## 13. Inspect the poster and screenshots

The full project poster is designed as a concise technical product map. It states the problem and value proposition, shows a real cited-answer capture, names the forty-page and fifteen-hundred-ninety-seven-passage corpus, and traces both offline ingestion and live answering. Its Q R code resolves to the deployed app. The media gallery includes the empty workspace, guidance dialog, grounded answer, answer trail, focused citation, honest refusal, and mobile answer and evidence states. Captions say exactly what each image proves. There are no invented integrations or fabricated dashboard numbers. The same interaction story appears in the app, screenshots, poster, and this video.

## 14. Read the real architecture

The architecture image separates owner-run ingestion from the online query path. A scoped, robots-aware crawl cleans and chunks Python documentation. Real embeddings go into persistent Chroma; the same chunks build B M twenty-five lexical search. On a question, React calls FastAPI, and LangGraph controls retrieval, relevance gating, structured synthesis, server-owned quote restoration, verification, bounded retry, and final answer or refusal. The bundled index is copied to writable temporary storage on a Vercel cold start. The credential stays server-side. This diagram was generated from a reproducible source script and pushed before the recorded walkthrough. The detailed architecture document contains the exact graph, source-metadata path, and deployment limits.

## 15. Check evaluation, cost, and setup

The repository includes frozen question sets, raw response records, citation and retrieval diagnostics, and explicit failures. The original twelve-question independent holdout had four of four correct unknown refusals but two false refusals among eight answerables. The later, inspected thirty-eight-question regression reached thirty-seven of thirty-eight answerability decisions and sixty-one of sixty-one exact quote-provenance checks, with one false refusal. Quote matching is not a human semantic audit. The current cost report uses observed provider usage: about zero point zero zero one five five nine dollars per query in this small mix, with scenarios for one hundred, one thousand, and ten thousand questions. Setup instructions explain the private environment file, CLI ingestion, API, tests, and deployment. Those details make the project reproducible and make its limits visible.

## 16. Close on the evidence

The source code, live app, poster, screenshots, architecture, evaluation, and costs are linked from this README. A reviewer can replay the browser flow, inspect any cited Python documentation page, and read the raw records behind the measured numbers. My webcam is damaged, so this is a screen-based presentation with clearly labeled synthetic narration and English captions. Thank you for reviewing WebRAG.
