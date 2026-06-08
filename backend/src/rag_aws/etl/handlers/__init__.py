"""Lambda handlers wrapping the ETL stage libraries.

- ``events`` — parse S3 EventBridge events into normalized document events.
- ``dispatch`` — SQS-triggered: batch events and start a Step Functions run.
- ``process`` — process one document event (index on create, delete on remove).
"""

from rag_aws.etl.handlers.dispatch import build_execution_input, dispatch
from rag_aws.etl.handlers.events import DocumentEvent, parse_eventbridge_event
from rag_aws.etl.handlers.process import process_item

__all__ = [
    "DocumentEvent",
    "build_execution_input",
    "dispatch",
    "parse_eventbridge_event",
    "process_item",
]
