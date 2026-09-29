"""Validated configuration; secrets never appear in serialized responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class _ProgrammaticFlagSource(PydanticBaseSettingsSource):
    """Keep the loopback test exception out of every non-init settings source."""

    def __init__(
        self, settings_cls: type[BaseSettings], source: PydanticBaseSettingsSource
    ) -> None:
        super().__init__(settings_cls)
        self.source = source

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self.source.get_field_value(field, field_name)

    def __call__(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.source().items()
            if key.casefold() != "test_allow_localhost"
        }


# Official model pages, checked 2026-09-29. USD per million tokens.
PRICING_AS_OF = "2026-09-29"
PRICING_SOURCE = "https://developers.openai.com/api/docs/models/gpt-4o-mini"
PRICING = {"input": 0.15, "output": 0.60, "embedding": 0.02}


class Settings(BaseSettings):
    """Load a safe local default or explicitly selected paid-provider mode."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    provider: Literal["local", "openai"] = "local"
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    data_dir: Path = Path("data")
    start_url: str = "https://docs.python.org/3/tutorial/index.html"
    allowed_prefix: str = "https://docs.python.org/3/"
    max_pages: int = Field(default=40, ge=1, le=500)
    max_depth: int = Field(default=3, ge=0, le=10)
    crawl_delay_s: float = Field(default=0.5, ge=0)
    crawl_concurrency: int = Field(default=4, ge=1, le=10)
    request_timeout_s: float = Field(default=20, gt=0)
    max_response_bytes: int = Field(default=2_000_000, ge=1024)
    user_agent: str = "WebRAGAssessment/1.0 (+https://github.com/9059Rohith/WebRAG-Grounded-Website-Intelligence-Agent)"
    chunk_tokens: int = Field(default=200, ge=60, le=900)
    chunk_overlap_tokens: int = Field(default=30, ge=0)
    min_chunk_tokens: int = Field(default=20, ge=1)
    retrieve_k_dense: int = Field(default=12, ge=1)
    retrieve_k_bm25: int = Field(default=12, ge=1)
    final_top_k: int = Field(default=8, ge=1, le=20)
    min_relevance: float = Field(default=0.25, ge=0, le=1)
    mmr_lambda: float = Field(default=0.7, ge=0, le=1)
    retrieval_mode: Literal["hybrid", "dense", "bm25"] = "hybrid"
    diversify: bool = True
    llm_max_output_tokens: int = Field(default=900, ge=50, le=2000)
    llm_timeout_s: float = Field(default=30, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    verify_with_llm: bool = True
    max_question_chars: int = Field(default=500, ge=1)
    rate_limit_per_min: int = Field(default=30, ge=1)
    cache_ttl_s: float = Field(default=3600, ge=0)
    cache_max_items: int = Field(default=512, ge=1)
    api_token: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    max_concurrent_queries: int = Field(default=2, ge=1, le=16)
    api_timeout_s: float = Field(default=90, gt=0)
    port: int = Field(default=8000, ge=1, le=65535)
    # Programmatic only: fixture tests may allow localhost; never a public CLI flag.
    test_allow_localhost: bool = Field(default=False, exclude=True)

    @field_validator("openai_api_key", "api_token", mode="before")
    @classmethod
    def empty_secret_is_none(cls, value: Any) -> Any:
        """An untouched environment template must keep optional auth disabled."""
        return None if isinstance(value, str) and not value.strip() else value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _ProgrammaticFlagSource(settings_cls, env_settings),
            _ProgrammaticFlagSource(settings_cls, dotenv_settings),
            _ProgrammaticFlagSource(settings_cls, file_secret_settings),
        )

    @model_validator(mode="after")
    def validate_settings(self) -> Settings:
        """Reject unusable provider and chunk configurations before doing work."""
        if self.chunk_overlap_tokens >= self.chunk_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_TOKENS")
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError("Set OPENAI_API_KEY before selecting PROVIDER=openai")
        if self.provider == "openai" and (
            self.llm_model != "gpt-4o-mini" or self.embedding_model != "text-embedding-3-small"
        ):
            raise ValueError(
                "Cost table supports gpt-4o-mini and text-embedding-3-small only; update pricing before changing models"
            )
        return self

    @property
    def embedding_id(self) -> str:
        """Identify incompatible collections by provider and embedding model."""
        model = self.local_embedding_model if self.provider == "local" else self.embedding_model
        return f"{self.provider}:{model}"
