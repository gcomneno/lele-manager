import argparse
import logging
import time

from pathlib import Path
from typing import Dict, Sequence

logger = logging.getLogger(__name__)

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="File watcher minimale basato su polling.")
    parser.add_argument("directory", type=Path, help="Directory da monitorare")
    parser.add_argument(
        "--interval",
        "-n",
        type=float,
        default=2.0,
        help="Intervallo di polling in secondi (default: 2.0)",
    )
    return parser.parse_args(argv)

def snapshot(dir_path: Path) -> Dict[Path, float]:
    """Ritorna una mappa {file -> mtime} per tutti i file sotto dir_path."""
    return {
        p: p.stat().st_mtime
        for p in dir_path.rglob("*")
        if p.is_file()
    }

def watch(directory: Path, interval: float = 2.0) -> None:
    if not directory.exists() or not directory.is_dir():
        logger.error("Directory non valida: %s", directory)
        raise SystemExit(1)

    logger.info("Watching directory: %s", directory)
    prev = snapshot(directory)

    try:
        while True:
            time.sleep(interval)
            current = snapshot(directory)

            # nuovi file
            for path in current.keys() - prev.keys():
                logger.info("Nuovo file: %s", path)

            # modifiche
            for path in current.keys() & prev.keys():
                if current[path] != prev[path]:
                    logger.info("File modificato: %s", path)

            prev = current
    except KeyboardInterrupt:
        logger.info("Interrotto dall'utente.")

def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    watch(args.directory, args.interval)

if __name__ == "__main__":
    main()
