"""The legacy freeze manifest (master plan O-10; ``docs/legacy/INDEX.md`` §5, step 1).

A hash manifest of the legacy working tree, written **outside** the legacy repository. It reads
every file as bytes and changes nothing: no file is opened for writing, no database is opened as a
database, nothing is run.

What a manifest is, and is not:

* It **is** a complete listing — relative path, size, SHA-256 — of every file under the legacy
  root except the ``.git`` directory, which is represented by the commit it has checked out and
  the state ``git status`` reports. (``.git`` holds an index that git may rewrite when it merely
  looks at the tree; hashing it would make the manifest fail for reasons that are not changes.)
* Fixity is **bytes, not timestamps**: a file whose modification time changed and whose bytes did
  not is unchanged; a file with the same time and other bytes is changed. Times are not recorded.
* It is **not** the frozen release. ``coprepan-legacy-2026-06`` is complete only with a verified
  copy on a preservation target and a restore check (steps 2–4), which need master plan O-3. The
  manifest's state says so: ``MANIFEST_ONLY``.

The listing is deterministic: the same tree gives the same bytes. The manifest around it carries
the time and the tool version and binds the listing by its hash.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import __version__, naming
from .canonical import line_json, record_json, sha256_bytes, sha256_file
from .identity import format_instant
from .storage_roots import is_inside

FREEZE_ID = naming.LEGACY_RELEASE_ID
MANIFEST_SCHEMA = naming.schema_id("legacy-freeze-manifest", 1)
LISTING_SCHEMA = naming.schema_id("legacy-freeze-listing", 1)
TOOL = "legacy-freeze/1"
STATE_MANIFEST_ONLY = "MANIFEST_ONLY"

EXCLUDED_DIRECTORIES = (".git",)
# The stores the frozen release is defined over (docs/legacy/INDEX.md §5). Everything else in the
# tree is listed too; this marks which part is the corpus and its databases.
RELEASE_SCOPE = ("json_annotated/", "json_raw/", "json_raw_extended/", "data/db/", "state/annotation/", "backup/",
                 "outputs/section_inventory/")
LISTING_NAME, MANIFEST_NAME = "files.jsonl", "manifest.json"

VERIFIED, DIFFERS = "VERIFIED", "DIFFERS"


class FreezeError(RuntimeError):
    """The manifest cannot be built or read as asked."""


def area_of(relative_path: str) -> str:
    """The top-level directory of a path, or ``(root)`` for a file directly in the root."""
    return relative_path.split("/", 1)[0] if "/" in relative_path else "(root)"


def in_release_scope(relative_path: str) -> bool:
    return relative_path.startswith(RELEASE_SCOPE)


def scan(root: Path) -> Iterator[dict[str, Any]]:
    """Every file under ``root`` outside ``.git``, in path order, with size and SHA-256.

    Links are not followed and not accepted: a tree that is to be frozen byte for byte must not
    point outside itself.
    """
    root = Path(root)
    if not root.is_dir():
        raise FreezeError("the legacy root is not a directory")
    entries: list[tuple[str, Path]] = []
    for directory, names, files in os.walk(root, followlinks=False):
        here = Path(directory)
        if here == root:
            names[:] = [name for name in names if name not in EXCLUDED_DIRECTORIES]
        for name in list(names) + files:
            if (here / name).is_symlink():
                raise FreezeError(f"a link in the tree cannot be frozen: {(here / name).relative_to(root).as_posix()}")
        entries += [((here / name).relative_to(root).as_posix(), here / name) for name in files]
    for relative, path in sorted(entries):
        digest, size = sha256_file(path)
        yield {"path": relative, "size_bytes": size, "sha256": digest}


def listing_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(line_json({"schema": LISTING_SCHEMA, **row}) for row in rows)


def build(
    root: Path,
    out_dir: Path,
    *,
    created_at: datetime,
    git_head: str,
    git_status_porcelain: str,
    operator: str,
) -> dict[str, Any]:
    """Hash the tree and write ``files.jsonl`` and ``manifest.json`` into ``out_dir`` — which must
    lie outside the legacy tree and must not already hold a manifest.
    """
    root, out_dir = Path(root), Path(out_dir)
    if is_inside(out_dir, root):
        raise FreezeError("the manifest is written outside the legacy tree")
    if (out_dir / MANIFEST_NAME).exists() or (out_dir / LISTING_NAME).exists():
        raise FreezeError("a manifest already exists there; a freeze manifest is never overwritten")
    rows = list(scan(root))
    listing = listing_bytes(rows)
    areas: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = areas.setdefault(area_of(row["path"]), {"files": 0, "bytes": 0})
        entry["files"] += 1
        entry["bytes"] += row["size_bytes"]
    scope = [row for row in rows if in_release_scope(row["path"])]
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "freeze_id": FREEZE_ID,
        "state": STATE_MANIFEST_ONLY,
        "state_note": "Step 1 of the legacy freeze. The frozen release needs a verified preservation copy and a restore check (O-3).",
        "created_at": format_instant(created_at),
        "operator": operator,
        "tool": {"name": TOOL, "package_version": __version__},
        "hash": "sha256",
        "fixity_semantics": "bytes: path, size and SHA-256. Modification times are not recorded and not compared.",
        "legacy_repository": {
            "directory_name": root.name,
            "git_head": git_head,
            "git_status_clean": git_status_porcelain.strip() == "",
            "git_status_sha256": sha256_bytes(git_status_porcelain.encode("utf-8")),
        },
        "excluded": [f"{name}/ — represented by git_head and git_status" for name in EXCLUDED_DIRECTORIES],
        "totals": {"files": len(rows), "bytes": sum(row["size_bytes"] for row in rows)},
        "release_scope": {"prefixes": list(RELEASE_SCOPE), "files": len(scope), "bytes": sum(row["size_bytes"] for row in scope)},
        "areas": dict(sorted(areas.items())),
        "listing": {"file": LISTING_NAME, "schema": LISTING_SCHEMA, "sha256": sha256_bytes(listing),
                    "size_bytes": len(listing), "rows": len(rows)},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / LISTING_NAME, "xb") as handle:
        handle.write(listing)
    with open(out_dir / MANIFEST_NAME, "xb") as handle:
        handle.write(record_json(manifest))
    return manifest


def read(manifest_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """A manifest and its listing — refused unless the listing is the one the manifest binds."""
    manifest_dir = Path(manifest_dir)
    try:
        manifest = json.loads((manifest_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        data = (manifest_dir / LISTING_NAME).read_bytes()
        if manifest["schema"] != MANIFEST_SCHEMA:
            raise ValueError(f"schema {manifest['schema']!r}")
        if sha256_bytes(data) != manifest["listing"]["sha256"]:
            raise ValueError("the listing is not the one the manifest names")
        rows = [json.loads(line.decode("utf-8")) for line in data.split(b"\n")[:-1]]
        if len(rows) != manifest["listing"]["rows"] or any(row["schema"] != LISTING_SCHEMA for row in rows):
            raise ValueError("the listing does not have the rows the manifest names")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise FreezeError(f"not a readable freeze manifest: {error}") from error
    return manifest, {row["path"]: row for row in rows}


def verify(root: Path, manifest_dir: Path, *, git_head: str | None = None) -> dict[str, Any]:
    """Hash the tree again and compare it with a manifest. Reports every difference; raises only
    when the manifest itself cannot be trusted.
    """
    manifest, expected = read(manifest_dir)
    added, changed, seen = [], [], set()
    for row in scan(root):
        seen.add(row["path"])
        held = expected.get(row["path"])
        if held is None:
            added.append(row["path"])
        elif (held["size_bytes"], held["sha256"]) != (row["size_bytes"], row["sha256"]):
            changed.append(row["path"])
    removed = sorted(set(expected) - seen)
    head_matches = None if git_head is None else git_head == manifest["legacy_repository"]["git_head"]
    intact = not (added or changed or removed) and head_matches is not False
    return {
        "freeze_id": manifest["freeze_id"], "status": VERIFIED if intact else DIFFERS,
        "files_in_manifest": len(expected), "files_in_tree": len(seen), "unchanged": len(seen) - len(added) - len(changed),
        "added": added, "removed": removed, "changed": changed, "git_head_matches": head_matches,
        "listing_sha256": manifest["listing"]["sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the legacy freeze manifest. Reads the legacy tree; writes outside it.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, required=True, help="the legacy working tree")
        command.add_argument("--manifest-dir", type=Path, required=True)
        command.add_argument("--git-head", required=True, help="the commit the legacy tree has checked out")
        if name == "build":
            command.add_argument("--git-status-file", type=Path, required=True, help="output of `git status --porcelain` of the legacy tree")
            command.add_argument("--operator", required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "build":
        manifest = build(arguments.root, arguments.manifest_dir, created_at=datetime.now(timezone.utc), git_head=arguments.git_head,
                         git_status_porcelain=arguments.git_status_file.read_text(encoding="utf-8"), operator=arguments.operator)
        print(json.dumps({key: manifest[key] for key in ("freeze_id", "state", "totals", "release_scope", "listing")}, indent=2))
        return 0
    report = verify(arguments.root, arguments.manifest_dir, git_head=arguments.git_head)
    print(json.dumps({**report, "added": report["added"][:20], "removed": report["removed"][:20], "changed": report["changed"][:20]}, indent=2))
    return 0 if report["status"] == VERIFIED else 1


if __name__ == "__main__":
    raise SystemExit(main())
