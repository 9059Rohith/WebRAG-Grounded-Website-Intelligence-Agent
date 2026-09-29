"""Stable domain errors for safe CLI and API boundaries."""


class RagError(Exception):
    """Base operational failure."""


class IndexMismatchError(RagError):
    """The index was built using an incompatible embedding model."""


class LLMError(RagError):
    """A provider did not return a usable structured response."""
