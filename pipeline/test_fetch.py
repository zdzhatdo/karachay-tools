import hashlib
import json

import pytest

from pipeline.fetch import fetch_dump

DUMP_URL = "/testwiki/20260101/testwiki-20260101-pages-articles.xml.bz2"


def fake_get(payload: bytes, published: bytes):
    """A stand-in for the network: dumpstatus.json describes `published`, the download returns `payload`."""
    status = {"jobs": {"articlesdump": {"status": "done", "files": {
        "testwiki-20260101-pages-articles.xml.bz2": {
            "size": len(published),
            "sha1": hashlib.sha1(published).hexdigest(),
            "url": DUMP_URL,
        }}}}}
    downloads = []

    def get(url: str) -> bytes:
        if url.endswith("dumpstatus.json"):
            return json.dumps(status).encode()
        downloads.append(url)
        return payload

    return get, downloads


def test_stores_dump_by_sha256_and_records_it(tmp_path):
    get, _ = fake_get(b"dump bytes", b"dump bytes")
    record = fetch_dump("testwiki", "20260101", tmp_path, get)

    assert record["path"] == hashlib.sha256(b"dump bytes").hexdigest() + ".xml.bz2"
    assert (tmp_path / record["path"]).read_bytes() == b"dump bytes"
    assert json.loads((tmp_path / "manifest.jsonl").read_text()) == record


def test_second_run_downloads_nothing(tmp_path):
    get, downloads = fake_get(b"dump bytes", b"dump bytes")
    first = fetch_dump("testwiki", "20260101", tmp_path, get)
    second = fetch_dump("testwiki", "20260101", tmp_path, get)

    assert second == first
    assert len(downloads) == 1
    assert len((tmp_path / "manifest.jsonl").read_text().splitlines()) == 1


def test_corrupted_download_is_rejected_and_not_stored(tmp_path):
    get, _ = fake_get(b"dump bytez", b"dump bytes")
    with pytest.raises(ValueError, match="SHA-1"):
        fetch_dump("testwiki", "20260101", tmp_path, get)

    assert list(tmp_path.iterdir()) == []
