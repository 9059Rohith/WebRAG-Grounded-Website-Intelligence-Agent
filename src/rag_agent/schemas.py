"""Shared typed contracts for ingestion, retrieval and answering."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Section(BaseModel):
    heading_path: str
    text: str


class Page(BaseModel):
    url: str
    title: str
    text: str
    sections: list[Section]
    content_hash: str
    crawled_at: str = ""
    lang: str = "en"


class Chunk(BaseModel):
    chunk_id: str
    source_url: str
    title: str
    heading_path: str
    text: str
    embedded_text: str
    token_count: int
    content_hash: str
    chunk_index: int
    crawled_at: str = ""


class Hit(BaseModel):
    chunk: Chunk
    score: float
    dense_score: float = 0.0


class RetrievalResult(BaseModel):
    hits: list[Hit] = Field(default_factory=list)
    relevant: bool = False
    best_score: float = 0.0
    timings_ms: dict[str, float] = Field(default_factory=dict)


class Citation(BaseModel):
    url: str
    title: str
    evidence: str
    chunk_id: str


class Claim(BaseModel):
    text: str
    chunk_id: str
    evidence: str


class Draft(BaseModel):
    answerable: bool = Field(
        description="Whether the supplied website evidence supports a complete answer. "
        "This is NOT the yes/no answer to the question. A supported negative answer "
        "or correction of a false premise has answerable=true."
    )
    claims: list[Claim] = Field(
        default_factory=list,
        description="Source-supported claims answering the question, including negative "
        "answers and corrections. Empty only when the website cannot answer.",
    )


class Usage(BaseModel):
    embedding_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: float = 0.0
    provider: str = "local"
    token_source: str = "estimated_tiktoken"


class Answer(BaseModel):
    answer: str
    answerable: bool
    sources: list[Citation] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    cached: bool = False
    request_id: str = ""
    mode: str = "extractive"
    retrieved_urls: list[str] = Field(default_factory=list)
    retrieval_score: float = 0.0
    attempts: int = 0
