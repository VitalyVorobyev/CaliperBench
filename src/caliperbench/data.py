"""Local cache operations; archives are never extracted automatically."""

import hashlib
import json
import re
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def under_root(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("path escapes data root")
    return path


def registry(path):
    entries = json.loads(Path(path).read_text())["datasets"]
    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate dataset ID")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", id) for id in ids):
        raise ValueError("invalid dataset ID")
    return {e["id"]: e for e in entries}


def register(root, entry, path, source_url, expected_sha256=None):
    """Record existing bytes and provenance locally; no image contents enter metadata."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entry["id"]):
        raise ValueError("invalid dataset ID")
    parsed = urlparse(source_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("source URL must not contain credentials, query or fragment")
    path = Path(path).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("registered files must live under the local data root")
    digest = sha256(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("SHA-256 mismatch")
    record = {
        "dataset_id": entry["id"],
        "source_url": source_url,
        "source_version": entry["version"],
        "license": entry["license"],
        "path": path.relative_to(Path(root).resolve()).as_posix(),
        "sha256": digest,
        "bytes": path.stat().st_size,
        "registered_at": datetime.now(UTC).isoformat(),
    }
    manifest = under_root(root, "manifests/" + entry["id"] + ".jsonl")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    return record


def download(root, entry, url, expected_sha256, filename, max_bytes=10_000_000_000):
    if not entry["download_enabled"]:
        raise ValueError("download disabled: resolve dataset access/license restrictions first")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query:
        raise ValueError("use an HTTPS URL without embedded credentials or query parameters")
    if parsed.hostname not in entry["download_hosts"]:
        raise ValueError("host is not in the reviewed dataset download allowlist")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("a pinned SHA-256 is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", filename):
        raise ValueError("filename must be a simple basename")
    target = under_root(root, f"raw/{entry['id']}/{filename}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return register(root, entry, target, url, expected_sha256)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=target.name, suffix=".part", delete=False
    ) as temporary:
        part = Path(temporary.name)
    try:
        with urllib.request.urlopen(url, timeout=60) as response, part.open("wb") as out:
            if urlparse(response.url).scheme != "https":
                raise ValueError("insecure redirect")
            total = 0
            for block in iter(lambda: response.read(1024 * 1024), b""):
                total += len(block)
                if total > max_bytes:
                    raise ValueError("download exceeds size limit")
                out.write(block)
        if sha256(part) != expected_sha256:
            raise ValueError("SHA-256 mismatch")
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return register(root, entry, target, url, expected_sha256)
