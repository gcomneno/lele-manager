"""Configured aggregate refresh backed by the existing vault-to-JSONL import."""

from __future__ import annotations

from pathlib import Path

from lele_manager.application.candidate_approval import (
    DerivedRefreshPortError,
    RefreshOutcome,
)
from lele_manager.core.vault import import_vault_to_jsonl
from lele_manager.core.projection_store import ProjectionStoreError


class VaultJsonlRefresh:
    def __init__(self, vault_dir: Path, output_path: Path) -> None:
        self._vault_dir = vault_dir
        self._output_path = output_path

    def refresh(self) -> RefreshOutcome:
        try:
            import_vault_to_jsonl(self._vault_dir, self._output_path)
        except (OSError, UnicodeError, ProjectionStoreError):
            raise DerivedRefreshPortError("configured refresh failed") from None
        return RefreshOutcome()
