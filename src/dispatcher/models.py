"""Data models for GitHub webhook dispatching and automated PR lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DispatchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    VERIFIED = "verified"
    PR_OPENED = "pr_opened"
    FAILED = "failed"


class GitHubWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str = ""
    repository: dict[str, Any] = Field(default_factory=dict)
    issue: dict[str, Any] | None = None
    comment: dict[str, Any] | None = None
    sender: dict[str, Any] = Field(default_factory=dict)

    @property
    def repo_full_name(self) -> str:
        return str(self.repository.get("full_name", ""))

    @property
    def repo_clone_url(self) -> str:
        return str(self.repository.get("clone_url", ""))

    @property
    def issue_number(self) -> int | None:
        if self.issue:
            return self.issue.get("number")
        return None

    @property
    def issue_title(self) -> str:
        if self.issue:
            return str(self.issue.get("title", ""))
        return ""

    @property
    def issue_body(self) -> str:
        if self.issue:
            return str(self.issue.get("body", ""))
        return ""

    @property
    def labels(self) -> list[str]:
        if self.issue:
            return [str(lbl.get("name", "")) for lbl in self.issue.get("labels", [])]
        return []


class DispatchTask(BaseModel):
    task_id: str
    repo_name: str
    issue_number: int | None
    goal: str
    branch_name: str
    status: DispatchStatus = DispatchStatus.PENDING
    worktree_path: str = ""
    pr_url: str | None = None
    failure_reason: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    logs: list[str] = Field(default_factory=list)


class DispatchResult(BaseModel):
    task_id: str
    status: DispatchStatus
    branch: str
    pr_url: str | None = None
    tests_passed: bool = False
    notes: str = ""
    receipt: dict[str, Any] = Field(default_factory=dict)
