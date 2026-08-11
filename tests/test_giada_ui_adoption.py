from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VENDOR = (
    FRONTEND
    / "vendor"
    / "giadaware-ui-components"
    / "b088653"
)
ARTIFACT = VENDOR / "giadaware-ui-components-0.0.0.tgz"

EXPECTED_DEPENDENCY = (
    "file:vendor/giadaware-ui-components/b088653/"
    "giadaware-ui-components-0.0.0.tgz"
)
EXPECTED_SHA256 = (
    "88b5cc12417fa911f5a885b9e554abd198f29a4322f0ac8d1"
    "fad823da16e2c7d"
)


def test_giada_ui_is_a_pinned_direct_dependency() -> None:
    package = json.loads(
        (FRONTEND / "package.json").read_text(encoding="utf-8")
    )
    assert (
        package["dependencies"]["giadaware-ui-components"]
        == EXPECTED_DEPENDENCY
    )

    lock_text = (FRONTEND / "package-lock.json").read_text(
        encoding="utf-8"
    )
    assert "giadaware-ui-components" in lock_text
    assert "giadaware-ui-components-0.0.0.tgz" in lock_text


def test_giada_ui_artifact_has_verified_provenance() -> None:
    assert ARTIFACT.is_file()
    assert (
        hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
        == EXPECTED_SHA256
    )

    provenance = (VENDOR / "PROVENANCE.md").read_text(
        encoding="utf-8"
    )
    assert "b088653cba3c940ff6b4baf3b396a109cb04e8b7" in provenance
    assert EXPECTED_SHA256 in provenance

    with tarfile.open(ARTIFACT, "r:gz") as archive:
        names = set(archive.getnames())

    assert "package/dist/index.js" in names
    assert "package/dist/studio/index.js" in names


def test_browse_uses_public_giada_ui_entry_points() -> None:
    browse = (
        FRONTEND / "src" / "routes" / "Browse.svelte"
    ).read_text(encoding="utf-8")

    assert "from 'giadaware-ui-components'" in browse
    assert "from 'giadaware-ui-components/studio'" in browse

    for component in (
        "<Panel",
        "<Button",
        "<FieldLabel",
        "<FormActions",
        "<FormStatus",
    ):
        assert component in browse

    assert "normalizeButtonVariant" not in browse
    assert ".giu-button {" not in browse


def test_stats_and_vault_use_public_giada_ui_components() -> None:
    stats = (
        FRONTEND / "src" / "routes" / "Stats.svelte"
    ).read_text(encoding="utf-8")
    vault = (
        FRONTEND / "src" / "routes" / "Vault.svelte"
    ).read_text(encoding="utf-8")

    assert "from 'giadaware-ui-components'" in stats
    assert "from 'giadaware-ui-components/studio'" in stats
    assert "<Panel" in stats
    assert stats.count("<Surface") == 5
    assert "<FormStatus" in stats
    assert '<section class="card stats">' not in stats

    assert "from 'giadaware-ui-components'" in vault
    assert "from 'giadaware-ui-components/studio'" in vault
    assert "<Panel" in vault
    assert vault.count("<FormActions") == 2
    assert 'aria-label="Vault management"' in vault
    assert 'class="vault-actions"' in vault
    assert "<Button" in vault
    assert "<FormStatus" in vault
    assert "<FormStatus" in vault
    assert '<section class="card">' not in vault
    assert 'class="btn' not in vault


def test_detail_editor_and_duplicate_controls_use_giada_ui() -> None:
    detail = (
        FRONTEND / "src" / "routes" / "Detail.svelte"
    ).read_text(encoding="utf-8")
    editor = (
        FRONTEND / "src" / "routes" / "Editor.svelte"
    ).read_text(encoding="utf-8")
    duplicates = (
        FRONTEND / "src" / "routes" / "Duplicates.svelte"
    ).read_text(encoding="utf-8")

    assert "from 'giadaware-ui-components'" in detail
    assert "from 'giadaware-ui-components/studio'" in detail
    assert "<Panel" in detail
    # Modify and Inspect are maintained Giada UI controls; Delete is a
    # deliberately local destructive button with stronger semantic styling.
    assert detail.count("<Button") == 2
    assert "<FormStatus" in detail
    assert '<section class="card main-pane">' not in detail
    assert '<button class="btn' not in detail

    assert "from 'giadaware-ui-components'" in editor
    assert "from 'giadaware-ui-components/studio'" in editor
    assert "<Panel" in editor
    # Save plus the explicit similarity-check action are both Giada UI buttons.
    assert editor.count("<Button") == 2
    assert editor.count("<FieldLabel") == 10
    assert "<FormStatus" in editor
    assert '<section class="card editor-pane">' not in editor
    assert '<button class="btn' not in editor

    assert "from 'giadaware-ui-components'" in duplicates
    assert "from 'giadaware-ui-components/studio'" in duplicates
    assert '<Panel title={$messages.duplicatesTitle}' in duplicates
    assert duplicates.count("<FieldLabel") == 3
    assert "<FormActions" in duplicates
    assert duplicates.count("<Button") == 1
    assert "<FormStatus" in duplicates
    assert '<section class="card controls">' not in duplicates
    assert '<button class="btn btn-primary"' not in duplicates

    # Domain-specific comparison cards intentionally remain local.
    assert '<article class="card duplicate-pair">' in duplicates
