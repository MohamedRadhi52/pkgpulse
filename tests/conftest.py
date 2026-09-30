import csv
import hashlib
import io
import json
import tarfile
import threading
from datetime import date, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


class Handler(SimpleHTTPRequestHandler):
    """Sert les fichiers avec l'ETag MD5 de S3 ; un fichier .etag voisin impose un autre ETag."""

    def end_headers(self):
        path = Path(self.translate_path(self.path))
        if path.is_file():
            forced = path.with_name(f"{path.name}.etag")
            etag = (
                forced.read_text()
                if forced.exists()
                else hashlib.md5(path.read_bytes()).hexdigest()
            )
            self.send_header("ETag", f'"{etag}"')
        super().end_headers()

    def log_message(self, *args):
        pass


def csv_text(header: list[str], rows: list[tuple]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


class FakeCratesIo:
    """Faux static.crates.io : fichiers d'archive, index.json et dump quotidien."""

    def __init__(self, root: Path, url: str):
        self.root = root
        self.url = url
        self.archive_dir = root / "archive" / "version-downloads"
        self.archive_dir.mkdir(parents=True)
        self.index = []

    def add_archive_day(self, day: date, rows: list[tuple[int, int]]) -> Path:
        path = self.archive_dir / f"{day}.csv"
        path.write_text(csv_text(["version_id", "downloads"], rows))
        self.index.append({"name": path.name, "size": path.stat().st_size})
        (self.archive_dir / "index.json").write_text(json.dumps(self.index))
        return path

    def publish_dump(
        self, timestamp: datetime, downloads: list[tuple[date, int, int]], skip: str = ""
    ) -> None:
        """Publie un dump dont les téléchargements sont des triplets (jour, version, nombre)."""
        files = {
            "README.md": "# crates.io Database Dump\n",
            "metadata.json": json.dumps(
                {"timestamp": f"{timestamp.isoformat()}Z", "crates_io_commit": "0" * 40}
            ),
            "data/version_downloads.csv": csv_text(
                ["date", "downloads", "version_id"], [(d, n, v) for d, v, n in downloads]
            ),
            "data/crates.csv": csv_text(
                ["created_at", "description", "id", "name", "readme", "updated_at"],
                [
                    (
                        "2014-12-05 20:20:39.48",
                        "Sérialisation",
                        1,
                        "serde",
                        "# serde",
                        "2026-06-01 10:00:00",
                    ),
                    (
                        "2016-07-31 22:35:13.21",
                        'Runtime "async"',
                        2,
                        "tokio",
                        "",
                        "2026-06-02 11:00:00",
                    ),
                ],
            ),
            "data/versions.csv": csv_text(
                ["crate_id", "created_at", "features", "id", "num", "yanked"],
                [
                    (1, "2025-01-01 00:00:00", "{}", 1, "1.0.0", "f"),
                    (1, "2026-06-01 10:00:00", "{}", 2, "1.0.1", "f"),
                    (2, "2026-06-02 11:00:00", '{"full":[]}', 3, "1.47.0", "t"),
                ],
            ),
            "data/categories.csv": csv_text(
                ["category", "id", "slug"],
                [("Encoding", 1, "encoding"), ("Asynchronous", 2, "asynchronous")],
            ),
            "data/crates_categories.csv": csv_text(["category_id", "crate_id"], [(1, 1), (2, 2)]),
        }
        prefix = timestamp.strftime("%Y-%m-%d-%H%M%S")
        with tarfile.open(self.root / "db-dump.tar.gz", "w:gz") as tar:
            for name, text in files.items():
                if skip and name.endswith(skip):
                    continue
                data = text.encode()
                info = tarfile.TarInfo(f"{prefix}/{name}")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))


@pytest.fixture
def crates_io(tmp_path):
    root = tmp_path / "static"
    root.mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield FakeCratesIo(root, f"http://127.0.0.1:{server.server_port}")
    server.shutdown()
    server.server_close()


@pytest.fixture
def series():
    """Deux paquets et la série autres, avec saisonnalité hebdomadaire ; le total est leur somme."""
    rng = np.random.default_rng(0)
    ds = pd.date_range("2026-01-01", periods=140, freq="D")
    weekly = np.where(ds.dayofweek >= 5, 0.5, 1.0)
    parts = {"paquet:a": (1000, "paquet"), "paquet:b": (400, "paquet"), "autres": (3000, "autres")}
    frames = [
        pd.DataFrame(
            {
                "unique_id": uid,
                "level": level,
                "ds": ds,
                "y": base * weekly * rng.uniform(0.9, 1.1, len(ds)),
                "versions_published": 0.0,
            }
        )
        for uid, (base, level) in parts.items()
    ]
    total = sum(frame["y"].to_numpy() for frame in frames)
    frames.append(frames[0].assign(unique_id="total", level="total", y=total))
    return pd.concat(frames, ignore_index=True).sort_values(["unique_id", "ds"], ignore_index=True)
