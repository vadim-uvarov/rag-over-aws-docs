import { AskResponse, QuotaError, Session } from "./types";

// Base URL of the API stage; injected at build time (empty in dev/tests → relative).
const API_BASE: string = import.meta.env.VITE_API_URL ?? "";

interface ErrorBody {
  error?: string;
  session?: Session;
}

/** POST a question to the RAG API and return the answer + chunks. */
export async function askQuestion(question: string, sessionId: string | null): Promise<AskResponse> {
  const response = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId ?? undefined }),
  });

  if (response.status === 429) {
    const body = (await response.json().catch(() => ({}))) as ErrorBody;
    throw new QuotaError(body.error ?? "Session question limit reached", body.session);
  }
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return (await response.json()) as AskResponse;
}
