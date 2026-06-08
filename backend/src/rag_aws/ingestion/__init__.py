"""Local corpus ingestion: mirror curated awsdocs repos into the project bucket.

Clones (or pulls) a configurable set of AWS documentation repositories, selects
their markdown files, and performs an incremental, hash-based sync into the
``corpus/raw/`` (A) prefix of the project bucket while maintaining a manifest in
``corpus/manifests/`` (D).
"""

from rag_aws.ingestion.config import CURATED_REPOS, RepoConfig
from rag_aws.ingestion.manifest import FileEntry, Manifest
from rag_aws.ingestion.sync import SyncPlan, SyncResult, build_sync_plan, sync_corpus

__all__ = [
    "CURATED_REPOS",
    "FileEntry",
    "Manifest",
    "RepoConfig",
    "SyncPlan",
    "SyncResult",
    "build_sync_plan",
    "sync_corpus",
]
