from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        raise SystemExit(f"{path}: addition already present")
    target.write_text(text.rstrip() + "\n\n" + addition.rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Canonical importer/projection
# ---------------------------------------------------------------------------
replace_once(
    "src/lele_manager/cli/import_from_dir.py",
    "from lele_manager.core.json_compat import json_native\n",
    "from lele_manager.core.json_compat import json_native\nfrom lele_manager.core.lifecycle import LifecycleValidationError, normalize_lifecycle, normalize_superseded_by\n",
)
replace_once(
    "src/lele_manager/cli/import_from_dir.py",
    """    title: Optional[str]\n    path: str\n""",
    """    title: Optional[str]\n    lifecycle: str\n    superseded_by: Optional[str]\n    path: str\n""",
)
replace_once(
    "src/lele_manager/cli/import_from_dir.py",
    """        # title\n        title = None\n        if \"title\" in frontmatter and isinstance(frontmatter[\"title\"], str):\n            title = frontmatter[\"title\"].strip() or None\n\n        frontmatter_hash = compute_frontmatter_hash(frontmatter)\n""",
    """        # title\n        title = None\n        if \"title\" in frontmatter and isinstance(frontmatter[\"title\"], str):\n            title = frontmatter[\"title\"].strip() or None\n\n        # lifecycle / supersession (#213). Missing lifecycle remains implicitly active\n        # without rewriting older Markdown. Invalid maintained metadata is blocking.\n        try:\n            lifecycle = normalize_lifecycle(frontmatter.get(\"lifecycle\"))\n            superseded_by = normalize_superseded_by(\n                frontmatter.get(\"superseded_by\"), lesson_id=lele_id\n            )\n        except LifecycleValidationError as exc:\n            plan.validation_problems.append(\n                ValidationProblem(\n                    code=\"invalid_lifecycle\",\n                    message=str(exc),\n                    path=rel_path,\n                    field=\"lifecycle\",\n                    blocking=True,\n                )\n            )\n            continue\n\n        frontmatter_hash = compute_frontmatter_hash(frontmatter)\n""",
)
replace_once(
    "src/lele_manager/cli/import_from_dir.py",
    """            date=date,\n            title=title,\n            path=rel_path,\n""",
    """            date=date,\n            title=title,\n            lifecycle=lifecycle,\n            superseded_by=superseded_by,\n            path=rel_path,\n""",
)

# ---------------------------------------------------------------------------
# Canonical Markdown writer
# ---------------------------------------------------------------------------
replace_once(
    "src/lele_manager/core/vault.py",
    "from lele_manager.core.projection_store import ProjectionStoreError\n" if False else "from lele_manager.composition import projection_store\n",
    "from lele_manager.composition import projection_store\nfrom lele_manager.core.lifecycle import LifecycleState, normalize_lifecycle, normalize_superseded_by\n",
)
replace_once(
    "src/lele_manager/core/vault.py",
    """    title: Optional[str],\n    provenance: Optional[Dict[str, object]] = None,\n) -> Dict[str, object]:\n""",
    """    title: Optional[str],\n    provenance: Optional[Dict[str, object]] = None,\n    lifecycle: LifecycleState = \"active\",\n    superseded_by: Optional[str] = None,\n) -> Dict[str, object]:\n""",
)
replace_once(
    "src/lele_manager/core/vault.py",
    """    if title:\n        frontmatter[\"title\"] = title\n    if provenance is not None:\n""",
    """    lifecycle = normalize_lifecycle(lifecycle)\n    superseded_by = normalize_superseded_by(superseded_by, lesson_id=lesson_id)\n    if title:\n        frontmatter[\"title\"] = title\n    if lifecycle != \"active\":\n        frontmatter[\"lifecycle\"] = lifecycle\n    if superseded_by is not None:\n        frontmatter[\"superseded_by\"] = superseded_by\n    if provenance is not None:\n""",
)
replace_once(
    "src/lele_manager/core/vault.py",
    """    title: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n) -> str:\n""",
    """    title: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n    lifecycle: LifecycleState = \"active\",\n    superseded_by: Optional[str] = None,\n) -> str:\n""",
)
replace_once(
    "src/lele_manager/core/vault.py",
    """        title=title,\n        provenance=provenance,\n    )\n""",
    """        title=title,\n        provenance=provenance,\n        lifecycle=lifecycle,\n        superseded_by=superseded_by,\n    )\n""",
)
replace_once(
    "src/lele_manager/core/vault.py",
    """    relative_path: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n) -> Path:\n""",
    """    relative_path: Optional[str] = None,\n    provenance: Optional[Dict[str, object]] = None,\n    lifecycle: LifecycleState = \"active\",\n    superseded_by: Optional[str] = None,\n) -> Path:\n""",
)
# There are now two matching title/provenance call blocks; only the second (write -> render) remains.
replace_once(
    "src/lele_manager/core/vault.py",
    """        title=title,\n        provenance=provenance,\n    )\n    md_path.parent.mkdir""",
    """        title=title,\n        provenance=provenance,\n        lifecycle=lifecycle,\n        superseded_by=superseded_by,\n    )\n    md_path.parent.mkdir""",
)

# Preserve lifecycle for older callers of the canonical update primitive.
replace_once(
    "src/lele_manager/application/lesson_writing.py",
    "from lele_manager.core.vault import find_markdown_paths_by_id, write_lesson_markdown\n",
    "from lele_manager.cli.import_from_dir import parse_markdown_with_frontmatter\nfrom lele_manager.core.lifecycle import LifecycleState, normalize_lifecycle, normalize_superseded_by\nfrom lele_manager.core.vault import find_markdown_paths_by_id, write_lesson_markdown\n",
)
replace_once(
    "src/lele_manager/application/lesson_writing.py",
    """    importance: int, tags: list[str], date: str, title: str | None,\n    invalidate_cache: Callable[[], None],\n) -> Path:\n""",
    """    importance: int, tags: list[str], date: str, title: str | None,\n    invalidate_cache: Callable[[], None],\n    lifecycle: LifecycleState | None = None,\n    superseded_by: str | None = None,\n    replace_lifecycle: bool = False,\n) -> Path:\n""",
)
replace_once(
    "src/lele_manager/application/lesson_writing.py",
    """    try:\n        relative_path = matches[0].resolve().relative_to(vault_dir.resolve()).as_posix()\n        result = write_lesson_markdown(\n""",
    """    try:\n        relative_path = matches[0].resolve().relative_to(vault_dir.resolve()).as_posix()\n        frontmatter, _existing_body = parse_markdown_with_frontmatter(\n            matches[0].read_text(encoding=\"utf-8\")\n        )\n        if replace_lifecycle:\n            resolved_lifecycle = normalize_lifecycle(lifecycle)\n            resolved_superseded_by = normalize_superseded_by(\n                superseded_by, lesson_id=lesson_id\n            )\n        else:\n            resolved_lifecycle = normalize_lifecycle(frontmatter.get(\"lifecycle\"))\n            resolved_superseded_by = normalize_superseded_by(\n                frontmatter.get(\"superseded_by\"), lesson_id=lesson_id\n            )\n        result = write_lesson_markdown(\n""",
)
replace_once(
    "src/lele_manager/application/lesson_writing.py",
    """            importance=importance, tags=tags, date=date, title=title,\n            relative_path=relative_path,\n        )\n""",
    """            importance=importance, tags=tags, date=date, title=title,\n            relative_path=relative_path, lifecycle=resolved_lifecycle,\n            superseded_by=resolved_superseded_by,\n        )\n""",
)

# ---------------------------------------------------------------------------
# API projection/search/authoring
# ---------------------------------------------------------------------------
replace_once(
    "src/lele_manager/api/server.py",
    "from lele_manager.core.json_compat import canonical_json\n",
    "from lele_manager.core.json_compat import canonical_json\nfrom lele_manager.core.lifecycle import LifecycleState, LifecycleValidationError, LIFECYCLE_STATES, normalize_lifecycle, normalize_superseded_by\n",
)
replace_once(
    "src/lele_manager/api/server.py",
    """    created_at: Optional[str] = Field(\n        default=None,\n        description=\"Timestamp tecnico (ISO 8601 UTC). Se omesso viene generato dal server.\",\n    )\n""",
    """    created_at: Optional[str] = Field(\n        default=None,\n        description=\"Timestamp tecnico (ISO 8601 UTC). Se omesso viene generato dal server.\",\n    )\n    lifecycle: LifecycleState = Field(\n        default=\"active\",\n        description=\"Maintained knowledge lifecycle state. Missing canonical metadata is active.\",\n    )\n    superseded_by: Optional[str] = Field(\n        default=None,\n        description=\"Stable ID of the maintained replacement lesson, when any.\",\n    )\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """    importance_lte: Optional[int] = Field(\n        default=None,\n        description=\"Filtro: importance <= questo valore.\",\n    )\n    limit: int = Field(\n""",
    """    importance_lte: Optional[int] = Field(\n        default=None,\n        description=\"Filtro: importance <= questo valore.\",\n    )\n    lifecycle_in: Optional[List[LifecycleState]] = Field(\n        default=None,\n        description=\"Lifecycle states to include. Omitted means active only.\",\n    )\n    superseded_by: Optional[str] = Field(\n        default=None,\n        description=\"Filter lessons that point to this replacement stable ID.\",\n    )\n    limit: int = Field(\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """    title: Optional[str] = Field(default=None)\n\n\nclass LessonVaultCreate""",
    """    title: Optional[str] = Field(default=None)\n    lifecycle: Optional[LifecycleState] = Field(default=None)\n    superseded_by: Optional[str] = Field(default=None)\n\n\nclass LessonVaultCreate""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """        \"created_at\",\n    ]:\n""",
    """        \"created_at\",\n        \"lifecycle\",\n        \"superseded_by\",\n    ]:\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """    title_val = _to_optional_str(row.get(\"title\"))\n\n    # importance""",
    """    title_val = _to_optional_str(row.get(\"title\"))\n    try:\n        lifecycle_val = normalize_lifecycle(_to_optional_str(row.get(\"lifecycle\")))\n        superseded_by_val = normalize_superseded_by(\n            _to_optional_str(row.get(\"superseded_by\")), lesson_id=lele_id\n        )\n    except LifecycleValidationError:\n        # Projection is derived from validated canonical import; fail closed if\n        # an older/corrupt projection somehow bypassed that boundary.\n        lifecycle_val = \"review-needed\"\n        superseded_by_val = None\n\n    # importance""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """        date=date_val,\n        title=title_val,\n    )\n""",
    """        date=date_val,\n        title=title_val,\n        lifecycle=lifecycle_val,\n        superseded_by=superseded_by_val,\n    )\n""",
)

# Shared lifecycle filter at API boundary.
replace_once(
    "src/lele_manager/api/server.py",
    """def _safe_dt_series(s: pd.Series) -> pd.Series:\n    \"\"\"\n    Parse free-form date strings to datetime; invalid/missing becomes NaT.\n    \"\"\"\n    return pd.to_datetime(s, errors=\"coerce\", utc=True)\n\n\ndef append_lesson_to_jsonl""",
    """def _safe_dt_series(s: pd.Series) -> pd.Series:\n    \"\"\"\n    Parse free-form date strings to datetime; invalid/missing becomes NaT.\n    \"\"\"\n    return pd.to_datetime(s, errors=\"coerce\", utc=True)\n\n\ndef _filter_lifecycle(\n    df: pd.DataFrame, states: Optional[List[LifecycleState]]\n) -> pd.DataFrame:\n    if df.empty:\n        return df\n    lifecycle = (\n        df[\"lifecycle\"] if \"lifecycle\" in df.columns\n        else pd.Series([\"active\"] * len(df), index=df.index)\n    )\n    lifecycle = lifecycle.fillna(\"active\").astype(str).replace(\"\", \"active\")\n    selected = list(states) if states is not None else [\"active\"]\n    return df[lifecycle.isin(selected)]\n\n\ndef append_lesson_to_jsonl""",
)

# GET list supports explicit state selection; omission is active-only.
replace_once(
    "src/lele_manager/api/server.py",
    """    source: Optional[str] = Query(\n        default=None,\n        description=\"Filtra per source esatto.\",\n    ),\n    limit: int = Query(\n""",
    """    source: Optional[str] = Query(\n        default=None,\n        description=\"Filtra per source esatto.\",\n    ),\n    lifecycle: Optional[List[LifecycleState]] = Query(\n        default=None,\n        description=\"Lifecycle states to include; omitted means active only.\",\n    ),\n    limit: int = Query(\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """    if df.empty:\n        return []\n\n    # Filtro testuale\n""",
    """    if df.empty:\n        return []\n\n    df = _filter_lifecycle(df, lifecycle)\n\n    # Filtro testuale\n""",
)
# POST search lifecycle + reverse supersession filter.
replace_once(
    "src/lele_manager/api/server.py",
    """    df = df.copy()\n\n    # Filtro testo (q)\n""",
    """    df = _filter_lifecycle(df.copy(), body.lifecycle_in)\n\n    if body.superseded_by:\n        superseded = df.get(\"superseded_by\")\n        if superseded is None:\n            return []\n        df = df[superseded.fillna(\"\").astype(str) == body.superseded_by]\n\n    # Filtro testo (q)\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """        importance_lte=body.importance_lte,\n        limit=body.limit,\n    )\n""",
    """        importance_lte=body.importance_lte,\n        lifecycle_in=body.lifecycle_in,\n        superseded_by=body.superseded_by,\n        limit=body.limit,\n    )\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """    if body.importance_lte is not None:\n        parts.append(f\"importance_lte={body.importance_lte}\")\n    if body.ids_in:\n""",
    """    if body.importance_lte is not None:\n        parts.append(f\"importance_lte={body.importance_lte}\")\n    parts.append(\n        f\"lifecycle_in={body.lifecycle_in if body.lifecycle_in is not None else ['active']}\"\n    )\n    if body.superseded_by:\n        parts.append(f\"superseded_by={body.superseded_by!r}\")\n    if body.ids_in:\n""",
)

# Canonical write resolves omitted lifecycle from current Markdown, validates target and cycles.
replace_once(
    "src/lele_manager/api/server.py",
    """def _write_lesson_to_vault(\n    *,\n    lesson_id: str,\n""",
    """def _validate_supersession_target(\n    vault_dir: Path, lesson_id: str, target_id: str | None\n) -> None:\n    if target_id is None:\n        return\n    matches = find_markdown_paths_by_id(vault_dir, target_id)\n    if len(matches) != 1:\n        raise ValueError(\"superseded_by must reference one existing canonical lesson\")\n    seen = {lesson_id}\n    current = target_id\n    while current is not None:\n        if current in seen:\n            raise ValueError(\"supersession links cannot form a cycle\")\n        seen.add(current)\n        current_matches = find_markdown_paths_by_id(vault_dir, current)\n        if len(current_matches) != 1:\n            break\n        frontmatter, _body = parse_markdown_with_frontmatter(\n            current_matches[0].read_text(encoding=\"utf-8\")\n        )\n        current = normalize_superseded_by(\n            frontmatter.get(\"superseded_by\"), lesson_id=current\n        )\n\n\ndef _write_lesson_to_vault(\n    *,\n    lesson_id: str,\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """    tags = payload.tags or []\n    date_str = _lesson_date_or_today(payload.date)\n    return write_lesson_markdown(\n""",
    """    tags = payload.tags or []\n    date_str = _lesson_date_or_today(payload.date)\n    lifecycle_value = payload.lifecycle\n    superseded_by_value = payload.superseded_by\n    if relative_path is not None:\n        existing_path = vault_dir / relative_path\n        frontmatter, _existing_body = parse_markdown_with_frontmatter(\n            existing_path.read_text(encoding=\"utf-8\")\n        )\n        if \"lifecycle\" not in payload.model_fields_set:\n            lifecycle_value = normalize_lifecycle(frontmatter.get(\"lifecycle\"))\n        if \"superseded_by\" not in payload.model_fields_set:\n            superseded_by_value = normalize_superseded_by(\n                frontmatter.get(\"superseded_by\"), lesson_id=lesson_id\n            )\n    lifecycle_value = normalize_lifecycle(lifecycle_value)\n    superseded_by_value = normalize_superseded_by(\n        superseded_by_value, lesson_id=lesson_id\n    )\n    _validate_supersession_target(vault_dir, lesson_id, superseded_by_value)\n    return write_lesson_markdown(\n""",
)
replace_once(
    "src/lele_manager/api/server.py",
    """        title=payload.title.strip() if payload.title else None,\n        relative_path=relative_path,\n    )\n""",
    """        title=payload.title.strip() if payload.title else None,\n        relative_path=relative_path,\n        lifecycle=lifecycle_value,\n        superseded_by=superseded_by_value,\n    )\n""",
)

# ---------------------------------------------------------------------------
# Export preserves maintained lifecycle metadata.
# ---------------------------------------------------------------------------
replace_once(
    "src/lele_manager/core/export.py",
    """        if lesson.get(\"title\"):\n            frontmatter[\"title\"] = lesson[\"title\"]\n\n        return render_markdown_with_frontmatter""",
    """        if lesson.get(\"title\"):\n            frontmatter[\"title\"] = lesson[\"title\"]\n        lifecycle = str(lesson.get(\"lifecycle\") or \"active\")\n        if lifecycle != \"active\":\n            frontmatter[\"lifecycle\"] = lifecycle\n        if lesson.get(\"superseded_by\"):\n            frontmatter[\"superseded_by\"] = lesson[\"superseded_by\"]\n\n        return render_markdown_with_frontmatter""",
)

# ---------------------------------------------------------------------------
# Frontend API
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/lib/api.ts",
    "export interface Lesson {\n",
    "export type LifecycleState = 'active' | 'review-needed' | 'deprecated' | 'archived'\n\nexport const ALL_LIFECYCLE_STATES: LifecycleState[] = ['active', 'review-needed', 'deprecated', 'archived']\n\nexport interface Lesson {\n",
)
replace_once(
    "frontend/src/lib/api.ts",
    """  created_at?: string | null\n}\n\nexport interface LessonSearchRequest""",
    """  created_at?: string | null\n  lifecycle: LifecycleState\n  superseded_by?: string | null\n}\n\nexport interface LessonSearchRequest""",
)
replace_once(
    "frontend/src/lib/api.ts",
    """  importance_lte?: number | null\n  limit?: number\n}\n""",
    """  importance_lte?: number | null\n  lifecycle_in?: LifecycleState[] | null\n  superseded_by?: string | null\n  limit?: number\n}\n""",
)
replace_once(
    "frontend/src/lib/api.ts",
    """  title?: string | null\n}\n\nexport interface LessonVaultCreate""",
    """  title?: string | null\n  lifecycle?: LifecycleState | null\n  superseded_by?: string | null\n}\n\nexport interface LessonVaultCreate""",
)
replace_once(
    "frontend/src/lib/api.ts",
    """  listLessons: (limit = 50) =>\n    request<Lesson[]>(`/lessons?limit=${encodeURIComponent(limit)}`),\n""",
    """  listLessons: (limit = 50, lifecycle: LifecycleState[] | null = null) => {\n    const params = new URLSearchParams({ limit: String(limit) })\n    for (const state of lifecycle ?? []) params.append('lifecycle', state)\n    return request<Lesson[]>(`/lessons?${params.toString()}`)\n  },\n""",
)

# ---------------------------------------------------------------------------
# Browse lifecycle filter
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/routes/Browse.svelte",
    "import { api, type ExportSearchRequest, type Lesson } from '../lib/api'\n",
    "import { ALL_LIFECYCLE_STATES, api, type ExportSearchRequest, type Lesson, type LifecycleState } from '../lib/api'\n",
)
replace_once(
    "frontend/src/routes/Browse.svelte",
    """  let importanceLte = $state('')\n  let limit = $state(20)\n""",
    """  let importanceLte = $state('')\n  let lifecycle = $state<LifecycleState | 'all'>('active')\n  let limit = $state(20)\n""",
)
replace_once(
    "frontend/src/routes/Browse.svelte",
    """      importance_lte: importanceLte ? Number(importanceLte) : null,\n      limit: Number(limit) || 20,\n""",
    """      importance_lte: importanceLte ? Number(importanceLte) : null,\n      lifecycle_in: lifecycle === 'all' ? [...ALL_LIFECYCLE_STATES] : [lifecycle],\n      limit: Number(limit) || 20,\n""",
)
replace_once(
    "frontend/src/routes/Browse.svelte",
    """    importanceLte = ''\n  }\n""",
    """    importanceLte = ''\n    lifecycle = 'active'\n  }\n""",
)
replace_once(
    "frontend/src/routes/Browse.svelte",
    """        <label>\n          <FieldLabel label={$messages.browseLimit} />\n          <input type=\"number\" min=\"1\" max=\"500\" bind:value={limit} />\n        </label>\n""",
    """        <label>\n          <FieldLabel label={$messages.fieldLifecycle} />\n          <select bind:value={lifecycle}>\n            <option value=\"active\">{$messages.lifecycleActive}</option>\n            <option value=\"review-needed\">{$messages.lifecycleReviewNeeded}</option>\n            <option value=\"deprecated\">{$messages.lifecycleDeprecated}</option>\n            <option value=\"archived\">{$messages.lifecycleArchived}</option>\n            <option value=\"all\">{$messages.lifecycleAll}</option>\n          </select>\n        </label>\n        <label>\n          <FieldLabel label={$messages.browseLimit} />\n          <input type=\"number\" min=\"1\" max=\"500\" bind:value={limit} />\n        </label>\n""",
)

# Lesson card makes non-active state unmistakable.
replace_once(
    "frontend/src/components/LessonCard.svelte",
    "import type { Lesson } from '../lib/api'\n",
    "import type { Lesson, LifecycleState } from '../lib/api'\nimport { messages } from '../lib/i18n'\n",
)
replace_once(
    "frontend/src/components/LessonCard.svelte",
    """  let { lesson, selected = false, onclick }: Props = $props()\n</script>\n""",
    """  let { lesson, selected = false, onclick }: Props = $props()\n\n  function lifecycleLabel(state: LifecycleState) {\n    return state === 'active' ? $messages.lifecycleActive\n      : state === 'review-needed' ? $messages.lifecycleReviewNeeded\n      : state === 'deprecated' ? $messages.lifecycleDeprecated\n      : $messages.lifecycleArchived\n  }\n</script>\n""",
)
replace_once(
    "frontend/src/components/LessonCard.svelte",
    """  <div class=\"meta row\">\n    <span>importance {lesson.importance ?? '?'}</span>\n""",
    """  <div class=\"meta row\">\n    <span class:non-active={lesson.lifecycle !== 'active'} class=\"lifecycle\">{lifecycleLabel(lesson.lifecycle)}</span>\n    <span>importance {lesson.importance ?? '?'}</span>\n""",
)
replace_once(
    "frontend/src/components/LessonCard.svelte",
    """  p {\n    margin: 0;\n""",
    """  .lifecycle {\n    font-weight: 700;\n  }\n\n  .lifecycle.non-active {\n    color: #8b1717;\n  }\n\n  p {\n    margin: 0;\n""",
)

# Detail: lifecycle, forward and reverse supersession navigation.
replace_once(
    "frontend/src/routes/Detail.svelte",
    "import { messages } from '../lib/i18n'\n",
    "import { formatMessage, messages } from '../lib/i18n'\n",
)
replace_once(
    "frontend/src/routes/Detail.svelte",
    """  let similarError = $state('')\n  let deleteTarget""",
    """  let similarError = $state('')\n  let supersedes = $state<Lesson[]>([])\n  let deleteTarget""",
)
replace_once(
    "frontend/src/routes/Detail.svelte",
    """      lesson = await api.getLesson(id)\n    } catch (e) {\n""",
    """      lesson = await api.getLesson(id)\n      supersedes = await api.searchLessons({\n        lifecycle_in: ['active', 'review-needed', 'deprecated', 'archived'],\n        superseded_by: id,\n        limit: 500,\n      })\n    } catch (e) {\n""",
)
replace_once(
    "frontend/src/routes/Detail.svelte",
    """      <div class=\"meta row\">\n        <span>{$messages.fieldTopic}: {lesson.topic ?? '—'}</span>\n""",
    """      <div class=\"lifecycle-banner\" class:non-active={lesson.lifecycle !== 'active'}>\n        <strong>{$messages.fieldLifecycle}: {lesson.lifecycle === 'active' ? $messages.lifecycleActive : lesson.lifecycle === 'review-needed' ? $messages.lifecycleReviewNeeded : lesson.lifecycle === 'deprecated' ? $messages.lifecycleDeprecated : $messages.lifecycleArchived}</strong>\n        {#if lesson.superseded_by}\n          <button type=\"button\" class=\"link-button\" onclick={() => navigate({ view: 'detail', id: lesson!.superseded_by! })}>\n            {formatMessage($messages.lifecycleSupersededBy, { id: lesson.superseded_by })}\n          </button>\n        {/if}\n      </div>\n      {#if supersedes.length}\n        <div class=\"supersedes-list\">\n          <strong>{$messages.lifecycleReplaces}</strong>\n          {#each supersedes as previous (previous.id)}\n            <button type=\"button\" class=\"link-button\" onclick={() => navigate({ view: 'detail', id: previous.id })}>{previous.id}</button>\n          {/each}\n        </div>\n      {/if}\n\n      <div class=\"meta row\">\n        <span>{$messages.fieldTopic}: {lesson.topic ?? '—'}</span>\n""",
)
replace_once(
    "frontend/src/routes/Detail.svelte",
    """  .row {\n    display: flex;\n""",
    """  .lifecycle-banner, .supersedes-list {\n    display: flex;\n    flex-wrap: wrap;\n    gap: 8px;\n    align-items: center;\n    margin-bottom: 12px;\n    padding: 8px 10px;\n    border: 1px solid var(--border);\n    border-radius: var(--radius-sm);\n  }\n\n  .lifecycle-banner.non-active {\n    border-color: #a22;\n    background: #fff7f7;\n  }\n\n  .link-button {\n    border: 0;\n    background: transparent;\n    color: var(--accent);\n    text-decoration: underline;\n    cursor: pointer;\n    padding: 0;\n  }\n\n  .row {\n    display: flex;\n""",
)

# Editor explicit lifecycle authoring.
replace_once(
    "frontend/src/routes/Editor.svelte",
    """    api,\n    type EditorMetadataOptionsResponse,\n    type Lesson,\n""",
    """    ALL_LIFECYCLE_STATES,\n    api,\n    type EditorMetadataOptionsResponse,\n    type Lesson,\n    type LifecycleState,\n""",
)
replace_once(
    "frontend/src/routes/Editor.svelte",
    """  let lessonId = $state('')\n  let loadedLesson""",
    """  let lessonId = $state('')\n  let lifecycle = $state<LifecycleState>('active')\n  let supersededBy = $state('')\n  let lifecycleTargets = $state<Lesson[]>([])\n  let loadedLesson""",
)
replace_once(
    "frontend/src/routes/Editor.svelte",
    """      title\n        ? `title: \\\"${title.replace(/\\\"/g, '\\\\\\\"')}\\\"`\n        : '',\n      '---',\n""" if False else """      title\n        ? `title: \"${title.replace(/\"/g, '\\\"')}\"`\n        : '',\n      '---',\n""",
    """      title\n        ? `title: \"${title.replace(/\"/g, '\\\"')}\"`\n        : '',\n      lifecycle !== 'active' ? `lifecycle: ${lifecycle}` : '',\n      supersededBy.trim() ? `superseded_by: ${supersededBy.trim()}` : '',\n      '---',\n""",
)
replace_once(
    "frontend/src/routes/Editor.svelte",
    """      tags = [...(lesson.tags ?? [])]\n\n      const parsed""",
    """      tags = [...(lesson.tags ?? [])]\n      lifecycle = lesson.lifecycle\n      supersededBy = lesson.superseded_by ?? ''\n\n      const parsed""",
)
replace_once(
    "frontend/src/routes/Editor.svelte",
    """      title: title.trim() || null,\n    }\n""",
    """      title: title.trim() || null,\n      lifecycle,\n      superseded_by: supersededBy.trim() || null,\n    }\n""",
)
replace_once(
    "frontend/src/routes/Editor.svelte",
    """  $effect(() => {\n    loadMetadataOptions()\n    if (id) {\n""",
    """  async function loadLifecycleTargets() {\n    try {\n      lifecycleTargets = await api.searchLessons({\n        lifecycle_in: [...ALL_LIFECYCLE_STATES],\n        limit: 500,\n      })\n    } catch {\n      lifecycleTargets = []\n    }\n  }\n\n  $effect(() => {\n    loadMetadataOptions()\n    loadLifecycleTargets()\n    if (id) {\n""",
)
replace_once(
    "frontend/src/routes/Editor.svelte",
    """      <label class=\"wide\">\n        <FieldLabel label={$messages.fieldTitle} />\n""",
    """      <label>\n        <FieldLabel label={$messages.fieldLifecycle} />\n        <select bind:value={lifecycle}>\n          <option value=\"active\">{$messages.lifecycleActive}</option>\n          <option value=\"review-needed\">{$messages.lifecycleReviewNeeded}</option>\n          <option value=\"deprecated\">{$messages.lifecycleDeprecated}</option>\n          <option value=\"archived\">{$messages.lifecycleArchived}</option>\n        </select>\n      </label>\n\n      <label>\n        <FieldLabel label={$messages.lifecycleReplacement} />\n        <input bind:value={supersededBy} list=\"lifecycle-targets\" placeholder={$messages.lifecycleReplacementPlaceholder} />\n        <datalist id=\"lifecycle-targets\">\n          {#each lifecycleTargets.filter((item) => item.id !== lessonId) as item (item.id)}\n            <option value={item.id}>{item.title ?? item.id}</option>\n          {/each}\n        </datalist>\n      </label>\n\n      <label class=\"wide\">\n        <FieldLabel label={$messages.fieldTitle} />\n""",
)

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/lib/i18n/en.ts",
    """  fieldTitle: 'Title',\n""",
    """  fieldTitle: 'Title',\n  fieldLifecycle: 'Lifecycle',\n  lifecycleActive: 'Active',\n  lifecycleReviewNeeded: 'Review needed',\n  lifecycleDeprecated: 'Deprecated',\n  lifecycleArchived: 'Archived',\n  lifecycleAll: 'All lifecycle states',\n  lifecycleReplacement: 'Superseded by',\n  lifecycleReplacementPlaceholder: 'Stable ID of the maintained replacement',\n  lifecycleSupersededBy: 'Superseded by {id}',\n  lifecycleReplaces: 'Replaces:',\n""",
)
replace_once(
    "frontend/src/lib/i18n/it.ts",
    """  fieldTitle: 'Titolo',\n""",
    """  fieldTitle: 'Titolo',\n  fieldLifecycle: 'Ciclo di vita',\n  lifecycleActive: 'Attiva',\n  lifecycleReviewNeeded: 'Da rivedere',\n  lifecycleDeprecated: 'Deprecata',\n  lifecycleArchived: 'Archiviata',\n  lifecycleAll: 'Tutti gli stati del ciclo di vita',\n  lifecycleReplacement: 'Sostituita da',\n  lifecycleReplacementPlaceholder: 'Stable ID della LeLe sostitutiva mantenuta',\n  lifecycleSupersededBy: 'Sostituita da {id}',\n  lifecycleReplaces: 'Sostituisce:',\n""",
)

# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------
append_once(
    "docs/gui-user-guide.md",
    "## Lesson lifecycle and supersession",
    """## Lesson lifecycle and supersession\n\nEvery canonical LeLe has a maintained lifecycle state. Existing Markdown with no lifecycle field is **Active** by definition and is not rewritten merely to add the default. The maintained states are **Active**, **Review needed**, **Deprecated**, and **Archived**. Lifecycle changes are explicit Editor actions; age, similarity, contradictions, or other derived signals never mutate lifecycle automatically.\n\nA LeLe may optionally set **Superseded by** to the stable ID of one existing canonical replacement. Self-links, missing/ambiguous targets, and supersession cycles are rejected. The replacement link is stored once in canonical Markdown; incoming/reverse links are derived from the projection and shown in Detail, so navigation works in both directions without duplicating relationship state.\n\nBrowse/search defaults to **Active** knowledge only. Use the Lifecycle filter to inspect Review needed, Deprecated, Archived, or all states. Non-active cards and Detail views are visually explicit rather than silently presenting obsolete knowledge as current. Search export uses the same lifecycle scope and preserves non-default `lifecycle` plus `superseded_by` in exported frontmatter.\n\nEditing body/metadata through older maintained write paths preserves existing lifecycle/supersession when those fields are not explicitly supplied. Setting lifecycle back to Active removes the redundant lifecycle field from canonical frontmatter; clearing Superseded by removes that link. No lifecycle transition deletes canonical content.\n""",
)
append_once(
    "docs/it/gui-user-guide.md",
    "## Ciclo di vita e sostituzione delle LeLe",
    """## Ciclo di vita e sostituzione delle LeLe\n\nOgni LeLe canonica ha uno stato di ciclo di vita mantenuto. Il Markdown esistente senza campo lifecycle è **Attivo** per definizione e non viene riscritto soltanto per aggiungere il default. Gli stati mantenuti sono **Attiva**, **Da rivedere**, **Deprecata** e **Archiviata**. I cambi di stato sono azioni esplicite nell’Editor: età, similarità, contraddizioni o altri segnali derivati non modificano mai automaticamente il lifecycle.\n\nUna LeLe può impostare opzionalmente **Sostituita da** con lo stable ID di una LeLe canonica sostitutiva esistente. Self-link, target mancanti/ambigui e cicli di sostituzione vengono rifiutati. Il collegamento è memorizzato una sola volta nel Markdown canonico; i link inversi vengono derivati dalla proiezione e mostrati nel Dettaglio, così la navigazione funziona in entrambe le direzioni senza duplicare stato relazionale.\n\nBrowse/ricerca mostra per default soltanto conoscenza **Attiva**. Il filtro Ciclo di vita consente di vedere Da rivedere, Deprecata, Archiviata oppure tutti gli stati. Le card non attive e il Dettaglio sono visivamente espliciti, evitando di presentare conoscenza obsoleta come corrente. L’export usa lo stesso scope lifecycle e conserva nel frontmatter esportato `lifecycle` non-default e `superseded_by`.\n\nLe modifiche di body/metadati attraverso percorsi mantenuti più vecchi preservano lifecycle/sostituzione quando tali campi non sono forniti esplicitamente. Riportare lo stato ad Attiva rimuove il campo lifecycle ridondante dal frontmatter; svuotare Sostituita da elimina il link. Nessuna transizione di lifecycle cancella contenuto canonico.\n""",
)

print("issue #213 lifecycle patch applied")
