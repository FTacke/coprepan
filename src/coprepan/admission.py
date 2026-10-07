"""Technical admission labels (CPD-0007 §1; ``docs/architecture/TARGET_ARCHITECTURE.md`` §7).

**Label, do not delete.** A fetched item that is an error page, a PDF, an empty body or a redirect
answer is not removed from anything: it gets a label that says what it technically is, with the
reason, the evidence and the rule version. Whether a labelled document enters a release is decided
by a release view, never here.

These labels are **technical and deterministic**. They state facts that follow from recorded
values — an HTTP status, an extraction outcome, a count — and nothing else. They are not:

* a judgement that a page *is an article* (that needs content, and a validated rule);
* genre, register, section, opinion or any linguistic quality — separate enrichment layers;
* a threshold. No length, age or share is tested here; the measured values are recorded as
  evidence, and a release view applies whatever threshold it states.

One label record per (fetch, rule-set version). A new rule set writes new records beside the old.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import acquisition, core_pipeline, extraction, naming
from .canonical import sha256_bytes
from .document_identity import IdentityTables
from .exclusive import writes_workspace
from .jsonl import append_row, keyed, read_rows

LABEL_SCHEMA = naming.schema_id("admission-label", 1)
RULESET = "admission-technical/1"

# Technical status: does a usable extracted text of an item exist?
TECHNICALLY_USABLE = "TECHNICALLY_USABLE"
TECHNICALLY_UNUSABLE = "TECHNICALLY_UNUSABLE"
STATUSES = (TECHNICALLY_USABLE, TECHNICALLY_UNUSABLE)

BLOCKS, INFORMS = "blocks", "informs"
# Closed vocabulary of reasons, each with its effect on the technical status.
REASONS = {
    "http_error_status": BLOCKS,                 # the server answered 4xx or 5xx: what was preserved is an error page
    "http_redirect_answer": BLOCKS,              # a 3xx answer that was not followed
    "not_modified_answer": BLOCKS,               # a 304: no body of its own (see `revalidates`)
    "http_status_other": BLOCKS,                 # 1xx, or 2xx without content (204, 205)
    "not_extractable": BLOCKS,                   # the extraction record says why
    "no_document": BLOCKS,                       # no URL of the fetch lies on a registered origin
    "no_body_text": BLOCKS,                      # extracted, and no block has the role body
    "superseded_attempt": INFORMS,               # an earlier attempt of a request that was retried
    "no_title": INFORMS,
    "publication_date_unknown": INFORMS,
    "author_unknown": INFORMS,
    "section_unknown": INFORMS,
    "language_undeclared": INFORMS,
    "decoding_replaced_characters": INFORMS,
    "duplicate_body_of_other_document": INFORMS,
    "moved_from_other_document": INFORMS,
    "extractor_not_active": INFORMS,             # produced by an extractor that is not adopted
}


class AdmissionError(ValueError):
    """A label cannot be built from what was given."""


def label_fetch(
    fetch_record: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    extraction_record: Mapping[str, Any] | None,
    *,
    relations: list[Mapping[str, Any]] = (),
    extractor_lifecycle: str | None = None,
    later_attempt_exists: bool = False,
) -> dict[str, Any]:
    """The technical admission label of one item fetch. Pure: recorded values in, a label out.

    ``result`` is the identity-and-extraction result of the fetch (``None`` when the stage has not
    seen it), ``extraction_record`` the stored extraction, ``relations`` the document relations
    that name its document.
    """
    if fetch_record["fetch_kind"] != acquisition.FETCH_KIND_ITEM or fetch_record["outcome"] != acquisition.OUTCOME_FETCHED:
        raise AdmissionError("only a fetched item is labelled: a channel document, a robots file or a failed fetch is not a document")
    reasons: list[dict[str, Any]] = []

    def add(reason: str, **evidence: Any) -> None:
        reasons.append({"reason": reason, "effect": REASONS[reason], "evidence": evidence})

    status = fetch_record["response"]["status"]
    if status == 304:
        add("not_modified_answer", http_status=status, revalidates=fetch_record.get("revalidates"))
    elif 300 <= status < 400:
        add("http_redirect_answer", http_status=status, redirect_not_followed=fetch_record["response"]["redirect_not_followed"])
    elif status >= 400:
        add("http_error_status", http_status=status)
    elif not 200 <= status < 300 or status in (204, 205):
        add("http_status_other", http_status=status)
    if later_attempt_exists:
        add("superseded_attempt", attempt_number=fetch_record["attempt_number"], request_id=fetch_record["request_id"])

    document_id = version_id = None
    measurements: dict[str, Any] = {}
    if result is None or result.get("identity") != "assigned":
        add("no_document", identity=(result or {}).get("identity", "not_processed"))
    else:
        document_id, version_id = result["document_id"], result["document_version_id"]
    if extraction_record is not None:
        blocks = extraction_record["blocks"]
        body = extraction.body_text(blocks)
        measurements = {
            "blocks": len(blocks), "body_blocks": sum(1 for b in blocks if b["role"] == extraction.ROLE_BODY),
            "body_characters": len(body), "body_whitespace_tokens": len(body.split()),
            "non_body_blocks": sum(1 for b in blocks if b["role"] == extraction.ROLE_NON_BODY),
        }
        if extraction_record["outcome"] != extraction.OUTCOME_EXTRACTED:
            add("not_extractable", extraction_reason=extraction_record["reason"],
                declared_content_type=extraction_record["input"]["declared_content_type"])
        else:
            if not body:
                add("no_body_text", blocks=len(blocks))
            if not any(b["role"] == extraction.ROLE_TITLE for b in blocks) and extraction_record["metadata"]["title"]["value"] == extraction.UNKNOWN:
                add("no_title")
            for field, reason in (("publication_date", "publication_date_unknown"), ("author", "author_unknown"),
                                  ("section", "section_unknown"), ("language", "language_undeclared")):
                if extraction_record["metadata"][field]["value"] == extraction.UNKNOWN:
                    add(reason)
            if extraction_record["decoding"]["replaced_characters"]:
                add("decoding_replaced_characters", replaced=extraction_record["decoding"]["replaced_characters"],
                    charset=extraction_record["decoding"]["charset"], basis=extraction_record["decoding"]["basis"])
    for relation in relations:
        if relation["document_id"] == document_id and relation["relation"] == "duplicate_of":
            add("duplicate_body_of_other_document", target_document_id=relation["target_document_id"])
        if relation["target_document_id"] == document_id and relation["relation"] == "moved_to":
            add("moved_from_other_document", from_document_id=relation["document_id"])
    if extraction_record is not None and extractor_lifecycle != extraction.LIFECYCLE_ACTIVE:
        add("extractor_not_active", extractor=extraction_record["extractor"], lifecycle=extractor_lifecycle or extraction.UNKNOWN)

    blocking = [entry["reason"] for entry in reasons if entry["effect"] == BLOCKS]
    return {
        "fetch_id": fetch_record["fetch_id"], "run_id": fetch_record["run_id"], "outlet_id": fetch_record["outlet_id"],
        "document_id": document_id, "document_version_id": version_id,
        "technical_status": TECHNICALLY_UNUSABLE if blocking else TECHNICALLY_USABLE,
        "blocking_reasons": blocking, "reasons": reasons, "measurements": measurements,
        "ruleset": RULESET,
        "extraction_fingerprint": (result or {}).get("extraction_fingerprint"),
        "extraction_payload_sha256": sha256_bytes(extraction.record_json(dict(extraction_record))) if extraction_record is not None else None,
    }


class LabelTable:
    """Append-only admission labels of one workspace, one per (fetch, rule set)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.rows = keyed(read_rows(self.path, LABEL_SCHEMA), lambda row: (row["fetch_id"], row["ruleset"]), "admission labels")

    def add(self, label: Mapping[str, Any], labelled_at: str) -> bool:
        key = (label["fetch_id"], label["ruleset"])
        if key in self.rows:
            return False
        self.rows[key] = append_row(self.path, LABEL_SCHEMA, {**label, "labelled_at": labelled_at})
        return True

    def of(self, fetch_id: str, ruleset: str | None = None) -> dict[str, Any] | None:
        return self.rows.get((fetch_id, ruleset or RULESET))


def label_table(workspace: core_pipeline.Workspace) -> LabelTable:
    return LabelTable(workspace.root / "admission" / "labels.jsonl")


@writes_workspace("admission labels")
def label_pack(workspace: core_pipeline.Workspace, *, preservation_root: Path, identifier: str,
               results: list[Mapping[str, Any]], extractor: extraction.Extractor, labelled_at: str) -> list[dict[str, Any]]:
    """Label every fetched item of a preserved pack from the stored records. Idempotent.

    Reads the preserved fetch records and the stored extractions; decides nothing that is not in
    them.
    """
    preserved = core_pipeline.open_preserved_pack(preservation_root, identifier)
    store, tables, table = workspace.layer_store(), IdentityTables(workspace.identity), label_table(workspace)
    by_fetch = {result["fetch_id"]: result for result in results}
    records = {fetch_id: preserved.fetch_record(fetch_id) for fetch_id, entry in preserved.entries.items() if entry.body_sha256 is not None}
    attempts: dict[str, int] = {}
    for record in records.values():
        if record["request_id"] != "not_applicable":
            attempts[record["request_id"]] = max(attempts.get(record["request_id"], 0), record["attempt_number"])
    labels = []
    for fetch_id, record in records.items():
        if record["fetch_kind"] != acquisition.FETCH_KIND_ITEM:
            continue
        result = by_fetch.get(fetch_id)
        stored = None
        if result and result.get("extraction_fingerprint"):
            stored = json.loads(store.read(extraction.STAGE, result["extraction_fingerprint"]).decode("utf-8"))
        label = label_fetch(record, result, stored, relations=tables.relations, extractor_lifecycle=extractor.lifecycle,
                            later_attempt_exists=record["attempt_number"] < attempts.get(record["request_id"], 0))
        table.add(label, labelled_at)
        labels.append(table.of(fetch_id, label["ruleset"]))
    return labels
