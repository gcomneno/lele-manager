"""Shared exclusion boundary for maintained canonical Markdown mutations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock


_LOCK = RLock()


@contextmanager
def canonical_mutation_boundary() -> Iterator[None]:
    """Serialize maintained mutations of canonical Vault Markdown.

    The boundary protects application-managed check-then-act sequences such as
    exact-byte verification followed by deletion. It does not claim atomicity
    against unrelated external processes modifying the filesystem.
    """
    with _LOCK:
        yield
