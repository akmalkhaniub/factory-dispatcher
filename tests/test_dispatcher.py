"""Tests for the GitHub Issue-to-PR Factory Dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dispatcher import IssueDispatcher, app
from dispatcher.models import GitHubWebhookPayload


def test_dispatcher_engine_local_run(tmp_path: Path) -> None:
    dispatcher = IssueDispatcher(base_work_dir=tmp_path)

    res = dispatcher.dispatch(
        repo_name="local-test-repo",
        goal="Implement verified service token generator",
        issue_number=42,
        simulate_github=True,
    )

    assert res.status.value == "pr_opened"
    assert res.tests_passed is True
    assert "factory/issue-42" in res.branch
    assert res.pr_url is not None
    assert "simulated" in res.pr_url


def test_webhook_trigger_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPATCHER_SIMULATE_GITHUB", "true")
    client = TestClient(app)

    # 1. Ignored webhook (unrelated label)
    ignored_payload = {
        "action": "labeled",
        "repository": {"full_name": "akmalkhaniub/sample", "clone_url": "https://github.com/..."},
        "issue": {
            "number": 10,
            "title": "Question about docs",
            "body": "How do I setup?",
            "labels": [{"name": "documentation"}],
        },
    }
    resp = client.post("/webhook/github", json=ignored_payload)
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"

    # 2. Triggered webhook (factory-build label)
    trigger_payload = {
        "action": "labeled",
        "repository": {"full_name": "akmalkhaniub/webhook-service", "clone_url": "https://github.com/..."},
        "issue": {
            "number": 12,
            "title": "Add rate limiter guard",
            "body": "Add token bucket rate limiter to prevent DOS attacks",
            "labels": [{"name": "factory-build"}],
        },
    }
    resp2 = client.post("/webhook/github", json=trigger_payload)
    assert resp2.status_code == 202
    assert resp2.json()["status"] == "dispatched"
    assert resp2.json()["issue_number"] == 12


def test_direct_dispatch_api(tmp_path: Path) -> None:
    client = TestClient(app)

    # Direct dispatch API
    req = {
        "repo_name": "akmalkhaniub/test-service",
        "goal": "Implement health probe verification",
        "issue_number": 99,
        "simulate_github": True,
    }
    resp = client.post("/api/dispatch", json=req)
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pr_opened"
    assert data["tests_passed"] is True

    # List tasks API
    tasks_resp = client.get("/api/tasks")
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json()["tasks"]
    assert len(tasks) >= 1


def test_pr_comment_fix_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPATCHER_SIMULATE_GITHUB", "true")
    client = TestClient(app)

    # Simulated PR comment webhook
    comment_payload = {
        "action": "created",
        "repository": {"full_name": "akmalkhaniub/webhook-service", "clone_url": "https://github.com/..."},
        "issue": {
            "number": 42,
            "title": "PR #42: Feature deployment",
            "body": "Base PR body",
            "labels": [],
            "pull_request": {"url": "https://api.github.com/repos/akmalkhaniub/webhook-service/pulls/42"},
        },
        "comment": {
            "id": 9901,
            "body": "/factory fix please correct test assertions and status code",
        },
    }
    resp = client.post("/webhook/github", json=comment_payload)
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "dispatched"
    assert data["type"] == "pr_fix"
    assert data["issue_number"] == 42
