"""tiktoken-based token counter used for chunk-size budgeting.

Nova's exact tokenizer is not publicly exposed, so we use tiktoken's
``cl100k_base`` as a documented proxy purely to measure chunk size. This keeps
token counting a swappable concern inside the chunk stage (see docs/etl.md).
"""

from __future__ import annotations

import tiktoken

from rag_aws.etl.interfaces import TokenCounter

DEFAULT_ENCODING = "cl100k_base"


class TiktokenCounter(TokenCounter):
    """Counts tokens with a tiktoken encoding (``cl100k_base`` by default)."""

    def __init__(self, encoding_name: str = DEFAULT_ENCODING) -> None:
        self._encoding_name = encoding_name
        # The encoding is loaded lazily so constructing the counter is cheap and
        # offline-safe; the (possibly network-backed) load happens on first use.
        self._encoding: tiktoken.Encoding | None = None

    def _get_encoding(self) -> tiktoken.Encoding:
        if self._encoding is None:
            self._encoding = tiktoken.get_encoding(self._encoding_name)
        return self._encoding

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._get_encoding().encode(text))

    def encode(self, text: str) -> list[int]:
        """Return token ids for ``text`` (used as the chunker's tokenizer)."""
        return self._get_encoding().encode(text)
