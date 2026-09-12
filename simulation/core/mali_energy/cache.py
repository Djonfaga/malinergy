"""HTTP fetching with an auditable on-disk cache.

Reproducibility rule of the project: a simulation must be re-runnable months
later and produce the same numbers. Every remote payload is therefore written
to ``data/raw`` next to a ``.meta.json`` recording the URL, the retrieval time
and the SHA-256 of the bytes; downstream code reads the cache, never the
network, unless explicitly refreshed.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .config import RAW_DIR

DEFAULT_TIMEOUT = 60
DEFAULT_RETRIES = 4
USER_AGENT = "mali-energy-core/1.0 (power system study; contact: repository owner)"


class FetchError(RuntimeError):
    """Raised when a remote source cannot be reached after retries."""


@dataclass
class CachedFile:
    path: Path
    url: str
    sha256: str
    retrieved: str
    from_cache: bool

    @property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")

    @property
    def bytes(self) -> bytes:
        return self.path.read_bytes()

    def json(self) -> Any:
        return json.loads(self.text)


def _slug(url: str) -> str:
    parsed = urlparse(url)
    tail = (parsed.path.rsplit("/", 1)[-1] or "index").replace(":", "_")
    digest = hashlib.sha256(url.encode()).hexdigest()[:10]
    host = parsed.netloc.replace(":", "_")
    return f"{host}__{tail}__{digest}"


def fetch(
    url: str,
    *,
    filename: str | None = None,
    refresh: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    params: dict | None = None,
    headers: dict | None = None,
    subdir: str = "",
) -> CachedFile:
    """Download ``url`` once and reuse the cached copy afterwards.

    Parameters
    ----------
    refresh:
        Ignore an existing cache entry and re-download.
    subdir:
        Optional folder under ``data/raw`` to keep sources tidy.
    """
    target_dir = RAW_DIR / subdir if subdir else RAW_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    name = filename or _slug(url)
    path = target_dir / name
    meta_path = path.with_suffix(path.suffix + ".meta.json")

    if path.exists() and meta_path.exists() and not refresh:
        meta = json.loads(meta_path.read_text())
        return CachedFile(
            path=path,
            url=meta.get("url", url),
            sha256=meta.get("sha256", ""),
            retrieved=meta.get("retrieved", ""),
            from_cache=True,
        )

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT, **(headers or {})},
            )
            response.raise_for_status()
            payload = response.content
            break
        except Exception as exc:
            last_error = exc
            if attempt == retries - 1:
                raise FetchError(
                    f"could not fetch {url} after {retries} attempts: {exc}. "
                    "If this host is blocked by a network policy, run the fetch "
                    "from an unrestricted machine and copy data/raw across."
                ) from exc
            time.sleep(2**attempt)
    else:  # pragma: no cover - defensive
        raise FetchError(str(last_error))

    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    meta_path.write_text(
        json.dumps(
            {
                "url": url,
                "params": params or {},
                "sha256": digest,
                "bytes": len(payload),
                "retrieved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
        )
    )
    return CachedFile(
        path=path,
        url=url,
        sha256=digest,
        retrieved=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        from_cache=False,
    )


def cached_only(url: str, *, filename: str | None = None, subdir: str = "") -> CachedFile | None:
    """Return the cache entry for ``url`` if present, without touching the network."""
    target_dir = RAW_DIR / subdir if subdir else RAW_DIR
    path = target_dir / (filename or _slug(url))
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if not (path.exists() and meta_path.exists()):
        return None
    meta = json.loads(meta_path.read_text())
    return CachedFile(
        path=path,
        url=meta.get("url", url),
        sha256=meta.get("sha256", ""),
        retrieved=meta.get("retrieved", ""),
        from_cache=True,
    )


def inventory() -> list[dict]:
    """List every cached payload with its checksum, for the reproducibility log."""
    rows = []
    for meta_path in sorted(RAW_DIR.rglob("*.meta.json")):
        meta = json.loads(meta_path.read_text())
        rows.append(
            {
                "file": str(meta_path.with_suffix("").relative_to(RAW_DIR)),
                "url": meta.get("url", ""),
                "sha256": meta.get("sha256", "")[:16],
                "bytes": meta.get("bytes", 0),
                "retrieved": meta.get("retrieved", ""),
            }
        )
    return rows
