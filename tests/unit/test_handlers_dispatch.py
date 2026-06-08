"""Unit tests for the SQS → Step Functions dispatcher."""

from __future__ import annotations

import json
from typing import Any

from rag_aws.etl.handlers.dispatch import build_execution_input, dispatch


def _sqs_record(detail_type: str, key: str, bucket: str = "b") -> dict[str, Any]:
    body = {
        "detail-type": detail_type,
        "detail": {"bucket": {"name": bucket}, "object": {"key": key}},
    }
    return {"body": json.dumps(body)}


class FakeSfnClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def start_execution(self, *, stateMachineArn: str, input: str) -> dict[str, str]:  # noqa: N803
        self.calls.append({"arn": stateMachineArn, "input": input})
        return {"executionArn": "arn:aws:states:::execution/x"}


def test_build_execution_input_collects_items() -> None:
    records = [
        _sqs_record("Object Created", "corpus/raw/r/a.md"),
        _sqs_record("Object Deleted", "corpus/raw/r/b.md"),
    ]
    payload = build_execution_input(records)
    assert payload == {
        "items": [
            {"bucket": "b", "key": "corpus/raw/r/a.md", "action": "created"},
            {"bucket": "b", "key": "corpus/raw/r/b.md", "action": "removed"},
        ]
    }


def test_dispatch_starts_one_execution_with_batch() -> None:
    client = FakeSfnClient()
    event = {"Records": [_sqs_record("Object Created", "corpus/raw/r/a.md")]}
    arn = dispatch(event, sfn_client=client, state_machine_arn="sm-arn")
    assert arn == "arn:aws:states:::execution/x"
    assert len(client.calls) == 1
    assert json.loads(client.calls[0]["input"])["items"][0]["key"] == "corpus/raw/r/a.md"


def test_dispatch_skips_empty_batch() -> None:
    client = FakeSfnClient()
    assert dispatch({"Records": []}, sfn_client=client, state_machine_arn="sm") == ""
    assert client.calls == []
