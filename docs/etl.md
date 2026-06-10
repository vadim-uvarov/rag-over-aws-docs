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

## Orchestration (PR4)

Automated, batched, resilient processing of changed files
(`terraform/modules/etl`):

```
S3 corpus/raw/ ─(EventBridge: Object Created/Deleted)─► SQS ingest (+ DLQ)
                                                          │ batch
                                     Lambda dispatch ◄────┘
                                          │ StartExecution({"items":[…]})
                                          ▼
                       Step Functions: Map(items) ─► Lambda process
                                                       (chunk → embed → index)
```

- **`handlers/events.py`** normalizes EventBridge S3 events into
  `DocumentEvent(bucket, key, action)`.
- **`handlers/dispatch.py`** (SQS-triggered) batches records into the Map input
  and starts one execution.
- **`handlers/process.py`** runs once per Map item: a created/updated key is
  chunked→embedded→indexed (chunk text also written to B); a removed key has its
  vectors and chunk objects deleted.
- The **Map** state bounds `MaxConcurrency` (Bedrock throttling control), retries
  each task with backoff, and tolerates a small failure percentage; the **DLQ**
  captures messages that fail repeatedly. (Failure alarms land in PR7.)
- Both Lambdas run from one **container image** (`backend/Dockerfile`) — in fact the
  same image also backs the query-API Lambda, with each function's handler selected
  via `image_config.command`. The prod deploy pipeline builds this image and pushes it
  to the shared `rag-aws-etl` ECR repository, then applies the ETL module with
  `enable_etl=true`; the `enable_etl` default stays `false` for local applies and PR
  plans. See [`architecture.md`](architecture.md#deploy-sequence).

### Backfill

`scripts/backfill.py --bucket <b> --queue-url <url>` enqueues an
`Object Created` event for every object under `corpus/raw/` onto the same SQS
buffer (batches of 10, optional `--delay`), so the initial bulk load flows
through the identical pipeline without thousands of concurrent executions.

## Tests

- **Unit** — per stage with fakes: token counting, chunk boundaries/metadata
  (empty/tiny/large border cases), chunk→S3 keys, fake-embedder determinism,
  Bedrock retry/backoff (throttle→retry, non-retryable, exhaustion), in-memory
  index upsert/search/delete; handler event parsing, dispatcher batching, the
  process handler (create→indexed, remove→deleted), and backfill enqueue/batching.
- **Contract** (`tests/contract/`) — the same assertions run against *every*
  implementation of `VectorIndex` and `Embedder`.
- **Integration** — chunk→embed→index on a sample doc with moto S3
  (`test_etl_pipeline.py`); and the full EventBridge→SQS→dispatch→Map(process)
  flow simulated against moto (`test_etl_orchestration.py`). Step Functions Local
  needs Java/Docker, so the orchestration test drives the same handler functions
  the Map state invokes rather than the real state machine.
