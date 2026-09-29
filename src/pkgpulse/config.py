"""Paramètres communs du pipeline."""

import os
from datetime import date
from pathlib import Path

DATA_DIR = Path(os.environ.get("PKGPULSE_DATA_DIR", "data"))
BRONZE_DIR = DATA_DIR / "bronze"

SOURCE_URL = "https://static.crates.io"
USER_AGENT = "pkgpulse/0.1 (daily analytics on crates.io public download data)"

# Premier jour complet après le passage au comptage des seuls téléchargements cargo
# (docs/DECISIONS.md, décision 2).
HISTORY_START = date(2025, 11, 1)
