const SESSION_STORAGE_KEY = "rag-aws-session-id";

/** Read the persisted session id, or null if none/unavailable. */
export function getSessionId(): string | null {
  try {
    return window.localStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Persist the session id returned by the API so the quota follows the user. */
export function setSessionId(sessionId: string): void {
  try {
    window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  } catch {
    // Ignore storage failures (private mode, etc.); the session is still usable in-memory.
  }
}
