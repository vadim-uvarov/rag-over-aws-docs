"""Curated list of AWS documentation repositories to ingest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoConfig:
    """A single AWS documentation source repository.

    Attributes:
        name: Logical name used as the top-level S3 key segment under
            ``corpus/raw/`` (for example ``amazon-s3-userguide``).
        url: Git clone URL.
        branch: Branch to clone/pull.
        doc_subdir: If set, only markdown under this sub-directory is ingested
            (awsdocs repos keep their content under ``doc_source/``). When empty,
            every ``.md`` file in the repo is considered.
    """

    name: str
    url: str
    branch: str = "main"
    doc_subdir: str = "doc_source"


# Starter curated set (see plan §"Open items"). Grow this list as needed — the
# sync is incremental, so adding a repo only uploads its new files.
CURATED_REPOS: tuple[RepoConfig, ...] = (
    RepoConfig("amazon-s3-userguide", "https://github.com/awsdocs/amazon-s3-userguide.git"),
    RepoConfig(
        "aws-lambda-developer-guide",
        "https://github.com/awsdocs/aws-lambda-developer-guide.git",
        doc_subdir="doc_source",
    ),
    RepoConfig("iam-user-guide", "https://github.com/awsdocs/iam-user-guide.git"),
    RepoConfig("amazon-ec2-user-guide", "https://github.com/awsdocs/amazon-ec2-user-guide.git"),
    RepoConfig("aws-cli-user-guide", "https://github.com/awsdocs/aws-cli-user-guide.git"),
)
