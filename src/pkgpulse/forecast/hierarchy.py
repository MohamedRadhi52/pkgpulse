"""Deux niveaux de prévision : le total prévu directement ou reconstitué par agrégation."""

import pandas as pd


def bottom_up_table(results: pd.DataFrame) -> pd.DataFrame:
    """MASE du total : prévision directe contre somme des paquets suivis et de la série autres."""
    keys = ["model", "origin", "h", "ds"]
    parts = results[results["level"].isin(["paquet", "autres"])]
    bottom_up = parts.groupby(keys, as_index=False)["y_hat"].sum()
    total = results[results["level"] == "total"].merge(bottom_up, on=keys, suffixes=("", "_bu"))
    total["direct"] = (total["y"] - total["y_hat"]).abs() / total["mase_scale"]
    total["ascendant"] = (total["y"] - total["y_hat_bu"]).abs() / total["mase_scale"]
    return total.groupby(["model", "h"])[["direct", "ascendant"]].mean().round(3).reset_index()
