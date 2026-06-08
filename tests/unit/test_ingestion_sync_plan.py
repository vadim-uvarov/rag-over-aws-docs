"""Unit tests for the pure hash-diff sync planner."""

from __future__ import annotations

from rag_aws.ingestion.sync import build_sync_plan


def test_build_sync_plan_detects_additions() -> None:
    plan = build_sync_plan(desired={"a": "h1", "b": "h2"}, current={"a": "h1"})
    assert plan.to_add == ["b"]
    assert plan.to_update == []
    assert plan.to_delete == []
    assert plan.unchanged == ["a"]


def test_build_sync_plan_detects_updates() -> None:
    plan = build_sync_plan(desired={"a": "new"}, current={"a": "old"})
    assert plan.to_update == ["a"]
    assert plan.to_add == []


def test_build_sync_plan_detects_deletions() -> None:
    plan = build_sync_plan(desired={}, current={"a": "h1", "b": "h2"})
    assert plan.to_delete == ["a", "b"]
    assert plan.has_changes is True


def test_build_sync_plan_noop_when_identical() -> None:
    state = {"a": "h1", "b": "h2"}
    plan = build_sync_plan(desired=state, current=state)
    assert plan.unchanged == ["a", "b"]
    assert plan.has_changes is False


def test_build_sync_plan_first_run_adds_everything() -> None:
    plan = build_sync_plan(desired={"a": "h1", "b": "h2"}, current={})
    assert plan.to_add == ["a", "b"]


def test_build_sync_plan_lists_are_sorted() -> None:
    plan = build_sync_plan(desired={"z": "1", "a": "1"}, current={})
    assert plan.to_add == ["a", "z"]
