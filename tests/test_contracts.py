import csv
from datetime import datetime

import duckdb
import pytest

from pkgpulse.ingest import contracts
from pkgpulse.ingest.contracts import ContractError

# Extraits au format réel : en-têtes complets (colonnes en plus comprises), export PostgreSQL.
CRATES_HEADER = ["created_at", "description", "id", "name", "readme", "repository", "updated_at"]
CRATES_ROW = [
    "2014-12-05 20:20:39.487502",
    "A generic serialization framework",
    "463",
    "serde",
    "# serde",
    "https://github.com/serde-rs/serde",
    "2026-09-02 13:07:27.123456",
]
SAMPLES = [
    (contracts.ARCHIVE, ["version_id", "downloads"], [["12124", "4446"], ["8441", "1515"]]),
    (
        contracts.VERSION_DOWNLOADS,
        ["date", "downloads", "version_id"],
        [["2026-09-27", "3", "12124"], ["2026-09-28", "5", "12124"]],
    ),
    (contracts.CRATES, CRATES_HEADER, [CRATES_ROW]),
    (
        contracts.VERSIONS,
        ["crate_id", "created_at", "downloads", "features", "id", "license", "num", "yanked"],
        [
            ["463", "2014-12-05 20:20:39.487502", "10", "{}", "1001", "MIT", "0.1.0", "t"],
            ["463", "2026-09-02 13:07:27", "3", '{"std":[]}', "1002", "MIT", "1.0.228", "f"],
        ],
    ),
    (
        contracts.CATEGORIES,
        ["category", "crates_cnt", "created_at", "description", "id", "path", "slug"],
        [
            ["Encoding", "900", "2017-01-17 19:13:05.112025", "", "7", "root.encoding", "encoding"],
            [
                "Testing",
                "2000",
                "2017-01-17 19:13:05.112025",
                "",
                "8",
                "root.development_tools.testing",
                "development-tools::testing",
            ],
        ],
    ),
    (contracts.CRATES_CATEGORIES, ["category_id", "crate_id"], [["7", "463"], ["8", "463"]]),
]


def write_csv(path, header, rows):
    with path.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.fixture
def con():
    return duckdb.connect()


@pytest.mark.parametrize(("contract", "header", "rows"), SAMPLES, ids=[s[0].name for s in SAMPLES])
def test_each_source_loads_with_contract_types(con, tmp_path, contract, header, rows):
    contracts.load(con, write_csv(tmp_path / "source.csv", header, rows), contract)

    described = con.sql(f"DESCRIBE {contract.name}").fetchall()
    assert {row[0]: row[1] for row in described} == contract.columns
    assert con.sql(f"SELECT count(*) FROM {contract.name}").fetchone()[0] == len(rows)


def test_user_supplied_fields_are_read_safely(con, tmp_path):
    row = CRATES_ROW.copy()
    row[1] = 'Dit "bonjour",\npuis =SOMME(A1)'
    row[4] = "x" * 3_000_000
    row[6] = "2026-09-02 13:07:27.5+00"
    contracts.load(con, write_csv(tmp_path / "crates.csv", CRATES_HEADER, [row]), contracts.CRATES)

    assert con.sql("SELECT name, updated_at FROM crates").fetchall() == [
        ("serde", datetime(2026, 9, 2, 13, 7, 27, 500000))
    ]


def test_missing_column_is_rejected(con, tmp_path):
    path = write_csv(tmp_path / "archive.csv", ["version_id"], [["1"]])
    with pytest.raises(ContractError, match="downloads"):
        contracts.load(con, path, contracts.ARCHIVE)


def test_empty_source_is_rejected(con, tmp_path):
    path = write_csv(tmp_path / "archive.csv", ["version_id", "downloads"], [])
    with pytest.raises(ContractError, match="aucune ligne"):
        contracts.load(con, path, contracts.ARCHIVE)


def test_unconvertible_value_is_rejected(con, tmp_path):
    path = write_csv(tmp_path / "archive.csv", ["version_id", "downloads"], [["1", "beaucoup"]])
    with pytest.raises(duckdb.ConversionException, match="beaucoup"):
        contracts.load(con, path, contracts.ARCHIVE)


@pytest.mark.parametrize(
    "rows", [[["1", "2"], ["1", "3"]], [["", "2"]]], ids=["doublon", "cle-nulle"]
)
def test_invalid_key_is_rejected(con, tmp_path, rows):
    path = write_csv(tmp_path / "archive.csv", ["version_id", "downloads"], rows)
    with pytest.raises(ContractError, match="clé"):
        contracts.load(con, path, contracts.ARCHIVE)
