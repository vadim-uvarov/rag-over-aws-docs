import { FormEvent, useState } from "react";
import { askQuestion } from "./api";
import { getSessionId, setSessionId } from "./session";
import { ChunkList } from "./components/ChunkList";
import { Chunk, QuotaError } from "./types";
import "./App.css";

export function App() {
  const [question, setQuestion] = useState("");
  const [prompt, setPrompt] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }

    // Echo the prompt, clear+disable the input, and show the spinner.
    setPrompt(trimmed);
    setQuestion("");
    setLoading(true);
    setError(null);
    setAnswer(null);
    setChunks([]);

    try {
      const response = await askQuestion(trimmed, getSessionId());
      setSessionId(response.session.id);
      setAnswer(response.answer);
      setChunks(response.chunks);
    } catch (caught) {
      if (caught instanceof QuotaError) {
        setError("You've reached this session's question limit. Please try again later.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <h1>Ask AWS Docs</h1>

      <form onSubmit={handleSubmit} className="ask-form">
        <input
          type="text"
          aria-label="Your question"
          placeholder="Ask a question about AWS…"
          value={question}
          disabled={loading}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button type="submit" disabled={loading || question.trim().length === 0}>
          Ask
        </button>
      </form>

      {prompt && (
        <p className="prompt">
          <strong>You asked:</strong> {prompt}
        </p>
      )}

      {loading && (
        <p className="spinner" role="status">
          Thinking…
        </p>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {!loading && answer && (
        <>
          <section className="answer" aria-label="Answer">
            <h2>Answer</h2>
            <p>{answer}</p>
          </section>
          <ChunkList chunks={chunks} />
        </>
      )}
    </main>
  );
}
