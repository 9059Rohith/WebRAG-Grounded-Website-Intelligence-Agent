"""Explicit, bounded LangGraph retrieve/generate/verify/refuse workflow."""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from rag_agent.cache import QueryCache
from rag_agent.config import Settings
from rag_agent.cost import token_count, usage_cost
from rag_agent.embeddings import EmbeddingProvider
from rag_agent.errors import LLMError
from rag_agent.grounding import (
    INJECTION_PATTERN,
    REFUSAL,
    canonicalize_draft_evidence,
    evidence_occurs,
    normalize_evidence,
    resolve_quote_references,
    verify_draft,
)
from rag_agent.prompts import build_reference_prompt, build_verification_prompt
from rag_agent.retriever import Retriever, content_terms, question_facets, stem_terms, tokenize
from rag_agent.schemas import Answer, Claim, Draft, Hit, RetrievalResult, Usage
from rag_agent.vectorstore import VectorStore

MIXED_PROVENANCE = "mixed_api_and_estimated"


class State(TypedDict, total=False):
    question: str
    normalized_question: str
    retrieval: RetrievalResult
    usage: Usage
    draft: Draft
    verified: bool
    attempt: int
    answer: Answer
    started: float
    blocked: bool
    timings: dict[str, float]


def validate_question(question: str, max_chars: int) -> str:
    """Reject oversized input before stripping controls; normalize cache keys."""
    if len(question) > max_chars:
        raise ValueError(f"Question must be at most {max_chars} characters")
    question = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", question).split())
    if not question:
        raise ValueError("Question must not be empty")
    return question


def sentence_candidates(hits: list[Hit]) -> list[tuple[Hit, str]]:
    """Keep source sentences verbatim and include concise adjacent definition lines."""
    candidates: list[tuple[Hit, str]] = []
    for hit in hits:
        text = re.sub(r"```[\s\S]*?```", " ", hit.chunk.text)
        paragraphs = text.split("\n\n")
        for paragraph in paragraphs:
            quote = normalize_evidence(paragraph)
            if (
                len(re.split(r"(?<=[.!?])\s+", quote)) > 1
                and 4 <= len(quote.split()) <= 60
                and ">>>" not in quote
                and not INJECTION_PATTERN.search(quote)
                and evidence_occurs(quote, hit.chunk.text)
            ):
                candidates.append((hit, quote))
        contextual_definitions: dict[str, str] = {}
        for previous, following in zip(paragraphs, paragraphs[1:], strict=False):
            label = " ".join(previous.split())
            definition = re.split(r"(?<=[.!?])\s+", following.strip())[0]
            combined = " ".join((label + " " + definition).split())
            if (
                1 <= len(label.split()) <= 12
                and not label.endswith((".", "!", "?"))
                and 4 <= len(combined.split()) <= 60
                and not INJECTION_PATTERN.search(combined)
            ):
                candidates.append((hit, combined))
                contextual_definitions[" ".join(definition.split())] = combined
        sentences = re.split(r"(?<=[.!?])\s+|\n", text)
        for sentence in sentences:
            sentence = " ".join(sentence.split()).strip()
            sentence = contextual_definitions.get(sentence, sentence)
            if 4 <= len(sentence.split()) <= 60 and not INJECTION_PATTERN.search(sentence):
                candidates.append((hit, sentence))
    return candidates


def extract_draft(
    question: str,
    hits: list[Hit],
    semantic_scores: dict[str, float] | None = None,
    facet_scores: list[dict[str, float]] | None = None,
) -> Draft:
    """Local fallback quotes evidence; it does not claim abstractive LLM reasoning."""
    terms = stem_terms(question)
    # An extractive engine cannot infer missing entities, future numbers or
    # preferences. Require topic coverage in evidence, not just a nearby page.
    evidence_terms = stem_terms(" ".join(h.chunk.text for h in hits))
    if terms and len(terms & evidence_terms) / len(terms) < 0.6:
        return Draft(answerable=False)
    requested_qualifiers = set(
        re.findall(
            r"\b(?:best|better|fastest|favorite|favourite|recommend|future|current|predict|guarantee|always|never)\b",
            question.casefold(),
        )
    )
    asks_mutability = bool(
        re.search(
            r"\b(?:mutable|immutable|changed|change|modify|modification)\b", question.casefold()
        )
    )
    candidates: list[tuple[float, Hit, str]] = []
    for hit, sentence in sentence_candidates(hits):
        st = stem_terms(sentence)
        overlap = len(terms & st)
        if not overlap and semantic_scores is None:
            continue
        if semantic_scores is not None:
            semantic = semantic_scores.get(hit.chunk.chunk_id + "\0" + sentence, 0)
            if semantic < 0.38:
                continue
            score = semantic * 0.8 + overlap / max(len(terms), 1) * 0.2
        else:
            score = overlap / max(len(terms), 1) + hit.dense_score * 0.3
        # Preferences, predictions and universal claims need explicit evidence.
        # A nearby factual paragraph cannot answer that stronger question.
        if requested_qualifiers and not requested_qualifiers.intersection(set(tokenize(sentence))):
            continue
        if asks_mutability and not re.search(
            r"\b(?:immutable|mutable|change|changed|assign|modify|replace|modification)\b",
            sentence.casefold(),
        ):
            continue
        # Definitions and explicit corrections are more useful than crosslinks.
        if re.search(r"\b(is|are|returns?|immutable|mutable|raises?)\b", sentence):
            score += 0.05
        candidates.append((score, hit, sentence))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if not candidates:
        return Draft(answerable=False)
    # Require a meaningful fraction of question content, and semantic evidence.
    top_score, top_hit, top_sentence = candidates[0]
    if top_hit.dense_score < 0.30 or top_score < 0.23:
        return Draft(answerable=False)
    selected: list[tuple[float, Hit, str]] = []
    seen_sentences: set[str] = set()
    seen_urls: set[str] = set()
    # Compound questions need complementary evidence, not four variations of
    # the same definition. Pick a relevant sentence for each explicit facet.
    for facet in facet_scores or []:
        candidate = max(candidates, key=lambda c: facet.get(c[1].chunk.chunk_id + "\0" + c[2], 0))
        _, hit, sentence = candidate
        if (
            facet.get(hit.chunk.chunk_id + "\0" + sentence, 0) >= 0.4
            and sentence not in seen_sentences
        ):
            selected.append(candidate)
            seen_sentences.add(sentence)
            seen_urls.add(hit.chunk.source_url)
    for candidate in candidates:
        score, hit, sentence = candidate
        if score < top_score * 0.80 or sentence in seen_sentences:
            continue
        if (
            sum(
                previous_hit.chunk.source_url == hit.chunk.source_url
                for _, previous_hit, _ in selected
            )
            >= 2
        ):
            continue
        selected.append(candidate)
        seen_sentences.add(sentence)
        seen_urls.add(hit.chunk.source_url)
        if len(selected) >= 4:
            break
    return Draft(
        answerable=True,
        claims=[
            Claim(text=sentence, chunk_id=hit.chunk.chunk_id, evidence=sentence)
            for _, hit, sentence in selected
        ],
    )


class Agent:
    """Compile once and hold the warm store, clients, lexical index and query cache."""

    def __init__(
        self,
        settings: Settings,
        store: VectorStore | None = None,
        embeddings: EmbeddingProvider | None = None,
        generator: Callable[[str, list[Hit]], Draft] | None = None,
    ) -> None:
        self.settings = settings
        self.store = store or VectorStore(settings)
        self.embeddings = embeddings or EmbeddingProvider(settings)
        self.retriever = Retriever(settings, self.store, self.embeddings)
        self.cache = QueryCache(
            settings.cache_ttl_s,
            settings.cache_max_items,
            version=str(self.store.info.get("index_version", "")),
        )
        self._generator = generator
        self._llm: Any = None
        self._telemetry_lock = threading.Lock()
        builder = StateGraph(State)
        for name, fn in [
            ("validate_input", self._validate),
            ("retrieve", self._retrieve),
            ("generate", self._generate),
            ("verify", self._verify),
            ("expand_query", self._expand),
            ("refuse", self._refuse),
            ("finalize", self._finalize),
        ]:
            builder.add_node(name, fn)
        builder.add_edge(START, "validate_input")
        builder.add_conditional_edges(
            "validate_input",
            lambda s: "refuse" if s["blocked"] else "retrieve",
            {"refuse": "refuse", "retrieve": "retrieve"},
        )
        builder.add_conditional_edges(
            "retrieve",
            lambda s: "generate" if s["retrieval"].relevant else "refuse",
            {"generate": "generate", "refuse": "refuse"},
        )
        builder.add_edge("generate", "verify")
        builder.add_conditional_edges(
            "verify",
            lambda s: (
                "finalize" if s["verified"] else ("expand_query" if s["attempt"] == 0 else "refuse")
            ),
            {"finalize": "finalize", "expand_query": "expand_query", "refuse": "refuse"},
        )
        builder.add_edge("expand_query", "retrieve")
        builder.add_edge("refuse", "finalize")
        builder.add_edge("finalize", END)
        self.graph = builder.compile()

    def _validate(self, state: State) -> State:
        question = validate_question(state["question"], self.settings.max_question_chars)
        return {
            "normalized_question": question,
            "blocked": bool(INJECTION_PATTERN.search(question)),
            "attempt": 0,
            "usage": Usage(provider=self.settings.provider),
            "timings": {},
        }

    def _retrieve(self, state: State) -> State:
        retrieval, usage = self.retriever.retrieve_with_usage(state["normalized_question"])
        total = state["usage"].model_copy(deep=True)
        total.embedding_tokens += usage.embedding_tokens
        timings = dict(state["timings"])
        for name, value in retrieval.timings_ms.items():
            timings[name] = timings.get(name, 0) + value
        return {
            "retrieval": retrieval,
            "usage": total,
            "timings": timings,
        }

    def _client(self) -> Any:
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.settings.llm_model,
                api_key=self.settings.openai_api_key,
                temperature=0,
                max_tokens=self.settings.llm_max_output_tokens,
                timeout=self.settings.llm_timeout_s,
                max_retries=self.settings.llm_max_retries,
            )
        return self._llm

    def _generate(self, state: State) -> State:
        start = time.perf_counter()
        hits = state["retrieval"].hits
        usage = state["usage"].model_copy(deep=True)
        if self._generator is not None:
            draft = self._generator(state["question"], hits)
        elif self.settings.provider == "local":
            candidates = sentence_candidates(hits)
            if candidates:
                import numpy as np

                facets = question_facets(state["question"])
                vectors, sentence_usage = self.embeddings.embed_with_usage(
                    [state["question"]] + facets + [sentence for _, sentence in candidates]
                )
                usage.embedding_tokens += sentence_usage.embedding_tokens
                query_vector = np.asarray(vectors[0])
                scores = {
                    hit.chunk.chunk_id + "\0" + sentence: float(np.dot(query_vector, vector))
                    for (hit, sentence), vector in zip(
                        candidates, vectors[1 + len(facets) :], strict=True
                    )
                }
                facet_scores = [
                    {
                        hit.chunk.chunk_id + "\0" + sentence: float(
                            np.dot(np.asarray(facet_vector), vector)
                        )
                        for (hit, sentence), vector in zip(
                            candidates, vectors[1 + len(facets) :], strict=True
                        )
                    }
                    for facet_vector in vectors[1 : 1 + len(facets)]
                ]
                draft = extract_draft(state["question"], hits, scores, facet_scores)
            else:
                draft = Draft(answerable=False)
        else:
            quotes = {
                f"q{index:03d}": (hit.chunk.chunk_id, sentence)
                for index, (hit, sentence) in enumerate(sentence_candidates(hits), 1)
                if evidence_occurs(sentence, hit.chunk.text)
            }
            system, prompt = build_reference_prompt(state["question"], hits, quotes)
            try:
                result = (
                    self._client()
                    .with_structured_output(Draft, include_raw=True)
                    .invoke([("system", system), ("human", prompt)])
                )
                parsed = result.get("parsed")
                raw = result["raw"]
                metadata = raw.usage_metadata or {}
                native_refusal = bool(getattr(raw, "additional_kwargs", {}).get("refusal"))
                draft = parsed if isinstance(parsed, Draft) else Draft(answerable=False)
                previous_chat_tokens = usage.input_tokens + usage.output_tokens
                previous_source = usage.token_source
                usage.input_tokens += int(
                    metadata.get("input_tokens", token_count(system + prompt))
                )
                usage.output_tokens += int(
                    metadata.get("output_tokens", token_count(draft.model_dump_json()))
                )
                reported = "api_reported" if metadata else "estimated_tiktoken"
                usage.token_source = (
                    MIXED_PROVENANCE
                    if previous_chat_tokens and previous_source != reported
                    else reported
                )
                if not isinstance(parsed, Draft) and not native_refusal:
                    raise LLMError("Provider returned invalid structured output")
                draft = resolve_quote_references(draft, quotes)
                draft = canonicalize_draft_evidence(draft, hits)
                # Omit unusable proposed claims before the complete-answer
                # semantic check. Never expose a claim with invalid provenance.
                if self.settings.verify_with_llm and draft.answerable:
                    retained = [
                        claim
                        for claim in draft.claims
                        if verify_draft(Draft(answerable=True, claims=[claim]), hits)[0]
                    ]
                    draft = Draft(answerable=bool(retained), claims=retained)
            except LLMError:
                raise
            except Exception as exc:
                raise LLMError("Answer provider unavailable") from exc
        timings = dict(state["timings"])
        timings["generation"] = timings.get("generation", 0) + (time.perf_counter() - start) * 1000
        return {"draft": draft, "usage": usage, "timings": timings}

    def _verify(self, state: State) -> State:
        start = time.perf_counter()
        valid, _ = verify_draft(state["draft"], state["retrieval"].hits)
        usage = state["usage"].model_copy(deep=True)
        if (
            valid
            and self.settings.provider == "openai"
            and self.settings.verify_with_llm
            and self._generator is None
        ):
            system, prompt = build_verification_prompt(
                state["question"], state["retrieval"].hits, state["draft"]
            )
            from pydantic import BaseModel, Field

            class Check(BaseModel):
                explanation: str = Field(
                    max_length=300,
                    description="A concise evidence-assessment summary in 1-2 sentences, at most "
                    "300 characters: state whether each claim follows from its own exact quote "
                    "and the combined claims answer every requested part. Identify any gap.",
                )
                supported: bool = Field(
                    description="True only when all proposed answer claims are entailed by their "
                    "own exact quoted evidence and together completely answer the question. "
                    "A supported negative answer or false-premise correction has supported=true."
                )

            try:
                result = (
                    self._client()
                    .with_structured_output(Check, include_raw=True)
                    .invoke(
                        [
                            ("system", system),
                            ("human", prompt),
                        ]
                    )
                )
                check = result.get("parsed")
                valid = isinstance(check, Check) and check.supported
                metadata = result["raw"].usage_metadata or {}
                usage.input_tokens += int(
                    metadata.get(
                        "input_tokens",
                        token_count(system + prompt),
                    )
                )
                usage.output_tokens += (
                    int(metadata.get("output_tokens", token_count(check.model_dump_json())))
                    if isinstance(check, Check)
                    else int(metadata.get("output_tokens", 0))
                )
                reported = "api_reported" if metadata else "estimated_tiktoken"
                if usage.token_source != reported:
                    usage.token_source = MIXED_PROVENANCE
            except Exception as exc:
                raise LLMError("Grounding verification provider unavailable") from exc
        timings = dict(state["timings"])
        timings["verification"] = (
            timings.get("verification", 0) + (time.perf_counter() - start) * 1000
        )
        return {"verified": valid, "usage": usage, "timings": timings}

    def _expand(self, state: State) -> State:
        # One deterministic expansion avoids another paid call and exposes the
        # bounded retry in the graph. Do not inject facts or conversation history.
        facets = question_facets(state["question"])
        keywords = (
            " and ".join(" ".join(sorted(content_terms(facet))) for facet in facets)
            if facets
            else " ".join(sorted(content_terms(state["question"])))
        )
        return {"normalized_question": keywords or state["question"], "attempt": 1}

    def _refuse(self, state: State) -> State:
        return {"draft": Draft(answerable=False), "verified": False}

    def _finalize(self, state: State) -> State:
        retrieval = state.get("retrieval", RetrievalResult())
        valid, citations = verify_draft(state["draft"], retrieval.hits)
        valid = valid and state.get("verified", False)
        text = (
            "\n\n".join(f"{claim.text} [{i}]" for i, claim in enumerate(state["draft"].claims, 1))
            if valid
            else REFUSAL
        )
        usage = state["usage"].model_copy(deep=True)
        usage.estimated_usd = usage_cost(
            usage.embedding_tokens, usage.input_tokens, usage.output_tokens, self.settings.provider
        )
        timings = dict(state["timings"])
        timings["total"] = (time.perf_counter() - state["started"]) * 1000
        answer = Answer(
            answer=text,
            answerable=valid,
            sources=citations if valid else [],
            usage=usage,
            timings_ms=timings,
            request_id=uuid.uuid4().hex,
            mode="extractive" if self.settings.provider == "local" else "llm",
            retrieved_urls=[h.chunk.source_url for h in retrieval.hits],
            retrieval_score=retrieval.best_score,
            attempts=state["attempt"] + 1,
        )
        return {"answer": answer}

    def ask(self, question: str, use_cache: bool = True) -> Answer:
        """Answer with only verified evidence; surface operational errors distinctly."""
        normalized = validate_question(question, self.settings.max_question_chars)
        # Technical identifiers and literals are case-sensitive.
        key = normalized
        if use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                cached.request_id = uuid.uuid4().hex
                return cached
        state = self.graph.invoke({"question": normalized, "started": time.perf_counter()})
        answer = Answer.model_validate(state["answer"])
        if use_cache:
            self.cache.put(key, answer)
        return answer

    def stats(self) -> dict[str, Any]:
        """Describe the loaded snapshot without exposing secrets or source text."""
        return {
            **self.store.info,
            "provider": self.settings.provider,
            "mode": "extractive" if self.settings.provider == "local" else "llm",
            "cache_items": len(self.cache),
        }
