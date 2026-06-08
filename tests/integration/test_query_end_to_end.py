"""End-to-end query: real retriever/generator over a local index + fakes.

Uses the deterministic FakeEmbedder so an exact-text query matches its chunk
(similarity 1.0) while an unrelated query falls below the 0.7 threshold and
yields the fallback answer.
"""

from __future__ import annotations

from rag_aws.config.settings import Settings
from rag_aws.etl.embedding.fake import FakeEmbedder
from rag_aws.etl.indexing.memory_index import InMemoryVectorIndex
from rag_aws.etl.interfaces import Chunk, EmbeddedChunk
from rag_aws.query.generator import FALLBACK_ANSWER, AnswerGenerator
from rag_aws.query.handler import QueryDependencies, process_query
from rag_aws.query.retriever import Retriever
from rag_aws.query.session import SessionUsage

DIMENSIONS = 32

DOCS = {
    "s3/buckets.md": "Amazon S3 stores objects in buckets across regions.",
    "lambda/intro.md": "AWS Lambda runs code without provisioning servers.",
}


class _EchoModel:
    def invoke(self, prompt: str) -> str:
        return "Grounded answer based on the provided excerpts."


class _AllowQuota:
    def record_question(self, session_id: str, now: float | None = None) -> SessionUsage:
        return SessionUsage(session_id, used=1, limit=20, allowed=True)


def _build_index(embedder: FakeEmbedder) -> InMemoryVectorIndex:
    index = InMemoryVectorIndex()
    for chunk_index, (doc, text) in enumerate(DOCS.items()):
        chunk = Chunk(
            chunk_id=f"r/{doc}#0",
            text=text,
            source_doc=doc,
            repo="r",
            chunk_index=chunk_index,
            char_start=0,
            char_end=len(text),
            token_count=len(text.split()),
        )
        vector = embedder.embed_texts([text])[0]
        index.upsert([EmbeddedChunk(chunk=chunk, vector=vector)])
    return index


def _deps() -> QueryDependencies:
    embedder = FakeEmbedder(dimensions=DIMENSIONS)
    settings = Settings(retrieval_similarity_threshold=0.7, retrieval_top_k_final=5)
    return QueryDependencies(
        retriever=Retriever(embedder, _build_index(embedder), settings=settings),
        generator=AnswerGenerator(_EchoModel()),
        quota=_AllowQuota(),
    )


def test_known_question_returns_expected_chunk() -> None:
    # An exact-text query embeds to the same vector as its chunk (similarity 1.0).
    status, payload = process_query(
        {"question": "Amazon S3 stores objects in buckets across regions."}, _deps()
    )
    assert status == 200
    assert payload["answer"] != FALLBACK_ANSWER
    assert payload["chunks"][0]["source_doc"] == "s3/buckets.md"


def test_nonsense_question_returns_fallback() -> None:
    status, payload = process_query({"question": "completely unrelated gibberish xyzzy"}, _deps())
    assert status == 200
    assert payload["answer"] == FALLBACK_ANSWER
    assert payload["chunks"] == []
