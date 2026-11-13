# Attractor Factory Dispatcher

An autonomous **GitHub Issue-to-PR automation dispatcher** powered by the [Attractor Software Factory](https://github.com/akmalkhaniub/attractor-factory).

## Architecture

```
GitHub Issue (labeled 'factory-build')
          │
          ▼
Factory Dispatcher (FastAPI Webhook Server)
          │
          ├── 1. Prepares isolated git worktree sandbox
          ├── 2. Dispatches Attractor DOT Software Factory
          ├── 3. Executes coding agent & runs pytest suite
          └── 4. Pushes branch 'factory/issue-<id>' & Opens Pull Request
          │
          ▼
Verified Pull Request with Test Receipts
```

## Features

- **Event-Driven GitHub Webhook**: Triggers automatically on issues labeled `factory-build`, `needs-ai`, or comments containing `@factory` / `/factory`.
- **Self-Healing PR Comment Repair**: Responds to review comments on PRs like `/factory fix <instructions>`, checks out the PR branch, repairs the code, and pushes updates directly.
- **Ephemeral Sandbox Isolation**: Creates dedicated worktree environments so concurrent tasks do not collide.
- **Direct REST API & CLI**: Dispatch tasks on-demand via `POST /api/dispatch` or `python -m dispatcher.cli`.
- **Test-Gated PR Opening**: Only opens Pull Requests if 100% of automated unit tests pass.

## Running Tests

```bash
uv run --extra dev pytest tests -v
```

## Running the Webhook Server

```bash
uv run uvicorn dispatcher.server:app --port 8080
```
