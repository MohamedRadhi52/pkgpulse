"""Export des agrégats gold en CSV : les seules données que le projet publie."""

from pathlib import Path

import duckdb

from pkgpulse.config import DATA_DIR, EXPORT_DIR

TABLES = ["gold_daily_total", "gold_daily_category", "gold_daily_crate", "gold_top_crates"]


def export_gold(warehouse: Path, out_dir: Path) -> list[Path]:
    """Écrit un CSV trié par table gold et renvoie les chemins écrits."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse), read_only=True)
    paths = []
    for table in TABLES:
        path = out_dir / f"{table}.csv"
        query = f"COPY (SELECT * FROM gold.{table} ORDER BY ALL) TO $path (FORMAT csv, HEADER)"
        con.execute(query, {"path": str(path)})
        paths.append(path)
    return paths


if __name__ == "__main__":
    export_gold(DATA_DIR / "warehouse.duckdb", EXPORT_DIR)
