"""Answer generation with Amazon Nova Micro via LangChain.

The retrieved chunks are injected into a prompt; with no chunks the generator
returns exactly ``"I don't know the answer"`` and never calls the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from rag_aws.config.settings import NOVA_MICRO_MODEL_ID
from rag_aws.etl.interfaces import SearchResult

# Returned verbatim when retrieval finds nothing relevant (exact wording matters).
FALLBACK_ANSWER = "I don't know the answer"

_PROMPT_TEMPLATE = """\
You are an assistant that answers questions about AWS using only the provided \
documentation excerpts. If the excerpts do not contain the answer, say you don't know.

Documentation excerpts:
{context}

Question: {question}

Answer:"""


class ChatModel(Protocol):
    """A minimal chat model: prompt in, answer text out."""

    def invoke(self, prompt: str) -> str: ...


def build_prompt(question: str, chunks: Sequence[SearchResult]) -> str:
    """Assemble the generation prompt from the question and retrieved chunks."""
    context = "\n\n".join(
        f"[{index + 1}] (source: {chunk.source_doc})\n{chunk.text}"
        for index, chunk in enumerate(chunks)
    )
    return _PROMPT_TEMPLATE.format(context=context, question=question)


class AnswerGenerator:
    """Turn a question + retrieved chunks into an answer."""

    def __init__(self, model: ChatModel) -> None:
        self._model = model

    def generate_answer(self, question: str, chunks: Sequence[SearchResult]) -> str:
        if not chunks:
            return FALLBACK_ANSWER
        return self._model.invoke(build_prompt(question, chunks))


class NovaMicroModel(ChatModel):
    """`ChatModel` backed by Amazon Nova Micro through ``langchain_aws``."""

    def __init__(
        self,
        model_id: str = NOVA_MICRO_MODEL_ID,
        region_name: str = "eu-west-1",
        temperature: float = 0.0,
    ) -> None:
        from langchain_aws import ChatBedrockConverse

        self._chat = ChatBedrockConverse(
            model=model_id, region_name=region_name, temperature=temperature
        )

    def invoke(self, prompt: str) -> str:
        response = self._chat.invoke(prompt)
        content = response.content
        # LangChain content may be a string or a list of content blocks.
        if isinstance(content, str):
            return content
        return "".join(part if isinstance(part, str) else str(part) for part in content)
