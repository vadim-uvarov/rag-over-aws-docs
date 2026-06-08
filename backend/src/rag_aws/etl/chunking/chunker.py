"""Naive document chunker built on LlamaIndex's ``SentenceSplitter``.

Splitting is delegated to LlamaIndex; the size budget is measured through the
injected :class:`TokenCounter`, so the tokenizer used for budgeting is swappable
(see docs/etl.md). Each chunk carries provenance plus a best-effort char span.
"""

from __future__ import annotations

from llama_index.core.node_parser import SentenceSplitter

from rag_aws.etl.chunking.token_counter import TiktokenCounter
from rag_aws.etl.interfaces import Chunk, Chunker, TokenCounter

DEFAULT_CHUNK_SIZE_TOKENS = 512
DEFAULT_CHUNK_OVERLAP_TOKENS = 50


class NaiveChunker(Chunker):
    """Split documents into token-budgeted chunks at sentence boundaries."""

    def __init__(
        self,
        token_counter: TokenCounter | None = None,
        chunk_size_tokens: int = DEFAULT_CHUNK_SIZE_TOKENS,
        chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    ) -> None:
        self._token_counter = token_counter or TiktokenCounter()
        # SentenceSplitter only uses the tokenizer's *length*; returning a list
        # sized by our TokenCounter routes budgeting through the swappable counter.
        self._splitter = SentenceSplitter(
            chunk_size=chunk_size_tokens,
            chunk_overlap=chunk_overlap_tokens,
            tokenizer=lambda text: [0] * self._token_counter.count_tokens(text),
        )

    def chunk_document(self, text: str, *, source_doc: str, repo: str) -> list[Chunk]:
        if not text.strip():
            return []

        chunks: list[Chunk] = []
        search_from = 0
        for index, piece in enumerate(self._splitter.split_text(text)):
            char_start = text.find(piece, search_from)
            if char_start == -1:  # whitespace normalisation can prevent an exact find
                char_start = min(search_from, len(text))
            char_end = min(char_start + len(piece), len(text))
            # Advance past this chunk's start (not its end) so overlapping chunks
            # can still be located in the source text.
            search_from = char_start + 1
            chunks.append(
                Chunk(
                    chunk_id=Chunk.make_id(repo, source_doc, index),
                    text=piece,
                    source_doc=source_doc,
                    repo=repo,
                    chunk_index=index,
                    char_start=char_start,
                    char_end=char_end,
                    token_count=self._token_counter.count_tokens(piece),
                )
            )
        return chunks
