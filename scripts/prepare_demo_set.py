#!/usr/bin/env python3
"""Prepare the demo image set for the tampering-detection project.
 
Copies a hand-curated subset of raw candidate images into a destination
directory organised by category, and writes a manifest.csv describing each
image. This script does NOT classify images; all curation judgment lives in
the curation CSV (or the CURATION dict below).
 
Curation CSV columns (header row required):
    filename, label, source, licence, expected_verdict
 
``filename`` is looked up under --src (directly first, then recursively by
name). If a bare name matches more than one file, give a path relative to
--src instead (e.g. ``CASIA2/Tp/Tp_D_xxx.jpg``).
 
Usage:
    python scripts/prepare_demo_set.py --curation data/curation.csv
    python scripts/prepare_demo_set.py --curation data/curation.csv --dry-run
 
Output layout:
    data/demo_images/real/<file>
    data/demo_images/spliced/<file>
    data/demo_images/copy_move/<file>
    data/demo_images/ai_generated/<file>
    data/demo_images/manifest.csv   (filename column is relative to the
                                     destination dir, e.g. "spliced/a.jpg")
"""
 
from __future__ import annotations
 
import argparse
import csv
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
 
LABELS: tuple[str, ...] = ("real", "spliced", "copy_move", "ai_generated")
VERDICTS: tuple[str, ...] = ("authentic", "suspicious", "likely_tampered")
MANIFEST_FIELDS: tuple[str, ...] = (
    "filename",
    "label",
    "source",
    "licence",
    "expected_verdict",
)
 
# Optional in-code alternative to a curation CSV. Maps filename ->
# (label, source, licence, expected_verdict). Ignored if --curation is given.
CURATION: dict[str, tuple[str, str, str, str]] = {
    # "Au_ani_00001.jpg": ("real", "CASIA v2", "research use only", "authentic"),
}
 
 
@dataclass(frozen=True)
class Entry:
    """One curated image and its metadata."""
 
    filename: str
    label: str
    source: str
    licence: str
    expected_verdict: str
 
 
def load_curation_csv(path: Path) -> list[Entry]:
    """Read curation entries from a CSV file."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = set(MANIFEST_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"{path} is missing column(s): {', '.join(sorted(missing))}"
            )
        return [
            Entry(**{k: (row[k] or "").strip() for k in MANIFEST_FIELDS})
            for row in reader
            if any((v or "").strip() for v in row.values())
        ]
 
 
def load_curation_dict(mapping: dict[str, tuple[str, str, str, str]]) -> list[Entry]:
    """Convert the in-code CURATION dict into entries."""
    return [Entry(name, *vals) for name, vals in mapping.items()]
 
 
def validate(entries: list[Entry]) -> list[str]:
    """Return a list of human-readable problems with the curation list."""
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for e in entries:
        if e.label not in LABELS:
            problems.append(
                f"{e.filename}: label {e.label!r} not in {', '.join(LABELS)}"
            )
        if e.expected_verdict not in VERDICTS:
            problems.append(
                f"{e.filename}: expected_verdict {e.expected_verdict!r} "
                f"not in {', '.join(VERDICTS)}"
            )
        key = (e.label, Path(e.filename).name)
        if key in seen:
            problems.append(
                f"{e.filename}: duplicate name within category {e.label!r}"
            )
        seen.add(key)
    return problems
 
 
def resolve_source(src_dir: Path, filename: str) -> Path:
    """Locate ``filename`` under ``src_dir``.
 
    Raises FileNotFoundError if absent, ValueError if ambiguous.
    """
    direct = src_dir / filename
    if direct.is_file():
        return direct
    matches = [p for p in src_dir.rglob(Path(filename).name) if p.is_file()]
    if not matches:
        raise FileNotFoundError(f"not found under {src_dir}")
    if len(matches) > 1:
        listing = ", ".join(str(m.relative_to(src_dir)) for m in matches[:5])
        raise ValueError(
            f"ambiguous, {len(matches)} matches ({listing}); "
            "use a path relative to --src"
        )
    return matches[0]
 
 
def build_demo_set(
    entries: list[Entry], src_dir: Path, dest_dir: Path, dry_run: bool
) -> tuple[list[dict[str, str]], list[str]]:
    """Copy images and return (manifest rows, error messages)."""
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    for e in entries:
        try:
            src = resolve_source(src_dir, e.filename)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(f"{e.filename}: {exc}")
            continue
 
        rel = Path(e.label) / src.name
        dest = dest_dir / rel
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        rows.append(
            {
                "filename": rel.as_posix(),
                "label": e.label,
                "source": e.source,
                "licence": e.licence,
                "expected_verdict": e.expected_verdict,
            }
        )
    return rows, errors
 
 
def write_manifest(rows: list[dict[str, str]], dest_dir: Path) -> Path:
    """Write manifest.csv into ``dest_dir`` and return its path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path
 
 
def print_summary(rows: list[dict[str, str]]) -> bool:
    """Print per-category counts; return True if every category is non-empty."""
    counts = Counter(r["label"] for r in rows)
    print("\nDemo set summary")
    print("----------------")
    for label in LABELS:
        print(f"  {label:<13} {counts.get(label, 0)}")
    print(f"  {'total':<13} {len(rows)}")
 
    empty = [label for label in LABELS if counts.get(label, 0) == 0]
    for label in empty:
        print(f"WARNING: category {label!r} has zero images; demo set is unbalanced.")
    return not empty
 
 
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", type=Path, default=Path("data/datasets_raw"))
    parser.add_argument("--dest", type=Path, default=Path("data/demo_images"))
    parser.add_argument(
        "--curation",
        type=Path,
        help="CSV with filename,label,source,licence,expected_verdict "
        "(default: use the CURATION dict in this file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and report without copying files or writing the manifest",
    )
    return parser.parse_args(argv)
 
 
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
 
    if args.curation:
        entries = load_curation_csv(args.curation)
    else:
        entries = load_curation_dict(CURATION)
    if not entries:
        print("No curation entries provided.", file=sys.stderr)
        return 2
    if not args.src.is_dir():
        print(f"Source directory not found: {args.src}", file=sys.stderr)
        return 2
 
    problems = validate(entries)
    if problems:
        print("Curation list has problems:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
 
    rows, errors = build_demo_set(entries, args.src, args.dest, args.dry_run)
 
    if not args.dry_run:
        manifest = write_manifest(rows, args.dest)
        print(f"Copied {len(rows)} image(s) to {args.dest}")
        print(f"Wrote {manifest}")
    else:
        print(f"[dry run] would copy {len(rows)} image(s) to {args.dest}")
 
    balanced = print_summary(rows)
 
    if errors:
        print("\nSkipped entries:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
    return 0 if (balanced and not errors) else 1
 
 
if __name__ == "__main__":
    sys.exit(main())
 