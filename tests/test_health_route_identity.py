"""Stage 6.6C: authoritative /health is main.py (not base_router shadow)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_handler_is_main_not_legacy_base_router():
    """GET /health must expose Redis-aware main.py schema, not 0.1.0 base_router."""
    from app.main import app

    # Prefer route inspection (no full lifespan/redis required for path ownership)
    paths = []
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        if path == "/health" and "GET" in methods:
            paths.append(r)
    assert paths, "no GET /health registered"
    # Only one GET /health should remain after removing base_router duplicate
    assert len(paths) == 1, f"duplicate /health routes: {paths!r}"

    # Endpoint callable should be main.health (name check)
    endpoint = getattr(paths[0], "endpoint", None)
    assert endpoint is not None
    assert endpoint.__module__ == "app.main", endpoint.__module__
    assert endpoint.__name__ == "health"


def test_root_handler_is_main():
    from app.main import app

    roots = [
        r
        for r in app.routes
        if getattr(r, "path", None) == "/" and "GET" in (getattr(r, "methods", None) or set())
    ]
    assert len(roots) == 1, roots
    assert roots[0].endpoint.__module__ == "app.main"
