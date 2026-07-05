from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_BASE_URL = os.environ.get("LELE_API_URL", "http://127.0.0.1:8000")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lele",
        description="Client CLI per LeLe Manager API.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL delle API (default: {DEFAULT_BASE_URL!r} o variabile LELE_API_URL).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ------------------------------------------------------------------
    # lele search
    # ------------------------------------------------------------------
    p_search = subparsers.add_parser(
        "search",
        help="Ricerca lezioni (POST /lessons/search).",
    )
    p_search.add_argument(
        "q",
        nargs="?",
        help="Testo da cercare (substring case-insensitive sul campo 'text').",
    )
    p_search.add_argument(
        "--topic",
        dest="topic_in",
        action="append",
        help="Filtra per uno o più topic (ripetibile).",
    )
    p_search.add_argument(
        "--source",
        dest="source_in",
        action="append",
        help="Filtra per una o più source (ripetibile).",
    )
    p_search.add_argument(
        "--min-importance",
        dest="importance_gte",
        type=int,
        help="Filtra per importance >= valore dato.",
    )
    p_search.add_argument(
        "--max-importance",
        dest="importance_lte",
        type=int,
        help="Filtra per importance <= valore dato.",
    )
    p_search.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Numero massimo di risultati (default: 10).",
    )
    p_search.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta come JSON invece che in formato umano.",
    )

    # ------------------------------------------------------------------
    # lele show <id>
    # ------------------------------------------------------------------
    p_show = subparsers.add_parser(
        "show",
        help="Mostra una singola lesson (GET /lessons/{id}).",
    )
    p_show.add_argument(
        "lesson_id",
        help="ID della lesson.",
    )
    p_show.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta come JSON invece che in formato umano.",
    )

    # ------------------------------------------------------------------
    # lele similar <id>
    # ------------------------------------------------------------------
    p_similar = subparsers.add_parser(
        "similar",
        help="Mostra lesson simili (GET /lessons/{id}/similar).",
    )
    p_similar.add_argument(
        "lesson_id",
        help="ID della lesson da usare come query.",
    )
    p_similar.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Numero di risultati simili (default: 5).",
    )
    p_similar.add_argument(
        "--min-score",
        type=float,
        default=0.1,
        help="Soglia minima di similarità (default: 0.1).",
    )
    p_similar.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta come JSON invece che in formato umano.",
    )
    p_similar.add_argument(
        "--explain",
        action="store_true",
        help="Include rank, topic e meta di debug (explain=true).",
    )


    # ------------------------------------------------------------------
    # lele suggest
    # ------------------------------------------------------------------
    p_suggest = subparsers.add_parser(
        "suggest",
        help="Suggerisce lesson simili a testo libero (POST /similar).",
    )
    src = p_suggest.add_mutually_exclusive_group(required=False)
    src.add_argument(
        "--text",
        help="Testo query esplicito.",
    )
    src.add_argument(
        "--file",
        type=str,
        help="Legge testo da file.",
    )
    src.add_argument(
        "--watch",
        type=str,
        help="Monitora un file e ristampa suggerimenti quando cambia.",
    )
    p_suggest.add_argument(
        "--every",
        type=int,
        default=2,
        help="Intervallo (s) per --watch (default: 2).",
    )
    p_suggest.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Numero di risultati simili (default: 5).",
    )
    p_suggest.add_argument(
        "--min-score",
        type=float,
        default=0.1,
        help="Soglia minima di similarità (default: 0.1).",
    )
    p_suggest.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta come JSON invece che in formato umano.",
    )
    p_suggest.add_argument(
        "--explain",
        action="store_true",
        help="Include rank, topic e meta di debug (explain=true).",
    )
    # ------------------------------------------------------------------
    # lele train-topic
    # ------------------------------------------------------------------
    p_train = subparsers.add_parser(
        "train-topic",
        help="Allena il topic model via API (POST /train/topic).",
    )
    p_train.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta come JSON invece che in formato umano.",
    )

    # ------------------------------------------------------------------
    # lele stats
    # ------------------------------------------------------------------
    p_stats = subparsers.add_parser(
        "stats",
        help="Statistiche aggregate sul dataset (GET /stats/summary).",
    )
    p_stats.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta come JSON invece che in formato umano.",
    )

    # ------------------------------------------------------------------
    # lele timeline
    # ------------------------------------------------------------------
    p_timeline = subparsers.add_parser(
        "timeline",
        help="Timeline acquisizione conoscenza (GET /stats/timeline).",
    )
    p_timeline.add_argument(
        "--group-by",
        choices=["year", "month", "topic"],
        default="month",
        help="Raggruppamento (default: month).",
    )
    p_timeline.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta come JSON invece che in formato umano.",
    )

    return parser


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _print_human_lessons(results: List[Dict[str, Any]]) -> None:
    if not results:
        print("[info] Nessuna lesson trovata.")
        return

    for item in results:
        lesson_id = item.get("id", "")
        topic = item.get("topic") or "-"
        importance = item.get("importance")
        importance_str = str(importance) if importance is not None else "-"
        title = item.get("title") or ""

        text = (item.get("text") or "").replace("\n", " ")
        if len(text) > 140:
            text = text[:137] + "..."

        header = f"- {lesson_id} | topic={topic} | importance={importance_str}"
        print(header)
        if title:
            print(f"  {title}")
        print(f"  {text}")


def _print_human_lesson(item: Dict[str, Any]) -> None:
    lesson_id = item.get("id", "")
    title = item.get("title") or ""
    topic = item.get("topic") or "-"
    source = item.get("source") or "-"
    importance = item.get("importance")
    importance_str = str(importance) if importance is not None else "-"
    date = item.get("date") or "-"
    tags = item.get("tags") or []

    print(f"ID:   {lesson_id}")
    if title:
        print(f"Titolo: {title}")
    print(f"Topic: {topic}")
    print(f"Source: {source}")
    print(f"Importanza: {importance_str}")
    print(f"Data: {date}")
    if tags:
        print(f"Tag:  {', '.join(str(t) for t in tags)}")
    print("")
    print(item.get("text") or "")


def _print_human_similar(results: List[Dict[str, Any]], query: str, meta: Dict[str, Any] | None = None) -> None:
    print("=== Query ===")
    q = query.replace("\n", " ")
    if len(q) > 140:
        q = q[:137] + "..."
    print(q)
    if meta:
        parts = [f"top_k={meta.get('top_k')}", f"min_score={meta.get('min_score')}"]
        if meta.get("query_topic"):
            parts.append(f"query_topic={meta['query_topic']}")
        if meta.get("query_tags"):
            parts.append(f"query_tags={','.join(meta['query_tags'])}")
        print(f"[meta] {', '.join(str(p) for p in parts)}")
    print("")
    if not results:
        print("[info] Nessuna lesson simile trovata.")
        return

    print("=== Risultati simili ===")
    for r in results:
        lesson_id = r.get("id", "")
        score = r.get("score", 0.0)
        rank = r.get("rank")
        topic = r.get("topic")
        text_preview = r.get("text_preview", "")
        rank_prefix = f"#{rank} " if rank is not None else ""
        topic_suffix = f" | topic={topic}" if topic else ""
        print(f"- {rank_prefix}{lesson_id} | score={score:.3f}{topic_suffix}")
        tags_shared = r.get("tags_shared") or []
        if tags_shared:
            print(f"  tag in comune: {', '.join(str(t) for t in tags_shared)}")
        print(f"  {text_preview}")


# ----------------------------------------------------------------------
# Command handlers
# ----------------------------------------------------------------------
def cmd_search(base_url: str, args: argparse.Namespace) -> int:
    payload: Dict[str, Any] = {
        "q": args.q,
        "topic_in": args.topic_in,
        "source_in": args.source_in,
        "importance_gte": args.importance_gte,
        "importance_lte": args.importance_lte,
        "limit": args.limit,
    }
    # Rimuovo i None, lasciando 0/False se mai servissero
    payload = {k: v for k, v in payload.items() if v is not None}

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        try:
            resp = client.post("/lessons/search", json=payload)
        except httpx.RequestError as exc:
            print(f"[errore] Errore di rete verso {exc.request.url}: {exc}", file=sys.stderr)
            return 1

    if resp.status_code >= 400:
        print(f"[errore] {resp.status_code} {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    if args.json:
        _print_json(data)
    else:
        _print_human_lessons(data)
    return 0


def cmd_show(base_url: str, args: argparse.Namespace) -> int:
    lesson_id = args.lesson_id

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        try:
            resp = client.get(f"/lessons/{lesson_id}")
        except httpx.RequestError as exc:
            print(f"[errore] Errore di rete verso {exc.request.url}: {exc}", file=sys.stderr)
            return 1

    if resp.status_code == 404:
        print(f"[errore] LeLe con id={lesson_id!r} non trovata.", file=sys.stderr)
        return 1

    if resp.status_code >= 400:
        print(f"[errore] {resp.status_code} {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    if args.json:
        _print_json(data)
    else:
        _print_human_lesson(data)
    return 0


def cmd_similar(base_url: str, args: argparse.Namespace) -> int:
    lesson_id = args.lesson_id
    params = {
        "top_k": args.top_k,
        "min_score": args.min_score,
    }
    if getattr(args, "explain", False):
        params["explain"] = True

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        try:
            resp = client.get(f"/lessons/{lesson_id}/similar", params=params)
        except httpx.RequestError as exc:
            print(f"[errore] Errore di rete verso {exc.request.url}: {exc}", file=sys.stderr)
            return 1

    if resp.status_code == 404:
        print(f"[errore] LeLe con id={lesson_id!r} non trovata.", file=sys.stderr)
        return 1

    if resp.status_code >= 400:
        print(f"[errore] {resp.status_code} {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    query_text = data.get("query", "")
    results = data.get("results", [])
    meta = data.get("meta")

    if args.json:
        _print_json(data)
    else:
        _print_human_similar(results, query_text, meta)
    return 0

def _read_text_or_stdin(args: argparse.Namespace) -> str:
    if getattr(args, "text", None):
        return str(args.text)
    f = getattr(args, "file", None)
    if f:
        return Path(f).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def cmd_suggest(base_url: str, args: argparse.Namespace) -> int:
    def do_once(text: str) -> int:
        text = (text or "").strip()
        if not text:
            print("[errore] Testo query vuoto.", file=sys.stderr)
            return 1

        payload: Dict[str, Any] = {
            "text": text,
            "top_k": args.top_k,
            "min_score": args.min_score,
        }

        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            try:
                post_kwargs: Dict[str, Any] = {"json": payload}
                if getattr(args, "explain", False):
                    post_kwargs["params"] = {"explain": "true"}
                resp = client.post("/similar", **post_kwargs)
            except httpx.RequestError as exc:
                print(f"[errore] Errore di rete verso {exc.request.url}: {exc}", file=sys.stderr)
                return 1

        if resp.status_code == 503:
            print("[errore] Modello mancante. Allena prima con: lele train-topic", file=sys.stderr)
            return 1

        if resp.status_code >= 400:
            print(f"[errore] {resp.status_code} {resp.text}", file=sys.stderr)
            return 1

        data = resp.json()
        if args.json:
            _print_json(data)
        else:
            query_text = data.get("query", "")
            results = data.get("results", [])
            meta = data.get("meta")
            _print_human_similar(results, query_text, meta)
        return 0

    watch = getattr(args, "watch", None)
    if watch:
        p = Path(watch)
        last: Optional[str] = None
        while True:
            try:
                cur = p.read_text(encoding="utf-8")
            except OSError as exc:
                print(f"[errore] Impossibile leggere {p}: {exc}", file=sys.stderr)
                return 1

            if cur != last:
                print("=== suggest ===")
                rc = do_once(cur)
                if rc != 0:
                    return rc
                last = cur
            time.sleep(int(args.every))
        return 0
    else:
        text = _read_text_or_stdin(args)
        return do_once(text)
def cmd_train_topic(base_url: str, args: argparse.Namespace) -> int:  # noqa: ARG001
    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        try:
            resp = client.post("/train/topic")
        except httpx.RequestError as exc:
            print(f"[errore] Errore di rete verso {exc.request.url}: {exc}", file=sys.stderr)
            return 1

    if resp.status_code >= 400:
        print(f"[errore] {resp.status_code} {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    if args.json:
        _print_json(data)
    else:
        msg = data.get("message", "Topic model allenato.")
        n_lessons = data.get("n_lessons")
        topics = data.get("topics", [])
        print(f"[ok] {msg}")
        if n_lessons is not None:
            print(f"[info] LeLe usate per il training: {n_lessons}")
        if topics:
            print(f"[info] Topic visti: {', '.join(topics)}")
    return 0


def cmd_stats(base_url: str, args: argparse.Namespace) -> int:
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        try:
            resp = client.get("/stats/summary")
        except httpx.RequestError as exc:
            print(f"[errore] Errore di rete verso {exc.request.url}: {exc}", file=sys.stderr)
            return 1

    if resp.status_code >= 400:
        print(f"[errore] {resp.status_code} {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    if args.json:
        _print_json(data)
        return 0

    print(f"[info] LeLe: {data.get('n_lessons', 0)} | Topic: {data.get('n_topics', 0)} | Tag: {data.get('n_unique_tags', 0)}")
    print(f"[info] Lunghezza media: {data.get('avg_text_length')} caratteri")
    if data.get("avg_importance") is not None:
        print(f"[info] Importance media: {data.get('avg_importance')}")
    top_tags = data.get("top_tags") or []
    if top_tags:
        print("[info] Top tag:", ", ".join(f"{t['tag']}({t['count']})" for t in top_tags[:8]))
    return 0


def cmd_timeline(base_url: str, args: argparse.Namespace) -> int:
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        try:
            resp = client.get("/stats/timeline", params={"group_by": args.group_by})
        except httpx.RequestError as exc:
            print(f"[errore] Errore di rete verso {exc.request.url}: {exc}", file=sys.stderr)
            return 1

    if resp.status_code >= 400:
        print(f"[errore] {resp.status_code} {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    if args.json:
        _print_json(data)
        return 0

    print(f"[info] Timeline group_by={data.get('group_by')}")
    for bucket in data.get("buckets") or []:
        print(f"  {bucket.get('key')}: {bucket.get('count')} LeLe")
    return 0


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    base_url = (args.base_url or DEFAULT_BASE_URL).rstrip("/")

    try:
        if args.command == "search":
            code = cmd_search(base_url, args)
        elif args.command == "show":
            code = cmd_show(base_url, args)
        elif args.command == "similar":
            code = cmd_similar(base_url, args)
        elif args.command == "suggest":
            code = cmd_suggest(base_url, args)
        elif args.command == "train-topic":
            code = cmd_train_topic(base_url, args)
        elif args.command == "stats":
            code = cmd_stats(base_url, args)
        elif args.command == "timeline":
            code = cmd_timeline(base_url, args)
        else:
            parser.error(f"Comando non riconosciuto: {args.command!r}")
            return
    except KeyboardInterrupt:
        print("[errore] Interrotto dall'utente.", file=sys.stderr)
        code = 1

    sys.exit(code)
