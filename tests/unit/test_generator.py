"""Unit tests for prompt assembly and answer generation."""

from __future__ import annotations

from rag_aws.etl.interfaces import SearchResult
from rag_aws.query.generator import FALLBACK_ANSWER, AnswerGenerator, build_prompt


def _hit(text: str, source_doc: str = "s3/intro.md") -> SearchResult:
    return SearchResult(
        chunk_id="r/d#0", text=text, source_doc=source_doc, repo="r", chunk_index=0, score=0.9
    )


class _EchoModel:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "generated answer"


def test_build_prompt_includes_question_and_chunks() -> None:
    prompt = build_prompt("What is a bucket?", [_hit("A bucket holds objects.")])
    assert "What is a bucket?" in prompt
    assert "A bucket holds objects." in prompt
    assert "s3/intro.md" in prompt


def test_generate_answer_returns_fallback_when_no_chunks() -> None:
    model = _EchoModel()
    answer = AnswerGenerator(model).generate_answer("anything", [])
    assert answer == FALLBACK_ANSWER
    assert model.prompts == []  # model not called on the empty path


def test_generate_answer_invokes_model_with_chunks() -> None:
    model = _EchoModel()
    answer = AnswerGenerator(model).generate_answer("q", [_hit("context text")])
    assert answer == "generated answer"
    assert "context text" in model.prompts[0]
