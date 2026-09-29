"""Backfill et mise à jour quotidienne depuis l'archive des téléchargements."""

import logging
import tempfile
from datetime import date
from pathlib import Path

import duckdb

from pkgpulse.ingest import bronze, contracts
from pkgpulse.ingest.download import download, fetch_json
from pkgpulse.ingest.junction import should_write

log = logging.getLogger(__name__)


def available_days(base_url: str) -> list[date]:
    index = fetch_json(f"{base_url}/archive/version-downloads/index.json")
    return sorted(date.fromisoformat(entry["name"].removesuffix(".csv")) for entry in index)


def ingest_archive(
    bronze_dir: Path, base_url: str, start: date, end: date | None = None, force: bool = False
) -> list[date]:
    """Écrit une partition par jour d'archive entre start et end, et renvoie les jours écrits.

    Les jours déjà pris dans l'archive ne sont pas retéléchargés, sauf avec force.
    """
    con = duckdb.connect()
    state = bronze.read_state(con, bronze_dir)
    archived = {day for day, partition in state.items() if partition.source == "archive"}
    days = [day for day in available_days(base_url) if start <= day <= (end or date.max)]
    todo = [day for day in days if force or day not in archived]

    written = []
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "archive.csv"
        for day in todo:
            extracted_at = download(f"{base_url}/archive/version-downloads/{day}.csv", csv_path)
            contracts.load(con, csv_path, contracts.ARCHIVE)
            con.execute(
                "CREATE OR REPLACE TABLE day_downloads AS "
                "SELECT $day::DATE AS date, version_id, downloads FROM archive",
                {"day": day},
            )
            partition = bronze.Partition("archive", bronze.checksum(con, "day_downloads", day))
            if should_write(state.get(day), partition):
                bronze.write_partition(
                    con, "day_downloads", day, partition, extracted_at, bronze_dir
                )
                written.append(day)
                log.info("%s : partition écrite depuis l'archive", day)

    log.info(
        "Bilan archive : %d jours disponibles depuis le %s, %d téléchargés, %d partitions écrites",
        len(days),
        start,
        len(todo),
        len(written),
    )
    return written
