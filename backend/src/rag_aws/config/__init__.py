"""Central configuration: settings, model identifiers, and timestamp helpers."""

from rag_aws.config.settings import (
    EMBEDDING_DIMENSIONS,
    NOVA_MICRO_MODEL_ID,
    TITAN_EMBED_MODEL_ID,
    Settings,
    load_settings,
)
from rag_aws.config.timestamps import format_timestamp

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "NOVA_MICRO_MODEL_ID",
    "TITAN_EMBED_MODEL_ID",
    "Settings",
    "format_timestamp",
    "load_settings",
]
