from datetime import date, datetime, timedelta
from urllib.error import HTTPError

import duckdb
import pytest

from pkgpulse.ingest import bronze
from pkgpulse.ingest.archive import ingest_archive
from pkgpulse.ingest.contracts import ContractError
from pkgpulse.ingest.dump import ingest_dump

D1, D2, D3, D4 = (date(2026, 6, 27) + timedelta(days=i) for i in range(4))
DUMP_TIME = datetime(2026, 7, 1, 2, 0, 15)


@pytest.fixture
def bronze_dir(tmp_path):
    return tmp_path / "bronze"


def run_archive(crates_io, bronze_dir, **options):
    return ingest_archive(bronze_dir, crates_io.url, D1, **options)


def run_dump(crates_io, bronze_dir):
    return ingest_dump(bronze_dir, f"{crates_io.url}/db-dump.tar.gz")


def state(bronze_dir):
    return bronze.read_state(duckdb.connect(), bronze_dir)


def sources(bronze_dir):
    return {day: partition.source for day, partition in state(bronze_dir).items()}


def downloads(bronze_dir, day):
    path = str(bronze.partition_path(bronze_dir, day))
    query = "SELECT version_id, downloads FROM read_parquet($path) ORDER BY 1"
    return duckdb.execute(query, {"path": path}).fetchall()


def inodes(directory):
    """Un fichier réécrit change d'inode : comparer les inodes montre ce qui a été réécrit."""
    return {path.name: path.stat().st_ino for path in directory.rglob("*.parquet")}


def test_backfill_twice_gives_same_state(crates_io, bronze_dir):
    for day in (D1, D2, D3):
        crates_io.add_archive_day(day, [(1, 10), (2, day.day)])
    assert run_archive(crates_io, bronze_dir) == [D1, D2, D3]
    first, files = state(bronze_dir), inodes(bronze_dir)

    assert run_archive(crates_io, bronze_dir) == []
    assert run_archive(crates_io, bronze_dir, force=True) == []
    assert state(bronze_dir) == first
    assert inodes(bronze_dir) == files


def test_missing_partition_is_filled(crates_io, bronze_dir):
    for day in (D1, D2, D3):
        crates_io.add_archive_day(day, [(1, day.day)])
    run_archive(crates_io, bronze_dir)
    first = state(bronze_dir)
    bronze.partition_path(bronze_dir, D2).unlink()
    others = inodes(bronze_dir)

    assert run_archive(crates_io, bronze_dir) == [D2]
    assert state(bronze_dir) == first
    after = inodes(bronze_dir)
    assert {name: after[name] for name in others} == others


def test_backfill_resumes_after_error(crates_io, bronze_dir):
    for day in (D1, D2, D3):
        crates_io.add_archive_day(day, [(1, day.day)])
    missing = crates_io.archive_dir / f"{D2}.csv"
    content = missing.read_text()
    missing.unlink()

    with pytest.raises(HTTPError):
        run_archive(crates_io, bronze_dir)
    assert sorted(state(bronze_dir)) == [D1]
    assert not list(bronze_dir.rglob("*.tmp"))

    missing.write_text(content)
    assert run_archive(crates_io, bronze_dir) == [D2, D3]


def test_corrupted_download_is_rejected(crates_io, bronze_dir):
    path = crates_io.add_archive_day(D1, [(1, 10)])
    path.with_name(f"{path.name}.etag").write_text("0" * 32)

    with pytest.raises(ValueError, match="ETag"):
        run_archive(crates_io, bronze_dir)
    assert state(bronze_dir) == {}


def test_dump_writes_partitions_and_metadata(crates_io, bronze_dir):
    crates_io.publish_dump(DUMP_TIME, [(D3, 1, 5), (D3, 2, 7), (D4, 3, 1)])

    assert run_dump(crates_io, bronze_dir) == [D3, D4]
    assert sources(bronze_dir) == {D3: "dump", D4: "dump"}
    assert downloads(bronze_dir, D3) == [(1, 5), (2, 7)]
    for table in ("crates", "versions", "categories", "crates_categories"):
        assert (bronze_dir / f"{table}.parquet").exists()
    query = "SELECT DISTINCT extracted_at FROM read_parquet($path)"
    path = str(bronze.partition_path(bronze_dir, D4))
    assert duckdb.execute(query, {"path": path}).fetchall() == [(DUMP_TIME,)]

    assert run_dump(crates_io, bronze_dir) == []


@pytest.mark.parametrize(
    "archive_first", [True, False], ids=["archive-puis-dump", "dump-puis-archive"]
)
def test_archive_wins_over_dump_in_any_order(crates_io, bronze_dir, archive_first):
    crates_io.add_archive_day(D3, [(1, 50)])
    crates_io.publish_dump(DUMP_TIME, [(D3, 1, 49), (D4, 1, 60)])

    steps = [run_archive, run_dump] if archive_first else [run_dump, run_archive]
    for step in steps:
        step(crates_io, bronze_dir)

    assert sources(bronze_dir) == {D3: "archive", D4: "dump"}
    assert downloads(bronze_dir, D3) == [(1, 50)]


def test_late_data_rewrites_only_changed_days(crates_io, bronze_dir, caplog):
    crates_io.publish_dump(DUMP_TIME, [(D3, 1, 5), (D4, 1, 2)])
    run_dump(crates_io, bronze_dir)
    files = inodes(bronze_dir / "version_downloads")

    crates_io.publish_dump(DUMP_TIME + timedelta(days=1), [(D3, 1, 5), (D4, 1, 9)])
    with caplog.at_level("INFO"):
        assert run_dump(crates_io, bronze_dir) == [D4]

    after = inodes(bronze_dir / "version_downloads")
    assert after[f"{D3}.parquet"] == files[f"{D3}.parquet"]
    assert after[f"{D4}.parquet"] != files[f"{D4}.parquet"]
    assert downloads(bronze_dir, D4) == [(1, 9)]
    assert "données tardives, 9 téléchargements au lieu de 2" in caplog.text


def test_dump_without_expected_table_is_rejected(crates_io, bronze_dir):
    crates_io.publish_dump(DUMP_TIME, [(D3, 1, 5)], skip="versions.csv")

    with pytest.raises(ContractError, match="versions.csv"):
        run_dump(crates_io, bronze_dir)
    assert not bronze_dir.exists()
