import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { askQuestion } from "../src/api";
import { AskResponse, QuotaError } from "../src/types";

vi.mock("../src/api", () => ({ askQuestion: vi.fn() }));

const askQuestionMock = vi.mocked(askQuestion);

function response(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    answer: "Versioning keeps multiple variants of an object.",
    chunks: [
      { source_doc: "s3/versioning.md", link: "https://example.com/v", cosine_distance: 0.12 },
      { source_doc: "s3/intro.md", link: "https://example.com/i", cosine_distance: 0.31 },
    ],
    session: { id: "sess-1", used: 1, limit: 20 },
    ...overrides,
  };
}

beforeEach(() => {
  askQuestionMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function ask(question: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/your question/i), question);
  await user.click(screen.getByRole("button", { name: /ask/i }));
  return user;
}

describe("App", () => {
  it("disables the input and shows a spinner while a request is in flight", async () => {
    let resolve!: (value: AskResponse) => void;
    askQuestionMock.mockReturnValue(new Promise<AskResponse>((r) => (resolve = r)));

    render(<App />);
    await ask("What is versioning?");

    expect(screen.getByRole("status")).toHaveTextContent(/thinking/i);
    expect(screen.getByLabelText(/your question/i)).toBeDisabled();
    expect(screen.getByText(/what is versioning\?/i)).toBeInTheDocument();

    resolve(response());
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("renders the answer and the chunks in the given order", async () => {
    askQuestionMock.mockResolvedValue(response());

    render(<App />);
    await ask("What is versioning?");

    await screen.findByText(/versioning keeps multiple variants/i);
    const links = screen.getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["s3/versioning.md", "s3/intro.md"]);
    expect(screen.getByText(/cosine distance: 0\.120/i)).toBeInTheDocument();
  });

  it("shows the fallback answer with no sources", async () => {
    askQuestionMock.mockResolvedValue(
      response({ answer: "I don't know the answer", chunks: [] }),
    );

    render(<App />);
    await ask("Something unrelated");

    await screen.findByText(/i don't know the answer/i);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows a limit message on 429", async () => {
    askQuestionMock.mockRejectedValue(new QuotaError("limit reached"));

    render(<App />);
    await ask("Another question");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/session's question limit/i);
  });

  it("shows a generic error on failure", async () => {
    askQuestionMock.mockRejectedValue(new Error("network down"));

    render(<App />);
    await ask("Will this fail?");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/something went wrong/i);
  });
});
