"""Import the versioned Personal Knowledge Publishing System package v1.

This boundary deliberately creates ordinary TritaLeLe candidates only.  It
does not know the vault, projection store, or any ML component.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
from typing import Callable, Mapping
from urllib.parse import urlparse
import zipfile

from lele_manager.application.lesson_candidate import (
    CandidateProvenance,
    CandidateRepository,
    CandidateRepositoryError,
    LessonCandidate,
)
from lele_manager.application.raw_source import SourceKind
from lele_manager.core.json_compat import canonical_json


class PkpsImportError(Exception):
    """Base class for controlled PKPS import failures."""


class PkpsPackageError(PkpsImportError):
    """The supplied package cannot safely be read."""


class PkpsValidationError(PkpsImportError):
    """The package does not satisfy the PKPS v1 contract."""


class PkpsConflictError(PkpsImportError):
    """A package ID has already been imported with other content."""


class PkpsPersistenceError(PkpsImportError):
    """Candidate persistence failed while staging a valid package."""


MAX_MANIFEST_BYTES = 256 * 1024
MAX_LESSON_BYTES = 16 * 1024 * 1024
MAX_ZIP_ENTRIES = 128
MAX_ZIP_UNCOMPRESSED_BYTES = 32 * 1024 * 1024


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number {value}")


def _object(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise PkpsValidationError(f"{field} must be an object")
    return value


def _non_empty_string(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise PkpsValidationError(f"{field} must be a non-empty string")
    return value


def _valid_json_strings(value: object) -> None:
    """Reject JSON strings that candidate persistence cannot safely preserve."""
    if isinstance(value, str):
        if any("\ud800" <= character <= "\udfff" for character in value):
            raise PkpsValidationError("manifest contains invalid Unicode")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _valid_json_strings(key)
            _valid_json_strings(item)
    elif isinstance(value, list):
        for item in value:
            _valid_json_strings(item)


def _relative_path(value: object) -> str:
    path = _non_empty_string(value, "lesson.path")
    if "\\" in path:
        raise PkpsValidationError(
            "lesson.path must be a normalized relative POSIX path"
        )
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or any(part in (".", "..") for part in candidate.parts):
        raise PkpsValidationError("lesson.path must be a normalized relative path")
    if candidate.as_posix() != path or path.startswith("/"):
        raise PkpsValidationError("lesson.path must be a normalized relative path")
    return path


def _utc_timestamp(value: object, field: str) -> datetime:
    raw = _non_empty_string(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise PkpsValidationError(f"{field} must be a valid UTC timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PkpsValidationError(f"{field} must be a valid UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _source(value: object) -> dict[str, object]:
    source = dict(_object(value, "source"))
    if source.get("type") not in {"youtube", "article"}:
        raise PkpsValidationError("source.type must be 'youtube' or 'article'")
    url = _non_empty_string(source.get("url"), "source.url")
    try:
        parsed = urlparse(url)
    except ValueError:
        raise PkpsValidationError(
            "source.url must be an absolute HTTP/HTTPS URL"
        ) from None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PkpsValidationError("source.url must be an absolute HTTP/HTTPS URL")
    if "title" in source:
        _non_empty_string(source["title"], "source.title")
    return source


@dataclass(frozen=True)
class PkpsPackage:
    package_id: str
    schema_version: int
    producer: Mapping[str, str]
    created_at: datetime
    source: Mapping[str, object]
    lesson_path: str
    lesson_sha256: str
    lesson_bytes: int
    lesson_text: str
    manifest: Mapping[str, object]


def _validate_manifest(manifest: object, lesson_content: bytes) -> PkpsPackage:
    document = _object(manifest, "manifest")
    _valid_json_strings(document)
    schema_version = document.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise PkpsValidationError("unsupported PKPS schema_version")
    package_id = _non_empty_string(document.get("package_id"), "package_id")
    producer_data = _object(document.get("producer"), "producer")
    if producer_data.get("name") != "gyte-study-tools":
        raise PkpsValidationError("producer.name must be 'gyte-study-tools'")
    producer = {
        "name": "gyte-study-tools",
        "version": _non_empty_string(producer_data.get("version"), "producer.version"),
    }
    created_at = _utc_timestamp(document.get("created_at"), "created_at")
    lesson = _object(document.get("lesson"), "lesson")
    lesson_path = _relative_path(lesson.get("path"))
    sha256 = lesson.get("sha256")
    if (
        type(sha256) is not str
        or len(sha256) != 64
        or any(char not in "0123456789abcdef" for char in sha256)
    ):
        raise PkpsValidationError(
            "lesson.sha256 must be 64 lowercase hexadecimal characters"
        )
    byte_count = lesson.get("bytes")
    if type(byte_count) is not int or byte_count <= 0:
        raise PkpsValidationError("lesson.bytes must be a positive integer")
    if byte_count > MAX_LESSON_BYTES:
        raise PkpsValidationError("lesson.bytes exceeds the PKPS v1 limit")
    source = _source(document.get("source"))
    if len(lesson_content) != byte_count:
        raise PkpsValidationError("lesson byte count does not match manifest")
    if hashlib.sha256(lesson_content).hexdigest() != sha256:
        raise PkpsValidationError("lesson SHA-256 does not match manifest")
    try:
        lesson_text = lesson_content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PkpsValidationError("lesson is not valid UTF-8 Markdown") from None
    return PkpsPackage(
        package_id=package_id,
        schema_version=schema_version,
        producer=producer,
        created_at=created_at,
        source=source,
        lesson_path=lesson_path,
        lesson_sha256=sha256,
        lesson_bytes=byte_count,
        lesson_text=lesson_text,
        manifest=document,
    )


def _safe_file(root: Path, relative: str) -> Path:
    target = root
    for part in PurePosixPath(relative).parts:
        target /= part
        try:
            mode = target.lstat().st_mode
        except OSError:
            raise PkpsPackageError(f"package file is missing: {relative}") from None
        if stat.S_ISLNK(mode):
            raise PkpsPackageError(f"package path contains a symlink: {relative}")
    try:
        if not target.is_file():
            raise PkpsPackageError(f"package path is not a file: {relative}")
    except OSError:
        raise PkpsPackageError(f"could not inspect package file: {relative}") from None
    return target


def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
) -> bytes:
    try:
        info = path.stat()
    except OSError:
        raise PkpsPackageError(f"could not inspect {label}") from None

    if not stat.S_ISREG(info.st_mode):
        raise PkpsPackageError(f"{label} is not a regular file")
    if info.st_size > maximum_bytes:
        raise PkpsPackageError(f"{label} exceeds the PKPS v1 size limit")

    try:
        content = path.read_bytes()
    except OSError:
        raise PkpsPackageError(f"could not read {label}") from None

    if len(content) > maximum_bytes:
        raise PkpsPackageError(f"{label} exceeds the PKPS v1 size limit")

    return content


def _load_directory(root: Path) -> PkpsPackage:
    try:
        mode = root.lstat().st_mode
    except OSError:
        raise PkpsPackageError("could not inspect package path") from None

    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise PkpsPackageError(
            "package path must be a non-symlink directory or ZIP file"
        )

    manifest_path = _safe_file(root, "pkps-manifest.json")
    manifest_content = _read_regular_file(
        manifest_path,
        maximum_bytes=MAX_MANIFEST_BYTES,
        label="manifest",
    )

    try:
        raw_manifest = manifest_content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PkpsPackageError("manifest is not valid UTF-8") from None

    try:
        manifest = json.loads(
            raw_manifest,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, ValueError, UnicodeError):
        raise PkpsValidationError("manifest is not valid JSON") from None

    lesson = _object(
        _object(manifest, "manifest").get("lesson"),
        "lesson",
    )
    lesson_path = _relative_path(lesson.get("path"))
    lesson_file = _safe_file(root, lesson_path)
    content = _read_regular_file(
        lesson_file,
        maximum_bytes=MAX_LESSON_BYTES,
        label="lesson",
    )

    return _validate_manifest(manifest, content)


def _zip_relative(name: str) -> PurePosixPath:
    if not name or "\\" in name:
        raise PkpsPackageError("ZIP entry path is invalid")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise PkpsPackageError("ZIP entry path is not normalized")
    expected = path.as_posix() + ("/" if name.endswith("/") else "")
    if expected != name:
        raise PkpsPackageError("ZIP entry path is not normalized")
    return path


def _read_zip_entry(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
    *,
    maximum_bytes: int,
    label: str,
) -> bytes:
    if entry.file_size < 0 or entry.file_size > maximum_bytes:
        raise PkpsPackageError(f"{label} exceeds the PKPS v1 size limit")

    try:
        content = archive.read(entry)
    except (OSError, RuntimeError, zipfile.BadZipFile):
        raise PkpsPackageError(f"could not read ZIP package {label}") from None

    if len(content) > maximum_bytes or len(content) != entry.file_size:
        raise PkpsPackageError(f"{label} exceeds the PKPS v1 size limit")

    return content


def _load_zip(path: Path) -> PkpsPackage:
    try:
        mode = path.lstat().st_mode
    except OSError:
        raise PkpsPackageError("could not inspect package path") from None

    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise PkpsPackageError(
            "package path must be a non-symlink directory or ZIP file"
        )

    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()

            if not entries:
                raise PkpsPackageError("ZIP package is empty")
            if len(entries) > MAX_ZIP_ENTRIES:
                raise PkpsPackageError("ZIP package exceeds the PKPS v1 entry limit")

            total_uncompressed = 0
            seen: set[str] = set()
            roots: set[str] = set()
            files: dict[str, zipfile.ZipInfo] = {}

            for entry in entries:
                if entry.file_size < 0:
                    raise PkpsPackageError("ZIP package contains an invalid entry size")

                total_uncompressed += entry.file_size
                if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise PkpsPackageError(
                        "ZIP package exceeds the PKPS v1 uncompressed-size limit"
                    )

                relative = _zip_relative(entry.filename)
                normalized = relative.as_posix()

                if normalized in seen:
                    raise PkpsPackageError("ZIP package has duplicate entries")

                seen.add(normalized)
                roots.add(relative.parts[0])

                entry_mode = entry.external_attr >> 16
                if stat.S_ISLNK(entry_mode):
                    raise PkpsPackageError("ZIP package contains a symlink")

                if not entry.is_dir():
                    files[normalized] = entry

            for name in files:
                if any(name.startswith(f"{other}/") for other in files):
                    raise PkpsPackageError("ZIP package has incompatible file roots")

            if len(roots) != 1:
                raise PkpsPackageError(
                    "ZIP package must have exactly one root directory"
                )

            root = next(iter(roots))
            manifest_name = f"{root}/pkps-manifest.json"
            manifest_entry = files.get(manifest_name)

            if manifest_entry is None:
                raise PkpsPackageError("ZIP package has no manifest at its root")

            manifest_content = _read_zip_entry(
                archive,
                manifest_entry,
                maximum_bytes=MAX_MANIFEST_BYTES,
                label="manifest",
            )

            try:
                raw_manifest = manifest_content.decode(
                    "utf-8",
                    errors="strict",
                )
            except UnicodeDecodeError:
                raise PkpsPackageError("manifest is not valid UTF-8") from None

            try:
                manifest = json.loads(
                    raw_manifest,
                    parse_constant=_reject_constant,
                    object_pairs_hook=_unique_object,
                )
            except (
                json.JSONDecodeError,
                ValueError,
                UnicodeError,
            ):
                raise PkpsValidationError("manifest is not valid JSON") from None

            lesson = _object(
                _object(manifest, "manifest").get("lesson"),
                "lesson",
            )
            lesson_path = _relative_path(lesson.get("path"))
            lesson_entry = files.get(f"{root}/{lesson_path}")

            if lesson_entry is None:
                raise PkpsPackageError("ZIP package lesson is missing")

            content = _read_zip_entry(
                archive,
                lesson_entry,
                maximum_bytes=MAX_LESSON_BYTES,
                label="lesson",
            )

    except PkpsImportError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile):
        raise PkpsPackageError("could not read ZIP package") from None

    return _validate_manifest(manifest, content)


def load_pkps_package(path: Path) -> PkpsPackage:
    """Read a directory package or a securely inspected ZIP package."""
    try:
        mode = path.lstat().st_mode
    except OSError:
        raise PkpsPackageError("could not inspect package path") from None

    try:
        if stat.S_ISLNK(mode):
            raise PkpsPackageError("package path must not be a symlink")
        if stat.S_ISDIR(mode):
            return _load_directory(path)
        if stat.S_ISREG(mode) and path.suffix.lower() == ".zip":
            return _load_zip(path)
        raise PkpsPackageError(
            "package path must be a non-symlink directory or ZIP file"
        )
    except PkpsImportError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError):
        raise PkpsPackageError("could not read PKPS package") from None


@dataclass(frozen=True)
class PkpsImportResult:
    package: PkpsPackage
    candidate: LessonCandidate
    reused: bool


def _pkps_metadata(candidate: LessonCandidate) -> Mapping[str, object] | None:
    pkps = candidate.provenance.run_metadata.get("pkps")
    return pkps if isinstance(pkps, Mapping) else None


class PkpsImportService:
    """Validate PKPS and stage it through the existing candidate repository."""

    def __init__(
        self, repository: CandidateRepository, clock: Callable[[], datetime]
    ) -> None:
        self._repository = repository
        self._clock = clock

    def import_package(self, path: Path) -> PkpsImportResult:
        package = load_pkps_package(path)
        try:
            existing = self._repository.list()
        except CandidateRepositoryError:
            raise PkpsPersistenceError("candidate storage is unavailable") from None
        for candidate in existing:
            metadata = _pkps_metadata(candidate)
            if metadata is None or metadata.get("package_id") != package.package_id:
                continue
            if metadata.get("lesson_sha256") != package.lesson_sha256:
                raise PkpsConflictError(
                    "package_id already exists with different lesson content"
                )
            return PkpsImportResult(package, candidate, reused=True)

        imported_at = self._clock()
        if imported_at.tzinfo is None or imported_at.utcoffset() is None:
            raise PkpsPersistenceError("PKPS import clock must be timezone-aware")
        try:
            provenance = CandidateProvenance(
                source_kind=SourceKind.MARKDOWN,
                source_logical_name=f"pkps:{package.package_id}",
                source_fingerprint=f"sha256:{package.lesson_sha256}",
                ingested_at=imported_at,
                run_metadata={
                    "pkps": {
                        "package_id": package.package_id,
                        "schema_version": package.schema_version,
                        "producer": dict(package.producer),
                        "created_at": package.created_at.isoformat(),
                        "source": dict(package.source),
                        "lesson_sha256": package.lesson_sha256,
                        "lesson_bytes": package.lesson_bytes,
                        "imported_at": imported_at.astimezone(timezone.utc).isoformat(),
                        "manifest": json.loads(canonical_json(package.manifest)),
                    }
                },
            )
            candidate = LessonCandidate(text=package.lesson_text, provenance=provenance)
        except (TypeError, ValueError, UnicodeError):
            raise PkpsValidationError("package provenance is not persistable") from None
        try:
            created = self._repository.create(candidate)
        except CandidateRepositoryError as exc:
            # An identical TritaLeLe identity can only be safely reused when it
            # carries the same PKPS package provenance.
            try:
                persisted = self._repository.get(candidate.candidate_id)
            except CandidateRepositoryError:
                raise PkpsPersistenceError("could not stage PKPS candidate") from None
            metadata = _pkps_metadata(persisted)
            if (
                metadata is not None
                and metadata.get("package_id") == package.package_id
                and metadata.get("lesson_sha256") == package.lesson_sha256
            ):
                return PkpsImportResult(package, persisted, reused=True)
            raise PkpsPersistenceError("could not stage PKPS candidate") from exc
        return PkpsImportResult(package, created, reused=False)
