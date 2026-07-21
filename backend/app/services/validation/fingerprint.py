"""
SHA-256 fingerprinting for uploaded files.

Used for idempotency: if an uploaded file's hash matches the currently
active version for its file type, the upload is a no-op ("already
uploaded, no changes") instead of creating a redundant dataset version.
This also makes re-submitting the same upload after a network hiccup
safe rather than silently duplicating a version.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | Path) -> str:
    """Return the hex SHA-256 digest of a file, read in chunks."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of an in-memory byte string."""
    return hashlib.sha256(data).hexdigest()
