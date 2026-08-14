from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/lele_manager/api/tritalele.py",
    "from lele_manager.core.vault_registry import ActiveVaultContext, active_vault_context\n",
    "from lele_manager.api.vault_danger import router as vault_danger_router\nfrom lele_manager.core.vault_registry import ActiveVaultContext, active_vault_context\n",
)
replace_once(
    "src/lele_manager/api/tritalele.py",
    "from lele_manager.api.vault_danger import router as vault_danger_router\n\n_application_router = APIRouter()\n",
    "_application_router = APIRouter()\n",
)

replace_once(
    "src/lele_manager/core/vault_danger.py",
    """    if operation in (\"delete\", \"merge_delete_source\") and target.vault_id == active_vault_id:\n        raise VaultDangerError(\"activate another Vault before deleting this Vault from disk\")\n""",
    """    if operation in (\"delete\", \"merge_delete_source\") and target.vault_id == active_vault_id:\n        raise VaultDangerTargetError(\"activate another Vault before deleting this Vault from disk\")\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """def _delete_canonical_set(root: Path, canonical: dict[str, bytes]) -> tuple[int, str | None]:\n    _verify_all_canonical(root, canonical)\n    deleted = 0\n""",
    """def _delete_canonical_set(root: Path, canonical: dict[str, bytes]) -> tuple[int, str | None]:\n    try:\n        _verify_all_canonical(root, canonical)\n    except (SnapshotPlanStaleError, SnapshotTargetError) as exc:\n        raise VaultDangerPlanStaleError(\n            \"canonical state changed after destructive preflight\"\n        ) from exc\n    deleted = 0\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """    vault_directory_deleted: bool | None\n    registry_removed: bool | None\n""",
    """    vault_directory_deleted: bool | None\n    vault_directory_error: str | None\n    registry_removed: bool | None\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """    directory_deleted: bool | None = None\n    registry_removed: bool | None = None\n""",
    """    directory_deleted: bool | None = None\n    directory_error: str | None = None\n    registry_removed: bool | None = None\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """            None,\n            None,\n            None,\n        )\n\n    if operation == \"reset\":""",
    """            None,\n            None,\n            None,\n            None,\n        )\n\n    if operation == \"reset\":""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """            None,\n            None,\n            None,\n        )\n\n    tree_entries = _scan_managed_tree""",
    """            None,\n            None,\n            None,\n            None,\n        )\n\n    tree_entries = _scan_managed_tree""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """        except VaultDangerTargetError as exc:\n            directory_deleted = False\n            canonical_error = str(exc)\n""",
    """        except VaultDangerTargetError as exc:\n            directory_deleted = False\n            directory_error = str(exc)\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """        directory_deleted,\n        registry_removed,\n        registry_error,\n""",
    """        directory_deleted,\n        directory_error,\n        registry_removed,\n        registry_error,\n""",
)

replace_once(
    "src/lele_manager/api/vault_danger.py",
    """    vault_directory_deleted: bool | None = None\n    registry_removed: bool | None = None\n""",
    """    vault_directory_deleted: bool | None = None\n    vault_directory_error: str | None = None\n    registry_removed: bool | None = None\n""",
)
replace_once(
    "src/lele_manager/api/vault_danger.py",
    """        vault_directory_deleted=result.vault_directory_deleted,\n        registry_removed=result.registry_removed,\n""",
    """        vault_directory_deleted=result.vault_directory_deleted,\n        vault_directory_error=result.vault_directory_error,\n        registry_removed=result.registry_removed,\n""",
)

replace_once(
    "frontend/src/lib/api.ts",
    """  vault_directory_deleted: boolean | null\n  registry_removed: boolean | null\n""",
    """  vault_directory_deleted: boolean | null\n  vault_directory_error: string | null\n  registry_removed: boolean | null\n""",
)

print("issue #194 hardening patch applied")
