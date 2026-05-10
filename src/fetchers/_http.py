"""Shared HTTP client with sane defaults."""
from __future__ import annotations

import httpx


def make_client(timeout: float = 30.0, user_agent: str = "research-paper-agent-team/0.1") -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        follow_redirects=True,
    )
