# Dataset curation and local cache

`registry/datasets.json` is a candidate registry, not a claim of subpixel labels or
unrestricted redistribution. Evidence links record publisher statements; `null`
means not verified. Priorities are curation judgments: P1 pilot first, P2 diversity,
P3 access/rights/quality investigation. Dataset and repository code licenses differ.

The first pass checked public source metadata on 2026-09-26. The Figshare API supplied
the weld dataset's MIT license where the website blocked automated access. The
institutional AmodalAppleSize record supplied CC BY 4.0 metadata; its canonical
Dataverse page was not retrievable by the browser. No image archive was downloaded.
The steel-plate paper is located but no usable dataset download or data license was
found. Never treat an article's open-access license as a dataset grant.

## Acquire

The CLI implements a generic HTTPS adapter with reviewed host allowlists, explicit
size limits, checksum verification, atomic final filenames and local provenance.
It does not scrape login pages, bypass access forms or guess changing archive URLs.
Download URLs/checksums are deliberately not fabricated. For each selected version:

1. Follow the registry's evidence links and inspect the actual file list and notices.
2. Select the real subset (e.g. ITODD validation, original MovingCables sequences).
3. Obtain an upstream SHA-256 where available. Otherwise download manually into the
   ignored cache, inspect it, and register its computed hash. A locally computed hash
   establishes a reproducibility pin, not independent publisher authentication.
4. Pin the exact version, direct HTTPS URL and SHA-256 in your local acquisition log.

```sh
# Values below are placeholders, not a download claim.
uv run caliperbench download visa --url HTTPS_FILE_URL --sha256 SHA256 \
  --filename VisA.tar --data-root data
# Or register an inspected, manually acquired archive/image:
uv run caliperbench register visa data/raw/visa/VisA.tar \
  --url SOURCE_URL --data-root data
```

Downloads require a reviewed host and a checksum; signed/query URLs should be acquired
manually so credentials do not enter provenance. Registration never downloads and
can document unresolved/restricted sources; it does not certify permission to use
them. Download is disabled for unresolved DeepPCB, literature-weld rights, and
inaccessible steel-plate entries. ITODD is noncommercial; assess your intended use
against its terms before invoking acquisition. Do not mix it into unrestricted tracks.

Files go under `data/raw/<id>/`; append-only acquisition records under
`data/manifests/<id>.jsonl` contain source, version, license, relative path, size,
SHA-256 and timestamp. Interrupted temporary files are removed. Archives are not
extracted automatically: inspect archive paths and sizes, and extract locally with
a safe tool. Keep images in `data/`, prepared task records in `data/annotations.jsonl`,
and predictions/reports in `outputs/`.

Source-specific conversion remains a deliberate extension point: inspect one version,
write a small script under `scripts/`, preserve original IDs, validate Sample records,
and document mappings rather than assuming all masks represent boundaries. Inventory
actual dimensions/counts and update the registry after inspection. None of the seeded
sources is presently promoted to a released CaliperBench test set.

## Keep Git clean

`.gitignore` excludes data/cache/output/private directories, common image/archive/model
formats and credential files. `scripts/check_repository.py` rejects staged/tracked
binary content, files larger than 1 MB and forbidden paths; CI runs it too. Install
its pre-commit hook with `git config core.hooksPath .githooks` (configured in the initial
checkout). Ignore rules and hooks are safeguards, not permission to force-add raw data.
Review `git diff --cached` before every public commit. No Git LFS image storage here.

MovingCables needs particular care: the standard release is composited, and even its
177 source clips are postprocessed RGBA with chroma-key alpha. It is P2 pending RGB
edge inspection. The registry pins the publisher's source archive URL and SHA-256;
the roughly 60 GiB download requires an explicit larger `--max-bytes`. It has not been
downloaded or accepted as localization ground truth.
