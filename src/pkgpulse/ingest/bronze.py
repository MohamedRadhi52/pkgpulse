"""Couche bronze : une partition Parquet par jour de téléchargement, remplacée de façon atomique."""

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class Partition:
    source: str  # "archive" ou "dump"
    checksum: str


def partition_path(bronze_dir: Path, day: date) -> Path:
    return bronze_dir / "version_downloads" / f"{day}.parquet"


def read_state(con: duckdb.DuckDBPyConnection, bronze_dir: Path) -> dict[date, Partition]:
    """Source et empreinte de chaque partition déjà écrite."""
    files = sorted(str(path) for path in (bronze_dir / "version_downloads").glob("*.parquet"))
    if not files:
        return {}
    rows = con.execute(
        "SELECT date, any_value(source), any_value(checksum) "
        "FROM read_parquet($files) GROUP BY date",
        {"files": files},
    ).fetchall()
    return {day: Partition(source, checksum) for day, source, checksum in rows}


def checksum(con: duckdb.DuckDBPyConnection, table: str, day: date) -> str:
    """Empreinte MD5 des lignes d'un jour triées, identique quelle que soit la source."""
    return con.execute(
        f"SELECT md5(string_agg(version_id || ':' || downloads, ',' ORDER BY version_id)) "
        f"FROM {table} WHERE date = $day",
        {"day": day},
    ).fetchone()[0]


def write_partition(
    con: duckdb.DuckDBPyConnection,
    table: str,
    day: date,
    partition: Partition,
    extracted_at: datetime,
    bronze_dir: Path,
) -> None:
    """Remplace la partition d'un jour par les lignes de table pour ce jour."""
    query = f"""
        SELECT date, version_id, downloads, $source AS source, $checksum AS checksum,
            $extracted_at AS extracted_at
        FROM {table} WHERE date = $day ORDER BY version_id
    """
    params = {
        "source": partition.source,
        "checksum": partition.checksum,
        "extracted_at": extracted_at,
        "day": day,
    }
    _copy_atomic(con, query, params, partition_path(bronze_dir, day))


def write_table(
    con: duckdb.DuckDBPyConnection, table: str, extracted_at: datetime, bronze_dir: Path
) -> None:
    """Remplace une table de métadonnées du dump."""
    query = f"SELECT *, $extracted_at AS extracted_at FROM {table}"
    _copy_atomic(con, query, {"extracted_at": extracted_at}, bronze_dir / f"{table}.parquet")


def _copy_atomic(con: duckdb.DuckDBPyConnection, query: str, params: dict, path: Path) -> None:
    # Fichier temporaire puis renommage : un arrêt brutal ne laisse jamais de fichier à moitié
    # écrit, et les lecteurs, qui cherchent *.parquet, ignorent le temporaire.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    con.execute(
        f"COPY ({query}) TO $path (FORMAT parquet, COMPRESSION zstd)", {**params, "path": str(tmp)}
    )
    os.replace(tmp, path)
