from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

DOCUMENT_PAIRS = (
    (Path("README.md"), Path("README.it.md")),
    (Path("ROADMAP.md"), Path("ROADMAP.it.md")),
    (Path("CONTRIBUTING.md"), Path("CONTRIBUTING.it.md")),
    (
        Path("docs/documentation-policy.md"),
        Path("docs/it/documentation-policy.md"),
    ),
    (Path("docs/projection-store.md"), Path("docs/it/projection-store.md")),
    (Path("docs/pkps-package.md"), Path("docs/it/pkps-package.md")),
    (
        Path("docs/gui-user-guide.md"),
        Path("docs/it/gui-user-guide.md"),
    ),
    (
        Path("docs/brand-design-system.md"),
        Path("docs/it/brand-design-system.md"),
    ),
)

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+]\(([^)]+)\)")


def _read(path: Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _relative_link(from_path: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, start=from_path.parent)).as_posix()


def _relative_targets(path: Path) -> list[Path]:
    targets: list[Path] = []
    for raw_target in MARKDOWN_LINK.findall(_read(path)):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
        if (
            not target
            or target.startswith(("#", "http://", "https://", "mailto:"))
        ):
            continue
        target = unquote(target.split("#", 1)[0])
        if not target:
            continue
        targets.append((ROOT / path.parent / target).resolve())
    return targets


def test_required_bilingual_pairs_exist() -> None:
    for english, italian in DOCUMENT_PAIRS:
        assert (ROOT / english).is_file(), english
        assert (ROOT / italian).is_file(), italian


def test_language_selectors_are_reciprocal() -> None:
    for english, italian in DOCUMENT_PAIRS:
        english_head = "\n".join(_read(english).splitlines()[:8])
        italian_head = "\n".join(_read(italian).splitlines()[:8])

        assert "English" in english_head, english
        assert "Italiano" in english_head, english
        assert "English" in italian_head, italian
        assert "Italiano" in italian_head, italian
        assert _relative_link(english, italian) in english_head, english
        assert _relative_link(italian, english) in italian_head, italian


def test_relative_links_in_bilingual_documents_exist() -> None:
    repository_root = ROOT.resolve()
    for pair in DOCUMENT_PAIRS:
        for path in pair:
            for target in _relative_targets(path):
                is_in_repository = (
                    target == repository_root or repository_root in target.parents
                )
                assert is_in_repository, f"{path}: target escapes repository: {target}"
                assert target.exists(), f"{path}: missing relative target {target}"


def test_root_navigation_stays_in_the_same_language() -> None:
    english_readme = _read(Path("README.md"))
    italian_readme = _read(Path("README.it.md"))

    assert "(ROADMAP.md)" in english_readme
    assert "(CONTRIBUTING.md)" in english_readme
    assert "(ROADMAP.it.md)" in italian_readme
    assert "(CONTRIBUTING.it.md)" in italian_readme
