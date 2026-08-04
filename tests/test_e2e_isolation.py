from pathlib import Path


def test_playwright_server_uses_only_targeted_fixture_directories() -> None:
    root = Path(__file__).parents[1]
    prepare = (root / "scripts/e2e-prepare.py").read_text(encoding="utf-8")
    serve = (root / "scripts/e2e-serve.sh").read_text(encoding="utf-8")

    assert 'FIXTURE_DIR = ROOT / ".e2e-fixture"' in prepare
    assert "shutil.rmtree(FIXTURE_DIR, ignore_errors=True)" in prepare
    assert "FIXTURE_DIR.is_symlink()" in prepare
    assert "FIXTURE_DIR.unlink()" in prepare
    assert "shutil.rmtree(ROOT" not in prepare
    assert 'DATA_DIR = FIXTURE_DIR / "data"' in prepare
    assert 'CACHE_DIR = FIXTURE_DIR / "cache"' in prepare
    assert 'VAULT_DIR = FIXTURE_DIR / "vault"' in prepare

    for variable, child in (
        ("LELE_DATA_DIR", "data"),
        ("LELE_CACHE_DIR", "cache"),
        ("LELE_VAULT_DIR", "vault"),
    ):
        assert f'export {variable}="$ROOT/.e2e-fixture/{child}"' in serve
    assert "unset LELE_DATA_PATH" in serve
    assert "unset LELE_MODEL_PATH" in serve
