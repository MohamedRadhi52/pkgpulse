"""Échantillon synthétique au format bronze, pour exécuter dbt sans télécharger crates.io."""

import argparse
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import duckdb

from pkgpulse.config import HISTORY_START
from pkgpulse.ingest import bronze

CRATES = 30
ARCHIVE_DELAY = timedelta(days=91)


def write_sample(bronze_dir: Path, start: date, end: date) -> None:
    """Écrit une partition par jour de start à end ; end, pris dans un dump à 2 h, est partiel."""
    con = duckdb.connect()
    con.execute(f"""
        CREATE TABLE categories AS SELECT * FROM (VALUES
            (1, 'Development tools', 'development-tools'),
            (2, 'Testing', 'development-tools::testing'),
            (3, 'Web programming', 'web-programming'),
            (4, 'Asynchronous', 'asynchronous')
        ) AS t(id, category, slug);

        -- Une ancienne version par paquet, et une nouvelle publiée pendant la période.
        CREATE TABLE versions AS
        SELECT 2 * i - 1 AS id, i AS crate_id, '1.0.0' AS num,
            TIMESTAMP '2024-01-01' AS created_at, false AS yanked
        FROM range(1, {CRATES} + 1) AS t(i)
        UNION ALL
        SELECT 2 * i, i, '1.1.0', DATE '{start}' + INTERVAL 7 DAY * i, false
        FROM range(1, {CRATES} + 1) AS t(i);

        CREATE TABLE crates AS
        SELECT crate_id AS id, 'crate-' || crate_id AS name,
            TIMESTAMP '2020-01-01' AS created_at, max(created_at) AS updated_at
        FROM versions GROUP BY crate_id;

        CREATE TABLE crates_categories AS
        SELECT id AS crate_id, 1 + id % 4 AS category_id FROM crates;

        -- Demande décroissante avec le rang du paquet, week-end à moitié, bruit de 20 %.
        CREATE TABLE downloads AS
        SELECT day::DATE AS date, versions.id AS version_id,
            round(10000 / versions.crate_id
                * CASE WHEN dayofweek(day) IN (0, 6) THEN 0.5 ELSE 1 END
                * (0.8 + 0.4 * random()))::BIGINT AS downloads
        FROM range(DATE '{start}', DATE '{end}' + INTERVAL 1 DAY, INTERVAL 1 DAY) AS t(day)
        INNER JOIN versions ON versions.created_at <= day;
    """)

    dump_time = datetime.combine(end, time(2))
    for (day,) in con.sql("SELECT DISTINCT date FROM downloads ORDER BY date").fetchall():
        if day + ARCHIVE_DELAY < end:
            source, extracted_at = "archive", datetime.combine(day + ARCHIVE_DELAY, time(23, 30))
        else:
            source, extracted_at = "dump", dump_time
        partition = bronze.Partition(source, bronze.checksum(con, "downloads", day))
        bronze.write_partition(con, "downloads", day, partition, extracted_at, bronze_dir)
    for table in ("crates", "versions", "categories", "crates_categories"):
        bronze.write_table(con, table, dump_time, bronze_dir)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pkgpulse.sample", description=__doc__)
    parser.add_argument("data_dir", type=Path, help="dossier cible, par exemple data/sample")
    args = parser.parse_args()
    write_sample(args.data_dir / "bronze", HISTORY_START, datetime.now(UTC).date())


if __name__ == "__main__":
    main()
