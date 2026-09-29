"""Ingestion du dump quotidien : 90 derniers jours de téléchargements et métadonnées."""

import json
import logging
import shutil
import tarfile
import tempfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath

import duckdb

from pkgpulse.ingest import bronze, contracts
from pkgpulse.ingest.download import open_url
from pkgpulse.ingest.junction import should_write

log = logging.getLogger(__name__)

METADATA = [contracts.CRATES, contracts.VERSIONS, contracts.CATEGORIES, contracts.CRATES_CATEGORIES]


def extract(url: str, workdir: Path) -> int:
    """Lit le dump en flux, n'écrit sur disque que les fichiers utiles et renvoie sa taille."""
    wanted = {"metadata.json"} | {f"{c.name}.csv" for c in [contracts.VERSION_DOWNLOADS, *METADATA]}
    with open_url(url) as response, tarfile.open(fileobj=response, mode="r|gz") as tar:
        size = int(response.headers["Content-Length"])
        for member in tar:
            name = PurePosixPath(member.name).name
            if member.isfile() and name in wanted:
                with tar.extractfile(member) as src, (workdir / name).open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    missing = sorted(name for name in wanted if not (workdir / name).exists())
    if missing:
        raise contracts.ContractError(f"dump : fichiers absents {missing}")
    return size


def ingest_dump(bronze_dir: Path, url: str) -> list[date]:
    """Écrit les métadonnées puis les partitions des jours présents dans le dump.

    Renvoie les jours écrits : jours nouveaux, ou jours déjà vus dont le compte a changé.
    """
    con = duckdb.connect()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        size = extract(url, workdir)
        timestamp = json.loads((workdir / "metadata.json").read_text())["timestamp"]
        extracted_at = datetime.fromisoformat(timestamp).replace(tzinfo=None)
        for contract in [contracts.VERSION_DOWNLOADS, *METADATA]:
            contracts.load(con, workdir / f"{contract.name}.csv", contract)

    # Métadonnées d'abord : toute version citée dans les téléchargements est alors connue.
    for contract in METADATA:
        bronze.write_table(con, contract.name, extracted_at, bronze_dir)

    state = bronze.read_state(con, bronze_dir)
    rows = con.sql("SELECT DISTINCT date FROM version_downloads ORDER BY date").fetchall()
    days = [row[0] for row in rows]
    written, late = [], 0
    for day in days:
        partition = bronze.Partition("dump", bronze.checksum(con, "version_downloads", day))
        if not should_write(state.get(day), partition):
            continue
        if day in state:
            late += 1
            log_late_data(con, bronze_dir, day)
        bronze.write_partition(con, "version_downloads", day, partition, extracted_at, bronze_dir)
        written.append(day)

    log.info(
        "Bilan dump du %s (%d Mo) : %d jours du %s au %s, %d partitions écrites dont %d corrigées",
        extracted_at,
        size // 10**6,
        len(days),
        days[0],
        days[-1],
        len(written),
        late,
    )
    return written


def log_late_data(con: duckdb.DuckDBPyConnection, bronze_dir: Path, day: date) -> None:
    """Journalise l'écart entre la partition déjà écrite et le nouveau compte du même jour."""
    path = str(bronze.partition_path(bronze_dir, day))
    old = con.execute("SELECT sum(downloads) FROM read_parquet($path)", {"path": path}).fetchone()[
        0
    ]
    query = "SELECT sum(downloads) FROM version_downloads WHERE date = $day"
    new = con.execute(query, {"day": day}).fetchone()[0]
    log.info(
        "%s : données tardives, %d téléchargements au lieu de %d (%+.2f %%)",
        day,
        new,
        old,
        100 * (new / old - 1),
    )
