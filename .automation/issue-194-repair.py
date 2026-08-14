from pathlib import Path

path = Path('.automation/issue-194-apply.py')
text = path.read_text(encoding='utf-8')
old = '''    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
'''
new = '''    if count != 1:
        if path == "frontend/src/routes/Ops.svelte" and "opsDangerDecisionsCount" in old:
            fallback = "          · {formatMessage($messages.opsDangerDecisionsCount, { count: dangerPreview.duplicate_decision_count })}\\n"
            fallback_count = text.count(fallback)
            if fallback_count != 1:
                raise SystemExit(
                    f"{path}: expected one decisions-count fallback anchor, found {fallback_count}"
                )
            target.write_text(text.replace(fallback, "", 1), encoding="utf-8")
            return
        raise SystemExit(f"{path}: expected one anchor, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
'''
if text.count(old) != 1:
    raise SystemExit(f'expected one replace_once helper body, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('issue #194 patch helper repaired')
