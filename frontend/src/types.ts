export interface Chunk {
  source_doc: string;
  link: string;
  cosine_distance: number;
}

export interface Session {
  id: string;
  used: number;
  limit: number;
}

export interface AskResponse {
  answer: string;
  chunks: Chunk[];
  session: Session;
}

/** Raised when the API returns 429 (per-session question limit reached). */
export class QuotaError extends Error {
  session?: Session;

  constructor(message: string, session?: Session) {
    super(message);
    this.name = "QuotaError";
    this.session = session;
  }
}
