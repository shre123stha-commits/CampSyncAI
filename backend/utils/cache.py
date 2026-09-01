"""Disk cache for deterministic, expensive work.

Document extraction is the slowest part of the pipeline (two LLM calls) and is
*deterministic for a given document*. Caching it keyed by a fingerprint of the
source files removes both calls from every request after the first, leaving
only the planning call.

The cache is plain JSON on disk: no server to run, easy to inspect, and safe
to delete at any time.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from config import CACHE_DIR, CACHE_ENABLED, get_logger

logger = get_logger(__name__)


def fingerprint_files(*paths: Path) -> str:
    """A short hash of the identity of *paths* (name, size, mtime).

    Cheaper than hashing contents, and sufficient: any edit changes the size
    or the modification time.
    """
    parts: list[str] = []

    for path in sorted(paths, key=str):
        if path.exists():
            stat = path.stat()
            parts.append(f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}")
        else:
            parts.append(f"{path.name}:missing")

    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()

    return digest[:16]


def _cache_path(namespace: str, key: str) -> Path:
    safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
    return Path(CACHE_DIR) / namespace / f"{safe_key}.json"


def cache_get(namespace: str, key: str) -> Any | None:
    """Return the cached value, or None on a miss."""
    if not CACHE_ENABLED:
        return None

    path = _cache_path(namespace, key)

    if not path.exists():
        return None

    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Discarding unreadable cache entry %s: %s", path, exc)
        path.unlink(missing_ok=True)
        return None

    logger.info("Cache hit: %s/%s", namespace, key)

    return payload


def cache_set(namespace: str, key: str, value: Any) -> None:
    """Store *value*. Failures are logged and ignored - a cache must never
    break the request that populates it."""
    if not CACHE_ENABLED:
        return

    path = _cache_path(namespace, key)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically so a crash cannot leave a truncated file behind.
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            json.dump(value, handle, ensure_ascii=False)
            temp_name = handle.name

        os.replace(temp_name, path)

        logger.info("Cache write: %s/%s", namespace, key)

    except OSError as exc:
        logger.warning("Could not write cache entry %s: %s", path, exc)


def cache_clear(namespace: str | None = None, key: str | None = None) -> int:
    """Delete cache entries. Returns how many files were removed."""
    root = Path(CACHE_DIR)

    if not root.exists():
        return 0

    if namespace and key:
        target = _cache_path(namespace, key)
        if target.exists():
            target.unlink()
            return 1
        return 0

    search_root = root / namespace if namespace else root

    if not search_root.exists():
        return 0

    removed = 0
    for entry in search_root.rglob("*.json"):
        entry.unlink()
        removed += 1

    return removed
