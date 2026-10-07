"""Candidate qualification: between "a channel listed this URL" and "plan a fetch" (CPD-0007 §2).

```text
discovered candidate → qualification (QUALIFIED | REJECTED | DEFERRED, with reasons) → fetch intent
```

Discovery records everything a channel lists; an HTML listing lists its navigation too. This
layer decides which candidates are worth a request. It **deletes nothing**: the discovery event
and the candidate stay as they are, and the decision is a separate, append-only row that names
the rule set that made it. A new rule-set version is a new row; the old decision stays on record.

Rules are about the URL only — never about content, never about what an outlet "usually" does:

* a **generic** rule set, versioned here, for what is structurally not an article page (assets,
  binary documents, the site root, the channel documents themselves);
* optional **outlet** rules from ``config/candidate_rules.json``, set by review per outlet.
  None exists yet: the legacy system had no per-outlet URL rule that could be carried over.

When an outlet's allow rule and any reject rule both match, the decision is ``DEFERRED`` with both
on record — a conflict is a question for a reviewer, not something to resolve by rule order.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from . import naming
from .jsonl import append_row, read_rows
from .storage_roots import CHECKOUT

QUALIFICATION_SCHEMA = naming.schema_id("candidate-qualification", 1)
RULES_SCHEMA = naming.schema_id("candidate-rules", 1)
GENERIC_RULESET = "candidate-filter-generic/1"
DEFAULT_RULES_FILE = CHECKOUT / "config" / "candidate_rules.json"

QUALIFIED, REJECTED, DEFERRED = "QUALIFIED", "REJECTED", "DEFERRED"
DECISIONS = (QUALIFIED, REJECTED, DEFERRED)

_ASSETS = ("jpg", "jpeg", "png", "gif", "webp", "svg", "ico", "bmp", "avif", "css", "js", "mjs", "json", "map",
           "woff", "woff2", "ttf", "otf", "eot", "mp3", "mp4", "m4a", "m4v", "ogg", "wav", "webm", "mov", "avi",
           "zip", "gz", "rar", "7z", "tar", "exe", "apk", "dmg")
_BINARY_DOCUMENTS = ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "epub", "odt")
_CHANNEL_DOCUMENTS = ("xml", "rss", "atom", "rdf")
_OUTLET_KEYS = {"version", "reject_path_prefixes", "reject_path_patterns", "allow_path_patterns"}


class CandidateRulesError(ValueError):
    """The candidate rules are not rules this layer can apply."""


def load_rules(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The per-outlet rules by ``outlet_id``. An outlet without an entry has generic rules only."""
    try:
        document = json.loads(Path(path or DEFAULT_RULES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CandidateRulesError(f"candidate rules are not readable: {error}") from error
    if not isinstance(document, dict) or document.get("schema") != RULES_SCHEMA or not isinstance(document.get("outlets"), dict):
        raise CandidateRulesError(f"candidate rules have the schema {RULES_SCHEMA} and an 'outlets' object")
    for outlet_id, rules in document["outlets"].items():
        validate_outlet_rules(outlet_id, rules)
    return document["outlets"]


def validate_outlet_rules(outlet_id: str, rules: Any) -> None:
    if not naming.is_outlet_id(outlet_id) or not isinstance(rules, dict) or set(rules) != _OUTLET_KEYS:
        raise CandidateRulesError(f"{outlet_id}: outlet rules have exactly {sorted(_OUTLET_KEYS)}")
    if not isinstance(rules["version"], str) or not rules["version"]:
        raise CandidateRulesError(f"{outlet_id}: outlet rules carry a version")
    for prefix in rules["reject_path_prefixes"]:
        if not isinstance(prefix, str) or not prefix.startswith("/"):
            raise CandidateRulesError(f"{outlet_id}: a path prefix starts with '/': {prefix!r}")
    for key in ("reject_path_patterns", "allow_path_patterns"):
        for pattern in rules[key]:
            try:
                re.compile(pattern)
            except (re.error, TypeError) as error:
                raise CandidateRulesError(f"{outlet_id}: {key} holds an invalid pattern {pattern!r}: {error}") from error


def ruleset_id(outlet_rules: Mapping[str, Any] | None) -> str:
    return f"{GENERIC_RULESET}+{outlet_rules['version'] if outlet_rules else 'no-outlet-rules'}"


def qualify(candidate: Mapping[str, Any], *, outlet_rules: Mapping[str, Any] | None = None,
            channel_url_keys: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Decide one candidate. Pure: the same candidate under the same rules gives the same row."""
    parts = urlsplit(candidate["url_key"])
    path = parts.path or "/"
    extension = path.rsplit("/", 1)[-1].rpartition(".")[2].lower() if "." in path.rsplit("/", 1)[-1] else ""
    rejections: list[str] = []
    if path == "/" and not parts.query:
        rejections.append("generic: site_root_is_not_an_item")
    if extension in _ASSETS:
        rejections.append(f"generic: asset_extension .{extension}")
    if extension in _BINARY_DOCUMENTS:
        rejections.append(f"generic: binary_document_out_of_scope .{extension}")
    if extension in _CHANNEL_DOCUMENTS:
        rejections.append(f"generic: channel_document_extension .{extension}")
    if candidate["url_key"] in channel_url_keys:
        rejections.append("generic: is_a_registered_channel_document")

    allowed_by: list[str] = []
    if outlet_rules:
        rejections += [f"outlet: path_prefix {prefix}" for prefix in outlet_rules["reject_path_prefixes"]
                       if path == prefix or path.startswith(prefix.rstrip("/") + "/")]
        rejections += [f"outlet: path_pattern {pattern}" for pattern in outlet_rules["reject_path_patterns"] if re.search(pattern, path)]
        allowed_by = [f"outlet: allow_pattern {pattern}" for pattern in outlet_rules["allow_path_patterns"] if re.search(pattern, path)]
        if outlet_rules["allow_path_patterns"] and not allowed_by:
            rejections.append("outlet: not_matched_by_any_allow_pattern")

    if rejections and allowed_by:
        decision, reasons = DEFERRED, ["conflicting_rules", *allowed_by, *rejections]
    elif rejections:
        decision, reasons = REJECTED, rejections
    else:
        decision, reasons = QUALIFIED, allowed_by or ["no_rule_rejects"]
    return {
        "candidate_id": candidate["candidate_id"], "outlet_id": candidate["outlet_id"], "url_key": candidate["url_key"],
        "decision": decision, "reasons": reasons, "ruleset": ruleset_id(outlet_rules),
        "evidence": {"path": path, "extension": extension or None, "has_query": bool(parts.query)},
    }


class QualificationTable:
    """Append-only qualification decisions of one workspace, keyed by candidate and rule set."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.rows = {(row["candidate_id"], row["ruleset"]): row for row in read_rows(self.path, QUALIFICATION_SCHEMA)}

    def decide(self, candidate: Mapping[str, Any], *, outlet_rules: Mapping[str, Any] | None,
               channel_url_keys: frozenset[str], run_id: str, decided_at: str) -> dict[str, Any]:
        """The decision for a candidate under the current rules; recorded once per rule set."""
        key = (candidate["candidate_id"], ruleset_id(outlet_rules))
        if key not in self.rows:
            row = qualify(candidate, outlet_rules=outlet_rules, channel_url_keys=channel_url_keys)
            self.rows[key] = append_row(self.path, QUALIFICATION_SCHEMA, {**row, "run_id": run_id, "decided_at": decided_at})
        return self.rows[key]

    def history(self, candidate_id: str) -> list[dict[str, Any]]:
        return [row for (identifier, _), row in self.rows.items() if identifier == candidate_id]
