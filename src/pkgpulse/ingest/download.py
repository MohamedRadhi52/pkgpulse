"""Téléchargements depuis static.crates.io."""

import hashlib
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

from pkgpulse.config import USER_AGENT

TIMEOUT_SECONDS = 60
CHUNK_BYTES = 1 << 20


def open_url(url: str):
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT_SECONDS)


def fetch_json(url: str):
    with open_url(url) as response:
        return json.load(response)


def download(url: str, dest: Path) -> datetime:
    """Enregistre url dans dest, vérifie le MD5 de l'ETag et renvoie Last-Modified en UTC."""
    md5 = hashlib.md5()
    with open_url(url) as response, dest.open("wb") as out:
        while chunk := response.read(CHUNK_BYTES):
            md5.update(chunk)
            out.write(chunk)
        etag = response.headers["ETag"].strip('"')
        last_modified = parsedate_to_datetime(response.headers["Last-Modified"])
    # Sur S3, l'ETag est le MD5 du fichier, sauf pour un envoi en plusieurs parties (suffixe -N).
    if "-" not in etag and etag != md5.hexdigest():
        raise ValueError(f"{url} : MD5 {md5.hexdigest()} différent de l'ETag {etag}")
    return last_modified.replace(tzinfo=None)
