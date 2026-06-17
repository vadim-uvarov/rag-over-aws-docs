# API

Synchronous RAG endpoint. Provisioned by the `query-api` Terraform module;
base URL is the `ask_endpoint` output.

## `POST /ask`

### Request

```json
{
  "question": "How do I enable versioning on an S3 bucket?",
  "session_id": "optional-existing-session-id"
}
```

- `question` (required) — the user's question.
- `session_id` (optional) — reuse a prior session to share its quota; if omitted
  a new id is generated and returned.

### Response `200`

Chunks are ordered by **descending relevance** (ascending cosine distance).

```json
{
  "answer": "To enable versioning, ...",
  "chunks": [
    {
      "source_doc": "s3/versioning.md",
      "link": "https://github.com/awsdocs/amazon-s3-userguide/blob/main/doc_source/s3/versioning.md",
      "cosine_distance": 0.12
    }
  ],
  "session": { "id": "ab12…", "used": 3, "limit": 20 }
}
```

When retrieval finds nothing relevant, `answer` is exactly
`"I don't know the answer"` and `chunks` is `[]`.

### Errors

| Status | When | Body |
|---|---|---|
| `400` | Missing `question` or non-JSON body | `{ "error": "…" }` |
| `429` | Session question limit reached | `{ "error": "session question limit reached", "session": {…} }` |

Additional limits enforced outside the handler: per-IP WAF rate limiting, a
global daily usage-plan quota, and stage throttling.

## CORS

The SPA is served from CloudFront, a different origin than the API, so requests
are cross-origin. Two pieces make that work:

- **Preflight:** an `OPTIONS /ask` method with a MOCK integration returns the
  CORS headers (`Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods:
  OPTIONS,POST`, `Access-Control-Allow-Headers: Content-Type`) without invoking
  the Lambda. Without it the browser's preflight gets a 403 and surfaces a CORS
  error.
- **Actual response:** the `POST /ask` response from the Lambda includes
  `Access-Control-Allow-Origin: *` so the browser lets the SPA read it.
