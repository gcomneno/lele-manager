from pathlib import Path

path = Path("src/lele_manager/core/vault_danger.py")
text = path.read_text(encoding="utf-8")
old = '''    if operation == "empty":
        deletes = ("all approved canonical Markdown lessons", "target Vault derived projection/model refreshed")
'''
new = '''    deletes: tuple[str, ...]
    keeps: tuple[str, ...]
    if operation == "empty":
        deletes = ("all approved canonical Markdown lessons", "target Vault derived projection/model refreshed")
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one preview scope anchor, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("issue #194 mypy fix applied")
