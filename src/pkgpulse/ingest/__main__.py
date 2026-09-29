"""Ligne de commande : python -m pkgpulse.ingest archive|dump."""

import argparse
import logging
from datetime import date

from pkgpulse.config import BRONZE_DIR, HISTORY_START, SOURCE_URL
from pkgpulse.ingest.archive import ingest_archive
from pkgpulse.ingest.dump import ingest_dump


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pkgpulse.ingest")
    commands = parser.add_subparsers(dest="command", required=True)
    archive = commands.add_parser("archive", help="backfill et mise à jour depuis l'archive")
    archive.add_argument("--start", type=date.fromisoformat, default=HISTORY_START)
    archive.add_argument("--end", type=date.fromisoformat)
    archive.add_argument("--force", action="store_true", help="retélécharger les jours archivés")
    commands.add_parser("dump", help="90 derniers jours et métadonnées depuis le dump quotidien")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.command == "archive":
        ingest_archive(BRONZE_DIR, SOURCE_URL, args.start, args.end, args.force)
    else:
        ingest_dump(BRONZE_DIR, f"{SOURCE_URL}/db-dump.tar.gz")


if __name__ == "__main__":
    main()
