"""CLI entrypoint for the Factory Dispatcher."""

from __future__ import annotations

import argparse
import sys

from .engine import IssueDispatcher


def main() -> None:
    parser = argparse.ArgumentParser(description="Attractor Issue-to-PR Dispatcher")
    parser.add_argument("--repo", required=True, help="GitHub repo 'owner/repo' or local path")
    parser.add_argument("--goal", required=True, help="Task description or issue objective")
    parser.add_argument("--issue", type=int, default=None, help="Issue number")
    parser.add_argument("--simulate", action="store_true", help="Simulate GitHub API / push")
    args = parser.parse_args()

    dispatcher = IssueDispatcher()
    print(f"🚀 Dispatching Attractor Factory for {args.repo} (Issue #{args.issue})...")
    res = dispatcher.dispatch(
        repo_name=args.repo,
        goal=args.goal,
        issue_number=args.issue,
        simulate_github=args.simulate,
    )
    print(f"Result: {res.status.value}")
    print(f"Branch: {res.branch}")
    print(f"PR URL: {res.pr_url}")
    print(f"Notes: {res.notes}")
    if not res.tests_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
