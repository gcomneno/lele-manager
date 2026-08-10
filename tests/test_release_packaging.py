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

def test_gui_build_packages_authoritative_license() -> None:
    script = read("scripts/build-gui.py")

    assert 'ROOT / "LICENSE"' in script
    assert 'FRONTEND_DIST / "LICENSE"' in script
    assert "shutil.copy2(license_source, license_target)" in script


def test_tag_release_publishes_exact_native_version_assets() -> None:
    release = read(".github/workflows/release.yml")

    assert "github-release:" in release
    assert "actions/download-artifact@v7" in release
    assert "pattern: lele-manager-*" in release
    assert "merge-multiple: true" in release
    assert 'version="${GITHUB_REF_NAME#v}"' in release
    assert 'LeLe-Manager-v"${version}"-*' in release
    assert 'gh release create "${GITHUB_REF_NAME}"' in release
    assert "--verify-tag" in release

def test_native_release_is_smoked_before_upload() -> None:
    release = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    package = release.index("Package native release")
    smoke = release.index("Smoke published-style native release")
    upload = release.index("Upload native package")

    assert package < smoke < upload
    assert "python scripts/smoke-native-release.py" in release

def test_native_build_rejects_stale_installed_version() -> None:
    script = Path("scripts/build-native-app.py").read_text(encoding="utf-8")

    assert "verify_installed_version()" in script
    assert 'version("lele-manager")' in script
    assert '"project"]["version"]' in script
    assert "metadata lele-manager non allineata" in script


def test_linux_native_release_ships_the_user_local_installer() -> None:
    script = read("scripts/package-native-release.py")
    installer = ROOT / "packaging/linux/install.sh"

    assert installer.is_file()
    assert installer.stat().st_mode & 0o111
    assert 'LINUX_INSTALLER = ROOT / "packaging" / "linux" / "install.sh"' in script
    assert 'shutil.copy2(LINUX_INSTALLER, staging / "install.sh")' in script

def test_pypi_publication_uses_dedicated_manual_trusted_workflow() -> None:
    release = read(".github/workflows/release.yml")
    pypi = read(".github/workflows/publish-pypi.yml")

    assert "Publish to PyPI" not in release
    assert "publish_pypi:" not in release

    assert "workflow_dispatch:" in pypi
    assert "version_tag:" in pypi
    assert "push:" not in pypi

    assert BUILD_COMMAND in pypi
    assert "environment: pypi" in pypi
    assert "id-token: write" in pypi
    assert "pypa/gh-action-pypi-publish@release/v1" in pypi
