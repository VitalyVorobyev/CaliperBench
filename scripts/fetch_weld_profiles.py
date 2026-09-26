"""Fetch the small real weld-profile pilot with publisher MD5 and local SHA-256 pins."""

import argparse
import hashlib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RECORD = "https://zenodo.org/api/records/20301441"
DATASET_ID = "weld-profiles-2026"
DOI = "10.5281/zenodo.20301441"
LICENSE = "CC-BY-4.0"
PINS = Path(__file__).resolve().parents[1] / "registry/weld-profiles-v1-files.json"


def digest(data, algorithm):
    return hashlib.new(algorithm, data).hexdigest()


def fetch_one(file, root, pinned):
    name = file["key"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:_mask\.png|\.jpg)", name):
        raise ValueError(f"unexpected upstream filename: {name}")
    if file["size"] > 1_000_000:
        raise ValueError(f"unexpected upstream file size: {name}")
    expected = file["checksum"]
    if not re.fullmatch(r"md5:[a-f0-9]{32}", expected):
        raise ValueError(f"unexpected upstream checksum: {name}")
    url = file["links"]["self"]
    if not url.startswith(RECORD + "/files/") or not url.endswith("/content"):
        raise ValueError(f"unexpected upstream URL: {name}")
    path = root / name
    if path.exists():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=40) as response:
            data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError(f"oversized download: {name}")
    if len(data) != file["size"] or digest(data, "md5") != expected.removeprefix("md5:"):
        raise ValueError(f"publisher checksum/size mismatch: {name}")
    if digest(data, "sha256") != pinned["sha256"]:
        raise ValueError(f"pinned SHA-256 mismatch: {name}")
    if not path.exists():
        path.write_bytes(data)
    return {
        "name": name,
        "size": len(data),
        "source_url": url,
        "publisher_md5": expected,
        "sha256": digest(data, "sha256"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    args = parser.parse_args()
    with urllib.request.urlopen(RECORD, timeout=40) as response:
        record = json.load(response)
    if record["id"] != 20301441 or record["metadata"]["license"]["id"] != "cc-by-4.0":
        raise ValueError("upstream record or license changed; review before proceeding")
    files = sorted(record["files"], key=lambda item: item["key"])
    if len(files) != 98 or sum(file["key"].endswith(".jpg") for file in files) != 49:
        raise ValueError("upstream file inventory changed; review before proceeding")
    pinned = json.loads(PINS.read_text())
    pins_by_name = {file["name"]: file for file in pinned["files"]}
    upstream = {file["key"]: (file["size"], file["checksum"]) for file in files}
    expected = {name: (file["size"], file["publisher_md5"]) for name, file in pins_by_name.items()}
    if pinned["doi"] != DOI or pinned["license"] != LICENSE or upstream != expected:
        raise ValueError("upstream record differs from committed v1 pins")
    root = args.data_root / "raw" / DATASET_ID
    root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        assets = list(
            pool.map(lambda file: fetch_one(file, root, pins_by_name[file["key"]]), files)
        )
    manifest = {
        "dataset_id": DATASET_ID,
        "source_url": RECORD,
        "doi": DOI,
        "version": "v1",
        "license": LICENSE,
        "files": assets,
    }
    destination = args.data_root / "manifests" / f"{DATASET_ID}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Verified {len(assets)} files, {sum(a['size'] for a in assets)} bytes; manifest: {destination}"
    )


if __name__ == "__main__":
    main()
