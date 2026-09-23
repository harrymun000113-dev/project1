"""TTL caching utilities.

Three flavors are provided, all sharing the same "never let a broken cache
crash the pipeline" principle:

- ``ttl_cache``      : in-memory only. Cheap, per-process. Used for the small
                       / high-frequency lookups (FX day snapshots, yfinance
                       batches, tariff crawl results before they are also
                       persisted to disk).
- ``disk_json_cache``: JSON file per call, survives process restarts. Used
                       for tariff results and the final `/api/analyze`
                       payload.
- ``parquet_cache``  : DataFrame-returning functions (Comtrade raw pulls),
                       persisted as Parquet.

Every decorator: (1) never caches a "failed" result unless the caller's
``cache_if`` says so, and (2) if the on-disk cache file itself is corrupt or
unreadable, treats that as a cache miss instead of raising.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

log = logging.getLogger(__name__)

_store: dict[tuple, tuple[float, Any]] = {}
_lock = threading.Lock()


def ttl_cache(ttl: int, cache_if: Callable[[Any], bool] = lambda r: True):
    """In-memory TTL cache keyed by (qualified function name, args, kwargs).

    Args/kwargs must be hashable. ``cache_if(result)`` decides whether a
    given result is worth keeping (e.g. skip caching empty/failed results so
    the next call retries immediately).
    """

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__qualname__, args, tuple(sorted(kwargs.items())))
            now = time.time()
            with _lock:
                hit = _store.get(key)
                if hit and now - hit[0] < ttl:
                    return hit[1]
            result = fn(*args, **kwargs)
            try:
                keep = cache_if(result)
            except Exception:  # a bad predicate should not break the call
                keep = False
            if keep:
                with _lock:
                    _store[key] = (now, result)
            return result

        wrapper.cache_clear = lambda: _store.clear()  # test helper
        return wrapper

    return deco


def _stable_key(prefix: str, *parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def disk_json_cache(cache_dir: Path, ttl: int, cache_if: Callable[[Any], bool] = lambda r: True):
    """JSON-file backed TTL cache. Result must be JSON-serializable."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            cache_dir.mkdir(parents=True, exist_ok=True)
            path = cache_dir / f"{_stable_key(fn.__name__, args, kwargs)}.json"
            if path.exists():
                try:
                    age = time.time() - path.stat().st_mtime
                    if age < ttl:
                        with path.open("r", encoding="utf-8") as fh:
                            return json.load(fh)
                except (OSError, json.JSONDecodeError) as e:
                    log.warning("cache read failed for %s, recomputing: %s", path, e)

            result = fn(*args, **kwargs)
            try:
                if cache_if(result):
                    tmp = path.with_suffix(".tmp")
                    with tmp.open("w", encoding="utf-8") as fh:
                        json.dump(result, fh, ensure_ascii=False)
                    tmp.replace(path)
            except (OSError, TypeError) as e:
                log.warning("cache write failed for %s: %s", path, e)
            return result

        return wrapper

    return deco


def parquet_cache(cache_dir: Path, ttl: int, cache_if: Callable[[pd.DataFrame], bool] = lambda df: not df.empty):
    """Parquet-file backed TTL cache for DataFrame-returning functions."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            cache_dir.mkdir(parents=True, exist_ok=True)
            path = cache_dir / f"{_stable_key(fn.__name__, args, kwargs)}.parquet"
            if path.exists():
                try:
                    age = time.time() - path.stat().st_mtime
                    if age < ttl:
                        return pd.read_parquet(path)
                except Exception as e:  # corrupt file, missing engine, etc.
                    log.warning("parquet cache read failed for %s, recomputing: %s", path, e)

            result = fn(*args, **kwargs)
            try:
                if isinstance(result, pd.DataFrame) and cache_if(result):
                    tmp = path.with_suffix(".tmp")
                    result.to_parquet(tmp)
                    tmp.replace(path)
            except Exception as e:
                log.warning("parquet cache write failed for %s: %s", path, e)
            return result

        return wrapper

    return deco


def _path_for_key(key: str, cache_dir: Path) -> Path:
    return cache_dir / f"{hashlib.sha1(key.encode()).hexdigest()[:20]}.json"


def peek(key: str, cache_dir: Path, ttl: int) -> dict | None:
    """Non-computing read: returns the cached value if fresh, else None."""
    path = _path_for_key(key, cache_dir)
    if not path.exists():
        return None
    try:
        if time.time() - path.stat().st_mtime >= ttl:
            return None
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("meta", {})["stale"] = False
        return data
    except (OSError, json.JSONDecodeError) as e:
        log.warning("cache peek failed for %s: %s", key, e)
        return None


def get_or_compute(key: str, compute: Callable[[], dict], ttl: int, cache_dir: Path) -> dict:
    """One-off helper (not a decorator) for keying by a single string, e.g.
    the final `/api/analyze` response cached by `hs6`."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _path_for_key(key, cache_dir)
    if path.exists():
        try:
            if time.time() - path.stat().st_mtime < ttl:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    data.setdefault("meta", {})["stale"] = False
                    return data
        except (OSError, json.JSONDecodeError) as e:
            log.warning("analyze cache read failed for %s: %s", key, e)

    try:
        result = compute()
    except Exception:
        # Compute failed outright: fall back to a stale cached copy if we have
        # one at all, rather than a hard 500 (§6.5 Comtrade 한도초과/전 키 소진).
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                data.setdefault("meta", {})["stale"] = True
                log.warning("analyze compute failed for %s, serving stale cache", key)
                return data
            except (OSError, json.JSONDecodeError):
                pass
        raise

    try:
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False)
        tmp.replace(path)
    except (OSError, TypeError) as e:
        log.warning("analyze cache write failed for %s: %s", key, e)
    return result
