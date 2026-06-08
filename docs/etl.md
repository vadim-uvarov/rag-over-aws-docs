# ETL stages

The ETL pipeline turns raw documentation into a searchable vector store in three
stages: **chunk → embed → index**. PR3 delivers these as pure, unit-testable
libraries behind swappable interfaces; PR4 wires them into orchestration infra.

## Interfaces

All stages are abstract base classes in `backend/src/rag_aws/etl/interfaces.py`,
so implementations swap freely (real vs. fake, LanceDB vs. in-memory):

| Interface | Responsibility | Implementations |
|---|---|---|
| `TokenCounter` | Count tokens for size budgeting | `TiktokenCounter` |
| `Chunker` | Split a document into `Chunk`s | `NaiveChunker` |
| `Embedder` | Text → vectors | `BedrockTitanEmbedder`, `FakeEmbedder` |
| `VectorIndex` | Store + search embedded chunks | `LanceDBIndex`, `InMemoryVectorIndex` |

Data flows as `Chunk` → `EmbeddedChunk` → (`VectorIndex`) → `SearchResult`.

## Chunking

`NaiveChunker` delegates splitting to LlamaIndex's `SentenceSplitter`, but the
**size budget is measured through the injected `TokenCounter`** — the splitter's
tokenizer just returns a list sized by `count_tokens`, so swapping the counter
swaps the budgeting. Each `Chunk` carries provenance (`repo`, `source_doc`,
`chunk_index`), a stable `chunk_id` (`<repo>/<doc>#<index>`), a best-effort char
span, and its `token_count`.

> **Tokenizer caveat (from the plan):** Nova's exact tokenizer is not publicly
> exposed, so `TiktokenCounter` uses tiktoken's `cl100k_base` as a documented
> proxy *only* for chunk-size budgeting — not for the model's own tokenization.

Chunk text is persisted to `corpus/chunks/` (B) at
`corpus/chunks/<repo>/<doc>/<index>.txt` by `write_chunks_to_s3`.

## Embedding

`BedrockTitanEmbedder` calls Amazon Titan Text Embeddings V2
(`amazon.titan-embed-text-v2:0`, 512-dim, normalized). Titan embeds one text per
`invoke_model` call, so `embed_texts` iterates and retries throttled calls with
exponential backoff. The Bedrock client is injected (structural typing), so tests
use a fake. `FakeEmbedder` produces deterministic, unit-normalized vectors with
no network — used in tests and local pipelines.

## Indexing

`VectorIndex` stores `{id, vector, text, source_doc, repo, chunk_index, ts}`.
Upserts merge by `chunk_id` (idempotent); `delete_document` removes all chunks of
one source doc (drives updates/removals); `search` returns hits ranked by
descending cosine similarity.

- `LanceDBIndex` — LanceDB over `corpus/vector-store/` (C). Imported lazily; not
  every dev platform has a LanceDB wheel (e.g. Intel macOS), so its tests skip
  where it is unavailable. CI (Linux) exercises it.
- `InMemoryVectorIndex` — pure-Python reference implementation; runs everywhere.

## Swapping an implementation

Construct the stage you want and pass it to `process_document`
(`etl/pipeline.py`), which runs chunk → store → embed → index for one document
and re-indexes safely (deletes a document's old chunks before upserting):

```python
process_document(
    text, source_doc="s3/intro.md", repo="amazon-s3-userguide",
    chunker=NaiveChunker(), embedder=FakeEmbedder(), index=InMemoryVectorIndex(),
    s3_client=s3, bucket=bucket,   # optional: also persist chunk text to B
)
```

## Tests

- **Unit** — per stage with fakes: token counting, chunk boundaries/metadata
  (empty/tiny/large border cases), chunk→S3 keys, fake-embedder determinism,
  Bedrock retry/backoff (throttle→retry, non-retryable, exhaustion), in-memory
  index upsert/search/delete.
- **Contract** (`tests/contract/`) — the same assertions run against *every*
  implementation of `VectorIndex` and `Embedder`.
- **Integration** (`tests/integration/test_etl_pipeline.py`) — chunk→embed→index
  on a sample doc with moto S3 and a local index (LanceDB where available).
