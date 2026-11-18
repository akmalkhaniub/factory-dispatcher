"""Webhook HMAC-SHA256 signature verification and repository policy guardrails."""

from __future__ import annotations

import fnmatch
import hashlib
import hmac
import os


def compute_github_signature(payload_body: bytes, secret: str) -> str:
    """Compute GitHub X-Hub-Signature-256 header value for a raw body and secret."""
    mac = hmac.new(secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_github_signature(
    payload_body: bytes,
    signature_header: str | None,
    secret: str | None = None,
) -> tuple[bool, str]:
    """Verify GitHub webhook X-Hub-Signature-256 using constant-time comparison.

    When no secret is configured (both argument and GITHUB_WEBHOOK_SECRET env var empty),
    verification succeeds in development mode.
    """
    active_secret = secret if secret is not None else os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not active_secret:
        return True, "unverified_dev_mode"

    if not signature_header:
        return False, "Missing X-Hub-Signature-256 header."

    if not signature_header.startswith("sha256="):
        return False, "Invalid signature format; expected 'sha256=<hex>'."

    expected = compute_github_signature(payload_body, active_secret)
    if hmac.compare_digest(expected, signature_header.strip()):
        return True, "verified"
    return False, "Webhook signature mismatch."


def is_repo_allowed(repo_name: str, allowed_patterns_csv: str | None = None) -> tuple[bool, str]:
    """Check whether a repository matches DISPATCHER_ALLOWED_REPOS allowlist patterns."""
    raw = (
        allowed_patterns_csv
        if allowed_patterns_csv is not None
        else os.environ.get("DISPATCHER_ALLOWED_REPOS", "")
    )
    patterns = [p.strip() for p in raw.split(",") if p.strip()]
    if not patterns:
        return True, "allowlist_unrestricted"

    for pat in patterns:
        if fnmatch.fnmatch(repo_name.lower(), pat.lower()):
            return True, f"matched:{pat}"

    return False, f"Repository '{repo_name}' is not permitted by allowlist ({', '.join(patterns)})."
