# Frontend

React + TypeScript + Vite single-page app that talks to the RAG `/ask` API.

## UX

1. Type a question and press **Ask**.
2. On submit the input is cleared and disabled, the prompt is echoed ("You
   asked: …"), and a **"Thinking…"** spinner shows.
3. On response the **answer** renders, followed by the retrieved **sources** in
   descending relevance — each a link to the parent doc with its cosine distance.
4. The session id is stored in `localStorage` and sent on each request so the
   per-session quota follows the user. A `429` shows a "session limit reached"
   message; other failures show a generic error.

## Run / build / deploy

```sh
cd frontend
npm ci
npm run dev         # local dev server
npm run typecheck   # tsc --noEmit
npm test            # Vitest + React Testing Library
npm run build       # production build → dist/
npm run test:e2e    # Playwright smoke (builds + previews + mocks the API)
```

Deploy (after `enable_frontend=true` provisions CloudFront):

```sh
scripts/deploy_frontend.sh <bucket> <distribution-id> <api-url>
```

## Configuration

`VITE_API_URL` (build-time) sets the API base; `/ask` is appended. Empty means
same-origin (useful for the Playwright mock).

## Tests

- **Component** (Vitest + RTL, runs in CI): submit disables input + shows the
  spinner; renders the answer and chunks in order; the "I don't know the answer"
  path renders no sources; the `429` and generic-error paths show messages.
- **Smoke e2e** (Playwright): the happy path against a mocked `/ask`. Run locally
  with `npm run test:e2e` — it is kept out of the main CI job because installing
  browsers there is heavy/flaky.
