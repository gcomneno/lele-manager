from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
BUILD_COMMAND = "./scripts/build-release-artifacts.sh"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ci_and_release_share_artifact_build_entrypoint() -> None:
    ci = read(".github/workflows/ci.yml")
    release = read(".github/workflows/release.yml")

    assert BUILD_COMMAND in ci
    assert BUILD_COMMAND in release


def test_release_workflow_prepares_node_before_build() -> None:
    release = read(".github/workflows/release.yml")

    node_position = release.index("actions/setup-node@v6")
    build_position = release.index(BUILD_COMMAND)

    assert node_position < build_position
    assert 'node-version: "22"' in release


def test_artifact_script_builds_gui_before_python_distributions() -> None:
    script = read("scripts/build-release-artifacts.sh")

    gui_position = script.index("scripts/build-gui.sh")
    package_position = script.index("python -m build")

    assert gui_position < package_position
    assert "python -m twine check" in script


def test_packaging_smoke_rebuilds_wheel_from_sdist() -> None:
    ci = read(".github/workflows/ci.yml")

    assert "python -m pip wheel" in ci
    assert "dist/*.tar.gz" in ci
    assert "/tmp/sdist-venv" in ci
    assert "scripts/smoke-installed-package.py" in ci


def test_packaging_metadata_uses_current_spdx_license() -> None:
    data = tomllib.loads(read("pyproject.toml"))

    assert data["build-system"]["requires"] == ["setuptools>=77.0.0"]
    assert data["project"]["license"] == "MIT"
    assert data["project"]["license-files"] == ["LICENSE"]


def test_brand_design_docs_are_declared_in_sdist_manifest() -> None:
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    for documentation_path in (
        "docs/brand-design-system.md",
        "docs/it/brand-design-system.md",
    ):
        assert f"include {documentation_path}" in manifest

def test_tag_release_publishes_exact_native_version_assets() -> None:
    release = read(".github/workflows/release.yml")

    assert "github-release:" in release
    assert "actions/download-artifact@v6" in release
    assert "pattern: lele-manager-*" in release
    assert "merge-multiple: true" in release
    assert 'version="${GITHUB_REF_NAME#v}"' in release
    assert 'LeLe-Manager-v"${version}"-*' in release
    assert 'gh release create "${GITHUB_REF_NAME}"' in release
    assert "--verify-tag" in release
