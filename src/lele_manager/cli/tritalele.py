"""Local, non-HTTP CLI composition for the TritaLeLe review workflow."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from datetime import datetime, timezone
from enum import Enum
import io
import json
import math
from pathlib import Path
import sys
from typing import Any, TextIO

from lele_manager.adapters.canonical_markdown_vault import (
    FilesystemCanonicalMarkdownVault,
)
from lele_manager.adapters.json_candidate_repository import JsonCandidateRepository
from lele_manager.adapters.raw_sources import (
    MarkdownFileSourceAdapter,
    PlainTextFileSourceAdapter,
    RawSourceError,
    SourceDecodingError,
    SourceReadError,
    StdinSourceAdapter,
    UnsupportedSourceError,
)
from lele_manager.adapters.vault_jsonl_refresh import VaultJsonlRefresh
from lele_manager.application.candidate_approval import (
    ApprovalCandidatePersistenceError,
    ApprovalCollisionError,
    ApprovalIdentityCollisionError,
    ApprovalPathCollisionError,
    ApprovalRefreshError,
    ApprovalResult,
    ApprovalVaultStorageError,
    CandidateApprovalError,
    CandidateApprovalNotFoundError,
    CandidateApprovalService,
    InvalidApprovalInputError,
    InvalidApprovalLifecycleError,
    InvalidApprovalMetadataError,
    PartialApprovalError,
    PartialRefreshError,
    StaleApprovalRevisionError,
)
from lele_manager.application.candidate_review import (
    CandidateReviewConflictError,
    CandidateReviewError,
    CandidateReviewFilter,
    CandidateReviewService,
    CandidateReviewStorageError,
    InvalidCandidateReviewInputError,
    InvalidCandidateTransitionError,
    ReviewCandidateNotFoundError,
    StaleCandidateRevisionError,
)
from lele_manager.application.lesson_candidate import CandidateState, LessonCandidate
from lele_manager.application.raw_source import RawSource, SourceKind
from lele_manager.application.raw_source_chunking import (
    ChunkingSettings,
    DeterministicRawSourceChunker,
)
from lele_manager.application.raw_source_ingestion import (
    IngestionConflictError,
    IngestionPlanError,
    IngestionStagingError,
    PartialIngestionError,
    RawSourceIngestionError,
    RawSourceIngestionResult,
    RawSourceIngestionService,
)
from lele_manager.core.paths import candidates_path, lessons_path
from lele_manager.core.vault import resolve_vault_dir


class TritaLeLeCliInputError(Exception):
    """User input rejected before invoking an application operation."""


class TritaLeLeCliConfigurationError(Exception):
    """Configured local storage could not be resolved."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _add_json_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa solo JSON stabile.",
    )


def _add_ingestion_leaf(
    subparsers: Any, name: str, *, help_text: str
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument(
        "source_path",
        metavar="PATH|-",
        help="File .md/.markdown/.txt oppure '-' per stdin UTF-8.",
    )
    parser.add_argument(
        "--max-characters",
        type=int,
        default=ChunkingSettings().max_characters,
        metavar="N",
        help="Dimensione massima deterministica di ogni chunk (default: 2000).",
    )
    _add_json_option(parser)
    return parser


def _add_revision_and_reason(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "candidate_id",
        metavar="CANDIDATE-ID",
        help="ID esplicito del candidato.",
    )
    parser.add_argument(
        "--revision",
        required=True,
        type=int,
        metavar="N",
        help="Revisione attesa per il controllo di concorrenza.",
    )
    parser.add_argument(
        "--reason",
        help="Motivo opzionale registrato nella cronologia di revisione.",
    )
    _add_json_option(parser)


def register_commands(subparsers: Any) -> None:
    """Register the two nested TritaLeLe command groups."""
    ingest = subparsers.add_parser(
        "ingest",
        help="Prepara o mette in staging candidati da una sorgente locale.",
    )
    ingest_subparsers = ingest.add_subparsers(
        dest="ingest_command", required=True, metavar="{preview,create}"
    )
    preview = _add_ingestion_leaf(
        ingest_subparsers,
        "preview",
        help_text="Mostra il piano senza scrivere candidati o lesson.",
    )
    preview.set_defaults(tritalele_command="ingest_preview")
    create = _add_ingestion_leaf(
        ingest_subparsers,
        "create",
        help_text="Mette in staging i candidati mancanti, senza approvarli.",
    )
    create.set_defaults(tritalele_command="ingest_create")

    candidates = subparsers.add_parser(
        "candidates",
        help="Esamina e revisiona i candidati locali.",
    )
    candidate_subparsers = candidates.add_subparsers(
        dest="candidates_command",
        required=True,
        metavar="{list,show,update,accept,reject,approve}",
    )

    list_parser = candidate_subparsers.add_parser(
        "list", help="Elenca candidati in ordine deterministico."
    )
    list_parser.add_argument(
        "--state", choices=[state.value for state in CandidateState]
    )
    list_parser.add_argument(
        "--source-kind", choices=[kind.value for kind in SourceKind]
    )
    list_parser.add_argument("--source-fingerprint")
    list_parser.add_argument("--source-logical-name")
    list_parser.add_argument("--chunk-index", type=int)
    _add_json_option(list_parser)
    list_parser.set_defaults(tritalele_command="candidates_list")

    show_parser = candidate_subparsers.add_parser(
        "show", help="Mostra contenuto, provenienza e cronologia di un candidato."
    )
    show_parser.add_argument("candidate_id", metavar="CANDIDATE-ID")
    _add_json_option(show_parser)
    show_parser.set_defaults(tritalele_command="candidates_show")

    update_parser = candidate_subparsers.add_parser(
        "update", help="Revisiona proposta testuale o metadati; resta staged."
    )
    update_parser.add_argument("candidate_id", metavar="CANDIDATE-ID")
    update_parser.add_argument("--revision", required=True, type=int, metavar="N")
    text_group = update_parser.add_mutually_exclusive_group()
    text_group.add_argument("--text", dest="proposed_text")
    text_group.add_argument("--text-file", type=Path, metavar="FILE")
    update_parser.add_argument("--topic")
    update_parser.add_argument("--source")
    update_parser.add_argument("--importance", type=int)
    update_parser.add_argument("--tag", dest="tags", action="append")
    update_parser.add_argument("--date")
    update_parser.add_argument("--title")
    update_parser.add_argument("--reason")
    _add_json_option(update_parser)
    update_parser.set_defaults(tritalele_command="candidates_update")

    for command, help_text in (
        ("accept", "Sposta un candidato staged in revisione."),
        ("reject", "Rifiuta un candidato staged o in revisione."),
    ):
        parser = candidate_subparsers.add_parser(command, help=help_text)
        _add_revision_and_reason(parser)
        parser.set_defaults(tritalele_command=f"candidates_{command}")

    approve_parser = candidate_subparsers.add_parser(
        "approve", help="Approva esattamente un candidato in revisione."
    )
    approve_parser.add_argument("candidate_id", metavar="CANDIDATE-ID")
    approve_parser.add_argument("--revision", required=True, type=int, metavar="N")
    _add_json_option(approve_parser)
    approve_parser.set_defaults(tritalele_command="candidates_approve")


def _plain_json(value: object) -> object:
    if isinstance(value, Enum):
        return _plain_json(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise TypeError("non-finite values are not JSON-compatible")
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain_json(item) for item in value]
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _print_json(value: object, *, file: TextIO | None = None) -> None:
    target = sys.stdout if file is None else file
    print(
        json.dumps(
            _plain_json(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        file=target,
    )


def _provenance_dict(candidate: LessonCandidate) -> dict[str, object]:
    provenance = candidate.provenance
    span = provenance.source_span
    return {
        "source_kind": provenance.source_kind.value,
        "source_logical_name": provenance.source_logical_name,
        "source_fingerprint": provenance.source_fingerprint,
        "ingested_at": provenance.ingested_at.isoformat(),
        "chunk_index": provenance.chunk_index,
        "source_span": None if span is None else {"start": span.start, "end": span.end},
        "run_metadata": _plain_json(provenance.run_metadata),
        "transformations": _plain_json(provenance.transformations),
    }


def candidate_to_dict(candidate: LessonCandidate) -> dict[str, object]:
    """Return the stable public representation used by all candidate commands."""
    return {
        "candidate_id": candidate.candidate_id,
        "state": candidate.state.value,
        "revision": candidate.revision,
        "original_text": candidate.text,
        "proposed_text": candidate.proposed_text,
        "effective_text": candidate.effective_text,
        "proposed_metadata": _plain_json(candidate.proposed_metadata),
        "provenance": _provenance_dict(candidate),
        "review_history": [
            {
                "revision": event.revision,
                "action": event.action.value,
                "occurred_at": event.occurred_at.isoformat(),
                "previous_state": event.previous_state.value,
                "resulting_state": event.resulting_state.value,
                "reason": event.reason,
            }
            for event in candidate.review_history
        ],
    }


def _approval_dict(result: ApprovalResult) -> dict[str, object]:
    return {
        "candidate_id": result.candidate_id,
        "candidate_revision": result.candidate_revision,
        "lesson_id": result.lesson_id,
        "relative_vault_path": result.relative_vault_path,
        "vault_write_outcome": result.vault_write_outcome.value,
        "candidate_state_changed": result.candidate_state_changed,
        "refresh_outcome": {"refreshed": result.refresh_outcome.refreshed},
    }


def _ingestion_dict(
    result: RawSourceIngestionResult,
    source: RawSource,
    settings: ChunkingSettings,
) -> dict[str, object]:
    return {
        "preview": result.preview,
        "source": {
            "kind": source.kind.value,
            "logical_name": source.logical_name,
            "fingerprint": result.source_fingerprint,
        },
        "chunking": {"max_characters": settings.max_characters},
        "candidate_ids": list(result.candidate_ids),
        "created_candidate_ids": list(result.created_candidate_ids),
        "skipped_candidate_ids": list(result.skipped_candidate_ids),
        "pending_candidate_ids": list(result.pending_candidate_ids),
        "counts": {
            "planned": len(result.planned_candidates),
            "created": result.created_count,
            "skipped": result.skipped_count,
            "pending": result.pending_count,
        },
        "candidates": [candidate_to_dict(item) for item in result.planned_candidates],
    }


def _candidate_repository() -> JsonCandidateRepository:
    try:
        path = candidates_path()
    except (OSError, RuntimeError):
        raise TritaLeLeCliConfigurationError(
            "Lo storage locale dei candidati non è disponibile."
        ) from None
    return JsonCandidateRepository(path)


def _review_service() -> CandidateReviewService:
    return CandidateReviewService(_candidate_repository(), _utc_now)


def _approval_service() -> CandidateApprovalService:
    try:
        vault_dir = resolve_vault_dir()
        projection_path = lessons_path()
    except (OSError, RuntimeError):
        raise TritaLeLeCliConfigurationError(
            "La configurazione locale di vault o proiezione non è disponibile."
        ) from None
    repository = _candidate_repository()
    return CandidateApprovalService(
        repository,
        FilesystemCanonicalMarkdownVault(vault_dir),
        VaultJsonlRefresh(vault_dir, projection_path),
        _utc_now,
    )


def _load_source(source_path: str) -> RawSource:
    if source_path == "-":
        try:
            content = sys.stdin.read()
        except UnicodeDecodeError:
            raise SourceDecodingError("stdin is not valid UTF-8") from None
        except OSError:
            raise SourceReadError("could not read stdin") from None
        return StdinSourceAdapter().load(content)

    path = Path(source_path)
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return MarkdownFileSourceAdapter().load(path)
    if suffix == ".txt":
        return PlainTextFileSourceAdapter().load(path)
    raise UnsupportedSourceError("unsupported source extension")


def _chunking_settings(raw_max_characters: int) -> ChunkingSettings:
    try:
        return ChunkingSettings(max_characters=raw_max_characters)
    except ValueError:
        raise TritaLeLeCliInputError(
            "--max-characters deve essere un intero positivo."
        ) from None


def _print_ingestion_human(result: RawSourceIngestionResult) -> None:
    if result.preview:
        print(
            f"[info] Anteprima: {len(result.planned_candidates)} candidati; "
            f"{result.pending_count} da creare, {result.skipped_count} già presenti."
        )
    else:
        print(
            f"[ok] Staging completato: {result.created_count} creati, "
            f"{result.skipped_count} già presenti."
        )
    if not result.planned_candidates:
        print("[info] Nessun candidato pianificato.")
        return
    created = set(result.created_candidate_ids)
    skipped = set(result.skipped_candidate_ids)
    for candidate in result.planned_candidates:
        if candidate.candidate_id in created:
            outcome = "created"
        elif candidate.candidate_id in skipped:
            outcome = "skipped"
        else:
            outcome = "pending"
        print(
            f"- {candidate.candidate_id} | "
            f"chunk={candidate.provenance.chunk_index} | {outcome}"
        )


def _run_ingest(args: argparse.Namespace, *, preview: bool) -> int:
    source = _load_source(args.source_path)
    settings = _chunking_settings(args.max_characters)
    result = RawSourceIngestionService(
        DeterministicRawSourceChunker(), _candidate_repository(), _utc_now
    ).ingest(source, settings, preview=preview)
    payload = _ingestion_dict(result, source, settings)
    if args.json:
        _print_json(payload)
    else:
        _print_ingestion_human(result)
    return 0


def _print_candidate_summary(candidate: LessonCandidate, *, prefix: str) -> None:
    print(
        f"{prefix} {candidate.candidate_id} | stato={candidate.state.value} | "
        f"revisione={candidate.revision}"
    )


def _run_candidates_list(args: argparse.Namespace) -> int:
    filters = CandidateReviewFilter(
        state=None if args.state is None else CandidateState(args.state),
        source_kind=(
            None if args.source_kind is None else SourceKind(args.source_kind)
        ),
        source_fingerprint=args.source_fingerprint,
        source_logical_name=args.source_logical_name,
        chunk_index=args.chunk_index,
    )
    candidates = _review_service().list_candidates(filters)
    if args.json:
        _print_json(
            {
                "count": len(candidates),
                "candidates": [candidate_to_dict(item) for item in candidates],
            }
        )
    elif not candidates:
        print("[info] Nessun candidato trovato.")
    else:
        print(f"[info] Candidati: {len(candidates)}")
        for candidate in candidates:
            provenance = candidate.provenance
            print(
                f"- {candidate.candidate_id} | stato={candidate.state.value} | "
                f"revisione={candidate.revision} | "
                f"sorgente={provenance.source_logical_name} | "
                f"chunk={provenance.chunk_index}"
            )
    return 0


def _print_candidate_human(candidate: LessonCandidate) -> None:
    provenance = candidate.provenance
    span = provenance.source_span
    print(f"ID: {candidate.candidate_id}")
    print(f"Stato: {candidate.state.value}")
    print(f"Revisione: {candidate.revision}")
    print("[info] Provenienza")
    print(f"  kind: {provenance.source_kind.value}")
    print(f"  nome logico: {provenance.source_logical_name}")
    print(f"  fingerprint: {provenance.source_fingerprint}")
    print(f"  acquisito: {provenance.ingested_at.isoformat()}")
    print(f"  chunk: {provenance.chunk_index}")
    print(
        "  intervallo: "
        + ("-" if span is None else f"{span.start}:{span.end}")
    )
    print("  run metadata: " + json.dumps(_plain_json(provenance.run_metadata)))
    print("  trasformazioni: " + json.dumps(_plain_json(provenance.transformations)))
    print("[info] Testo originale")
    print(candidate.text)
    print("[info] Testo proposto")
    print(candidate.proposed_text if candidate.proposed_text is not None else "-")
    print("[info] Testo effettivo")
    print(candidate.effective_text)
    print("[info] Metadati proposti")
    print(
        json.dumps(
            _plain_json(candidate.proposed_metadata),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    print("[info] Cronologia revisione")
    if not candidate.review_history:
        print("  (vuota)")
    for event in candidate.review_history:
        reason = f" | motivo={event.reason}" if event.reason else ""
        print(
            f"  r{event.revision} {event.action.value}: "
            f"{event.previous_state.value}->{event.resulting_state.value} | "
            f"{event.occurred_at.isoformat()}{reason}"
        )


def _run_candidates_show(args: argparse.Namespace) -> int:
    candidate = _review_service().get_candidate(args.candidate_id)
    if args.json:
        _print_json(candidate_to_dict(candidate))
    else:
        _print_candidate_human(candidate)
    return 0


def _read_proposed_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        raise TritaLeLeCliInputError(
            "Il file del testo proposto non è UTF-8 valido."
        ) from None
    except OSError:
        raise TritaLeLeCliInputError(
            "Impossibile leggere il file del testo proposto."
        ) from None


def _metadata_from_args(args: argparse.Namespace) -> dict[str, object] | None:
    values = {
        "topic": args.topic,
        "source": args.source,
        "importance": args.importance,
        "tags": args.tags,
        "date": args.date,
        "title": args.title,
    }
    supplied = [value is not None for value in values.values()]
    if any(supplied) and not all(supplied):
        raise TritaLeLeCliInputError(
            "I metadati richiedono insieme --topic, --source, --importance, "
            "almeno un --tag, --date e --title."
        )
    if not any(supplied):
        return None
    return {
        "topic": args.topic,
        "source": args.source,
        "importance": args.importance,
        "tags": list(args.tags),
        "date": args.date,
        "title": args.title,
    }


def _run_candidates_update(args: argparse.Namespace) -> int:
    metadata = _metadata_from_args(args)
    text_requested = args.proposed_text is not None or args.text_file is not None
    if not text_requested and metadata is None:
        raise TritaLeLeCliInputError(
            "update richiede un nuovo testo o il set completo di metadati."
        )
    proposed_text = (
        _read_proposed_text(args.text_file)
        if args.text_file is not None
        else args.proposed_text
    )
    service = _review_service()
    current = service.get_candidate(args.candidate_id)
    updated = service.revise_candidate(
        args.candidate_id,
        expected_revision=args.revision,
        proposed_text=current.proposed_text if not text_requested else proposed_text,
        proposed_metadata=(
            current.proposed_metadata if metadata is None else metadata
        ),
        reason=args.reason,
    )
    if args.json:
        _print_json(candidate_to_dict(updated))
    else:
        _print_candidate_summary(updated, prefix="[ok]")
    return 0


def _run_candidates_accept(args: argparse.Namespace) -> int:
    updated = _review_service().accept_candidate(
        args.candidate_id,
        expected_revision=args.revision,
        reason=args.reason,
    )
    payload = {
        "candidate_id": updated.candidate_id,
        "state": updated.state.value,
        "revision": updated.revision,
    }
    if args.json:
        _print_json(payload)
    else:
        _print_candidate_summary(updated, prefix="[ok]")
    return 0


def _run_candidates_reject(args: argparse.Namespace) -> int:
    updated = _review_service().reject_candidate(
        args.candidate_id,
        expected_revision=args.revision,
        reason=args.reason,
    )
    payload = {
        "candidate_id": updated.candidate_id,
        "state": updated.state.value,
        "revision": updated.revision,
    }
    if args.json:
        _print_json(payload)
    else:
        _print_candidate_summary(updated, prefix="[ok]")
    return 0


def _run_candidates_approve(args: argparse.Namespace) -> int:
    # The established vault importer is also used by a standalone human CLI and
    # prints progress. This command owns its output contract, so keep that legacy
    # progress text out of both JSON and the concise renderer below.
    with redirect_stdout(io.StringIO()):
        result = _approval_service().approve(
            args.candidate_id, expected_revision=args.revision
        )
    payload = _approval_dict(result)
    if args.json:
        _print_json(payload)
    else:
        print(
            f"[ok] {result.candidate_id} | "
            f"revisione={result.candidate_revision}"
        )
        print(f"[info] lesson ID: {result.lesson_id}")
        print(f"[info] path vault: {result.relative_vault_path}")
        print(f"[info] scrittura vault: {result.vault_write_outcome.value}")
        print(f"[info] stato candidato modificato: {result.candidate_state_changed}")
        print(f"[info] proiezione aggiornata: {result.refresh_outcome.refreshed}")
    return 0


def _format_detail(value: object) -> str:
    plain = _plain_json(value)
    if isinstance(plain, list):
        return ", ".join(str(item) for item in plain) if plain else "(nessuno)"
    if plain is None:
        return "-"
    return str(plain)


def _emit_error(
    args: argparse.Namespace,
    *,
    error_code: str,
    message: str,
    exit_code: int,
    details: Mapping[str, object] | None = None,
) -> int:
    details = {} if details is None else dict(details)
    if getattr(args, "json", False):
        _print_json(
            {
                "error": {
                    "code": error_code,
                    "message": message,
                    "details": details,
                }
            },
            file=sys.stderr,
        )
    else:
        print(f"[errore] {message}", file=sys.stderr)
        for name in sorted(details):
            print(f"[info] {name}: {_format_detail(details[name])}", file=sys.stderr)
    return exit_code


def _raw_source_error(args: argparse.Namespace, error: RawSourceError) -> int:
    if isinstance(error, UnsupportedSourceError):
        code, message = "unsupported_source", "Tipo di sorgente non supportato."
    elif isinstance(error, SourceDecodingError):
        code, message = "invalid_source_encoding", "La sorgente non è UTF-8 valida."
    elif isinstance(error, SourceReadError):
        code, message = "source_unavailable", "Impossibile leggere la sorgente."
    else:
        code, message = "invalid_source", "La sorgente non è valida."
    return _emit_error(
        args, error_code=code, message=message, exit_code=2
    )


def _ingestion_error(args: argparse.Namespace, error: RawSourceIngestionError) -> int:
    if isinstance(error, PartialIngestionError):
        return _emit_error(
            args,
            error_code="partial_ingestion",
            message="Ingestione parziale; ripetere il comando per completarla.",
            exit_code=1,
            details={
                "created_candidate_ids": error.created_candidate_ids,
                "failed_candidate_id": error.failed_candidate_id,
                "remaining_candidate_ids": error.remaining_candidate_ids,
            },
        )
    if isinstance(error, IngestionConflictError):
        return _emit_error(
            args,
            error_code="ingestion_conflict",
            message="Conflitto nell'identità di un candidato.",
            exit_code=1,
            details={
                "candidate_id": error.candidate_id,
                "created_candidate_ids": error.created_candidate_ids,
            },
        )
    if isinstance(error, IngestionStagingError):
        return _emit_error(
            args,
            error_code="candidate_storage_unavailable",
            message="Lo storage locale dei candidati non è disponibile o è malformato.",
            exit_code=2,
            details={
                "failed_candidate_id": error.failed_candidate_id,
                "remaining_candidate_ids": error.remaining_candidate_ids,
            },
        )
    if isinstance(error, IngestionPlanError):
        return _emit_error(
            args,
            error_code="ingestion_plan_failed",
            message="Non è stato possibile costruire il piano di ingestione.",
            exit_code=1,
        )
    return _emit_error(
        args,
        error_code="ingestion_failed",
        message="Ingestione non completata.",
        exit_code=1,
    )


def _review_error(args: argparse.Namespace, error: CandidateReviewError) -> int:
    if isinstance(error, InvalidCandidateReviewInputError):
        code, message, exit_code = (
            "invalid_candidate_input",
            "Input di revisione non valido.",
            2,
        )
    elif isinstance(error, ReviewCandidateNotFoundError):
        code, message, exit_code = (
            "candidate_not_found",
            "Candidato non trovato.",
            1,
        )
    elif isinstance(error, StaleCandidateRevisionError):
        code, message, exit_code = (
            "stale_candidate_revision",
            "La revisione attesa del candidato non è più corrente.",
            1,
        )
    elif isinstance(error, InvalidCandidateTransitionError):
        code, message, exit_code = (
            "invalid_candidate_transition",
            "Transizione di stato non consentita.",
            1,
        )
    elif isinstance(error, CandidateReviewConflictError):
        code, message, exit_code = (
            "candidate_conflict",
            "Conflitto nell'identità del candidato.",
            1,
        )
    elif isinstance(error, CandidateReviewStorageError):
        code, message, exit_code = (
            "candidate_storage_unavailable",
            "Lo storage locale dei candidati non è disponibile o è malformato.",
            2,
        )
    else:
        code, message, exit_code = (
            "candidate_review_failed",
            "Operazione di revisione non completata.",
            1,
        )
    return _emit_error(
        args, error_code=code, message=message, exit_code=exit_code
    )


def _approval_error(args: argparse.Namespace, error: CandidateApprovalError) -> int:
    if isinstance(error, PartialRefreshError):
        return _emit_error(
            args,
            error_code="partial_refresh",
            message=(
                "Lesson e candidato approvato sono persistiti, ma il refresh è fallito; "
                "ripetere approve con la revisione risultante."
            ),
            exit_code=1,
            details=_approval_dict(error.partial_result),
        )
    if isinstance(error, PartialApprovalError):
        return _emit_error(
            args,
            error_code="partial_approval",
            message=(
                "La lesson canonica esiste, ma la persistenza dell'approvazione non "
                "è stata confermata; verificare candidates show e ripetere approve "
                "con la revisione corrente."
            ),
            exit_code=1,
            details={
                "candidate_id": error.candidate_id,
                "lesson_id": error.lesson_id,
                "relative_vault_path": error.relative_vault_path,
                "vault_write_outcome": error.vault_write_outcome.value,
                "candidate_state_changed": None,
                "refresh_outcome": {"refreshed": False},
            },
        )
    if isinstance(error, InvalidApprovalInputError):
        code, message, exit_code = (
            "invalid_approval_input",
            "Input di approvazione non valido.",
            2,
        )
    elif isinstance(error, InvalidApprovalMetadataError):
        code, message, exit_code = (
            "invalid_approval_metadata",
            "I metadati proposti non sono completi o validi per l'approvazione.",
            2,
        )
    elif isinstance(error, CandidateApprovalNotFoundError):
        code, message, exit_code = (
            "candidate_not_found",
            "Candidato non trovato.",
            1,
        )
    elif isinstance(error, StaleApprovalRevisionError):
        code, message, exit_code = (
            "stale_candidate_revision",
            "La revisione attesa del candidato non è più corrente.",
            1,
        )
    elif isinstance(error, InvalidApprovalLifecycleError):
        code, message, exit_code = (
            "invalid_candidate_transition",
            "Il candidato non è in uno stato approvabile.",
            1,
        )
    elif isinstance(error, ApprovalPathCollisionError):
        code, message, exit_code = (
            "vault_path_collision",
            "Collisione sul path canonico della lesson.",
            1,
        )
    elif isinstance(error, ApprovalIdentityCollisionError):
        code, message, exit_code = (
            "vault_identity_collision",
            "Collisione sull'identità canonica della lesson.",
            1,
        )
    elif isinstance(error, ApprovalCollisionError):
        code, message, exit_code = (
            "vault_collision",
            "Collisione nella pubblicazione canonica.",
            1,
        )
    elif isinstance(error, ApprovalVaultStorageError):
        code, message, exit_code = (
            "vault_storage_unavailable",
            "Il vault canonico non è disponibile.",
            2,
        )
    elif isinstance(error, ApprovalCandidatePersistenceError):
        code, message, exit_code = (
            "candidate_storage_unavailable",
            "Lo storage locale dei candidati non è disponibile o è malformato.",
            2,
        )
    elif isinstance(error, ApprovalRefreshError):
        code, message, exit_code = (
            "refresh_failed",
            "Il refresh della proiezione derivata non è riuscito.",
            2,
        )
    else:
        code, message, exit_code = (
            "approval_failed",
            "Approvazione non completata.",
            1,
        )
    return _emit_error(
        args, error_code=code, message=message, exit_code=exit_code
    )


_HANDLERS = {
    "ingest_preview": lambda args: _run_ingest(args, preview=True),
    "ingest_create": lambda args: _run_ingest(args, preview=False),
    "candidates_list": _run_candidates_list,
    "candidates_show": _run_candidates_show,
    "candidates_update": _run_candidates_update,
    "candidates_accept": _run_candidates_accept,
    "candidates_reject": _run_candidates_reject,
    "candidates_approve": _run_candidates_approve,
}


def run_command(args: argparse.Namespace) -> int:
    """Dispatch one registered leaf and translate only controlled failures."""
    try:
        handler = _HANDLERS[args.tritalele_command]
    except KeyError:
        raise RuntimeError("unregistered TritaLeLe command") from None
    try:
        return handler(args)
    except TritaLeLeCliInputError as error:
        return _emit_error(
            args,
            error_code="invalid_cli_input",
            message=str(error),
            exit_code=2,
        )
    except TritaLeLeCliConfigurationError as error:
        return _emit_error(
            args,
            error_code="local_configuration_unavailable",
            message=str(error),
            exit_code=2,
        )
    except RawSourceError as error:
        return _raw_source_error(args, error)
    except RawSourceIngestionError as error:
        return _ingestion_error(args, error)
    except CandidateReviewError as error:
        return _review_error(args, error)
    except CandidateApprovalError as error:
        return _approval_error(args, error)
