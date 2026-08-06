"""CLI adapter for Personal Knowledge Publishing System package imports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.application.pkps_import import (
    PkpsConflictError,
    PkpsImportError,
    PkpsImportResult,
    PkpsImportService,
    PkpsPackageError,
    PkpsPersistenceError,
    PkpsValidationError,
)
from lele_manager.core.paths import candidates_path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def register_commands(subparsers: Any) -> None:
    """Register the ``lele pkps import`` command group."""
    pkps = subparsers.add_parser(
        "pkps", help="Importa package Personal Knowledge Publishing System (PKPS)."
    )
    nested = pkps.add_subparsers(dest="pkps_command", required=True, metavar="{import}")
    importer = nested.add_parser(
        "import", help="Valida un package PKPS e lo mette in staging TritaLeLe."
    )
    importer.add_argument("package_path", type=Path, metavar="PACKAGE_PATH")
    importer.add_argument(
        "--json", action="store_true", help="Stampa solo JSON stabile."
    )
    importer.set_defaults(pkps_command="import")


def _repository() -> JsonCandidateRepository:
    try:
        return JsonCandidateRepository(candidates_path())
    except (OSError, RuntimeError):
        raise PkpsPersistenceError(
            "candidate storage configuration is unavailable"
        ) from None


def _payload(result: PkpsImportResult) -> dict[str, object]:
    package = result.package
    return {
        "package_id": package.package_id,
        "schema_version": package.schema_version,
        "producer": dict(package.producer),
        "source": dict(package.source),
        "lesson_sha256": package.lesson_sha256,
        "lesson_bytes": package.lesson_bytes,
        "candidate_id": result.candidate.candidate_id,
        "candidate_status": result.candidate.state.value,
        "reused": result.reused,
        "idempotent": result.reused,
        "provenance_available": True,
    }


def _print_json(value: object, *, file: Any = None) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), file=file)


def _error(args: argparse.Namespace, code: str, message: str, exit_code: int) -> int:
    if args.json:
        _print_json({"error": {"code": code, "message": message}}, file=sys.stderr)
    else:
        print(f"[errore] {message}", file=sys.stderr)
    return exit_code


def _human(result: PkpsImportResult) -> None:
    package = result.package
    outcome = "riutilizzato (idempotente)" if result.reused else "messo in staging"
    print(f"[ok] Package PKPS {outcome}.")
    print(f"Package: {package.package_id} (schema v{package.schema_version})")
    print(
        f"Candidato: {result.candidate.candidate_id} | stato={result.candidate.state.value}"
    )
    print(f"Lesson: sha256={package.lesson_sha256} | bytes={package.lesson_bytes}")
    print("Provenienza PKPS: disponibile nel candidato TritaLeLe.")


def run_command(args: argparse.Namespace) -> int:
    """Run a PKPS leaf and translate only stable domain failures."""
    try:
        if args.pkps_command != "import":
            raise RuntimeError("unregistered PKPS command")
        result = PkpsImportService(_repository(), _utc_now).import_package(
            args.package_path
        )
        if args.json:
            _print_json(_payload(result))
        else:
            _human(result)
        return 0
    except PkpsConflictError as error:
        return _error(args, "package_id_conflict", str(error), 1)
    except PkpsValidationError as error:
        return _error(args, "invalid_package", str(error), 1)
    except PkpsPackageError as error:
        return _error(args, "unreadable_package", str(error), 1)
    except PkpsPersistenceError as error:
        return _error(args, "candidate_storage_unavailable", str(error), 2)
    except PkpsImportError as error:
        return _error(args, "pkps_import_failed", str(error), 1)
