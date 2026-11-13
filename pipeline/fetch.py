"""Stage 1 (fetch): download a Wikipedia dump, verify it, and store it by content hash."""

import hashlib
import json
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

STAGE_VERSION = "fetch-1"
DUMPS = "https://dumps.wikimedia.org"
USER_AGENT = "karachay-tools/0.1 (https://github.com/zdzhatdo/karachay-tools)"
LICENSE = "CC BY-SA 4.0"


def http_get(url: str) -> bytes:
    """Download a URL; raises on any non-2xx response."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def dump_info(wiki: str, date: str, get: Callable[[str], bytes]) -> dict:
    """Return Wikimedia's published size and checksums for one articles dump."""
    status = json.loads(get(f"{DUMPS}/{wiki}/{date}/dumpstatus.json"))
    job = status["jobs"]["articlesdump"]
    if job["status"] != "done":
        raise RuntimeError(f"{wiki} {date} dump is not finished: {job['status']}")
    name = f"{wiki}-{date}-pages-articles.xml.bz2"
    return {"name": name, **job["files"][name]}


def verify(data: bytes, info: dict) -> None:
    """Raise if the download doesn't match the published size and SHA-1."""
    if len(data) != info["size"]:
        raise ValueError(f"size {len(data)} does not match published {info['size']}")
    if hashlib.sha1(data).hexdigest() != info["sha1"]:
        raise ValueError("SHA-1 does not match the published checksum")


def read_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def fetch_dump(wiki: str, date: str, raw_dir: Path, get: Callable[[str], bytes] = http_get) -> dict:
    """Download, verify, and store a dump; return its manifest record.

    Idempotent: if these exact bytes are already stored, nothing is downloaded.
    """
    info = dump_info(wiki, date, get)
    manifest = raw_dir / "manifest.jsonl"
    for record in read_manifest(manifest):
        if record["sha1"] == info["sha1"] and (raw_dir / record["path"]).exists():
            return record

    url = DUMPS + info["url"]
    data = get(url)
    verify(data, info)

    sha256 = hashlib.sha256(data).hexdigest()
    path = f"{sha256}.xml.bz2"
    raw_dir.mkdir(parents=True, exist_ok=True)
    partial = raw_dir / f"{path}.part"
    partial.write_bytes(data)
    partial.replace(raw_dir / path)  # rename, so a crash never leaves a half-written file under the final name

    record = {
        "source": wiki,
        "url": url,
        "dump_date": date,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "license": LICENSE,
        "size": len(data),
        "sha1": info["sha1"],
        "sha256": sha256,
        "path": path,
        "stage_version": STAGE_VERSION,
    }
    with manifest.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
    return record
