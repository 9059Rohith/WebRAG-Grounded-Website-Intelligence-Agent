"""Hybrid retrieval with reciprocal rank fusion and source diversification."""

from __future__ import annotations

import re
import time
from collections import defaultdict

from rank_bm25 import BM25Okapi

from rag_agent.config import Settings
from rag_agent.embeddings import EmbeddingProvider
from rag_agent.schemas import Hit, RetrievalResult, Usage
from rag_agent.vectorstore import VectorStore

STOPWORDS = set(
    "a an the is are be to of in on and or for with by do does how what when where why can could would should tell me about it its i using use from according website python please explain compare difference between versus vs".split()
)
STOPWORDS.update(
    "documentation tutorial claim claims say says state states site selected given does called gives facility one more after last made among stopping point whether changed creation creates create manages attach".split()
)
STOPWORDS.update(
    "define handle help work works get ways different separate final can cannot".split()
)


def stem_terms(text: str) -> set[str]:
    """A light plural normalizer keeps identifiers intact and needs no model."""
    return {
        word[:-1] if word.endswith("s") and len(word) > 3 and not word.endswith("ss") else word
        for word in content_terms(text)
    }


def question_facets(question: str) -> list[str]:
    """Split explicit conjunctions, carrying a shared predicate to parallel subjects."""
    parts = [part.strip(" ,?.") for part in re.split(r"\band\b", question, flags=re.IGNORECASE)]
    if len(parts) < 2 or len(parts) > 3:
        return []
    predicate = re.search(r"\b(?:can|are|is|could|should)\b.+", parts[-1], flags=re.IGNORECASE)
    if predicate and not re.search(
        r"\b(?:can|are|is|could|should)\b", parts[0], flags=re.IGNORECASE
    ):
        parts[0] += " " + predicate.group()
    return [part for part in parts if stem_terms(part)]


def tokenize(text: str) -> list[str]:
    """Retain identifiers whole and split snake/camel case for technical questions."""
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*|\d+", text)
    out = []
    for token in tokens:
        lower = token.lower()
        out.append(lower)
        parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", token).replace("_", " ").lower().split()
        if parts != [lower]:
            out.extend(parts)
    return out


def content_terms(text: str) -> set[str]:
    """Remove question framing words without dropping technical identifiers."""
    return set(tokenize(text)) - STOPWORDS


class Retriever:
    """Reuse the warm lexical index across requests."""

    def __init__(
        self, settings: Settings, store: VectorStore, embeddings: EmbeddingProvider
    ) -> None:
        self.settings, self.store, self.embeddings = settings, store, embeddings
        self.tokens = [tokenize(c.embedded_text) for c in store.chunks]
        self.bm25 = BM25Okapi(self.tokens) if self.tokens else None
        self.section_positions = {
            (c.source_url, c.heading_path, c.chunk_index): c.chunk_id for c in store.chunks
        }
        self.last_usage = Usage(provider=settings.provider)

    def retrieve_with_usage(self, question: str) -> tuple[RetrievalResult, Usage]:
        """Gate on semantic similarity rather than incomparable raw BM25 scores."""
        timings: dict[str, float] = {}
        start = time.perf_counter()
        facets = question_facets(question)
        vectors, usage = self.embeddings.embed_with_usage([question] + facets)
        timings["embedding"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        dense = self.store.search(vectors[0], self.settings.retrieve_k_dense)
        facet_dense = [
            self.store.search(vector, self.settings.retrieve_k_dense) for vector in vectors[1:]
        ]
        timings["dense"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        scores = self.bm25.get_scores(tokenize(question)) if self.bm25 is not None else []
        lexical = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)[
            : self.settings.retrieve_k_bm25
        ]
        lexical = [i for i in lexical if float(scores[i]) > 0]
        facet_lexical: list[list[int]] = []
        if self.bm25 is not None:
            for facet in facets:
                facet_scores = self.bm25.get_scores(tokenize(facet))
                indices = sorted(
                    range(len(facet_scores)), key=lambda i: float(facet_scores[i]), reverse=True
                )[: self.settings.retrieve_k_bm25]
                facet_lexical.append([i for i in indices if float(facet_scores[i]) > 0])
        timings["bm25"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        fused: dict[str, float] = defaultdict(float)
        dense_scores = {c.chunk_id: score for c, score in dense}
        best = max(dense_scores.values(), default=0.0)
        if self.settings.retrieval_mode != "bm25":
            for rank, (chunk, _) in enumerate(dense, 1):
                fused[chunk.chunk_id] += 1 / (60 + rank)
            for results in facet_dense:
                for rank, (chunk, score) in enumerate(results, 1):
                    fused[chunk.chunk_id] += 0.7 / (60 + rank)
                    dense_scores[chunk.chunk_id] = max(dense_scores.get(chunk.chunk_id, 0), score)
        if self.settings.retrieval_mode != "dense":
            for rank, index in enumerate(lexical, 1):
                fused[self.store.chunks[index].chunk_id] += 1 / (60 + rank)
            for lexical_results in facet_lexical:
                for rank, index in enumerate(lexical_results, 1):
                    fused[self.store.chunks[index].chunk_id] += 0.7 / (60 + rank)
        ranked = sorted(fused, key=lambda cid: fused[cid], reverse=True)
        selected: list[str] = []
        source_counts: dict[str, int] = defaultdict(int)
        # Explicit comparisons need each concept represented. RRF can otherwise
        # crowd out one facet with many high-ranking chunks about the other.
        if self.settings.retrieval_mode != "dense":
            for lexical_results in facet_lexical:
                if lexical_results and len(selected) < self.settings.final_top_k:
                    chunk = self.store.chunks[lexical_results[0]]
                    if chunk.chunk_id not in selected:
                        selected.append(chunk.chunk_id)
                        source_counts[chunk.source_url] += 1
                        ranked.remove(chunk.chunk_id)
        if self.settings.retrieval_mode != "bm25":
            for results in facet_dense:
                if results and len(selected) < self.settings.final_top_k:
                    chunk, score = results[0]
                    if score >= self.settings.min_relevance and chunk.chunk_id not in selected:
                        selected.append(chunk.chunk_id)
                        source_counts[chunk.source_url] += 1
                        if chunk.chunk_id in ranked:
                            ranked.remove(chunk.chunk_id)
        # Token-window chunks can start in the middle of a rule. Restore the
        # predecessor from that exact source section, with its own citation ID.
        # This supplies context, not an inferred semantic similarity score.
        for cid in list(selected):
            chunk = self.store.by_id[cid]
            if not chunk.text.lstrip()[:1].islower():
                continue
            previous = self.section_positions.get(
                (chunk.source_url, chunk.heading_path, chunk.chunk_index - 1)
            )
            if previous and previous not in selected and len(selected) < self.settings.final_top_k:
                selected.append(previous)
                source_counts[chunk.source_url] += 1
                if previous in ranked:
                    ranked.remove(previous)
        while ranked and len(selected) < self.settings.final_top_k:
            # A greedy source-diversity penalty approximates MMR without an
            # extra embedding fetch; expose it honestly as source diversification.
            cid = max(
                ranked,
                key=lambda x: (
                    fused[x]
                    * (
                        self.settings.mmr_lambda
                        if source_counts[self.store.by_id[x].source_url] and self.settings.diversify
                        else 1.0
                    )
                ),
            )
            ranked.remove(cid)
            selected.append(cid)
            source_counts[self.store.by_id[cid].source_url] += 1
        hits = [
            Hit(
                chunk=self.store.by_id[cid],
                score=fused[cid],
                dense_score=dense_scores.get(cid, 0.0),
            )
            for cid in selected
        ]
        timings["fusion"] = (time.perf_counter() - start) * 1000
        timings["retrieval"] = sum(timings.values())
        self.last_usage = usage
        return RetrievalResult(
            hits=hits,
            relevant=bool(hits) and best >= self.settings.min_relevance,
            best_score=best,
            timings_ms=timings,
        ), usage

    def retrieve(self, question: str) -> RetrievalResult:
        """Return a timed top-k evidence bundle."""
        return self.retrieve_with_usage(question)[0]
