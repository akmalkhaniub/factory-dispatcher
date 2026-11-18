"""Tests for HMAC-SHA256 webhook signature verification, repo allowlist, and dashboard UI."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from dispatcher.security import compute_github_signature, is_repo_allowed, verify_github_signature
from dispatcher.server import app


def test_hmac_signature_verification_unit() -> None:
    body = b'{"action":"opened"}'
    secret = "super-secret-key"
    sig = compute_github_signature(body, secret)

    ok, status = verify_github_signature(body, sig, secret=secret)
    assert ok is True
    assert status == "verified"

    bad_ok, _ = verify_github_signature(body, "sha256=deadbeef", secret=secret)
    assert bad_ok is False

    missing_ok, _ = verify_github_signature(body, None, secret=secret)
    assert missing_ok is False


def test_webhook_hmac_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-webhook-secret-123"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("DISPATCHER_SIMULATE_GITHUB", "true")

    client = TestClient(app)
    payload = {
        "action": "opened",
        "repository": {"full_name": "akmalkhaniub/webhook-service"},
        "issue": {"number": 5, "title": "Docs typo", "body": "Fix typo", "labels": []},
    }
    raw = json.dumps(payload).encode("utf-8")

    # Missing signature -> 401
    r_missing = client.post("/webhook/github", content=raw, headers={"Content-Type": "application/json"})
    assert r_missing.status_code == 401

    # Tampered signature -> 401
    r_bad = client.post(
        "/webhook/github",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=0000"},
    )
    assert r_bad.status_code == 401

    # Valid signature -> 202
    valid_sig = compute_github_signature(raw, secret)
    r_ok = client.post(
        "/webhook/github",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig},
    )
    assert r_ok.status_code == 202
    assert r_ok.json()["status"] == "ignored"


def test_repo_allowlist_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPATCHER_ALLOWED_REPOS", "akmalkhaniub/*,trusted-org/core")
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)

    assert is_repo_allowed("akmalkhaniub/mcp-gateway")[0] is True
    assert is_repo_allowed("evil-org/random-repo")[0] is False

    client = TestClient(app)
    resp = client.post(
        "/api/dispatch",
        json={
            "repo_name": "evil-org/random-repo",
            "goal": "Unauthorized task attempt",
            "simulate_github": True,
        },
    )
    assert resp.status_code == 403


def test_dashboard_ui_and_task_detail_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "enforce-me")
    client = TestClient(app)

    ui = client.get("/")
    assert ui.status_code == 200
    assert "Factory Dispatcher" in ui.text

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["webhook_signature_enforced"] is True

    not_found = client.get("/api/tasks/non-existent-task")
    assert not_found.status_code == 404
