"""Legacy discovery audit: what the legacy system's own records show about each outlet and channel.

A read-only, deterministic comparison base between the legacy COPREPAN source register and the
COPREPAN 3.0 outlet registry (2026-10-09). It reads

* a **copy** of the legacy SQLite database (``--database-copy``; the copy must lie outside the legacy
  tree and is opened read-only -- the legacy database itself is never opened, ``docs/legacy/INDEX.md``
  section 2),
* the directory listing (names and sizes only, no file is opened) of the legacy export layers under
  ``--legacy-root``,
* the outlet registry (``--registry``),

and writes one JSON document (``coprepan-legacy-discovery-audit/v1``; sorted keys, LF, UTF-8). The
document holds no clock reading and no absolute path, so two runs on the same inputs are
byte-identical.

    python scripts/legacy_discovery_audit.py --database-copy COPY --legacy-root TREE \
        --registry config/outlet_registry.json --out OUT.json

It is a diagnosis: it changes nothing it reads, registers nothing and fetches nothing. Every class
it assigns is derived by the rules it prints under ``rules``; a class is a statement about what the
legacy records contain, never about whether a channel is alive today.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "coprepan-legacy-discovery-audit/v1"

# --- rule parameters (stated in the output under "rules") -----------------------------------------
PRODUCTIVE_RUN_MIN_OK_ARTICLES = 5  # a crawl run counts as productive for an outlet from this many 'ok' rows
REPEATED_MIN_PRODUCTIVE_RUN_DAYS = 2  # productive runs on at least this many distinct days = repeated
LEGACY_CRAWL_MIN_SCORE = 40  # legacy crawler contract: is_active, status 'active', feed_score >= 40
LAYERS = ("json_raw", "json_raw_extended", "json_annotated", "backup")
KIND_OF_LEGACY_TYPE = {kind: kind for kind in ("rss", "atom", "sitemap", "sitemap_index")}
DATED_NAME = re.compile(r"_(\d{4}-\d{2}-\d{2})(?:\.ann)?\.json$")

CHANNEL_CLASSES = ("PRODUCTIVE_REPEATED", "PRODUCTIVE_ONCE_OR_SPORADIC", "NEVER_SUCCESSFUL", "NO_EVIDENCE")
OUTLET_CLASSES = (
    "LEGACY_PRODUCTIVE_REPEATED",
    "LEGACY_PRODUCTIVE_SPORADIC",
    "LEGACY_NEVER_PRODUCTIVE",
    "LEGACY_NO_CHANNEL",
)

CHANNEL_BASIS = {
    "sole_successful_feed_of_source_with_repeated_source_success": {
        "class": "PRODUCTIVE_REPEATED",
        "shows": "last_success_at is set, no other feed row of the same legacy source has it set, and the "
        "source finished with saved > 0 in crawl runs of the feedback era on two or more distinct days; "
        "each such finish stamped at least one feed, so by exclusion it was this one",
        "does_not_show": "an inference, not a per-feed log: a feed deleted from the table since, or a crawl "
        "through another code path, would break it; it says nothing about the channel today",
    },
    "last_success_at_set": {
        "class": "PRODUCTIVE_ONCE_OR_SPORADIC",
        "shows": "the feed listed at least one URL that became an 'ok' article (>= 100 extracted words) in the "
        "crawl run that wrote last_success_at",
        "does_not_show": "how often: the table keeps only the last success per feed and nothing links an "
        "article to the feed that listed it, so a repetition cannot be attributed to this feed",
    },
    "crawled_in_feedback_era_without_success": {
        "class": "NEVER_SUCCESSFUL",
        "shows": "the feed was read by a crawl at or after the first recorded last_success_at and no success "
        "was ever stamped on it",
        "does_not_show": "why: an empty feed, URLs already stored, only short or discarded pages and a read "
        "error swallowed by the legacy code all look the same. Only the first feed of a source to list a "
        "new URL in a run was credited (feeds were read by score, priority, update time), so a feed that "
        "duplicates a better-ranked feed of the same outlet lands here although it lists good URLs. A run "
        "aborted before the feedback step leaves no stamp either",
    },
    "discovery_verdict_only": {
        "class": "NEVER_SUCCESSFUL",
        "shows": "no crawl read the feed in the feedback era; the last discovery scoring left a non-active "
        "verdict (see fail_category)",
        "does_not_show": "a crawl result: the verdict is one probe of at most 8 URLs with the legacy "
        "extractor, or an HTTP status seen once",
    },
    "sitemap_index_not_expanded_by_legacy": {
        "class": "NO_EVIDENCE",
        "shows": "the feed is a sitemap index; the legacy scorer never activated one and the crawl service "
        "skipped them",
        "does_not_show": "anything about what the index leads to",
    },
    "no_crawl_and_no_verdict": {
        "class": "NO_EVIDENCE",
        "shows": "no crawl in the feedback era, no success stamp and no discovery failure reason",
        "does_not_show": "anything about the feed's output",
    },
}

SOURCE_COLUMNS_IDENTITY = ("id", "country_code", "newspaper_code", "name", "base_url")
FEED_STATUS_FIELDS = (
    "status", "is_active", "feed_score", "priority", "discovered_by", "last_status", "last_crawled_at",
    "last_attempt_at", "last_success_at", "last_error_at", "last_discovery_at", "consecutive_empty_runs",
    "consecutive_fail_runs", "last_fail_reason", "error_message", "created_at", "updated_at",
)


class AuditError(RuntimeError):
    """The audit refuses to run or cannot read what it expects."""


# --- small helpers --------------------------------------------------------------------------------

def sha256_of(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def is_inside(path: Path, root: Path) -> bool:
    path_text = os.path.normcase(str(Path(path).resolve()))
    root_text = os.path.normcase(str(Path(root).resolve()))
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False


def ascii_fold(text: str) -> str:
    """NFKD, combining marks dropped, ASCII only, lower case, runs of other characters to '_'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    kept = "".join(char for char in decomposed if not unicodedata.combining(char))
    kept = kept.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", kept).strip("_")


def origin_of(url) -> str | None:
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not host:
        return None
    default = {"http": 80, "https": 443}[scheme]
    return f"{scheme}://{host}" + (f":{port}" if port and port != default else "")


def url_variant_key(url: str) -> str:
    """Key under which URLs differing only by scheme, 'www.' and a trailing slash coincide."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return host + (parts.path.rstrip("/") or "") + ("?" + parts.query if parts.query else "")


def day(stamp) -> str | None:
    return stamp[:10] if isinstance(stamp, str) and len(stamp) >= 10 else None


def bump(counter: dict, key, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + amount


def fail_category(reason) -> str:
    if reason is None:
        return "none"
    if reason.startswith("empty_output:"):
        return "crawl_empty_output"
    if "sitemap_index forced inactive" in reason:
        return "discovery_sitemap_index_forced_inactive"
    if "no usable output" in reason:
        return "discovery_output_probe_failed"
    if "INACTIVE (score=" in reason:
        return "discovery_inactive_by_score"
    match = re.fullmatch(r"HTTP (\d{3})", reason.strip())
    if match:
        return "discovery_http_" + match.group(1)
    if reason.startswith("HTTP fetch failed"):
        return "discovery_http_fetch_failed"
    if reason.startswith("HTTP 200 OK; Valid XML Content-Type"):
        return "discovery_http_200_xml_reason_cut_off"
    return "other"


def discovery_error_category(status, message) -> str:
    if status == "completed" and message is None:
        return "completed"
    text = message or ""
    if "TDM-Opt-Out" in text:
        return "tdm_opt_out_detected"
    if "timed out" in text:
        return "timeout"
    if "Server-Neustart" in text:
        return "aborted_by_server_restart"
    if message is None:
        return f"{status}_without_message"
    return "code_error_or_other"


# --- reading the database copy --------------------------------------------------------------------

def open_copy(copy: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(copy).resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def rows_of(connection, sql: str, parameters=()) -> list[dict]:
    result = []
    for row in connection.execute(sql, parameters):
        result.append({key: (row[key].hex() if isinstance(row[key], bytes) else row[key]) for key in row.keys()})
    return result


def schema_summary(connection) -> dict:
    tables, indexes = {}, []
    for entry in rows_of(connection, "SELECT name, type FROM sqlite_master ORDER BY type, name"):
        if entry["type"] == "table":
            columns = rows_of(connection, f'PRAGMA table_info("{entry["name"]}")')
            tables[entry["name"]] = {
                "row_count": connection.execute(f'SELECT count(*) FROM "{entry["name"]}"').fetchone()[0],
                "columns": [
                    {"name": c["name"], "type": c["type"], "notnull": c["notnull"], "pk": c["pk"]} for c in columns
                ],
                "foreign_keys": sorted(
                    f'{k["from"]} -> {k["table"]}.{k["to"]}'
                    for k in rows_of(connection, f'PRAGMA foreign_key_list("{entry["name"]}")')
                ),
            }
        elif entry["type"] == "index":
            indexes.append(entry["name"])
    return {
        "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
        "tables": tables,
        "indexes": indexes,
        "note": "articles carries source_id and crawl_run_id but no feed id: no table links an article to the "
        "feed that listed its URL",
    }


def article_statistics(connection) -> dict:
    """Per legacy source id: everything the articles table shows, by SQL aggregates only."""
    stats: dict[int, dict] = {}

    def entry(source_id):
        return stats.setdefault(
            source_id,
            {
                "rows": 0, "by_status": {}, "ok_rows": 0, "ok_words": 0, "first_fetched_at": None,
                "last_fetched_at": None, "fetch_days": 0, "ok_fetch_days": 0, "first_ok_fetch_day": None,
                "last_ok_fetch_day": None, "crawl_runs_with_rows": 0, "crawl_runs_with_ok_rows": 0,
                "productive_runs": 0, "productive_run_days": [], "ok_date_published_first": None,
                "ok_date_published_last": None, "ok_date_published_distinct": 0,
                "ok_by_date_published_source": {},
            },
        )

    for row in connection.execute(
        "SELECT source_id, status, count(*), coalesce(sum(words), 0) FROM articles GROUP BY 1, 2 ORDER BY 1, 2"
    ):
        item = entry(row[0])
        item["rows"] += row[2]
        item["by_status"][row[1]] = row[2]
        if row[1] == "ok":
            item["ok_rows"], item["ok_words"] = row[2], row[3]
    for row in connection.execute(
        "SELECT source_id, min(fetched_at), max(fetched_at), count(DISTINCT substr(fetched_at, 1, 10)), "
        "count(DISTINCT crawl_run_id) FROM articles GROUP BY 1"
    ):
        item = entry(row[0])
        item["first_fetched_at"], item["last_fetched_at"] = row[1], row[2]
        item["fetch_days"], item["crawl_runs_with_rows"] = row[3], row[4]
    for row in connection.execute(
        "SELECT source_id, count(DISTINCT substr(fetched_at, 1, 10)), min(substr(fetched_at, 1, 10)), "
        "max(substr(fetched_at, 1, 10)), min(date_published), max(date_published), "
        "count(DISTINCT date_published) FROM articles WHERE status = 'ok' GROUP BY 1"
    ):
        item = entry(row[0])
        item["ok_fetch_days"], item["first_ok_fetch_day"], item["last_ok_fetch_day"] = row[1], row[2], row[3]
        item["ok_date_published_first"], item["ok_date_published_last"] = row[4], row[5]
        item["ok_date_published_distinct"] = row[6]
    for row in connection.execute(
        "SELECT source_id, coalesce(date_published_source, 'none'), count(*) FROM articles "
        "WHERE status = 'ok' GROUP BY 1, 2 ORDER BY 1, 2"
    ):
        entry(row[0])["ok_by_date_published_source"][row[1]] = row[2]
    for row in connection.execute(
        "SELECT source_id, crawl_run_id, count(*), min(substr(fetched_at, 1, 10)) FROM articles "
        "WHERE status = 'ok' GROUP BY 1, 2 ORDER BY 1, 2"
    ):
        item = entry(row[0])
        item["crawl_runs_with_ok_rows"] += 1
        if row[2] >= PRODUCTIVE_RUN_MIN_OK_ARTICLES:
            item["productive_runs"] += 1
            if row[3] not in item["productive_run_days"]:
                item["productive_run_days"].append(row[3])
    for item in stats.values():
        item["productive_run_days"].sort()
    return stats


def crawl_run_statistics(crawl_runs: list[dict], era_start) -> tuple[dict, dict]:
    """Per legacy source id: what crawl_runs.source_results_json / source_timeouts record."""
    per_source: dict[int, dict] = {}
    totals = {"runs": len(crawl_runs), "by_status": {}, "runs_with_source_results": 0,
              "source_result_entries": 0, "source_result_status": {}, "unparsable_json_fields": 0,
              "first_started_at": None, "last_started_at": None, "feedback_era_runs": 0}

    def entry(source_id):
        return per_source.setdefault(
            source_id,
            {"runs_scheduled": 0, "result_entries": 0, "result_status": {}, "saved_total": 0,
             "words_total": 0, "runs_saved_gt0": 0, "run_days_saved_gt0": [],
             "feedback_era_runs_saved_gt0": 0, "feedback_era_run_days_saved_gt0": [], "source_timeouts": 0},
        )

    for run in crawl_runs:
        bump(totals["by_status"], run["status"])
        started = run["started_at"]
        if totals["first_started_at"] is None or started < totals["first_started_at"]:
            totals["first_started_at"] = started
        if totals["last_started_at"] is None or started > totals["last_started_at"]:
            totals["last_started_at"] = started
        in_era = era_start is not None and started >= era_start
        totals["feedback_era_runs"] += int(in_era)
        for field, default in (("source_ids_json", []), ("source_results_json", []), ("source_timeouts", {})):
            try:
                run["_" + field] = json.loads(run[field]) if run[field] else default
            except ValueError:
                run["_" + field] = default
                totals["unparsable_json_fields"] += 1
        for source_id in run["_source_ids_json"]:
            if isinstance(source_id, int):
                entry(source_id)["runs_scheduled"] += 1
        for key in run["_source_timeouts"]:
            if str(key).isdigit():
                entry(int(key))["source_timeouts"] += 1
        if run["_source_results_json"]:
            totals["runs_with_source_results"] += 1
        for result in run["_source_results_json"]:
            source_id = result.get("source_id")
            if not isinstance(source_id, int):
                continue
            item = entry(source_id)
            totals["source_result_entries"] += 1
            bump(totals["source_result_status"], str(result.get("status")))
            item["result_entries"] += 1
            bump(item["result_status"], str(result.get("status")))
            saved = result.get("saved") or 0
            item["saved_total"] += saved
            item["words_total"] += result.get("words") or 0
            if saved > 0:
                item["runs_saved_gt0"] += 1
                if day(started) not in item["run_days_saved_gt0"]:
                    item["run_days_saved_gt0"].append(day(started))
                if in_era:
                    item["feedback_era_runs_saved_gt0"] += 1
                    if day(started) not in item["feedback_era_run_days_saved_gt0"]:
                        item["feedback_era_run_days_saved_gt0"].append(day(started))
    for item in per_source.values():
        item["run_days_saved_gt0"].sort()
        item["feedback_era_run_days_saved_gt0"].sort()
    return per_source, totals


def run_containing(crawl_runs: list[dict], stamp) -> dict | None:
    """The latest-started crawl run whose [started_at, finished_at] window contains the stamp."""
    found = None
    for run in crawl_runs:
        if stamp is None or run["finished_at"] is None:
            continue
        if run["started_at"] <= stamp <= run["finished_at"] and (found is None or run["started_at"] > found["started_at"]):
            found = run
    return found


def discovery_statistics(discovery_runs: list[dict]) -> tuple[dict, dict]:
    per_source: dict[int, dict] = {}
    totals = {"runs": len(discovery_runs), "by_status": {}, "by_category": {}, "by_day": {},
              "first_started_at": None, "last_started_at": None, "distinct_days": 0,
              "sources_with_runs": 0, "feeds_found": 0, "feeds_created": 0, "feeds_updated": 0,
              "runs_per_source_min": None, "runs_per_source_max": None}
    for run in discovery_runs:
        category = discovery_error_category(run["status"], run["error_message"])
        started = run["started_at"]
        item = per_source.setdefault(
            run["source_id"],
            {"runs": 0, "by_status": {}, "by_category": {}, "first_started_at": started,
             "last_started_at": started, "days": [], "feeds_found": 0, "feeds_created": 0,
             "feeds_updated": 0, "last_run_status": None, "last_run_category": None,
             "last_completed_at": None, "last_completed_feeds_found": None},
        )
        item["runs"] += 1
        bump(item["by_status"], run["status"])
        bump(item["by_category"], category)
        bump(totals["by_status"], run["status"])
        bump(totals["by_category"], category)
        bump(totals["by_day"].setdefault(day(started), {}), run["status"])
        for field in ("feeds_found", "feeds_created", "feeds_updated"):
            item[field] += run[field] or 0
            totals[field] += run[field] or 0
        if day(started) not in item["days"]:
            item["days"].append(day(started))
        if started >= item["last_started_at"]:
            item["last_started_at"] = started
            item["last_run_status"], item["last_run_category"] = run["status"], category
        item["first_started_at"] = min(item["first_started_at"], started)
        if run["status"] == "completed" and (item["last_completed_at"] is None or started >= item["last_completed_at"]):
            item["last_completed_at"], item["last_completed_feeds_found"] = started, run["feeds_found"]
        if totals["first_started_at"] is None or started < totals["first_started_at"]:
            totals["first_started_at"] = started
        if totals["last_started_at"] is None or started > totals["last_started_at"]:
            totals["last_started_at"] = started
    for item in per_source.values():
        item["days"].sort()
        item["distinct_days"] = len(item["days"])
    totals["distinct_days"] = len(totals["by_day"])
    totals["sources_with_runs"] = len(per_source)
    if per_source:
        counts = [item["runs"] for item in per_source.values()]
        totals["runs_per_source_min"], totals["runs_per_source_max"] = min(counts), max(counts)
    return per_source, totals


# --- directory listing of the legacy export layers ------------------------------------------------

def list_layer(root: Path) -> dict:
    """Listing only: names and sizes below ``<layer>/<COUNTRY>/<slug>/``. No file is opened."""
    listing = {"present": root.is_dir(), "directories": {}, "loose_files": [], "files": 0, "bytes": 0}
    if not listing["present"]:
        return listing
    for current, directories, files in os.walk(root):
        directories.sort()
        relative = Path(current).relative_to(root).parts
        for name in sorted(files):
            size = os.path.getsize(os.path.join(current, name))
            listing["files"] += 1
            listing["bytes"] += size
            if len(relative) < 2:
                listing["loose_files"].append("/".join((*relative, name)))
                continue
            key = relative[0] + "/" + relative[1]
            item = listing["directories"].setdefault(
                key, {"files": 0, "bytes": 0, "json_files": 0, "dated_files": 0, "dates": set(), "other_files": []}
            )
            item["files"] += 1
            item["bytes"] += size
            item["json_files"] += int(name.lower().endswith(".json"))
            match = DATED_NAME.search(name) if len(relative) == 2 else None
            if match:
                item["dated_files"] += 1
                item["dates"].add(match.group(1))
            else:
                item["other_files"].append("/".join((*relative[2:], name)))
    for item in listing["directories"].values():
        dates = sorted(item.pop("dates"))
        item["first_date"], item["last_date"] = (dates[0], dates[-1]) if dates else (None, None)
        item["distinct_dates"] = len(dates)
    return listing


def annotation_state(copy: Path | None) -> dict | None:
    """Optional: article counts per input file from a copy of the legacy annotation state database."""
    if copy is None:
        return None
    connection = open_copy(copy)
    try:
        per_directory: dict[str, dict] = {}
        for row in connection.execute(
            "SELECT input_path, status, article_count, annotated_articles, token_count FROM annotation_state"
        ):
            parts = [part for part in re.split(r"[\\/]+", row[0] or "") if part]
            key = "/".join(parts[1:3]) if len(parts) >= 4 else "?"
            item = per_directory.setdefault(
                key, {"input_files": 0, "article_count": 0, "annotated_articles": 0, "token_count": 0, "by_status": {}}
            )
            item["input_files"] += 1
            item["article_count"] += row[2] or 0
            item["annotated_articles"] += row[3] or 0
            item["token_count"] += row[4] or 0
            bump(item["by_status"], row[1])
    finally:
        connection.close()
    return per_directory


# --- classification -------------------------------------------------------------------------------

def classify_channel(feed: dict, era_start, successful_in_source: int, source_runs: dict) -> tuple[str, str]:
    success_days = len(source_runs.get("feedback_era_run_days_saved_gt0", []))
    if feed["last_success_at"] is not None:
        if successful_in_source == 1 and success_days >= REPEATED_MIN_PRODUCTIVE_RUN_DAYS:
            return "PRODUCTIVE_REPEATED", "sole_successful_feed_of_source_with_repeated_source_success"
        return "PRODUCTIVE_ONCE_OR_SPORADIC", "last_success_at_set"
    touched = [stamp for stamp in (feed["last_crawled_at"], feed["last_attempt_at"]) if stamp is not None]
    if era_start is not None and touched and max(touched) >= era_start:
        return "NEVER_SUCCESSFUL", "crawled_in_feedback_era_without_success"
    if feed["type"] == "sitemap_index":
        return "NO_EVIDENCE", "sitemap_index_not_expanded_by_legacy"
    if feed["last_fail_reason"] is not None:
        return "NEVER_SUCCESSFUL", "discovery_verdict_only"
    return "NO_EVIDENCE", "no_crawl_and_no_verdict"


def classify_outlet(feed_rows: int, articles: dict) -> str:
    if articles["ok_rows"] > 0:
        if len(articles["productive_run_days"]) >= REPEATED_MIN_PRODUCTIVE_RUN_DAYS:
            return "LEGACY_PRODUCTIVE_REPEATED"
        return "LEGACY_PRODUCTIVE_SPORADIC"
    if feed_rows == 0 and articles["rows"] == 0:
        return "LEGACY_NO_CHANNEL"
    return "LEGACY_NEVER_PRODUCTIVE"


def merge_articles(parts: list[dict]) -> dict:
    """Article statistics of an outlet = those of its legacy sources (one source per outlet as imported)."""
    if len(parts) == 1:
        return parts[0]
    merged = {"rows": 0, "by_status": {}, "ok_rows": 0, "ok_words": 0, "productive_runs": 0,
              "productive_run_days": [], "crawl_runs_with_rows": 0, "crawl_runs_with_ok_rows": 0,
              "ok_by_date_published_source": {}, "fetch_days": None, "ok_fetch_days": None,
              "ok_date_published_distinct": None,
              "merge_note": "several legacy sources: day counts are not additive and are left null"}
    for part in parts:
        for key in ("rows", "ok_rows", "ok_words", "productive_runs", "crawl_runs_with_rows", "crawl_runs_with_ok_rows"):
            merged[key] += part[key]
        for name in ("by_status", "ok_by_date_published_source"):
            for key, value in part[name].items():
                bump(merged[name], key, value)
        merged["productive_run_days"] = sorted(set(merged["productive_run_days"]) | set(part["productive_run_days"]))
    for key, pick in (("first_fetched_at", min), ("last_fetched_at", max), ("first_ok_fetch_day", min),
                      ("last_ok_fetch_day", max), ("ok_date_published_first", min), ("ok_date_published_last", max)):
        values = [part[key] for part in parts if part[key] is not None]
        merged[key] = pick(values) if values else None
    return merged


EMPTY_ARTICLES = {
    "rows": 0, "by_status": {}, "ok_rows": 0, "ok_words": 0, "first_fetched_at": None, "last_fetched_at": None,
    "fetch_days": 0, "ok_fetch_days": 0, "first_ok_fetch_day": None, "last_ok_fetch_day": None,
    "crawl_runs_with_rows": 0, "crawl_runs_with_ok_rows": 0, "productive_runs": 0, "productive_run_days": [],
    "ok_date_published_first": None, "ok_date_published_last": None, "ok_date_published_distinct": 0,
    "ok_by_date_published_source": {},
}


# --- the audit ------------------------------------------------------------------------------------

def build(arguments) -> dict:
    copy, legacy_root, registry_path = arguments.database_copy, arguments.legacy_root, arguments.registry
    for label, path in (("--database-copy", copy), ("--annotation-state-copy", arguments.annotation_state_copy),
                        ("--out", arguments.out)):
        if path is not None and is_inside(path, legacy_root):
            raise AuditError(f"{label} lies inside --legacy-root; work on a copy outside the legacy tree")
    if not copy.is_file():
        raise AuditError("--database-copy is not a file")
    if not legacy_root.is_dir():
        raise AuditError("--legacy-root is not a directory")

    copy_sha, copy_size = sha256_of(copy)
    wal = copy.with_name(copy.name + "-wal")
    inputs = {
        "database_copy": {"file_name": copy.name, "sha256": copy_sha, "size_bytes": copy_size,
                          "wal_sibling": None, "opened": "read-only (mode=ro); the WAL sibling is read when present"},
        "registry": dict(zip(("sha256", "size_bytes"), sha256_of(registry_path)), file_name=registry_path.name),
    }
    if wal.is_file():
        wal_sha, wal_size = sha256_of(wal)
        inputs["database_copy"]["wal_sibling"] = {"file_name": wal.name, "sha256": wal_sha, "size_bytes": wal_size}
    for label, path in (("country_codes", arguments.country_codes), ("import_report", arguments.import_report),
                        ("registration_report", arguments.registration_report),
                        ("annotation_state_copy", arguments.annotation_state_copy)):
        inputs[label] = None if path is None else dict(zip(("sha256", "size_bytes"), sha256_of(path)), file_name=path.name)

    connection = open_copy(copy)
    try:
        schema = schema_summary(connection)
        sources = rows_of(connection, "SELECT * FROM sources ORDER BY id")
        feeds = rows_of(connection, "SELECT * FROM feeds ORDER BY id")
        discovery_runs = rows_of(connection, "SELECT * FROM discovery_runs ORDER BY id")
        crawl_runs = rows_of(connection, "SELECT * FROM crawl_runs ORDER BY id")
        articles = article_statistics(connection)
        article_totals = {
            "rows": connection.execute("SELECT count(*) FROM articles").fetchone()[0],
            "by_status": dict(connection.execute("SELECT status, count(*) FROM articles GROUP BY 1").fetchall()),
            "first_fetched_at": connection.execute("SELECT min(fetched_at) FROM articles").fetchone()[0],
            "last_fetched_at": connection.execute("SELECT max(fetched_at) FROM articles").fetchone()[0],
            "sources_with_rows": connection.execute("SELECT count(DISTINCT source_id) FROM articles").fetchone()[0],
            "rows_without_crawl_run_id": connection.execute(
                "SELECT count(*) FROM articles WHERE crawl_run_id IS NULL").fetchone()[0],
            "rows_with_unknown_source_id": connection.execute(
                "SELECT count(*) FROM articles WHERE source_id NOT IN (SELECT id FROM sources)").fetchone()[0],
        }
    finally:
        connection.close()
    if sha256_of(copy)[0] != copy_sha:
        raise AuditError("the database copy changed while it was read")

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    outlets = registry["outlets"]
    country_codes = None
    if arguments.country_codes is not None:
        country_codes = json.loads(arguments.country_codes.read_text(encoding="utf-8"))["codes"]

    discrepancies: list[dict] = []
    notes: list[dict] = []

    def discrepancy(kind: str, **detail) -> None:
        discrepancies.append({"kind": kind, **detail})

    def note(kind: str, **detail) -> None:
        notes.append({"kind": kind, **detail})

    # -- feedback era --------------------------------------------------------------------------
    success_stamps = [feed["last_success_at"] for feed in feeds if feed["last_success_at"] is not None]
    first_success = min(success_stamps) if success_stamps else None
    first_run = run_containing(crawl_runs, first_success)
    era_start = first_run["started_at"] if first_run else first_success
    crawl_per_source, crawl_totals = crawl_run_statistics(crawl_runs, era_start)
    discovery_per_source, discovery_totals = discovery_statistics(discovery_runs)

    # -- identity: legacy source -> outlet -------------------------------------------------------
    source_by_id = {source["id"]: source for source in sources}
    outlets_of_source: dict[int, list[str]] = {}
    outlet_by_id: dict[str, dict] = {}
    for outlet in outlets:
        outlet_id = outlet["outlet_id"]
        if outlet_id in outlet_by_id:
            discrepancy("outlet_id_twice_in_registry", outlet_id=outlet_id)
        outlet_by_id[outlet_id] = outlet
        observed = (outlet.get("legacy_observed") or {}).get("sources") or []
        if not observed:
            note("outlet_without_legacy_source", outlet_id=outlet_id)
        if len(observed) > 1:
            discrepancy("outlet_folds_several_legacy_sources", outlet_id=outlet_id,
                        legacy_source_ids=[row.get("id") for row in observed])
        if outlet.get("country_id") != outlet_id[:2]:
            discrepancy("country_id_differs_from_outlet_id_prefix", outlet_id=outlet_id,
                        country_id=outlet.get("country_id"))
        for row in observed:
            outlets_of_source.setdefault(row.get("id"), []).append(outlet_id)
            source = source_by_id.get(row.get("id"))
            if source is None:
                discrepancy("registry_source_not_in_database", outlet_id=outlet_id, legacy_source_id=row.get("id"))
                continue
            for column in sorted(set(source) | set(row)):
                if source.get(column, "<absent>") != row.get(column, "<absent>"):
                    discrepancy("source_row_differs", outlet_id=outlet_id, legacy_source_id=source["id"],
                                column=column, database=source.get(column, "<absent>"),
                                registry=row.get(column, "<absent>"))

    for source in sources:
        owners = outlets_of_source.get(source["id"], [])
        if not owners:
            discrepancy("legacy_source_not_in_registry", legacy_source_id=source["id"],
                        country_code=source["country_code"], newspaper_code=source["newspaper_code"])
            continue
        if len(owners) > 1:
            discrepancy("legacy_source_in_several_outlets", legacy_source_id=source["id"], outlet_ids=owners)
        for outlet_id in owners:
            outlet = outlet_by_id[outlet_id]
            if country_codes is not None:
                expected = country_codes.get(source["country_code"])
                if expected != outlet.get("country_id"):
                    discrepancy("country_mapping_differs", outlet_id=outlet_id, legacy_source_id=source["id"],
                                legacy_country_code=source["country_code"], expected_country_id=expected,
                                registry_country_id=outlet.get("country_id"))
            names = [entry.get("name") for entry in outlet.get("display_names", [])]
            if (source["name"] or "").strip() not in names:
                discrepancy("legacy_name_not_in_display_names", outlet_id=outlet_id, legacy_source_id=source["id"],
                            legacy_name=source["name"], display_names=names)
            origin = origin_of(source["base_url"])
            if origin is None:
                discrepancy("legacy_base_url_without_origin", outlet_id=outlet_id, legacy_source_id=source["id"],
                            base_url=source["base_url"])
            elif origin not in outlet.get("web_origins", []):
                discrepancy("legacy_origin_not_in_web_origins", outlet_id=outlet_id, legacy_source_id=source["id"],
                            legacy_origin=origin, web_origins=outlet.get("web_origins", []))
            aliases = [(alias.get("country_code"), alias.get("slug")) for alias in outlet.get("legacy_aliases", [])]
            if (source["country_code"], source["newspaper_code"]) not in aliases:
                discrepancy("legacy_alias_missing", outlet_id=outlet_id, legacy_source_id=source["id"],
                            country_code=source["country_code"], newspaper_code=source["newspaper_code"])
            slug = outlet_id[3:]
            if slug != source["newspaper_code"]:
                folded = ascii_fold(source["newspaper_code"])
                if slug == folded:
                    note("outlet_slug_is_ascii_fold_of_legacy_code", outlet_id=outlet_id,
                         legacy_source_id=source["id"], newspaper_code=source["newspaper_code"])
                else:
                    discrepancy("outlet_slug_is_not_ascii_fold_of_legacy_code", outlet_id=outlet_id,
                                legacy_source_id=source["id"], newspaper_code=source["newspaper_code"],
                                ascii_fold=folded)

    source_ids = sorted(source_by_id)
    gaps = sorted(set(range(1, (source_ids[-1] if source_ids else 0) + 1)) - set(source_ids))
    if gaps:
        note("legacy_source_id_gap", missing_ids=gaps,
             meaning="ids absent from the sources table; the database does not say what they were")
    by_origin: dict[str, list[int]] = {}
    for source in sources:
        key = url_variant_key(source["base_url"]) if isinstance(source["base_url"], str) else None
        by_origin.setdefault(key, []).append(source["id"])
    for key, members in sorted(by_origin.items(), key=lambda pair: str(pair[0])):
        if len(members) > 1:
            note("legacy_sources_share_a_host", host=key, legacy_source_ids=members)
    by_name: dict[tuple, list[int]] = {}
    for source in sources:
        by_name.setdefault((source["country_code"], ascii_fold(source["name"])), []).append(source["id"])
    for (country_code, name), members in sorted(by_name.items()):
        if len(members) > 1:
            note("legacy_sources_share_a_name_in_one_country", country_code=country_code, folded_name=name,
                 legacy_source_ids=members)

    # -- identity: legacy feed -> channel --------------------------------------------------------
    channel_of_feed: dict[int, list[tuple[str, dict]]] = {}
    for outlet in outlets:
        for channel in outlet.get("channels", []):
            observed = channel.get("legacy_observed")
            if not isinstance(observed, dict) or "id" not in observed:
                note("channel_without_legacy_feed", outlet_id=outlet["outlet_id"], channel_id=channel.get("channel_id"))
                continue
            channel_of_feed.setdefault(observed["id"], []).append((outlet["outlet_id"], channel))

    expected_channel_id: dict[int, str] = {}
    counters: dict[tuple, int] = {}
    for feed in feeds:
        owners = outlets_of_source.get(feed["source_id"], [])
        if len(owners) == 1:
            kind = KIND_OF_LEGACY_TYPE.get(feed["type"], "unknown")
            counters[(owners[0], kind)] = counters.get((owners[0], kind), 0) + 1
            expected_channel_id[feed["id"]] = f"{owners[0]}:ch:{kind}_{counters[(owners[0], kind)]:03d}"

    feed_ids_in_database = {feed["id"] for feed in feeds}
    for feed_id in sorted(set(channel_of_feed) - feed_ids_in_database):
        for outlet_id, channel in channel_of_feed[feed_id]:
            discrepancy("registry_feed_not_in_database", outlet_id=outlet_id, channel_id=channel["channel_id"],
                        legacy_feed_id=feed_id)

    registered_report: dict[str, dict] = {}
    for feed in feeds:
        holders = channel_of_feed.get(feed["id"], [])
        owners = outlets_of_source.get(feed["source_id"], [])
        if not holders:
            discrepancy("legacy_feed_not_in_registry", legacy_feed_id=feed["id"], legacy_source_id=feed["source_id"],
                        url=feed["url"], outlet_ids_of_source=owners)
            continue
        if len(holders) > 1:
            discrepancy("legacy_feed_in_several_channels", legacy_feed_id=feed["id"],
                        channel_ids=[channel["channel_id"] for _, channel in holders])
        for outlet_id, channel in holders:
            channel_id = channel["channel_id"]
            if outlet_id not in owners:
                discrepancy("legacy_feed_under_another_outlet", legacy_feed_id=feed["id"], channel_id=channel_id,
                            outlet_ids_of_source=owners)
            observed = channel["legacy_observed"]
            for column in sorted(set(feed) | set(observed)):
                if feed.get(column, "<absent>") != observed.get(column, "<absent>"):
                    discrepancy("feed_row_differs", channel_id=channel_id, legacy_feed_id=feed["id"], column=column,
                                database=feed.get(column, "<absent>"), registry=observed.get(column, "<absent>"))
            kind = KIND_OF_LEGACY_TYPE.get(feed["type"], "unknown")
            if channel.get("kind") != kind:
                discrepancy("channel_kind_differs_from_legacy_type", channel_id=channel_id, legacy_feed_id=feed["id"],
                            legacy_type=feed["type"], expected_kind=kind, registry_kind=channel.get("kind"))
            if kind == "unknown":
                note("legacy_type_without_channel_kind", channel_id=channel_id, legacy_feed_id=feed["id"],
                     legacy_type=feed["type"], url=feed["url"], legacy_status=feed["status"],
                     last_fail_reason=feed["last_fail_reason"])
            history = [entry.get("url") for entry in channel.get("url_history", [])]
            if history != [feed["url"]]:
                discrepancy("channel_url_history_differs_from_legacy_url", channel_id=channel_id,
                            legacy_feed_id=feed["id"], legacy_url=feed["url"], url_history=history)
            expected = expected_channel_id.get(feed["id"])
            if expected is not None and expected != channel_id:
                registered = outlet_by_id[outlet_id].get("registration_status") == "registered"
                (note if registered else discrepancy)(
                    "channel_id_differs_from_import_id", outlet_id=outlet_id, legacy_feed_id=feed["id"],
                    import_channel_id=expected, registry_channel_id=channel_id,
                    outlet_registration_status=outlet_by_id[outlet_id].get("registration_status"))

    for outlet in outlets:
        if outlet.get("registration_status") != "registered":
            continue
        outlet_id = outlet["outlet_id"]
        source_ids_of_outlet = [row.get("id") for row in (outlet.get("legacy_observed") or {}).get("sources") or []]
        kept, dropped = [], []
        for feed in feeds:
            if feed["source_id"] not in source_ids_of_outlet:
                continue
            holders = [channel for owner, channel in channel_of_feed.get(feed["id"], []) if owner == outlet_id]
            if not holders:
                dropped.append({"legacy_feed_id": feed["id"], "url": feed["url"], "legacy_type": feed["type"]})
            for channel in holders:
                kept.append({"legacy_feed_id": feed["id"], "url": feed["url"],
                             "import_channel_id": expected_channel_id.get(feed["id"]),
                             "registry_channel_id": channel["channel_id"],
                             "renamed": expected_channel_id.get(feed["id"]) != channel["channel_id"]})
        added = [channel.get("channel_id") for channel in outlet.get("channels", [])
                 if not isinstance(channel.get("legacy_observed"), dict)]
        registered_report[outlet_id] = {
            "legacy_feeds": len(kept) + len(dropped), "kept": kept, "kept_count": len(kept),
            "renamed_count": sum(1 for item in kept if item["renamed"]), "dropped": dropped,
            "channels_without_legacy_feed": added,
        }

    if arguments.registration_report is not None:
        report = json.loads(arguments.registration_report.read_text(encoding="utf-8"))
        current = {item["import_channel_id"]: item["registry_channel_id"]
                   for value in registered_report.values() for item in value["kept"]}
        for record in report.get("registered", []):
            for old, new in sorted((record.get("channel_ids") or {}).items()):
                if current.get(old) != new:
                    discrepancy("registration_report_rename_not_reproduced", outlet_id=record.get("outlet_id"),
                                import_channel_id=old, reported_channel_id=new, registry_channel_id=current.get(old))
    if arguments.import_report is not None:
        report = json.loads(arguments.import_report.read_text(encoding="utf-8"))
        for entry in report.get("legacy_name_to_outlet_id", []):
            owners = outlets_of_source.get(entry.get("legacy_source_id"), [])
            if owners != [entry.get("proposed_outlet_id")]:
                discrepancy("import_report_mapping_differs_from_registry", legacy_source_id=entry.get("legacy_source_id"),
                            import_report_outlet_id=entry.get("proposed_outlet_id"), registry_outlet_ids=owners)
        if (report.get("input") or {}).get("database_sha256") != copy_sha:
            discrepancy("import_report_database_sha256_differs", import_report=(report.get("input") or {}).get("database_sha256"),
                        database_copy=copy_sha)
        for key, measured in (("legacy_sources", len(sources)), ("legacy_feeds", len(feeds)),
                              ("proposed_outlets", len(outlets)),
                              ("proposed_channels", sum(len(outlet.get("channels", [])) for outlet in outlets))):
            if (report.get("counts") or {}).get(key) != measured:
                discrepancy("import_report_count_differs", count=key, import_report=(report.get("counts") or {}).get(key),
                            measured=measured)

    url_owners: dict[str, list[int]] = {}
    for feed in feeds:
        url_owners.setdefault(feed["url"], []).append(feed["id"])
    for url, members in sorted(url_owners.items()):
        if len(members) > 1:
            note("legacy_feed_url_on_several_rows", url=url, legacy_feed_ids=members,
                 legacy_source_ids=sorted({feed["source_id"] for feed in feeds if feed["id"] in members}))

    # -- disk listing ----------------------------------------------------------------------------
    layers = {layer: list_layer(legacy_root / layer) for layer in LAYERS}
    annotation = annotation_state(arguments.annotation_state_copy)
    alias_exact = {(source["country_code"], source["newspaper_code"]): source["id"] for source in sources}
    alias_folded: dict[tuple, list[int]] = {}
    for source in sources:
        alias_folded.setdefault((source["country_code"], ascii_fold(source["newspaper_code"])), []).append(source["id"])

    def map_directory(key: str) -> tuple[int | None, str]:
        country_code, _, slug = key.partition("/")
        if (country_code, slug) in alias_exact:
            return alias_exact[(country_code, slug)], "exact_legacy_code"
        candidates = alias_folded.get((country_code, ascii_fold(slug)), [])
        if len(candidates) == 1:
            return candidates[0], "ascii_fold_of_legacy_code"
        return None, "unmapped" if not candidates else "ambiguous_ascii_fold"

    disk_of_source: dict[int, dict] = {}
    unmapped_directories = []
    layer_totals = {}
    for layer, listing in layers.items():
        mapped_sources = set()
        for key in sorted(listing["directories"]):
            item = dict(listing["directories"][key], path=f"{layer}/{key}")
            source_id, how = map_directory(key)
            item["mapped_by"] = how
            if source_id is None:
                unmapped_directories.append(item)
                continue
            mapped_sources.add(source_id)
            disk_of_source.setdefault(source_id, {}).setdefault(layer, []).append(item)
        with_json = [key for key, value in listing["directories"].items() if value["json_files"] > 0]
        layer_totals[layer] = {
            "present": listing["present"], "files": listing["files"], "bytes": listing["bytes"],
            "loose_files": listing["loose_files"],
            "outlet_directories": len(listing["directories"]),
            "outlet_directories_with_json_files": len(with_json),
            "json_files_in_outlet_directories": sum(value["json_files"] for value in listing["directories"].values()),
            "dated_files_in_outlet_directories": sum(value["dated_files"] for value in listing["directories"].values()),
            "legacy_sources_mapped": len(mapped_sources),
            "unmapped_directories": sorted(item["path"] for item in unmapped_directories if item["path"].startswith(layer + "/")),
        }
    annotation_unmapped = []
    annotation_of_source: dict[int, dict] = {}
    if annotation is not None:
        for key in sorted(annotation):
            source_id, how = map_directory(key) if key != "?" else (None, "unmapped")
            if source_id is None:
                annotation_unmapped.append(dict(annotation[key], directory=key))
            else:
                target = annotation_of_source.setdefault(
                    source_id, {"input_files": 0, "article_count": 0, "annotated_articles": 0, "token_count": 0})
                for field in target:
                    target[field] += annotation[key][field]

    # -- per-outlet records ----------------------------------------------------------------------
    feeds_of_source: dict[int, list[dict]] = {}
    for feed in feeds:
        feeds_of_source.setdefault(feed["source_id"], []).append(feed)
    successful_in_source = {source_id: sum(1 for feed in rows if feed["last_success_at"] is not None)
                            for source_id, rows in feeds_of_source.items()}

    def channel_record(feed: dict, channel_id) -> dict:
        source_runs = crawl_per_source.get(feed["source_id"], {})
        klass, basis = classify_channel(feed, era_start, successful_in_source.get(feed["source_id"], 0), source_runs)
        success_run = run_containing(crawl_runs, feed["last_success_at"])
        touched = [stamp for stamp in (feed["last_crawled_at"], feed["last_attempt_at"]) if stamp is not None]
        success_days = source_runs.get("feedback_era_run_days_saved_gt0", [])
        successful = successful_in_source.get(feed["source_id"], 0)
        return {
            "channel_id": channel_id,
            "legacy_feed_id": feed["id"],
            "legacy_source_id": feed["source_id"],
            "url": feed["url"],
            "kind": KIND_OF_LEGACY_TYPE.get(feed["type"], "unknown"),
            "legacy_type": feed["type"],
            "legacy_status": {field: feed[field] for field in FEED_STATUS_FIELDS},
            "legacy_crawl_eligible_at_snapshot": bool(
                feed["is_active"] and feed["status"] == "active"
                and (feed["feed_score"] or 0) >= LEGACY_CRAWL_MIN_SCORE and feed["type"] != "sitemap_index"),
            "fail_category": fail_category(feed["last_fail_reason"]),
            "productivity_class": klass,
            "productivity_evidence": {
                "basis": basis,
                "last_success_day": day(feed["last_success_at"]),
                "last_success_crawl_run_id": success_run["id"] if success_run else None,
                "last_crawl_day": day(max(touched)) if touched else None,
                "crawled_in_feedback_era": bool(era_start is not None and touched and max(touched) >= era_start),
                "successful_feeds_in_source": successful,
                "source_success_runs_in_feedback_era": source_runs.get("feedback_era_runs_saved_gt0", 0),
                "source_success_run_days_in_feedback_era": len(success_days),
                "some_feed_of_source_repeated_by_pigeonhole": bool(
                    feed["last_success_at"] is not None and len(success_days) > successful),
            },
        }

    records: dict[str, dict] = {}
    for outlet in outlets:
        outlet_id = outlet["outlet_id"]
        source_ids_of_outlet = [row.get("id") for row in (outlet.get("legacy_observed") or {}).get("sources") or []
                                if row.get("id") in source_by_id]
        channels = []
        for channel in outlet.get("channels", []):
            observed = channel.get("legacy_observed")
            feed = next((row for row in feeds if isinstance(observed, dict) and row["id"] == observed.get("id")), None)
            if feed is not None:
                channels.append(channel_record(feed, channel["channel_id"]))
            else:
                channels.append({"channel_id": channel.get("channel_id"), "legacy_feed_id": None,
                                 "kind": channel.get("kind"), "productivity_class": "NO_EVIDENCE",
                                 "productivity_evidence": {"basis": "channel_has_no_legacy_feed"}})
        held = {item["legacy_feed_id"] for item in channels}
        legacy_feed_rows = [feed for source_id in source_ids_of_outlet for feed in feeds_of_source.get(source_id, [])]
        for feed in legacy_feed_rows:
            if feed["id"] not in held:
                channels.append(channel_record(feed, None))
        article_part = merge_articles([articles.get(source_id, EMPTY_ARTICLES) for source_id in source_ids_of_outlet]
                                      or [EMPTY_ARTICLES])
        on_disk = {}
        for layer in LAYERS:
            directories = [item for source_id in source_ids_of_outlet
                           for item in disk_of_source.get(source_id, {}).get(layer, [])]
            firsts = [item["first_date"] for item in directories if item["first_date"]]
            lasts = [item["last_date"] for item in directories if item["last_date"]]
            on_disk[layer] = {
                "directories": directories,
                "files": sum(item["files"] for item in directories),
                "json_files": sum(item["json_files"] for item in directories),
                "bytes": sum(item["bytes"] for item in directories),
                "first_date_in_file_names": min(firsts) if firsts else None,
                "last_date_in_file_names": max(lasts) if lasts else None,
                "distinct_dates_in_file_names": sum(item["distinct_dates"] for item in directories)
                if len(directories) <= 1 else None,
            }
        feed_fail = {}
        for feed in legacy_feed_rows:
            bump(feed_fail, fail_category(feed["last_fail_reason"]))
        discovery_parts = [discovery_per_source[source_id] for source_id in source_ids_of_outlet
                           if source_id in discovery_per_source]
        crawl_parts = [crawl_per_source[source_id] for source_id in source_ids_of_outlet if source_id in crawl_per_source]
        class_counts = {name: 0 for name in CHANNEL_CLASSES}
        for item in channels:
            class_counts[item["productivity_class"]] += 1
        records[outlet_id] = {
            "country_id": outlet.get("country_id"),
            "registration_status": outlet.get("registration_status"),
            "web_origins": outlet.get("web_origins", []),
            "legacy_sources": [
                {"id": source_by_id[source_id]["id"], "country_code": source_by_id[source_id]["country_code"],
                 "newspaper_code": source_by_id[source_id]["newspaper_code"], "name": source_by_id[source_id]["name"],
                 "base_url": source_by_id[source_id]["base_url"], "is_active": source_by_id[source_id]["is_active"],
                 "legal_basis": source_by_id[source_id]["legal_basis"], "created_at": source_by_id[source_id]["created_at"]}
                for source_id in source_ids_of_outlet
            ],
            "mapping_findings": sorted(
                {item["kind"] for item in discrepancies + notes
                 if item.get("outlet_id") == outlet_id
                 or (item.get("channel_id") or "").startswith(outlet_id + ":")
                 or (item.get("registry_channel_id") or "").startswith(outlet_id + ":")}),
            "channels": channels,
            "channel_counts": {
                "legacy_feed_rows": len(legacy_feed_rows),
                "registry_channels": len(outlet.get("channels", [])),
                "is_active": sum(1 for feed in legacy_feed_rows if feed["is_active"]),
                "crawl_eligible_at_snapshot": sum(1 for item in channels if item.get("legacy_crawl_eligible_at_snapshot")),
                "with_last_success_at": sum(1 for feed in legacy_feed_rows if feed["last_success_at"] is not None),
                "by_kind": {kind: sum(1 for item in channels if item.get("kind") == kind)
                            for kind in sorted({item.get("kind") for item in channels})},
                "by_legacy_status": {status: sum(1 for feed in legacy_feed_rows if feed["status"] == status)
                                     for status in sorted({feed["status"] for feed in legacy_feed_rows})},
                "by_productivity_class": class_counts,
            },
            "articles_in_database": article_part,
            "annotation_state": (annotation_of_source.get(source_ids_of_outlet[0]) if len(source_ids_of_outlet) == 1 else None)
            if annotation is not None else "NOT_MEASURED",
            "on_disk": on_disk,
            "date_spans": {
                "database_fetched_at": [article_part["first_fetched_at"], article_part["last_fetched_at"]],
                "database_ok_fetch_days": [article_part["first_ok_fetch_day"], article_part["last_ok_fetch_day"]],
                "database_ok_date_published": [article_part["ok_date_published_first"], article_part["ok_date_published_last"]],
                **{layer + "_file_names": [on_disk[layer]["first_date_in_file_names"], on_disk[layer]["last_date_in_file_names"]]
                   for layer in LAYERS},
            },
            "crawl_runs": crawl_parts[0] if len(crawl_parts) == 1 else (crawl_parts or None),
            "discovery_runs": discovery_parts[0] if len(discovery_parts) == 1 else (discovery_parts or None),
            "error_categories": {
                "feed_last_fail_reason": feed_fail,
                "feed_error_message_set": sum(1 for feed in legacy_feed_rows if feed["error_message"] is not None),
                "discovery_runs": _sum_counters([part["by_category"] for part in discovery_parts]),
                "crawl_source_results": _sum_counters([part["result_status"] for part in crawl_parts]),
                "crawl_source_timeouts": sum(part["source_timeouts"] for part in crawl_parts),
                "article_status": dict(article_part["by_status"]),
            },
            "outlet_class": classify_outlet(len(legacy_feed_rows), article_part),
        }

    unmapped_legacy = {
        "sources": [source for source in sources if not outlets_of_source.get(source["id"])],
        "feeds": [channel_record(feed, None) for feed in feeds if not outlets_of_source.get(feed["source_id"])],
        "directories": unmapped_directories,
        "annotation_state_directories": annotation_unmapped,
    }

    # -- totals ----------------------------------------------------------------------------------
    def by_country(items) -> dict:
        table: dict[str, dict] = {}
        for country_id, klass in items:
            bump(table.setdefault(country_id, {}), klass)
            bump(table.setdefault("ALL", {}), klass)
        return table

    channel_items = [(record["country_id"], channel["productivity_class"])
                     for record in records.values() for channel in record["channels"]]
    basis_counts: dict[str, int] = {}
    for record in records.values():
        for channel in record["channels"]:
            bump(basis_counts, channel["productivity_evidence"]["basis"])
    fail_counts: dict[str, int] = {}
    fail_verbatim: dict[str, int] = {}
    for feed in feeds:
        bump(fail_counts, fail_category(feed["last_fail_reason"]))
        reason = feed["last_fail_reason"]
        bump(fail_verbatim, "<null>" if reason is None else re.sub(r"for source \S+$", "for source <code>", reason))

    def outlets_where(test) -> list[str]:
        return sorted(outlet_id for outlet_id, record in records.items() if test(record))

    no_feed = outlets_where(lambda record: record["channel_counts"]["legacy_feed_rows"] == 0)
    no_active = outlets_where(lambda record: record["channel_counts"]["is_active"] == 0)
    no_eligible = outlets_where(lambda record: record["channel_counts"]["crawl_eligible_at_snapshot"] == 0)
    no_success = outlets_where(lambda record: record["channel_counts"]["with_last_success_at"] == 0)
    with_raw = outlets_where(lambda record: record["on_disk"]["json_raw"]["json_files"] > 0)
    with_ok = outlets_where(lambda record: record["articles_in_database"]["ok_rows"] > 0)
    with_rows = outlets_where(lambda record: record["articles_in_database"]["rows"] > 0)
    remeasured = {
        "newspapers_without_active_feed": {
            "legacy_sources_total": len(sources),
            "A_sources_without_any_feed_row": sum(1 for source in sources if not feeds_of_source.get(source["id"])),
            "B_sources_without_feed_row_with_is_active_1": sum(
                1 for source in sources if not any(feed["is_active"] for feed in feeds_of_source.get(source["id"], []))),
            "C_sources_without_crawl_eligible_feed": sum(
                1 for source in sources if not any(
                    feed["is_active"] and feed["status"] == "active"
                    and (feed["feed_score"] or 0) >= LEGACY_CRAWL_MIN_SCORE and feed["type"] != "sitemap_index"
                    for feed in feeds_of_source.get(source["id"], []))),
            "D_sources_without_feed_row_with_last_success_at": sum(
                1 for source in sources
                if not any(feed["last_success_at"] is not None for feed in feeds_of_source.get(source["id"], []))),
            "definition": "A-D count rows of the legacy sources table by the state of their feed rows at the "
            "snapshot. B is the reading 'no feed with is_active = 1'. B includes A. None of them counts "
            "outlets without articles or without files.",
            "outlets_A": no_feed, "outlets_B": no_active, "outlets_C": no_eligible, "outlets_D": no_success,
        },
        "outlet_directories_with_json_raw_material": {
            "json_raw_outlet_directories_with_json_files": layer_totals["json_raw"]["outlet_directories_with_json_files"],
            "of_these_mapped_to_a_legacy_source": layer_totals["json_raw"]["outlet_directories_with_json_files"]
            - sum(1 for item in unmapped_directories if item["path"].startswith("json_raw/") and item["json_files"] > 0),
            "distinct_registry_outlets_with_json_raw_files": len(with_raw),
            "unmapped_directories": layer_totals["json_raw"]["unmapped_directories"],
            "definition": "directories <COUNTRY>/<slug> under json_raw that hold at least one *.json file, by "
            "listing. A directory is not an outlet: two directories can belong to one outlet and a "
            "directory can match no legacy source.",
            "outlets": with_raw,
        },
        "cross": {
            "outlets_without_is_active_feed_and_with_json_raw_files": sorted(set(no_active) & set(with_raw)),
            "outlets_with_is_active_feed_and_without_json_raw_files": sorted(set(records) - set(no_active) - set(with_raw)),
            "outlets_with_ok_rows_and_without_json_raw_files": sorted(set(with_ok) - set(with_raw)),
            "outlets_with_json_raw_files_and_without_ok_rows": sorted(set(with_raw) - set(with_ok)),
            "outlets_with_article_rows": len(with_rows),
            "outlets_with_ok_article_rows": len(with_ok),
            "note": "the two figures answer different questions (feed state at the snapshot vs. files left by "
            "past exports) and must not be equated or subtracted from one another",
        },
    }

    totals = {
        "legacy_sources": len(sources), "legacy_feeds": len(feeds), "registry_outlets": len(outlets),
        "registry_channels": sum(len(outlet.get("channels", [])) for outlet in outlets),
        "registry_outlets_by_registration_status": _count(outlet.get("registration_status") for outlet in outlets),
        "feeds_by_type": _count(feed["type"] for feed in feeds),
        "feeds_by_status": _count(feed["status"] for feed in feeds),
        "feeds_by_status_and_is_active": _count(f'{feed["status"]}|is_active={feed["is_active"]}' for feed in feeds),
        "feeds_by_discovered_by": _count(feed["discovered_by"] for feed in feeds),
        "feeds_by_last_status": _count(str(feed["last_status"]) for feed in feeds),
        "feeds_with_last_success_at": len(success_stamps),
        "feeds_with_last_crawled_at": sum(1 for feed in feeds if feed["last_crawled_at"] is not None),
        "feeds_with_error_message": sum(1 for feed in feeds if feed["error_message"] is not None),
        "feeds_with_last_error_at": sum(1 for feed in feeds if feed["last_error_at"] is not None),
        "feeds_with_consecutive_fail_runs_gt0": sum(1 for feed in feeds if (feed["consecutive_fail_runs"] or 0) > 0),
        "feeds_by_consecutive_empty_runs": _count(str(feed["consecutive_empty_runs"]) for feed in feeds),
        "channels_by_productivity_class_and_country": by_country(channel_items),
        "channels_by_productivity_basis": basis_counts,
        "outlets_by_class_and_country": by_country((record["country_id"], record["outlet_class"]) for record in records.values()),
        "feed_fail_categories": fail_counts,
        "feed_last_fail_reason_verbatim": fail_verbatim,
        "articles": article_totals,
        "crawl_runs": crawl_totals,
        "discovery_runs": discovery_totals,
        "on_disk_layers": layer_totals,
        "annotation_state": "NOT_MEASURED" if annotation is None else {
            "directories": len(annotation),
            "input_files": sum(item["input_files"] for item in annotation.values()),
            "article_count": sum(item["article_count"] for item in annotation.values()),
            "annotated_articles": sum(item["annotated_articles"] for item in annotation.values()),
        },
        "remeasured_audit_figures": remeasured,
        "import_discrepancies": len(discrepancies),
        "import_notes": len(notes),
    }

    return {
        "schema": SCHEMA,
        "inputs": inputs,
        "rules": {
            "feedback_era": {
                "first_last_success_at": first_success,
                "crawl_run_containing_it": first_run["id"] if first_run else None,
                "start": era_start,
                "meaning": "feeds.last_success_at is the only per-feed success record. Its earliest value bounds "
                "from above the moment the legacy crawl feedback began; a crawl before 'start' could not "
                "stamp a feed, so only crawls from 'start' on count as evidence for or against a feed.",
            },
            "channel_class_order": [
                "last_success_at set, the only such feed of its source, source success on >= "
                f"{REPEATED_MIN_PRODUCTIVE_RUN_DAYS} run days in the feedback era -> PRODUCTIVE_REPEATED",
                "last_success_at set -> PRODUCTIVE_ONCE_OR_SPORADIC",
                "last_crawled_at or last_attempt_at >= feedback era start -> NEVER_SUCCESSFUL",
                "type sitemap_index -> NO_EVIDENCE",
                "last_fail_reason set -> NEVER_SUCCESSFUL (discovery verdict only)",
                "otherwise -> NO_EVIDENCE",
            ],
            "channel_basis": CHANNEL_BASIS,
            "source_success_run": "a crawl run of the feedback era whose source_results_json lists the source with "
            "saved > 0; the run day is the date of crawl_runs.started_at",
            "outlet_class": {
                "LEGACY_PRODUCTIVE_REPEATED": f"articles rows with status 'ok' in crawl runs that each gave >= "
                f"{PRODUCTIVE_RUN_MIN_OK_ARTICLES} 'ok' rows for the outlet, on >= {REPEATED_MIN_PRODUCTIVE_RUN_DAYS} "
                "distinct days (day of the run's first 'ok' fetch for the outlet)",
                "LEGACY_PRODUCTIVE_SPORADIC": "at least one 'ok' row, but not the above",
                "LEGACY_NEVER_PRODUCTIVE": "feed rows or article rows exist, no 'ok' row",
                "LEGACY_NO_CHANNEL": "no feed row and no article row",
                "parameters": {"PRODUCTIVE_RUN_MIN_OK_ARTICLES": PRODUCTIVE_RUN_MIN_OK_ARTICLES,
                               "REPEATED_MIN_PRODUCTIVE_RUN_DAYS": REPEATED_MIN_PRODUCTIVE_RUN_DAYS},
                "note": "the two parameters are choices of this audit, not legacy values; the counts they are "
                "applied to are in every record, so another threshold can be applied without a re-run. "
                "'ok' is the legacy status for >= 100 extracted words. Repeated is not lasting: see "
                "last_ok_fetch_day.",
            },
            "legacy_crawl_eligible_at_snapshot": f"is_active = 1 and status = 'active' and feed_score >= "
            f"{LEGACY_CRAWL_MIN_SCORE} and type != 'sitemap_index' (the legacy crawl service's filter)",
            "on_disk": "names and sizes from a directory listing; no file opened. The date in a file name is the "
            "legacy date_published of the records in it, not a fetch date. 'backup' is listed for "
            "completeness; its directory names predate the ASCII slug migration.",
            "directory_mapping": "<COUNTRY>/<slug> equals (country_code, newspaper_code) of a legacy source, else "
            "its ASCII fold equals the ASCII fold of exactly one newspaper_code of that country, else unmapped",
            "kind_of_legacy_type": dict(KIND_OF_LEGACY_TYPE, **{"<anything else>": "unknown"}),
            "times": "all legacy stamps are naive datetime.utcnow() values, compared as strings",
        },
        "database_schema": schema,
        "outlets": records,
        "registered_outlets": registered_report,
        "unmapped_legacy": unmapped_legacy,
        "totals": totals,
        "import_comparison": {
            "compared": {
                "source_rows_all_columns": len(sources), "feed_rows_all_columns": len(feeds),
                "checks": ["every legacy source in exactly one outlet", "every outlet row equals the database row",
                           "country mapping (when --country-codes is given)", "country_id equals the id prefix",
                           "legacy name in display_names", "origin of base_url in web_origins",
                           "(country_code, newspaper_code) in legacy_aliases", "outlet slug vs newspaper_code",
                           "every legacy feed in exactly one channel of the outlet of its source",
                           "every channel legacy_observed equals the database row",
                           "channel kind vs legacy type", "url_history equals [legacy url]",
                           "channel_id vs the id the importer derives", "import and registration reports (when given)"],
            },
        },
        "import_discrepancies": discrepancies,
        "import_notes": notes,
    }


def _sum_counters(counters: list[dict]) -> dict:
    total: dict = {}
    for counter in counters:
        for key, value in counter.items():
            bump(total, key, value)
    return total


def _count(values) -> dict:
    total: dict = {}
    for value in values:
        bump(total, value)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-copy", type=Path, required=True,
                        help="a copy of the legacy SQLite file (with its -wal sibling), outside the legacy tree")
    parser.add_argument("--legacy-root", type=Path, required=True, help="the legacy tree; only listed, never written")
    parser.add_argument("--registry", type=Path, required=True, help="the outlet registry JSON")
    parser.add_argument("--out", type=Path, required=True, help="the JSON document to write (outside the legacy tree)")
    parser.add_argument("--country-codes", type=Path, help="optional: legacy country-code table, to check the mapping")
    parser.add_argument("--import-report", type=Path, help="optional: the legacy registry import report, to cross-check")
    parser.add_argument("--registration-report", type=Path, help="optional: a registration report with channel_ids renames")
    parser.add_argument("--annotation-state-copy", type=Path,
                        help="optional: a copy of the legacy annotation state SQLite file, outside the legacy tree")
    arguments = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        document = build(arguments)
    except AuditError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    payload = (json.dumps(document, sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    with open(arguments.out, "wb") as handle:
        handle.write(payload)
    totals = document["totals"]
    print(json.dumps({
        "schema": SCHEMA, "out_sha256": hashlib.sha256(payload).hexdigest(), "out_bytes": len(payload),
        "legacy_sources": totals["legacy_sources"], "legacy_feeds": totals["legacy_feeds"],
        "import_discrepancies": totals["import_discrepancies"], "import_notes": totals["import_notes"],
        "channels_by_class": totals["channels_by_productivity_class_and_country"].get("ALL", {}),
        "outlets_by_class": totals["outlets_by_class_and_country"].get("ALL", {}),
    }, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
