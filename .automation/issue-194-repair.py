from pathlib import Path

path = Path('.automation/issue-194-apply.py')
text = path.read_text(encoding='utf-8')
old = '''replace_once(
    "frontend/src/routes/Ops.svelte",
    """          · {formatMessage($messages.opsDangerEntriesCount, { count: dangerPreview.filesystem_entry_count })}
          · {formatMessage($messages.opsDangerDecisionsCount, { count: dangerPreview.duplicate_decision_count })}
""",
    """          · {formatMessage($messages.opsDangerEntriesCount, { count: dangerPreview.filesystem_entry_count })}
""",
)
'''
new = '''replace_once(
    "frontend/src/routes/Ops.svelte",
    "          · {formatMessage($messages.opsDangerDecisionsCount, { count: dangerPreview.duplicate_decision_count })}\\n",
    "",
)
'''
if text.count(old) != 1:
    raise SystemExit(f'expected one fragile frontend patch block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('issue #194 patch script repaired')
