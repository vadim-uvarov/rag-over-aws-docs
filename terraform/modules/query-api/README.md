# query-api module

The synchronous RAG query backend and its abuse/cost controls.

```
client ─► WAF (per-IP rate) ─► API Gateway (usage plan: daily quota + throttle)
                                   └─► Query Lambda ──► DynamoDB (per-session quota)
                                                   ├─► Bedrock Titan v2 (embed)
                                                   ├─► LanceDB @ S3 (search)
                                                   ├─► Bedrock Nova Micro (generate)
                                                   └─► Secrets Manager (Langfuse keys)
   AWS Budgets (Bedrock cost) ─► SNS
```

## Resources

- **DynamoDB** `…-sessions` — per-session counter, `expires_at` TTL (24h).
- **Lambda** `…-query` — container image (`backend/Dockerfile`, command
  `rag_aws.query.handler.handler`), least-privilege IAM (read corpus, Bedrock
  invoke on the two model ARNs + inference profiles, DynamoDB update/get, read
  the Langfuse secret).
- **API Gateway** REST `POST /ask` (Lambda proxy) + stage with throttling.
- **Usage plan** — global daily request quota + steady/burst throttle.
- **WAFv2** web ACL — per-IP rate-based rule, associated to the stage.
- **Secrets Manager** — Langfuse keys (populate the value out of band).
- **AWS Budgets** — monthly Bedrock cost budget → **SNS** (optional email sub).

## Abuse / cost controls (layered)

| Control | Mechanism |
|---|---|
| Per-session cap | DynamoDB counter → `429` at `session_question_limit` |
| Per-IP rate | WAF rate-based rule |
| Global daily cap | API Gateway usage plan quota |
| Steady/burst rate | Usage plan + stage throttle |
| Bedrock spend | AWS Budgets alarm → SNS |

## Notes

Gated behind `enable_query_api` in `terraform/prod` until the Lambda image is in
ECR. After enabling, set the Langfuse secret value if tracing is wanted (it is
optional — the query path degrades gracefully without it). Deeper dashboards and
failure alarms are added in PR7.
