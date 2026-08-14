from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, expected: int) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} anchors, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


# Pure registry resolution: preview must never bootstrap the data directory.
replace_once(
    "src/lele_manager/api/vault_danger.py",
    """def _store() -> VaultRegistryStore:\n    return VaultRegistryStore()\n""",
    """def _store() -> VaultRegistryStore:\n    return VaultRegistryStore(resolved_data_dir() / \"vault-registry.json\")\n""",
)

# Bind exact captured canonical/editorial state to the preview used by execution.
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """    approved_count: int\n    filesystem_entry_count: int\n    candidate_state_present: bool\n    duplicate_decision_count: int\n""",
    """    approved_count: int\n    canonical_digest: str\n    filesystem_entry_count: int\n    candidate_state_present: bool\n    candidate_sha256: str | None\n    duplicate_decision_count: int\n    duplicate_decisions_digest: str | None\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """def _canonical_state(files: dict[str, bytes]) -> list[dict[str, str]]:\n    return [\n        {\"path\": path, \"sha256\": _sha(data)}\n        for path, data in sorted(files.items())\n    ]\n\n\ndef _confirmation""",
    """def _canonical_state(files: dict[str, bytes]) -> list[dict[str, str]]:\n    return [\n        {\"path\": path, \"sha256\": _sha(data)}\n        for path, data in sorted(files.items())\n    ]\n\n\ndef _canonical_digest(files: dict[str, bytes]) -> str:\n    return _sha((canonical_json(_canonical_state(files)) + \"\\n\").encode(\"utf-8\"))\n\n\ndef _decisions_digest(entries: list[dict[str, str]]) -> str:\n    return _sha((canonical_json(entries) + \"\\n\").encode(\"utf-8\"))\n\n\ndef _confirmation""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """        approved_count=len(canonical),\n        filesystem_entry_count=len(tree_entries),\n        candidate_state_present=candidate_state is not None,\n        duplicate_decision_count=len(decision_entries),\n""",
    """        approved_count=len(canonical),\n        canonical_digest=_canonical_digest(canonical),\n        filesystem_entry_count=len(tree_entries),\n        candidate_state_present=candidate_state is not None,\n        candidate_sha256=_sha(candidate_state) if candidate_state is not None else None,\n        duplicate_decision_count=len(decision_entries),\n        duplicate_decisions_digest=(\n            _decisions_digest(decision_entries)\n            if operation in (\"reset\", \"delete\", \"merge_delete_source\")\n            else None\n        ),\n""",
)

# Preserve changed editorial state instead of deleting data not present in the plan.
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """def _clear_editorial(context: ActiveVaultContext, decisions: DuplicateDecisionStore) -> tuple[bool, str | None]:\n    errors: list[str] = []\n""",
    """def _clear_editorial(\n    context: ActiveVaultContext,\n    decisions: DuplicateDecisionStore,\n    *,\n    expected_candidate_state: bytes | None,\n    expected_decisions: list[dict[str, str]],\n) -> tuple[bool, str | None]:\n    current_candidate_state = _read_scoped_state_file(context.candidates_path, \"candidate state\")\n    current_decisions = decisions.export_scope(context.duplicate_decision_scope)\n    if current_candidate_state != expected_candidate_state or current_decisions != expected_decisions:\n        return False, \"editorial state changed after preview; newer state was preserved\"\n    errors: list[str] = []\n""",
)
replace_count(
    "src/lele_manager/core/vault_danger.py",
    "_clear_editorial(final_target, decisions)",
    "_clear_editorial(\n                final_target,\n                decisions,\n                expected_candidate_state=expected_candidate_state,\n                expected_decisions=expected_decisions,\n            )",
    2,
)

# Stable-ID destination entries retain their canonical paths for immediate MOVE-delete proof.
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """def _lesson_ids(files: dict[str, bytes]) -> dict[str, bytes]:\n    result: dict[str, bytes] = {}\n""",
    """def _lesson_ids(files: dict[str, bytes]) -> dict[str, tuple[str, bytes]]:\n    result: dict[str, tuple[str, bytes]] = {}\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """        result[lesson_id] = raw\n    return result\n\n\ndef _verify_merged_source(source: dict[str, bytes], destination: dict[str, bytes]) -> None:\n    source_ids = _lesson_ids(source)\n    destination_ids = _lesson_ids(destination)\n    missing = [\n        lesson_id\n        for lesson_id, raw in sorted(source_ids.items())\n        if destination_ids.get(lesson_id) != raw\n    ]\n""",
    """        result[lesson_id] = (relative_path, raw)\n    return result\n\n\ndef _verify_merged_source(source: dict[str, bytes], destination: dict[str, bytes]) -> None:\n    source_ids = _lesson_ids(source)\n    destination_ids = _lesson_ids(destination)\n    missing = [\n        lesson_id\n        for lesson_id, (_source_path, raw) in sorted(source_ids.items())\n        if destination_ids.get(lesson_id) is None\n        or destination_ids[lesson_id][1] != raw\n    ]\n""",
)

replace_once(
    "src/lele_manager/core/vault_danger.py",
    """def _remove_empty_directories(root: Path, tree_entries: tuple[str, ...]) -> None:\n""",
    """def _delete_merged_source_set(\n    source_root: Path,\n    canonical: dict[str, bytes],\n    destination: ActiveVaultContext,\n) -> tuple[int, str | None]:\n    try:\n        _verify_all_canonical(source_root, canonical)\n        destination_entries = _lesson_ids(read_canonical_markdown_files(destination.vault_dir))\n        source_entries = _lesson_ids(canonical)\n    except (\n        SnapshotPlanStaleError,\n        SnapshotTargetError,\n        VaultDangerMergeVerificationError,\n    ) as exc:\n        raise VaultDangerPlanStaleError(\n            \"source or verified merge destination changed after destructive preflight\"\n        ) from exc\n\n    deleted = 0\n    for lesson_id, (source_path, raw) in sorted(source_entries.items()):\n        destination_entry = destination_entries.get(lesson_id)\n        if destination_entry is None or destination_entry[1] != raw:\n            return deleted, \"verified merge destination changed before source deletion\"\n        destination_path, _destination_raw = destination_entry\n        try:\n            verify_canonical_file(destination.vault_dir, destination_path, raw)\n        except (SnapshotPlanStaleError, SnapshotTargetError):\n            return deleted, \"verified merge destination changed before source deletion\"\n        try:\n            delete_canonical_file(source_root, source_path, raw)\n        except (SnapshotPlanStaleError, SnapshotTargetError) as exc:\n            return deleted, str(exc)\n        deleted += 1\n    return deleted, None\n\n\ndef _remove_empty_directories(root: Path, tree_entries: tuple[str, ...]) -> None:\n""",
)

# Revalidate after backup, bind the exact bytes we will delete, then use operation-specific deletion.
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """    canonical = read_canonical_markdown_files(final_target.vault_dir)\n    canonical_deleted, canonical_error = _delete_canonical_set(final_target.vault_dir, canonical)\n    canonical_complete = canonical_error is None and canonical_deleted == len(canonical)\n""",
    """    try:\n        post_backup_preview = preview_vault_danger(\n            operation=operation,\n            target=final_target,\n            active_vault_id=final_active_id,\n            decisions=decisions,\n            destination=final_destination,\n        )\n    except (VaultDangerError, SnapshotTargetError) as exc:\n        raise VaultDangerPlanStaleError(\n            \"danger-zone state changed before destructive mutation\"\n        ) from exc\n    if post_backup_preview.plan_digest != current.plan_digest:\n        raise VaultDangerPlanStaleError(\n            \"danger-zone state changed before destructive mutation\"\n        )\n    final_preview = post_backup_preview\n\n    expected_candidate_state: bytes | None = None\n    expected_decisions: list[dict[str, str]] = []\n    if operation in (\"reset\", \"delete\", \"merge_delete_source\"):\n        expected_candidate_state = _read_scoped_state_file(\n            final_target.candidates_path, \"candidate state\"\n        )\n        expected_decisions = decisions.export_scope(final_target.duplicate_decision_scope)\n        if (\n            (_sha(expected_candidate_state) if expected_candidate_state is not None else None)\n            != final_preview.candidate_sha256\n            or _decisions_digest(expected_decisions)\n            != final_preview.duplicate_decisions_digest\n        ):\n            raise VaultDangerPlanStaleError(\n                \"editorial state changed before destructive mutation\"\n            )\n\n    canonical = read_canonical_markdown_files(final_target.vault_dir)\n    if _canonical_digest(canonical) != final_preview.canonical_digest:\n        raise VaultDangerPlanStaleError(\n            \"canonical state changed before destructive mutation\"\n        )\n    if operation == \"merge_delete_source\":\n        assert final_destination is not None\n        canonical_deleted, canonical_error = _delete_merged_source_set(\n            final_target.vault_dir, canonical, final_destination\n        )\n    else:\n        canonical_deleted, canonical_error = _delete_canonical_set(\n            final_target.vault_dir, canonical\n        )\n    canonical_complete = canonical_error is None and canonical_deleted == len(canonical)\n""",
)

# A late foreign file after canonical success is a truthful partial result, never a masked error.
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """    tree_entries = _scan_managed_tree(final_target.vault_dir)\n    if canonical_complete:\n        try:\n            _remove_empty_directories(final_target.vault_dir, tree_entries)\n            directory_deleted = True\n        except VaultDangerTargetError as exc:\n            directory_deleted = False\n            directory_error = str(exc)\n    else:\n        directory_deleted = False\n""",
    """    if canonical_complete:\n        try:\n            tree_entries = _scan_managed_tree(final_target.vault_dir)\n            _remove_empty_directories(final_target.vault_dir, tree_entries)\n            directory_deleted = True\n        except VaultDangerTargetError as exc:\n            directory_deleted = False\n            directory_error = str(exc)\n    else:\n        directory_deleted = False\n""",
)

# Stable scope codes are localized by the GUI rather than leaking English domain prose.
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """        deletes = (\"all approved canonical Markdown lessons\", \"target Vault derived projection/model refreshed\")\n        keeps = (\"Vault registration\", \"Vault directory\", \"candidate staging\", \"duplicate decisions\")\n""",
    """        deletes = (\"canonical_markdown\", \"derived_refresh\")\n        keeps = (\"vault_registration\", \"vault_directory\", \"candidate_staging\", \"duplicate_decisions\")\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """        deletes = (\n            \"all approved canonical Markdown lessons\",\n            \"candidate staging\",\n            \"Vault-scoped duplicate decisions\",\n            \"Vault-scoped projection/model state\",\n        )\n        keeps = (\"Vault registration\", \"Vault directory\", \"global application configuration\")\n""",
    """        deletes = (\n            \"canonical_markdown\",\n            \"candidate_staging\",\n            \"duplicate_decisions\",\n            \"derived_state\",\n        )\n        keeps = (\"vault_registration\", \"vault_directory\", \"global_configuration\")\n""",
)
replace_once(
    "src/lele_manager/core/vault_danger.py",
    """        deletes = (\n            \"the managed Vault directory after proving it contains only canonical Markdown\",\n            \"candidate staging\",\n            \"Vault-scoped duplicate decisions\",\n            \"Vault-scoped projection/model state\",\n            \"Vault registry entry\",\n        )\n        keeps = (\"other registered Vaults\", \"global application configuration\")\n""",
    """        deletes = (\n            \"vault_directory\",\n            \"candidate_staging\",\n            \"duplicate_decisions\",\n            \"derived_state\",\n            \"vault_registration\",\n        )\n        keeps = (\"other_vaults\", \"global_configuration\")\n""",
)

replace_once(
    "frontend/src/routes/Ops.svelte",
    """  function dangerRequest() {\n""",
    """  function dangerScopeLabel(value: string) {\n    const labels: Record<string, string> = {\n      canonical_markdown: $messages.opsDangerScopeCanonical,\n      derived_refresh: $messages.opsDangerScopeDerivedRefresh,\n      candidate_staging: $messages.opsDangerScopeCandidates,\n      duplicate_decisions: $messages.opsDangerScopeDecisions,\n      derived_state: $messages.opsDangerScopeDerived,\n      vault_registration: $messages.opsDangerScopeRegistration,\n      vault_directory: $messages.opsDangerScopeDirectory,\n      global_configuration: $messages.opsDangerScopeGlobalConfig,\n      other_vaults: $messages.opsDangerScopeOtherVaults,\n    }\n    return labels[value] ?? value\n  }\n\n  function dangerRequest() {\n""",
)
replace_count(
    "frontend/src/routes/Ops.svelte",
    "<li>{item}</li>",
    "<li>{dangerScopeLabel(item)}</li>",
    2,
)
replace_once(
    "frontend/src/routes/Ops.svelte",
    """          · {formatMessage($messages.opsDangerEntriesCount, { count: dangerPreview.filesystem_entry_count })\n          · {formatMessage($messages.opsDangerDecisionsCount, { count: dangerPreview.duplicate_decision_count })\n""",
    """          · {formatMessage($messages.opsDangerEntriesCount, { count: dangerPreview.filesystem_entry_count })\n""",
)

EN = """  opsDangerKeeps: 'Will keep',\n"""
EN_NEW = """  opsDangerKeeps: 'Will keep',\n  opsDangerScopeCanonical: 'approved canonical Markdown lessons',\n  opsDangerScopeDerivedRefresh: 'derived projection/search state reconciled to the resulting Vault',\n  opsDangerScopeCandidates: 'Vault-scoped candidate staging',\n  opsDangerScopeDecisions: 'Vault-scoped duplicate-review decisions',\n  opsDangerScopeDerived: 'Vault-scoped projection/model/cache state',\n  opsDangerScopeRegistration: 'Vault registry entry',\n  opsDangerScopeDirectory: 'managed Vault directory',\n  opsDangerScopeGlobalConfig: 'global application configuration',\n  opsDangerScopeOtherVaults: 'other registered Vaults',\n"""
replace_once("frontend/src/lib/i18n/en.ts", EN, EN_NEW)

IT = """  opsDangerKeeps: 'Resterà',\n"""
IT_NEW = """  opsDangerKeeps: 'Resterà',\n  opsDangerScopeCanonical: 'LeLe Markdown canoniche approvate',\n  opsDangerScopeDerivedRefresh: 'proiezione/stato di ricerca derivati riconciliati sul Vault risultante',\n  opsDangerScopeCandidates: 'staging candidati scoped al Vault',\n  opsDangerScopeDecisions: 'decisioni di revisione duplicati scoped al Vault',\n  opsDangerScopeDerived: 'proiezione/modello/cache scoped al Vault',\n  opsDangerScopeRegistration: 'voce del Vault nel registry',\n  opsDangerScopeDirectory: 'directory gestita del Vault',\n  opsDangerScopeGlobalConfig: 'configurazione globale dell’applicazione',\n  opsDangerScopeOtherVaults: 'altri Vault registrati',\n"""
replace_once("frontend/src/lib/i18n/it.ts", IT, IT_NEW)

# E2E exercises destruction without leaving backup artifacts; backup failure/order is covered in domain tests.
replace_count(
    "frontend/e2e/vault-danger-zone.spec.ts",
    """    await expect(execute).toBeDisabled()\n\n    await danger.getByLabel(/Type exactly/).fill""",
    """    await expect(execute).toBeDisabled()\n    await danger.getByLabel('Create snapshot backup before continuing').uncheck()\n\n    await danger.getByLabel(/Type exactly/).fill""",
    1,
)
replace_once(
    "frontend/e2e/vault-danger-zone.spec.ts",
    """    await expect(danger.getByText(/Every source lesson is already present/)).toBeVisible()\n    await danger.getByLabel(/Type exactly/).fill('DELETE Issue 194 Source')\n""",
    """    await expect(danger.getByText(/Every source lesson is already present/)).toBeVisible()\n    await danger.getByLabel('Create snapshot backup before continuing').uncheck()\n    await danger.getByLabel(/Type exactly/).fill('DELETE Issue 194 Source')\n""",
)

# Regression tests for the concurrency/partial-success hardening.
tests = Path("tests/test_vault_danger.py")
text = tests.read_text(encoding="utf-8")
if "test_backup_race_stales_before_canonical_deletion" in text:
    raise SystemExit("danger concurrency tests already present")
text = text.replace(
    "import pytest\n\nfrom lele_manager.core.duplicate_decisions",
    "import pytest\n\nimport lele_manager.core.vault_danger as danger_module\nfrom lele_manager.core.duplicate_decisions",
    1,
)
text += '''\n\ndef test_backup_race_stales_before_canonical_deletion(tmp_path: Path) -> None:\n    target = _context(tmp_path, B_ID, "B")\n    path = _write(target, "topic/one", "previewed")\n    decisions = _decisions(tmp_path)\n    preview = preview_vault_danger(\n        operation="empty", target=target, active_vault_id=A_ID, decisions=decisions\n    )\n\n    def backup_then_change(_context: ActiveVaultContext) -> str:\n        path.write_bytes(_lesson("topic/one", "changed during backup"))\n        return "/backup.snapshot.zip"\n\n    with pytest.raises(VaultDangerPlanStaleError):\n        _execute(\n            preview=preview,\n            target=target,\n            decisions=decisions,\n            backup_before=True,\n            create_backup=backup_then_change,\n        )\n\n    assert path.read_bytes() == _lesson("topic/one", "changed during backup")\n\n\ndef test_reset_preserves_editorial_state_changed_after_preflight(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    target = _context(tmp_path, B_ID, "B")\n    _write(target, "topic/one")\n    target.candidates_path.parent.mkdir(parents=True)\n    target.candidates_path.write_text("old")\n    decisions = _decisions(tmp_path)\n    preview = preview_vault_danger(\n        operation="reset", target=target, active_vault_id=A_ID, decisions=decisions\n    )\n    original = danger_module._delete_canonical_set\n\n    def delete_then_change(root: Path, canonical: dict[str, bytes]) -> tuple[int, str | None]:\n        result = original(root, canonical)\n        target.candidates_path.write_text("newer")\n        return result\n\n    monkeypatch.setattr(danger_module, "_delete_canonical_set", delete_then_change)\n    result = _execute(preview=preview, target=target, decisions=decisions)\n\n    assert result.canonical_complete is True\n    assert result.editorial_cleared is False\n    assert "newer state was preserved" in (result.editorial_error or "")\n    assert target.candidates_path.read_text() == "newer"\n\n\ndef test_late_foreign_file_after_canonical_delete_is_truthful_partial(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    target = _context(tmp_path, B_ID, "B")\n    _write(target, "topic/one")\n    decisions = _decisions(tmp_path)\n    preview = preview_vault_danger(\n        operation="delete", target=target, active_vault_id=A_ID, decisions=decisions\n    )\n    original = danger_module._delete_canonical_set\n    foreign = target.vault_dir / "arrived-late.txt"\n\n    def delete_then_add_foreign(root: Path, canonical: dict[str, bytes]) -> tuple[int, str | None]:\n        result = original(root, canonical)\n        foreign.write_text("preserve me")\n        return result\n\n    monkeypatch.setattr(danger_module, "_delete_canonical_set", delete_then_add_foreign)\n    result = _execute(preview=preview, target=target, decisions=decisions)\n\n    assert result.canonical_complete is True\n    assert result.vault_directory_deleted is False\n    assert "non-Markdown file" in (result.vault_directory_error or "")\n    assert result.registry_removed is None\n    assert foreign.read_text() == "preserve me"\n'''
tests.write_text(text, encoding="utf-8")

print("issue #194 concurrency/localization hardening applied")
