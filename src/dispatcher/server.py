"""FastAPI Webhook Server for GitHub Issue-to-PR Automation."""

from __future__ import annotations

import os
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from .engine import IssueDispatcher
from .models import DispatchResult, GitHubWebhookPayload

app = FastAPI(
    title="Attractor Factory Dispatcher",
    description="Event-Driven GitHub Issue-to-PR Automation Server",
    version="0.1.0",
)

dispatcher = IssueDispatcher()


class DirectDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    repo_name: str = Field(..., description="GitHub repository 'owner/repo' or local path")
    goal: str = Field(..., min_length=5, description="Issue task or objective")
    issue_number: int | None = Field(default=None)
    custom_dot: str | None = Field(default=None)
    simulate_github: bool = Field(default=False)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "factory-dispatcher"}


@app.get("/api/tasks")
async def list_tasks() -> dict[str, Any]:
    return {"tasks": [t.model_dump() for t in dispatcher.tasks.values()]}


@app.post("/api/dispatch", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_task(payload: DirectDispatchRequest) -> dict[str, Any]:
    res = dispatcher.dispatch(
        repo_name=payload.repo_name,
        goal=payload.goal,
        issue_number=payload.issue_number,
        custom_dot=payload.custom_dot,
        simulate_github=payload.simulate_github,
    )
    return res.model_dump()


@app.post("/webhook/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    payload: GitHubWebhookPayload, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Receives GitHub webhook events for issues and comments."""
    action = payload.action
    labels = payload.labels

    should_dispatch = False
    goal = payload.issue_title

    if action in ("labeled", "opened") and any(
        lbl.lower() in ("factory-build", "needs-ai", "autofix") for lbl in labels
    ):
        should_dispatch = True
        goal = f"{payload.issue_title}: {payload.issue_body}"
    elif action == "created" and payload.comment:
        comment_text = payload.comment.get("body", "").lower()
        if "@factory" in comment_text or "/factory" in comment_text:
            should_dispatch = True
            goal = f"{payload.issue_title}: {comment_text}"

    if not should_dispatch:
        return {
            "status": "ignored",
            "reason": f"Action '{action}' with labels {labels} did not trigger factory dispatch.",
        }

    repo = payload.repo_full_name
    issue_no = payload.issue_number
    simulate_mode = os.environ.get("DISPATCHER_SIMULATE_GITHUB", "false").lower() == "true"

    # Execute in background
    background_tasks.add_task(
        dispatcher.dispatch,
        repo_name=repo,
        goal=goal,
        issue_number=issue_no,
        simulate_github=simulate_mode,
    )

    return {
        "status": "dispatched",
        "repo": repo,
        "issue_number": issue_no,
        "goal": goal,
    }
