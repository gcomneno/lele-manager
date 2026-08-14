from pathlib import Path

path = Path("src/lele_manager/core/vault_danger.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        '''    canonical = read_canonical_markdown_files(target.vault_dir)\n    tree_entries: tuple[str, ...] = ()\n''',
        '''    try:\n        canonical = read_canonical_markdown_files(target.vault_dir)\n    except SnapshotTargetError as exc:\n        raise VaultDangerTargetError(str(exc)) from exc\n    tree_entries: tuple[str, ...] = ()\n''',
    ),
    (
        '''    if destination is not None:\n        destination_canonical = read_canonical_markdown_files(destination.vault_dir)\n        _verify_merged_source(canonical, destination_canonical)\n        merge_verified = True\n''',
        '''    if destination is not None:\n        try:\n            destination_canonical = read_canonical_markdown_files(destination.vault_dir)\n        except SnapshotTargetError as exc:\n            raise VaultDangerTargetError(\n                "destination Vault is unavailable or unsafe"\n            ) from exc\n        _verify_merged_source(canonical, destination_canonical)\n        merge_verified = True\n''',
    ),
    (
        '''    current = preview_vault_danger(\n        operation=operation,\n        target=target,\n        active_vault_id=active_vault_id,\n        decisions=decisions,\n        destination=destination,\n    )\n    if current.plan_digest != plan_digest:\n''',
        '''    try:\n        current = preview_vault_danger(\n            operation=operation,\n            target=target,\n            active_vault_id=active_vault_id,\n            decisions=decisions,\n            destination=destination,\n        )\n    except (\n        VaultDangerMergeVerificationError,\n        VaultDangerTargetError,\n        SnapshotTargetError,\n    ) as exc:\n        raise VaultDangerPlanStaleError(\n            "danger-zone target or managed state changed after preview"\n        ) from exc\n    if current.plan_digest != plan_digest:\n''',
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one guarded anchor, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("issue #194 error-boundary fixes applied")
