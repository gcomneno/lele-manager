from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER_SOURCE = ROOT / "packaging" / "linux" / "install.sh"
CANONICAL_ICON = ROOT / "frontend" / "public" / "favicon.svg"


def create_extracted_release(
    tmp_path: Path,
    name: str,
    payload: str,
    *,
    valid: bool = True,
) -> Path:
    release = tmp_path / name
    release.mkdir()
    installer = release / "install.sh"
    shutil.copy2(INSTALLER_SOURCE, installer)
    shutil.copy2(CANONICAL_ICON, release / "lele-manager.svg")

    bundle = release / "LeLe-Manager"
    bundle.mkdir()
    executable = bundle / "LeLe-Manager"
    if valid:
        executable.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' '{payload}'\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)

    return release


def install(
    release: Path,
    home: Path,
    *,
    xdg_data_home: Path | None = None,
    bin_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    if xdg_data_home is None:
        environment.pop("XDG_DATA_HOME", None)
    else:
        environment["XDG_DATA_HOME"] = str(xdg_data_home)
    if bin_dir is None:
        environment.pop("LELE_MANAGER_INSTALL_BIN_DIR", None)
    else:
        environment["LELE_MANAGER_INSTALL_BIN_DIR"] = str(bin_dir)

    return subprocess.run(
        [str(release / "install.sh")],
        cwd=release,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_clean_install_honors_xdg_data_home_and_creates_stable_launcher(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "xdg-data"
    bin_dir = tmp_path / "bin"
    release = create_extracted_release(
        tmp_path,
        "LeLe-Manager-v1.2.3-Linux-x86_64",
        "payload-a",
    )
    state_file = data_home / "lele-manager" / "lessons.jsonl"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("existing runtime state\n", encoding="utf-8")

    result = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)

    assert result.returncode == 0, result.stderr
    app = data_home / "lele-manager" / "install" / "app" / "LeLe-Manager"
    launcher = bin_dir / "lele-manager"
    assert app.is_file()
    assert launcher.is_symlink()
    assert launcher.stat().st_mode & 0o111
    assert launcher.readlink() == app
    assert state_file.read_text(encoding="utf-8") == "existing runtime state\n"
    assert not state_file.is_relative_to(app.parents[1])
    assert "1.2.3" not in str(app)
    assert "1.2.3" not in str(launcher.readlink())
    assert subprocess.run(
        [str(launcher)], text=True, capture_output=True, check=True
    ).stdout == "payload-a\n"
    desktop_entry = data_home / "applications" / "lele-manager.desktop"
    icon = data_home / "icons/hicolor/scalable/apps/lele-manager.svg"
    assert desktop_entry.is_file()
    assert icon.read_bytes() == CANONICAL_ICON.read_bytes()
    desktop = desktop_entry.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in desktop
    assert "Type=Application" in desktop
    assert "Name=LeLe Manager" in desktop
    assert "Terminal=false" in desktop
    assert "Icon=lele-manager" in desktop
    assert "Categories=Development;" in desktop
    assert "StartupNotify=true" in desktop
    assert f'Exec="{launcher}"' in desktop
    assert f'TryExec="{launcher}"' in desktop
    assert "~" not in desktop
    assert "$HOME" not in desktop
    assert "/home/baltimora" not in desktop
    assert "1.2.3" not in desktop
    assert str(release) not in desktop
    assert str(app) not in desktop


def test_default_paths_use_home_local_conventions_without_real_home_writes(
    tmp_path: Path,
) -> None:
    home = tmp_path / "isolated home"
    release = create_extracted_release(tmp_path, "release", "payload-a")

    result = install(release, home)

    assert result.returncode == 0, result.stderr
    assert (
        home / ".local/share/lele-manager/install/app/LeLe-Manager"
    ).is_file()
    assert (home / ".local/bin/lele-manager").is_symlink()
    assert str(Path.home()) not in result.stdout
    assert str(Path.home()) not in result.stderr


def test_reinstall_is_idempotent_and_preserves_launcher_identity(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    release = create_extracted_release(tmp_path, "release", "payload-a")

    first = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)
    launcher = bin_dir / "lele-manager"
    original_inode = launcher.lstat().st_ino
    second = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert launcher.lstat().st_ino == original_inode
    assert list((data_home / "lele-manager").iterdir()) == [
        data_home / "lele-manager" / "install"
    ]
    assert list((data_home / "applications").glob("lele-manager.desktop")) == [
        data_home / "applications" / "lele-manager.desktop"
    ]


def test_upgrade_replaces_only_stable_app_payload_and_preserves_user_state(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    first_release = create_extracted_release(
        tmp_path, "LeLe-Manager-v1.2.3-Linux-x86_64", "payload-a"
    )
    second_release = create_extracted_release(
        tmp_path, "LeLe-Manager-v1.2.4-Linux-x86_64", "payload-b"
    )

    first = install(
        first_release, home, xdg_data_home=data_home, bin_dir=bin_dir
    )
    state_file = data_home / "lele-manager" / "lessons.jsonl"
    vault_file = tmp_path / "vault" / "lesson.md"
    state_file.write_text("persistent lessons\n", encoding="utf-8")
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text("persistent vault\n", encoding="utf-8")
    launcher = bin_dir / "lele-manager"
    original_inode = launcher.lstat().st_ino

    second = install(
        second_release, home, xdg_data_home=data_home, bin_dir=bin_dir
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert launcher.lstat().st_ino == original_inode
    installed_executable = (
        data_home / "lele-manager" / "install" / "app" / "LeLe-Manager"
    )
    assert launcher.readlink() == installed_executable
    assert subprocess.run(
        [str(launcher)], text=True, capture_output=True, check=True
    ).stdout == "payload-b\n"
    assert state_file.read_text(encoding="utf-8") == "persistent lessons\n"
    assert not state_file.is_relative_to(installed_executable.parents[1])
    assert vault_file.read_text(encoding="utf-8") == "persistent vault\n"
    assert not any(
        "1.2." in str(path)
        for path in (data_home / "lele-manager").rglob("*")
    )
    desktop = (data_home / "applications/lele-manager.desktop").read_text(
        encoding="utf-8"
    )
    assert f'Exec="{launcher}"' in desktop
    assert f'TryExec="{launcher}"' in desktop
    assert (data_home / "icons/hicolor/scalable/apps/lele-manager.svg").is_file()


def test_invalid_source_fails_before_replacing_existing_installation(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    good_release = create_extracted_release(tmp_path, "good", "payload-a")
    invalid_release = create_extracted_release(
        tmp_path, "invalid", "unused", valid=False
    )

    good = install(good_release, home, xdg_data_home=data_home, bin_dir=bin_dir)
    failed = install(
        invalid_release, home, xdg_data_home=data_home, bin_dir=bin_dir
    )

    assert good.returncode == 0, good.stderr
    assert failed.returncode != 0
    assert "eseguibile nativo assente" in failed.stderr
    assert subprocess.run(
        [str(bin_dir / "lele-manager")],
        text=True,
        capture_output=True,
        check=True,
    ).stdout == "payload-a\n"


def test_missing_icon_fails_before_replacing_desktop_resources(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    good_release = create_extracted_release(tmp_path, "good", "payload-a")
    invalid_release = create_extracted_release(tmp_path, "invalid", "payload-b")
    (invalid_release / "lele-manager.svg").unlink()

    good = install(good_release, home, xdg_data_home=data_home, bin_dir=bin_dir)
    desktop = data_home / "applications/lele-manager.desktop"
    icon = data_home / "icons/hicolor/scalable/apps/lele-manager.svg"
    old_desktop = desktop.read_bytes()
    old_icon = icon.read_bytes()
    failed = install(
        invalid_release, home, xdg_data_home=data_home, bin_dir=bin_dir
    )

    assert good.returncode == 0, good.stderr
    assert failed.returncode != 0
    assert "icona Linux assente" in failed.stderr
    assert desktop.read_bytes() == old_desktop
    assert icon.read_bytes() == old_icon
    assert subprocess.run(
        [str(bin_dir / "lele-manager")], text=True, capture_output=True, check=True
    ).stdout == "payload-a\n"


def test_existing_unowned_launcher_is_not_overwritten(tmp_path: Path) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    foreign = bin_dir / "lele-manager"
    foreign.write_text("do not replace\n", encoding="utf-8")
    release = create_extracted_release(tmp_path, "release", "payload-a")

    result = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)

    assert result.returncode != 0
    assert "non appartiene a LeLe Manager" in result.stderr
    assert foreign.read_text(encoding="utf-8") == "do not replace\n"
    assert not (data_home / "lele-manager" / "install" / "app").exists()


def test_existing_unrelated_desktop_entry_is_not_overwritten(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    foreign = data_home / "applications/lele-manager.desktop"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("[Desktop Entry]\nName=Other App\n", encoding="utf-8")
    release = create_extracted_release(tmp_path, "release", "payload-a")

    result = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)

    assert result.returncode != 0
    assert "voce desktop esistente non appartiene" in result.stderr
    assert foreign.read_text(encoding="utf-8") == "[Desktop Entry]\nName=Other App\n"
    assert not (data_home / "lele-manager" / "install" / "app").exists()


def test_existing_desktop_entry_symlink_is_rejected(tmp_path: Path) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    foreign = tmp_path / "foreign.desktop"
    foreign.write_text("[Desktop Entry]\n", encoding="utf-8")
    desktop = data_home / "applications/lele-manager.desktop"
    desktop.parent.mkdir(parents=True)
    desktop.symlink_to(foreign)
    release = create_extracted_release(tmp_path, "release", "payload-a")

    result = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)

    assert result.returncode != 0
    assert "non deve essere un link simbolico" in result.stderr
    assert desktop.is_symlink()


def test_custom_launcher_path_with_spaces_is_desktop_entry_escaped(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home with spaces"
    data_home = tmp_path / "data with spaces"
    bin_dir = tmp_path / "bin with spaces"
    release = create_extracted_release(tmp_path, "release with spaces", "payload-a")

    result = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)

    assert result.returncode == 0, result.stderr
    launcher = bin_dir / "lele-manager"
    desktop = (data_home / "applications/lele-manager.desktop").read_text(
        encoding="utf-8"
    )
    assert f'Exec="{launcher}"' in desktop
    assert f'TryExec="{launcher}"' in desktop
    validator = shutil.which("desktop-file-validate")
    if validator:
        validation = subprocess.run(
            [validator, str(data_home / "applications/lele-manager.desktop")],
            text=True,
            capture_output=True,
            check=False,
        )
        assert validation.returncode == 0, validation.stderr


def test_recognizable_manual_desktop_entry_is_adopted(tmp_path: Path) -> None:
    home = tmp_path / "home"
    data_home = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    launcher = bin_dir / "lele-manager"
    desktop = data_home / "applications/lele-manager.desktop"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        "[Desktop Entry]\nType=Application\nName=LeLe Manager\n"
        f"Exec={launcher}\nTryExec={launcher}\nIcon=lele-manager\n"
        "Terminal=false\nCategories=Development;\nStartupNotify=true\n",
        encoding="utf-8",
    )
    release = create_extracted_release(tmp_path, "release", "payload-a")

    result = install(release, home, xdg_data_home=data_home, bin_dir=bin_dir)

    assert result.returncode == 0, result.stderr
    assert "X-LeLe-Manager-Installer=true" in desktop.read_text(encoding="utf-8")


def test_distributed_installer_has_no_developer_home_or_release_version() -> None:
    content = INSTALLER_SOURCE.read_text(encoding="utf-8")

    assert "/home/baltimora" not in content
    assert "LeLe-Manager-v" not in content
    assert "LELE_MANAGER_INSTALL_BIN_DIR" in content


def test_installer_requires_absolute_override_paths(tmp_path: Path) -> None:
    release = create_extracted_release(tmp_path, "release", "payload-a")
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_DATA_HOME": "relative-data",
            "LELE_MANAGER_INSTALL_BIN_DIR": str(tmp_path / "bin"),
        }
    )

    result = subprocess.run(
        [str(release / "install.sh")],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "percorso assoluto" in result.stderr
