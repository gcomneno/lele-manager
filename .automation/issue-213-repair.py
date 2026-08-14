from pathlib import Path

path = Path('.automation/issue-213-apply.py')
text = path.read_text(encoding='utf-8')
old = '''replace_once(
    "src/lele_manager/core/vault.py",
    """    title: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n) -> str:\n""",
    """    title: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n    lifecycle: LifecycleState = \"active\",\n    superseded_by: Optional[str] = None,\n) -> str:\n""",
)
'''
new = '''replace_once(
    "src/lele_manager/core/vault.py",
    """def render_lesson_markdown(\n    *,\n    lesson_id: str,\n    body: str,\n    topic: str,\n    source: str,\n    importance: int,\n    tags: List[str],\n    date: str,\n    title: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n) -> str:\n""",
    """def render_lesson_markdown(\n    *,\n    lesson_id: str,\n    body: str,\n    topic: str,\n    source: str,\n    importance: int,\n    tags: List[str],\n    date: str,\n    title: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n    lifecycle: LifecycleState = \"active\",\n    superseded_by: Optional[str] = None,\n) -> str:\n""",
)
'''
if text.count(old) != 1:
    raise SystemExit(f'expected one renderer patch block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('issue #213 renderer anchor repaired')
