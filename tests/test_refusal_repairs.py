"""Regression evidence selection and fail-closed correction behavior, entirely offline."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from rag_agent.config import Settings
from rag_agent.graph import Agent, sentence_candidates
from rag_agent.grounding import REFUSAL, evidence_occurs
from rag_agent.retriever import Retriever, question_facets
from rag_agent.schemas import Chunk, Claim, Draft, Hit, Usage


def chunk(identifier: str, text: str, index: int = 0, heading: str = "Syntax") -> Chunk:
    return Chunk(
        chunk_id=identifier,
        source_url="https://example.test/"
        + ("strings" if identifier == "literal" else "templates"),
        title="Technical guide",
        heading_path=heading,
        text=text,
        embedded_text=text,
        token_count=30,
        content_hash=identifier,
        chunk_index=index,
    )


class OfflineEmbeddings:
    def embed_with_usage(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        return [[float(i)] for i in range(len(texts))], Usage(provider="openai")


def retrieval_fixture(
    tmp_path: Path, predecessor_heading: str = "Syntax", predecessor_url: str | None = None
) -> Retriever:
    literal = chunk("literal", "Formatted string literals prefix the string with f or F.")
    previous = chunk(
        "definition",
        "Template strings use dollar signs to introduce named fields.",
        3,
        heading=predecessor_heading,
    )
    if predecessor_url:
        previous.source_url = predecessor_url
    fragment = chunk("fragment", "not part of the placeholder, such as a noun suffix.", 4)
    fillers = [
        chunk(
            str(i),
            "Template substitution expressions placeholders use strings to substitute expressions.",
            10 + i,
        )
        for i in range(8)
    ]
    chunks = [literal, previous, fragment, *fillers]
    store = SimpleNamespace(
        chunks=chunks,
        by_id={c.chunk_id: c for c in chunks},
        search=lambda vector, k: [(fragment, 0.8), *[(c, 0.7) for c in fillers]][:k],
    )
    settings = Settings(_env_file=None, data_dir=tmp_path, final_top_k=6, retrieve_k_bm25=3)
    return Retriever(settings, store, OfflineEmbeddings())  # type: ignore[arg-type]


def test_comparison_keeps_lexical_evidence_for_each_facet(tmp_path: Path) -> None:
    # Whole-query fusion can drown out the exact first subject with second-subject hits.
    result = retrieval_fixture(tmp_path).retrieve(
        "Compare formatted string literals and Template substitution expressions or placeholders."
    )
    assert "literal" in {hit.chunk.chunk_id for hit in result.hits}
    assert len(result.hits) == 6


def test_fragment_retrieval_restores_same_section_predecessor(tmp_path: Path) -> None:
    # A quote starting halfway through a sentence cannot explain the placeholder rule.
    result = retrieval_fixture(tmp_path).retrieve(
        "Compare formatted string literals and Template substitution expressions or placeholders."
    )
    assert "definition" in {hit.chunk.chunk_id for hit in result.hits}
    assert result.relevant
    assert len(result.hits) <= 6


@pytest.mark.parametrize("heading,url", [("Other section", None), ("Syntax", "https://other.test")])
def test_fragment_context_cannot_cross_source_or_section(
    tmp_path: Path, heading: str, url: str | None
) -> None:
    retriever = retrieval_fixture(tmp_path, predecessor_heading=heading, predecessor_url=url)
    result = retriever.retrieve(
        "Compare formatted string literals and Template substitution expressions or placeholders."
    )
    assert "fragment" in {hit.chunk.chunk_id for hit in result.hits}
    assert "definition" not in {hit.chunk.chunk_id for hit in result.hits}


def test_retry_preserves_comparison_facets() -> None:
    agent = Agent.__new__(Agent)
    expanded = agent._expand({"question": "Compare formatted literals and Template placeholders."})
    assert question_facets(expanded["normalized_question"]) == [
        "formatted literals",
        "placeholders template",
    ]


def test_comparison_quote_table_preserves_literal_delimiters() -> None:
    sources = [
        chunk(
            "literal", "Formatted string literals prefix strings with f or F and use {expression}."
        ),
        chunk(
            "template",
            "Template placeholders use $identifier or ${identifier} for named substitutions.",
        ),
    ]
    hits = [Hit(chunk=c, score=0.8, dense_score=0.8) for c in sources]
    quotes = [text for _, text in sentence_candidates(hits)]
    assert sources[0].text in quotes and sources[1].text in quotes
    assert all(evidence_occurs(text, hit.chunk.text) for hit, text in sentence_candidates(hits))


def test_quote_table_includes_complete_contiguous_short_rule() -> None:
    rule = "${identifier} is equivalent to $identifier. Braces are required when identifier characters follow the placeholder."
    hit = Hit(chunk=chunk("rule", rule), score=0.8, dense_score=0.8)
    assert rule in [text for _, text in sentence_candidates([hit])]


def test_quote_table_never_stitches_separate_source_paragraphs() -> None:
    source = "The first field uses braces.\n\nUnrelated details intervene here.\n\nThe second field uses dollar signs."
    hit = Hit(chunk=chunk("rule", source), score=0.8, dense_score=0.8)
    assert all(evidence_occurs(text, source) for _, text in sentence_candidates([hit]))
    assert "The first field uses braces. The second field uses dollar signs." not in [
        text for _, text in sentence_candidates([hit])
    ]


class CorrectionLLM:
    def __init__(self, correction: bool, supported: bool, explanation: str = "") -> None:
        self.correction, self.supported = correction, supported
        self.explanation = explanation

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        def invoke(messages: list[tuple[str, str]]) -> dict[str, Any]:
            if schema is Draft:
                parsed = Draft(
                    answerable=True,
                    claims=[
                        Claim(
                            text="No. The trailing clause runs only when the loop finishes without an interruption."
                            if self.correction
                            else "Yes. The trailing clause runs after an interruption.",
                            chunk_id="correction",
                            evidence="q001",
                        )
                    ],
                )
            else:
                parsed = schema(supported=self.supported, explanation=self.explanation)
            return {
                "parsed": parsed,
                "raw": SimpleNamespace(
                    usage_metadata={"input_tokens": 10, "output_tokens": 10}, additional_kwargs={}
                ),
            }

        return SimpleNamespace(invoke=invoke)


@pytest.mark.parametrize("correction,supported", [(True, True), (False, False)])
def test_grounded_negative_answer_still_requires_semantic_entailment(
    tmp_path: Path, correction: bool, supported: bool
) -> None:
    source = chunk(
        "correction",
        "The trailing clause runs only when the loop finishes without an interruption.",
    )
    store = SimpleNamespace(
        info={"index_version": "fixture"},
        chunks=[source],
        by_id={source.chunk_id: source},
        search=lambda vector, k: [(source, 0.8)],
    )
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        provider="openai",
        openai_api_key=SecretStr("offline-fixture"),
        verify_with_llm=True,
    )
    agent = Agent(settings, store, OfflineEmbeddings())  # type: ignore[arg-type]
    agent._llm = CorrectionLLM(correction, supported)
    answer = agent.ask("The trailing clause runs after an interruption, correct?", use_cache=False)
    assert answer.answerable is supported
    if supported:
        assert answer.answer.startswith("No.") and answer.sources[0].evidence == source.text
    else:
        assert answer.answer == REFUSAL and answer.sources == []


@pytest.mark.parametrize(
    "explanation", ["", "Every claim is fully supported; the answer is complete."]
)
def test_negative_verdict_fails_closed_despite_explanation(
    tmp_path: Path, explanation: str
) -> None:
    source = chunk(
        "correction",
        "The trailing clause runs only when the loop finishes without an interruption.",
    )
    store = SimpleNamespace(
        info={"index_version": "fixture"},
        chunks=[source],
        by_id={source.chunk_id: source},
        search=lambda vector, k: [(source, 0.8)],
    )
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        provider="openai",
        openai_api_key=SecretStr("offline-fixture"),
        verify_with_llm=True,
    )
    agent = Agent(settings, store, OfflineEmbeddings())  # type: ignore[arg-type]
    agent._llm = CorrectionLLM(True, False, explanation)
    answer = agent.ask("Does the trailing clause run after an interruption?", use_cache=False)
    assert not answer.answerable
    assert answer.answer == REFUSAL and answer.sources == []
