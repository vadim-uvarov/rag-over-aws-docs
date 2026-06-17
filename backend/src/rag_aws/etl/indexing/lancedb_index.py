"""LanceDB-backed vector index over the ``corpus/vector-store/`` (C) prefix.

LanceDB and pyarrow are imported lazily so the rest of the ETL package (and its
tests) load even on platforms without a LanceDB wheel.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rag_aws.config.settings import EMBEDDING_DIMENSIONS
from rag_aws.config.timestamps import format_timestamp
from rag_aws.etl.interfaces import EmbeddedChunk, SearchResult, VectorIndex

TABLE_NAME = "chunks"


class VectorStoreNotFoundError(RuntimeError):
    """Raised when a read-only consumer opens a table that has not been built yet.

    Signals that the ETL backfill has not populated the vector store, rather than
    letting a read path attempt a write (``create_table``) it has no permission for.
    """


class LanceDBIndex(VectorIndex):
    """A :class:`VectorIndex` stored as a LanceDB table.

    Schema: ``{id, vector, text, source_doc, repo, chunk_index, ts}``. Upserts
    merge on ``id``; deletes are by source document.
    """

    def __init__(
        self,
        uri: str,
        dimensions: int = EMBEDDING_DIMENSIONS,
        table_name: str = TABLE_NAME,
        create_if_missing: bool = True,
    ) -> None:
        import lancedb

        self._dimensions = dimensions
        self._table_name = table_name
        self._db = lancedb.connect(uri)
        # Read-only consumers (the query Lambda) pass create_if_missing=False so a
        # missing table fails fast instead of attempting a write they can't perform.
        self._table = self._open_or_create_table(create_if_missing)

    def _build_schema(self) -> Any:
        import pyarrow as pa

        return pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self._dimensions)),
                pa.field("text", pa.string()),
                pa.field("source_doc", pa.string()),
                pa.field("repo", pa.string()),
                pa.field("chunk_index", pa.int64()),
                pa.field("ts", pa.string()),
            ]
        )

    def _open_or_create_table(self, create_if_missing: bool) -> Any:
        if self._table_name in self._db.table_names():
            return self._db.open_table(self._table_name)
        if not create_if_missing:
            raise VectorStoreNotFoundError(
                f"vector store table '{self._table_name}' not found; "
                "run the ETL backfill to populate it"
            )
        return self._db.create_table(self._table_name, schema=self._build_schema())

    def upsert(self, embedded_chunks: Sequence[EmbeddedChunk]) -> None:
        rows = [self._to_row(embedded) for embedded in embedded_chunks]
        if not rows:
            return
        (
            self._table.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    def delete_document(self, repo: str, source_doc: str) -> None:
        predicate = f"repo = '{_escape(repo)}' AND source_doc = '{_escape(source_doc)}'"
        self._table.delete(predicate)

    def search(self, query_vector: Sequence[float], top_k: int) -> list[SearchResult]:
        query = self._table.search(list(query_vector))
        # The metric setter was renamed across LanceDB versions; support both.
        if hasattr(query, "distance_type"):
            query = query.distance_type("cosine")
        elif hasattr(query, "metric"):
            query = query.metric("cosine")
        hits = query.limit(top_k).to_list()
        return [_row_to_result(hit) for hit in hits]

    def count(self) -> int:
        return int(self._table.count_rows())

    def _to_row(self, embedded: EmbeddedChunk) -> dict[str, Any]:
        chunk = embedded.chunk
        return {
            "id": chunk.chunk_id,
            "vector": list(embedded.vector),
            "text": chunk.text,
            "source_doc": chunk.source_doc,
            "repo": chunk.repo,
            "chunk_index": chunk.chunk_index,
            "ts": format_timestamp(),
        }


def _row_to_result(hit: dict[str, Any]) -> SearchResult:
    # LanceDB cosine distance is 1 - cosine_similarity.
    distance = float(hit.get("_distance", 0.0))
    return SearchResult(
        chunk_id=str(hit["id"]),
        text=str(hit["text"]),
        source_doc=str(hit["source_doc"]),
        repo=str(hit["repo"]),
        chunk_index=int(hit["chunk_index"]),
        score=1.0 - distance,
    )


def _escape(value: str) -> str:
    """Escape single quotes for a LanceDB SQL filter literal."""
    return value.replace("'", "''")
