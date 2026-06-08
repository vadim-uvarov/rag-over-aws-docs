"""Embedding stage: turn chunk text into vectors via Bedrock Titan v2."""

from rag_aws.etl.embedding.bedrock import BedrockTitanEmbedder
from rag_aws.etl.embedding.fake import FakeEmbedder

__all__ = ["BedrockTitanEmbedder", "FakeEmbedder"]
