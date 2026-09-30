"""Séries quotidiennes à prévoir, lues dans les exports gold."""

from pathlib import Path

import pandas as pd

COLUMNS = ["unique_id", "level", "ds", "y", "versions_published"]


def load_series(export_dir: Path) -> pd.DataFrame:
    """Une ligne par série et par jour, triée par série puis par date.

    La série autres (total moins les paquets suivis) ferme la hiérarchie : le total est la somme
    des paquets suivis et de autres.
    """
    total = _read(export_dir, "gold_daily_total")
    categories = _read(export_dir, "gold_daily_category")
    crates = _read(export_dir, "gold_daily_crate")

    tracked = crates.groupby("download_date")["downloads"].sum()
    others = total.set_index("download_date")["downloads"].sub(tracked).reset_index()

    series = pd.concat(
        [
            total.assign(unique_id="total", level="total"),
            others.assign(unique_id="autres", level="autres"),
            categories.assign(
                unique_id="categorie:" + categories["category_slug"], level="categorie"
            ),
            crates.assign(unique_id="paquet:" + crates["crate_name"], level="paquet"),
        ],
        ignore_index=True,
    ).rename(columns={"download_date": "ds", "downloads": "y"})
    series["versions_published"] = series["versions_published"].fillna(0)
    return series[COLUMNS].sort_values(["unique_id", "ds"], ignore_index=True)


def _read(export_dir: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(export_dir / f"{name}.csv", parse_dates=["download_date"])
