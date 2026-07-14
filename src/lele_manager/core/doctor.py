from __future__ import annotations

import datetime as dt
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import yaml


REQUIRED_FIELDS = ("id", "topic", "source", "importance", "tags", "date", "title")
NON_EMPTY_STRING_FIELDS = ("id", "topic", "source", "title")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class _DiagnosticLoader(yaml.SafeLoader):
    """Safe YAML loader that preserves date scalars for explicit validation."""


_DiagnosticLoader.yaml_implicit_resolvers = {
    key: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:timestamp"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class DoctorOperationalError(Exception):
    """An input or vault could not be inspected."""


@dataclass(frozen=True)
class DoctorProblem:
    code: str
    message: str
    path: str
    field: Optional[str] = None
    severity: Literal["error"] = "error"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParsedMarkdown:
    frontmatter: Optional[Dict[str, Any]]
    body: str
    problem: Optional[Tuple[str, str]] = None


@dataclass(frozen=True)
class DoctorReport:
    checked_files: Tuple[str, ...]
    unique_ids: int
    problems: Tuple[DoctorProblem, ...]

    @property
    def files_checked(self) -> int:
        return len(self.checked_files)

    @property
    def error_count(self) -> int:
        return sum(problem.severity == "error" for problem in self.problems)

    @property
    def valid(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "files_checked": self.files_checked,
            "checked_files": list(self.checked_files),
            "unique_ids": self.unique_ids,
            "error_count": self.error_count,
            "problems": [problem.to_dict() for problem in self.problems],
        }


def parse_markdown_diagnostic(content: str) -> ParsedMarkdown:
    """Parse frontmatter while preserving diagnostically distinct failures."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return ParsedMarkdown(
            frontmatter=None,
            body=content,
            problem=("missing_frontmatter", "frontmatter YAML assente"),
        )

    end_idx = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if end_idx is None:
        return ParsedMarkdown(
            frontmatter=None,
            body="",
            problem=("unclosed_frontmatter", "delimitatore finale del frontmatter assente"),
        )

    yaml_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    try:
        loaded = yaml.load(yaml_text, Loader=_DiagnosticLoader)
    except yaml.YAMLError as exc:
        detail = str(exc).splitlines()[0]
        return ParsedMarkdown(
            frontmatter=None,
            body=body,
            problem=("invalid_yaml", f"YAML non valido: {detail}"),
        )

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        return ParsedMarkdown(
            frontmatter=None,
            body=body,
            problem=("frontmatter_not_mapping", "il frontmatter deve essere un mapping YAML"),
        )
    return ParsedMarkdown(frontmatter=loaded, body=body)


def _display_path(path: Path, vault_dir: Optional[Path]) -> str:
    if vault_dir is not None:
        try:
            return path.relative_to(vault_dir).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _problem(
    problems: List[DoctorProblem],
    *,
    code: str,
    message: str,
    path: str,
    field: Optional[str] = None,
) -> None:
    problems.append(DoctorProblem(code=code, message=message, path=path, field=field))


def _valid_date(value: object) -> bool:
    if isinstance(value, dt.datetime):
        return False
    if isinstance(value, dt.date):
        return value.isoformat() == str(value)
    if not isinstance(value, str) or ISO_DATE_RE.fullmatch(value) is None:
        return False
    try:
        return dt.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _validate_frontmatter(
    frontmatter: Dict[str, Any],
    body: str,
    *,
    path: Path,
    display_path: str,
    vault_dir: Optional[Path],
) -> List[DoctorProblem]:
    problems: List[DoctorProblem] = []
    for field in REQUIRED_FIELDS:
        if field not in frontmatter:
            _problem(
                problems,
                code="missing_field",
                message=f"campo obbligatorio '{field}' assente",
                path=display_path,
                field=field,
            )

    for field in NON_EMPTY_STRING_FIELDS:
        if field not in frontmatter:
            continue
        value = frontmatter[field]
        if not isinstance(value, str) or not value.strip():
            _problem(
                problems,
                code="invalid_non_empty_string",
                message=f"{field} deve essere una stringa non vuota",
                path=display_path,
                field=field,
            )

    if "importance" in frontmatter:
        importance = frontmatter["importance"]
        if not isinstance(importance, int) or isinstance(importance, bool):
            _problem(
                problems,
                code="invalid_importance_type",
                message="importance deve essere un intero",
                path=display_path,
                field="importance",
            )
        elif not 1 <= importance <= 5:
            _problem(
                problems,
                code="importance_out_of_range",
                message="importance deve essere compresa tra 1 e 5",
                path=display_path,
                field="importance",
            )

    if "tags" in frontmatter:
        tags = frontmatter["tags"]
        if not isinstance(tags, list):
            _problem(
                problems,
                code="invalid_tags_type",
                message="tags deve essere una lista",
                path=display_path,
                field="tags",
            )
        elif not tags:
            _problem(
                problems,
                code="invalid_tags",
                message="tags deve contenere almeno una stringa non vuota",
                path=display_path,
                field="tags",
            )
        elif any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            _problem(
                problems,
                code="invalid_tag",
                message="ogni tag deve essere una stringa non vuota",
                path=display_path,
                field="tags",
            )

    if "date" in frontmatter and not _valid_date(frontmatter["date"]):
        _problem(
            problems,
            code="invalid_date",
            message="date deve essere una data valida nel formato YYYY-MM-DD",
            path=display_path,
            field="date",
        )

    if not body.strip():
        _problem(
            problems,
            code="empty_body",
            message="il body Markdown non può essere vuoto",
            path=display_path,
        )

    if vault_dir is not None:
        relative = path.relative_to(vault_dir)
        parts = relative.parts
        expected_topic = parts[0] if len(parts) > 1 else None
        topic = frontmatter.get("topic")
        if expected_topic is None:
            _problem(
                problems,
                code="missing_topic_directory",
                message="il file deve trovarsi in una directory topic del vault",
                path=display_path,
                field="topic",
            )
        elif isinstance(topic, str) and topic.strip() and topic.strip() != expected_topic:
            _problem(
                problems,
                code="topic_path_mismatch",
                message=f"topic deve corrispondere alla directory '{expected_topic}'",
                path=display_path,
                field="topic",
            )

        expected_id = relative.with_suffix("").as_posix()
        lesson_id = frontmatter.get("id")
        if isinstance(lesson_id, str) and lesson_id.strip() and lesson_id.strip() != expected_id:
            _problem(
                problems,
                code="id_path_mismatch",
                message=f"id deve corrispondere al percorso '{expected_id}'",
                path=display_path,
                field="id",
            )
    return problems


def _read_and_parse(path: Path) -> ParsedMarkdown:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ParsedMarkdown(
            frontmatter=None,
            body="",
            problem=("invalid_utf8", "il file non è leggibile come UTF-8"),
        )
    except OSError as exc:
        raise DoctorOperationalError(f"impossibile leggere {path}: {exc}") from exc
    return parse_markdown_diagnostic(content)


def _markdown_files(vault_dir: Path) -> List[Path]:
    try:
        paths: List[Path] = []
        for candidate in vault_dir.rglob("*.md"):
            if not candidate.is_file():
                continue
            path = candidate.resolve()
            try:
                path.relative_to(vault_dir)
            except ValueError as exc:
                raise DoctorOperationalError(
                    f"file Markdown fuori dalla radice del vault: {candidate} -> {path}"
                ) from exc
            paths.append(path)
        return sorted(paths, key=lambda path: path.as_posix())
    except OSError as exc:
        raise DoctorOperationalError(f"impossibile scandire il vault {vault_dir}: {exc}") from exc


def _resolve_inputs(paths: Sequence[Path], vault_dir: Optional[Path]) -> Tuple[List[Path], Optional[Path]]:
    resolved_vault = vault_dir.expanduser().resolve() if vault_dir is not None else None
    if resolved_vault is not None and not resolved_vault.is_dir():
        raise DoctorOperationalError(f"vault non trovato: {resolved_vault}")

    if not paths:
        if resolved_vault is None:
            raise DoctorOperationalError("vault non disponibile (usa --vault o LELE_VAULT_DIR)")
        return _markdown_files(resolved_vault), resolved_vault

    resolved_paths: List[Path] = []
    for raw_path in paths:
        path = raw_path.expanduser().resolve()
        if not path.exists():
            raise DoctorOperationalError(f"path non trovato: {path}")
        if not path.is_file():
            raise DoctorOperationalError(f"il path non è un file: {path}")
        if resolved_vault is not None:
            try:
                path.relative_to(resolved_vault)
            except ValueError as exc:
                raise DoctorOperationalError(
                    f"file selezionato fuori dalla radice del vault: {raw_path} -> {path}"
                ) from exc
        if path.suffix.lower() != ".md":
            raise DoctorOperationalError(f"il file non è Markdown (.md): {path}")
        resolved_paths.append(path)
    return sorted(set(resolved_paths), key=lambda path: path.as_posix()), resolved_vault


def check_markdown_files(
    paths: Sequence[Path],
    *,
    vault_dir: Optional[Path] = None,
) -> DoctorReport:
    """Validate selected Markdown files, using a vault as global context when given."""
    checked_paths, resolved_vault = _resolve_inputs(paths, vault_dir)
    checked_set = set(checked_paths)
    context_paths = _markdown_files(resolved_vault) if resolved_vault is not None else checked_paths
    context_paths = sorted(set(context_paths) | checked_set, key=lambda path: path.as_posix())

    parsed_by_path: Dict[Path, ParsedMarkdown] = {}
    ids_to_paths: Dict[str, List[Path]] = {}
    for path in context_paths:
        parsed = _read_and_parse(path)
        parsed_by_path[path] = parsed
        if parsed.frontmatter is not None:
            raw_id = parsed.frontmatter.get("id")
            if isinstance(raw_id, str) and raw_id.strip():
                ids_to_paths.setdefault(raw_id.strip(), []).append(path)

    problems: List[DoctorProblem] = []
    checked_display = tuple(_display_path(path, resolved_vault) for path in checked_paths)
    for path in checked_paths:
        display_path = _display_path(path, resolved_vault)
        parsed = parsed_by_path[path]
        if parsed.problem is not None:
            code, message = parsed.problem
            _problem(problems, code=code, message=message, path=display_path)
            continue
        assert parsed.frontmatter is not None
        problems.extend(
            _validate_frontmatter(
                parsed.frontmatter,
                parsed.body,
                path=path,
                display_path=display_path,
                vault_dir=resolved_vault,
            )
        )

        raw_id = parsed.frontmatter.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            duplicate_paths = ids_to_paths.get(raw_id.strip(), [])
            if len(duplicate_paths) > 1:
                locations = ", ".join(_display_path(item, resolved_vault) for item in duplicate_paths)
                _problem(
                    problems,
                    code="duplicate_id",
                    message=f"id '{raw_id.strip()}' condiviso da: {locations}",
                    path=display_path,
                    field="id",
                )

    problems.sort(key=lambda item: (item.path, item.code, item.field or "", item.message))
    return DoctorReport(
        checked_files=checked_display,
        unique_ids=len(ids_to_paths),
        problems=tuple(problems),
    )
