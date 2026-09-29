"""Contrats de schéma des sources crates.io (docs/DECISIONS.md, décision 3)."""

from dataclasses import dataclass
from pathlib import Path

import duckdb

# Export PostgreSQL : guillemets doublés, champs multilignes, README de plus de 2 Mo.
CSV_OPTIONS = (
    "header = true, all_varchar = true, delim = ',', quote = '\"', escape = '\"', "
    "max_line_size = 67108864"
)


class ContractError(Exception):
    """Une source ne respecte pas son contrat de schéma."""


@dataclass(frozen=True)
class Contract:
    name: str
    columns: dict[str, str]
    key: tuple[str, ...]


ARCHIVE = Contract("archive", {"version_id": "BIGINT", "downloads": "BIGINT"}, ("version_id",))
VERSION_DOWNLOADS = Contract(
    "version_downloads",
    {"version_id": "BIGINT", "downloads": "BIGINT", "date": "DATE"},
    ("version_id", "date"),
)
CRATES = Contract(
    "crates",
    {"id": "BIGINT", "name": "VARCHAR", "created_at": "TIMESTAMP", "updated_at": "TIMESTAMP"},
    ("id",),
)
VERSIONS = Contract(
    "versions",
    {
        "id": "BIGINT",
        "crate_id": "BIGINT",
        "num": "VARCHAR",
        "created_at": "TIMESTAMP",
        "yanked": "BOOLEAN",
    },
    ("id",),
)
CATEGORIES = Contract(
    "categories", {"id": "BIGINT", "category": "VARCHAR", "slug": "VARCHAR"}, ("id",)
)
CRATES_CATEGORIES = Contract(
    "crates_categories",
    {"crate_id": "BIGINT", "category_id": "BIGINT"},
    ("crate_id", "category_id"),
)


def load(con: duckdb.DuckDBPyConnection, path: Path, contract: Contract) -> None:
    """Charge un CSV dans une table DuckDB nommée comme le contrat, après vérification."""
    source = f"read_csv($path, {CSV_OPTIONS})"
    params = {"path": str(path)}
    described = con.execute(f"DESCRIBE SELECT * FROM {source}", params).fetchall()
    missing = sorted(set(contract.columns) - {row[0] for row in described})
    if missing:
        raise ContractError(f"{contract.name} : colonnes absentes {missing}")

    # Une valeur non convertible fait échouer le CAST, avec un message qui la cite.
    columns = ", ".join(f"CAST({c} AS {t}) AS {c}" for c, t in contract.columns.items())
    con.execute(
        f"CREATE OR REPLACE TABLE {contract.name} AS SELECT {columns} FROM {source}", params
    )

    key = ", ".join(contract.key)
    any_null = " OR ".join(f"{c} IS NULL" for c in contract.key)
    rows, null_keys, duplicates = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE {any_null}), "
        f"count(*) - count(DISTINCT ({key})) FROM {contract.name}"
    ).fetchone()
    if rows == 0:
        raise ContractError(f"{contract.name} : aucune ligne")
    if null_keys or duplicates:
        raise ContractError(
            f"{contract.name} : clé ({key}) nulle sur {null_keys} lignes, {duplicates} doublons"
        )
