"""FastAPI Webhook Server for GitHub Issue-to-PR Automation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .engine import IssueDispatcher
from .models import DispatchResult, GitHubWebhookPayload
from .security import is_repo_allowed, verify_github_signature

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Attractor Factory Dispatcher",
    description="Event-Driven GitHub Issue-to-PR Automation Server with HMAC-SHA256 verification and policy guardrails.",
    version="0.2.0",
)

dispatcher = IssueDispatcher()


class DirectDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    repo_name: str = Field(..., description="GitHub repository 'owner/repo' or local path")
    goal: str = Field(..., min_length=5, description="Issue task or objective")
    issue_number: int | None = Field(default=None)
    custom_dot: str | None = Field(default=None)
    simulate_github: bool = Field(default=False)


@app.get("/", response_class=HTMLResponse)
async def operator_dashboard() -> HTMLResponse:
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Attractor Factory Dispatcher</h1><p>Status: Online</p>")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "factory-dispatcher",
        "version": "0.2.0",
        "tasks_count": len(dispatcher.tasks),
        "webhook_signature_enforced": bool(os.environ.get("GITHUB_WEBHOOK_SECRET", "")),
        "repo_allowlist_enforced": bool(os.environ.get("DISPATCHER_ALLOWED_REPOS", "")),
    }


@app.get("/api/tasks")
async def list_tasks() -> dict[str, Any]:
    return {"tasks": [t.model_dump() for t in dispatcher.tasks.values()]}


@app.get("/api/tasks/{task_id}")
async def get_task_detail(task_id: str) -> dict[str, Any]:
    task = dispatcher.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task.model_dump()


@app.post("/api/dispatch", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_task(payload: DirectDispatchRequest) -> dict[str, Any]:
    allowed, reason = is_repo_allowed(payload.repo_name)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

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
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Receives GitHub webhook events for issues and comments with HMAC-SHA256 verification."""
    raw_body = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256")
    sig_ok, sig_reason = verify_github_signature(raw_body, sig_header)
    if not sig_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=sig_reason)

    try:
        payload = GitHubWebhookPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

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
    allowed, allow_reason = is_repo_allowed(repo)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=allow_reason)

    issue_no = payload.issue_number
    simulate_mode = os.environ.get("DISPATCHER_SIMULATE_GITHUB", "false").lower() == "true"
    task_mode = "pr_fix" if payload.is_pull_request else "new_issue"

    # Execute in background
    background_tasks.add_task(
        dispatcher.dispatch,
        repo_name=repo,
        goal=goal,
        issue_number=issue_no,
        simulate_github=simulate_mode,
        mode=task_mode,
    )

    return {
        "status": "dispatched",
        "type": task_mode,
        "repo": repo,
        "issue_number": issue_no,
        "goal": goal,
        "signature_status": sig_reason,
    }
