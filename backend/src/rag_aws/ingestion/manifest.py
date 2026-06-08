"""Ingestion manifest: per-file content hashes that drive incremental sync.

The manifest is a single JSON object stored at ``corpus/manifests/manifest.json``
(prefix D). It records, for every object currently in ``corpus/raw/``, the SHA-256
of its content plus provenance, so a later run can compute the add/update/delete
diff without re-reading the bucket.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from rag_aws.config.settings import MANIFESTS_PREFIX
from rag_aws.config.timestamps import format_timestamp

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

MANIFEST_KEY = f"{MANIFESTS_PREFIX}manifest.json"


@dataclass(frozen=True)
class FileEntry:
    """Provenance and content hash for one ingested file.

    Attributes:
        sha256: SHA-256 hex digest of the file content.
        source_repo: Logical repo name the file came from.
        source_path: Repo-relative path of the file.
        updated_at: ISO-8601 UTC timestamp of when this entry was last written.
    """

    sha256: str
    source_repo: str
    source_path: str
    updated_at: str


@dataclass
class Manifest:
    """The full ingestion manifest: a map of S3 key to :class:`FileEntry`."""

    files: dict[str, FileEntry] = field(default_factory=dict)
    generated_at: str = ""

    def hashes(self) -> dict[str, str]:
        """Return the ``{s3_key: sha256}`` view used by the diff."""
        return {key: entry.sha256 for key, entry in self.files.items()}

    def to_json(self) -> str:
        """Serialise to a stable, human-readable JSON string."""
        payload = {
            "generated_at": self.generated_at or format_timestamp(),
            "files": {key: asdict(entry) for key, entry in sorted(self.files.items())},
        }
        return json.dumps(payload, indent=2, sort_keys=False)

    @classmethod
    def from_json(cls, raw: str) -> Manifest:
        """Parse a manifest from its JSON representation."""
        data = json.loads(raw)
        files = {key: FileEntry(**entry) for key, entry in data.get("files", {}).items()}
        return cls(files=files, generated_at=data.get("generated_at", ""))


def load_manifest(s3_client: S3Client, bucket: str) -> Manifest:
    """Load the manifest from the bucket, returning an empty one if absent."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=MANIFEST_KEY)
    except s3_client.exceptions.NoSuchKey:
        return Manifest()
    return Manifest.from_json(response["Body"].read().decode("utf-8"))


def save_manifest(s3_client: S3Client, bucket: str, manifest: Manifest) -> None:
    """Write the manifest back to the bucket as JSON."""
    manifest.generated_at = format_timestamp()
    s3_client.put_object(
        Bucket=bucket,
        Key=MANIFEST_KEY,
        Body=manifest.to_json().encode("utf-8"),
        ContentType="application/json",
    )
