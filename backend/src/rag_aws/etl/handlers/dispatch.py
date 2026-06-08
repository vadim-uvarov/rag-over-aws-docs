"""Dispatcher: batch buffered S3 events and start a Step Functions execution.

Triggered by SQS (the buffer between EventBridge and the state machine). Each
SQS record carries one EventBridge S3 event; the dispatcher turns the batch into
a single ``{"items": [...]}`` input and starts one Map-based execution.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, cast

import boto3

from rag_aws.etl.handlers.events import parse_eventbridge_event

STATE_MACHINE_ARN_ENV = "STATE_MACHINE_ARN"


class StepFunctionsClient(Protocol):
    """Minimal structural type for the part of the SFN client we use."""

    def start_execution(self, *, stateMachineArn: str, input: str) -> Any: ...  # noqa: N803


def build_execution_input(sqs_records: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    """Build the state-machine input from a batch of SQS records.

    Args:
        sqs_records: The ``Records`` of an SQS Lambda event; each ``body`` is an
            EventBridge S3 event.

    Returns:
        ``{"items": [{"bucket", "key", "action"}, ...]}`` ready for the Map state.
    """
    items: list[dict[str, str]] = []
    for record in sqs_records:
        body = json.loads(record["body"])
        event = parse_eventbridge_event(body["detail-type"], body["detail"])
        items.append({"bucket": event.bucket, "key": event.key, "action": event.action})
    return {"items": items}


def dispatch(
    sqs_event: dict[str, Any],
    *,
    sfn_client: StepFunctionsClient,
    state_machine_arn: str,
) -> str:
    """Start one execution for the batch; return the execution ARN (or "" if empty)."""
    payload = build_execution_input(sqs_event.get("Records", []))
    if not payload["items"]:
        return ""
    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn, input=json.dumps(payload)
    )
    return str(response["executionArn"])


def handler(event: dict[str, Any], _context: object = None) -> dict[str, str]:
    """Lambda entry point: start a Step Functions run for the SQS batch."""
    state_machine_arn = os.environ[STATE_MACHINE_ARN_ENV]
    sfn_client = cast(StepFunctionsClient, boto3.client("stepfunctions"))
    execution_arn = dispatch(event, sfn_client=sfn_client, state_machine_arn=state_machine_arn)
    return {"executionArn": execution_arn}
