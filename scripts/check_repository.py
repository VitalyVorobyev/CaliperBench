"""Reject unsafe Git-index content before commit and in CI (standard library only)."""

import re
import subprocess
from pathlib import PurePosixPath

ALLOWED = {".py", ".md", ".json", ".jsonl", ".toml", ".lock", ".yml", ".yaml", ".txt"}
SPECIAL = {"LICENSE", ".gitignore", ".gitattributes", ".githooks/pre-commit"}
FORBIDDEN = {
    "data",
    "raw",
    "images",
    "cache",
    ".cache",
    "outputs",
    "results",
    "private",
    "local",
    "work",
    ".aws",
    ".ssh",
    ".venv",
}


def problem(path, content):
    p = PurePosixPath(path)
    if any(part.lower() in FORBIDDEN for part in p.parts):
        return "local-only directory"
    name = p.name.lower()
    if name.startswith((".env", "credentials", "secrets")):
        return "credential filename"
    if path not in SPECIAL and p.suffix.lower() not in ALLOWED:
        return "unapproved file type"
    if len(content) > 1_000_000:
        return "file exceeds 1 MB"
    try:
        value = content.decode("utf-8")
    except UnicodeDecodeError:
        return "binary content"
    if "\x00" in value:
        return "binary content"
    if re.search(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", value):
        return "private key content"
    if re.search(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})\b", value
    ):
        return "credential-like content"
    return None


def main():
    index = subprocess.check_output(["git", "ls-files", "--stage", "-z"])
    failures = []
    for item in index.split(b"\x00"):
        if not item:
            continue
        info, path = item.split(b"\t", 1)
        mode, blob, stage = info.decode().split()
        name = path.decode()
        if mode not in {"100644", "100755"} or stage != "0":
            failures.append((name, "symlink, submodule or unresolved index entry"))
            continue
        size = int(subprocess.check_output(["git", "cat-file", "-s", blob]))
        if size > 1_000_000:
            failures.append((name, "file exceeds 1 MB"))
            continue
        reason = problem(name, subprocess.check_output(["git", "cat-file", "blob", blob]))
        if reason:
            failures.append((name, reason))
    for name, reason in failures:
        print(f"Rejected {name}: {reason}")
    if failures:
        raise SystemExit(1)
    print("Git index content check passed.")


if __name__ == "__main__":
    main()
