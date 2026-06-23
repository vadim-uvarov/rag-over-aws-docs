# RAG query

How the `/ask` endpoint turns a question into a grounded answer
(`backend/src/rag_aws/query/`).

## Flow

1. **Retrieve** (`retriever.py`): embed the question with Titan v2 → LanceDB
   **top-20** → keep **cosine similarity ≥ 0.7** → keep **top-5**. If nothing
   survives, the list is empty.
2. **Generate** (`generator.py`): if there are chunks, build a prompt that
   injects them and call **Nova Micro** via LangChain. **With no chunks, return
   exactly `"I don't know the answer"`** and never call the model.
3. **Trace** (`tracing.py`): best-effort Langfuse event (keys from Secrets
   Manager); failures never break a query.
4. **Respond** (`handler.py`): shape the answer + chunks (descending relevance)
   and the session usage.

## Retrieval threshold

The spec's "keep cosine *distance* > 0.7" was inverted (larger distance = less
similar). We keep **cosine similarity ≥ 0.7 (distance ≤ 0.3)**. The threshold is
inclusive — a hit at exactly 0.7 is kept (`filter_hits`).

## Prompt

`build_prompt` instructs the model to answer **only** from the provided excerpts
and to say it doesn't know otherwise, then lists the numbered excerpts (with
their source doc) and the question.

## Abuse & cost controls

- **Per-session quota** — DynamoDB counter, 20 questions / session, 24h TTL;
  the 21st question returns `429`. The decision is `used <= limit`
  (`evaluate_quota`).
- **Global daily quota**, **throttle**, and a **Bedrock budget alarm** are
  provisioned by the `query-api` Terraform module.

## Models & swapping

`Retriever` takes any `Embedder` + `VectorIndex`; `AnswerGenerator` takes any
`ChatModel` (`NovaMicroModel` in prod, a fake in tests). This keeps the whole
flow testable without AWS.
