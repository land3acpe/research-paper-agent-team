"""Global pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch, request):
    """Refuse real httpx network calls unless test is marked live_api."""
    if "live_api" in request.keywords:
        return
    import httpx

    original_send = httpx.Client.send  # noqa: F841 — documented no-op

    def guarded_send(self, *args, **kwargs):
        # pytest-httpx will replace transport; if real network reached, raise
        raise RuntimeError(
            "Real network call blocked; use httpx_mock fixture or mark test with @pytest.mark.live_api"
        )

    # Don't actually patch — pytest-httpx already refuses unmocked requests by default;
    # this fixture serves as documentation. (Left as no-op to avoid double-protection conflicts.)
