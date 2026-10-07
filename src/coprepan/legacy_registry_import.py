"""Read-only import of the legacy outlets and feeds into a *proposed* outlet registry.

What it does (master plan §12 item 3.2, ``docs/corpus_supply/INDEX.md`` §12):

* copies the legacy database file (with its ``-wal`` / ``-shm`` siblings) into a work directory
  outside the legacy tree and opens **only that copy** — the legacy database is never opened in
  place (``docs/legacy/INDEX.md`` §2);
* turns every legacy ``sources`` row into a proposed outlet and every ``feeds`` row into a
  proposed channel, keeping each observed legacy value verbatim under ``legacy_observed``;
* records every observed legacy name as an alias with ``mapping_status: hypothesis``;
* writes a reviewable legacy-name → ``outlet_id`` mapping.

What it does not do: it registers nothing. Every outlet it writes is ``proposed``; an
``outlet_id`` becomes permanent only when a reviewer sets ``registered``. It fills no attribute
the legacy database does not hold (type, group, time zone, …): those stay ``unknown``.

Slug variants observed outside the database (directory names, fields of exported files) are not
visible here and are not covered.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from . import naming, registry
from .canonical import record_json, sha256_file
from .identity import IdentityError, channel_id, normalise_origin
from .storage_roots import CHECKOUT, is_inside

COUNTRY_CODES_SCHEMA = naming.schema_id("legacy-country-codes", 1)
IMPORT_REPORT_SCHEMA = naming.schema_id("legacy-registry-import", 1)
DEFAULT_COUNTRY_CODES_FILE = CHECKOUT / "config" / "legacy_country_codes.json"

OBSERVED_IN = "legacy_db.sources.newspaper_code"
PROPOSED_RULES_VERSION = "proposed"

_REQUIRED_COLUMNS = {
    "sources": {"id", "country_code", "newspaper_code", "name", "base_url"},
    "feeds": {"id", "source_id", "url", "type"},
}
# Legacy feed type -> channel kind. The tokens coincide; anything else stays 'unknown'.
_KIND_OF_LEGACY_TYPE = {kind: kind for kind in ("rss", "atom", "sitemap", "sitemap_index")}


class LegacyImportError(RuntimeError):
    """The import refuses to run or cannot read what it expects."""


@dataclass(frozen=True)
class ImportResult:
    registry: dict[str, Any]
    report: dict[str, Any]


def load_country_codes(path: Path | None = None) -> dict[str, str]:
    document = json.loads(Path(path or DEFAULT_COUNTRY_CODES_FILE).read_text(encoding="utf-8"))
    if document.get("schema") != COUNTRY_CODES_SCHEMA or not isinstance(document.get("codes"), dict):
        raise LegacyImportError("not a legacy country-code table")
    for legacy, country in document["codes"].items():
        if not isinstance(legacy, str) or not naming.is_country_id(country):
            raise LegacyImportError(f"bad country-code entry: {legacy!r} -> {country!r}")
    return dict(document["codes"])


def copy_database(database: Path, work_dir: Path) -> Path:
    """Copy the database and its WAL siblings into an empty directory outside its own tree."""
    database, work_dir = Path(database), Path(work_dir)
    if not database.is_file():
        raise LegacyImportError("the legacy database file does not exist")
    tree = _tree_of(database)
    if is_inside(work_dir, tree):
        raise LegacyImportError("the work directory lies inside the tree of the database; copy outside it")
    if not work_dir.is_dir() or any(work_dir.iterdir()):
        raise LegacyImportError("the work directory must exist and be empty")
    for suffix in ("", "-wal", "-shm"):
        sibling = database.with_name(database.name + suffix)
        if sibling.is_file():
            shutil.copyfile(sibling, work_dir / sibling.name)
    return work_dir / database.name


def _tree_of(database: Path) -> Path:
    """The repository the database lives in (nearest ancestor with a ``.git``), else its directory."""
    start = database.resolve().parent
    for ancestor in (start, *start.parents):
        if (ancestor / ".git").exists():
            return ancestor
    return start


def read_legacy_rows(copy: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """All ``sources`` and ``feeds`` rows of a database *copy*, every column, in id order."""
    connection = sqlite3.connect(copy)
    try:
        connection.row_factory = sqlite3.Row
        tables = {}
        for table, required in _REQUIRED_COLUMNS.items():
            columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not columns:
                raise LegacyImportError(f"the database has no table {table!r}")
            if not required <= columns:
                raise LegacyImportError(f"table {table!r} lacks column(s) {sorted(required - columns)}")
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            tables[table] = [{key: _plain(row[key]) for key in row.keys()} for row in rows]
    except sqlite3.DatabaseError as error:
        raise LegacyImportError(f"the database copy is not readable: {error}") from error
    finally:
        connection.close()
    return tables["sources"], tables["feeds"]


def _plain(value: Any) -> Any:
    return value.hex() if isinstance(value, bytes) else value


def build_proposal(
    sources: list[dict[str, Any]],
    feeds: list[dict[str, Any]],
    country_codes: Mapping[str, str],
) -> ImportResult:
    """Pure function: legacy rows in, proposed registry and review report out. Deterministic."""
    unresolved: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    outlet_of_source: dict[Any, str] = {}
    for source in sources:
        country = country_codes.get(source["country_code"])
        slug = registry.propose_slug(str(source["newspaper_code"] or ""))
        if country is None:
            unresolved.append(_unresolved("source", source, "country_code_not_in_table"))
        elif not slug:
            unresolved.append(_unresolved("source", source, "no_ascii_slug_from_newspaper_code"))
        else:
            proposed = f"{country}_{slug}"
            grouped.setdefault(proposed, []).append(source)
            outlet_of_source[source["id"]] = proposed

    feeds_of: dict[str, list[dict[str, Any]]] = {}
    for feed in feeds:
        owner = outlet_of_source.get(feed["source_id"])
        if owner is None:
            unresolved.append(_unresolved("feed", feed, "source_not_imported"))
        elif not isinstance(feed["url"], str) or not feed["url"].strip():
            unresolved.append(_unresolved("feed", feed, "empty_url"))
        else:
            feeds_of.setdefault(owner, []).append(feed)

    outlets, mapping = [], []
    for outlet_id in sorted(grouped):
        rows = grouped[outlet_id]
        notes = []
        if len(rows) > 1:
            notes.append(
                f"{len(rows)} legacy sources fold to this proposed id by ASCII slug; "
                "whether they are one outlet is a review decision"
            )
        origins = []
        for row in rows:
            origin = _origin(row["base_url"])
            if origin is None:
                notes.append(f"legacy source {row['id']}: base_url gives no usable web origin")
            elif origin not in origins:
                origins.append(origin)
        names = []
        for row in rows:
            name = str(row["name"] or "").strip()
            if name and name not in names:
                names.append(name)
        if not names:
            names.append(str(rows[0]["newspaper_code"]))
            notes.append("no legacy display name; the legacy code stands in")

        counters: dict[str, int] = {}
        channels = []
        for feed in feeds_of.get(outlet_id, []):
            kind = _KIND_OF_LEGACY_TYPE.get(feed["type"], registry.UNKNOWN)
            counters[kind] = counters.get(kind, 0) + 1
            channels.append(
                {
                    "channel_id": channel_id(outlet_id, f"{kind}_{counters[kind]:03d}"),
                    "kind": kind,
                    "url_history": [{"url": feed["url"], "valid_from": registry.UNKNOWN}],
                    "legacy_observed": feed,
                }
            )
        aliases = []
        for row in rows:
            alias = {
                "country_code": row["country_code"],
                "slug": row["newspaper_code"],
                "observed_in": OBSERVED_IN,
                "mapping_status": "hypothesis",
            }
            aliases.append(alias)
            mapping.append({**{k: alias[k] for k in ("country_code", "slug", "mapping_status")},
                            "legacy_source_id": row["id"], "proposed_outlet_id": outlet_id})
        outlets.append(
            {
                "outlet_id": outlet_id,
                "country_id": outlet_id[:2],
                "registration_status": "proposed",
                "display_names": [
                    {"name": name, "valid_from": registry.UNKNOWN, "valid_to": registry.UNKNOWN} for name in names
                ],
                "outlet_type": registry.UNKNOWN,
                "outlet_group": registry.UNKNOWN,
                "city": registry.UNKNOWN,
                "region": registry.UNKNOWN,
                "scope": registry.UNKNOWN,
                "access_model": registry.UNKNOWN,
                "medium": registry.UNKNOWN,
                "editions": [],
                "web_origins": origins,
                "timezone": registry.UNKNOWN,
                "same_outlet_basis": registry.UNKNOWN,
                "url_rules": {
                    "version": PROPOSED_RULES_VERSION,
                    "significant_query_params": [],
                    "strip_path_prefixes": [],
                    "strip_path_suffixes": [],
                },
                "channels": channels,
                "legacy_aliases": aliases,
                "legacy_observed": {"sources": rows},
                "review_notes": notes,
            }
        )

    document = {"schema": registry.REGISTRY_SCHEMA, "outlets": outlets}
    registry.validate_registry(document)
    report = {
        "schema": IMPORT_REPORT_SCHEMA,
        "counts": {
            "legacy_sources": len(sources),
            "legacy_feeds": len(feeds),
            "proposed_outlets": len(outlets),
            "proposed_channels": sum(len(outlet["channels"]) for outlet in outlets),
            "proposed_outlets_folding_several_sources": sum(1 for rows in grouped.values() if len(rows) > 1),
            "unresolved": len(unresolved),
        },
        "legacy_name_to_outlet_id": mapping,
        "unresolved": unresolved,
    }
    return ImportResult(document, report)


def _unresolved(kind: str, row: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {"kind": kind, "reason": reason, "legacy_observed": dict(row)}


def _origin(base_url: Any) -> str | None:
    if not isinstance(base_url, str):
        return None
    try:
        parts = urlsplit(base_url.strip())
        return normalise_origin(f"{parts.scheme}://{parts.netloc}")
    except (IdentityError, ValueError):
        return None


def run_import(
    database: Path,
    work_dir: Path,
    registry_out: Path,
    report_out: Path,
    country_codes: Mapping[str, str] | None = None,
) -> ImportResult:
    """Copy, read the copy, build the proposal, write both outputs. Never overwrites an output."""
    for output in (registry_out, report_out):
        if Path(output).exists():
            raise LegacyImportError(f"output already exists, refusing to overwrite: {Path(output).name}")
        if is_inside(Path(output), _tree_of(Path(database))):
            raise LegacyImportError("an output path lies inside the tree of the legacy database")
    source_sha256, source_size = sha256_file(Path(database))
    copy = copy_database(database, work_dir)
    sources, feeds = read_legacy_rows(copy)
    result = build_proposal(sources, feeds, load_country_codes() if country_codes is None else country_codes)
    result.report["input"] = {
        "database_file_name": Path(database).name,
        "database_sha256": source_sha256,
        "database_size_bytes": source_size,
        "wal_sibling_present": Path(database).with_name(Path(database).name + "-wal").is_file(),
    }
    for output, payload in ((registry_out, result.registry), (report_out, result.report)):
        with open(output, "xb") as handle:
            handle.write(record_json(payload))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", type=Path, required=True, help="the legacy SQLite file (read as a file, never opened)")
    parser.add_argument("--work-dir", type=Path, required=True, help="existing empty directory outside the legacy tree")
    parser.add_argument("--registry-out", type=Path, required=True, help="proposed registry to write (must not exist)")
    parser.add_argument("--report-out", type=Path, required=True, help="review report to write (must not exist)")
    arguments = parser.parse_args(argv)
    result = run_import(arguments.database, arguments.work_dir, arguments.registry_out, arguments.report_out)
    print(json.dumps(result.report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
