"""Offline replay of the first canary's preserved answers under the current code (2026-10-09, CPD-0019).

Reads the packs and the discovery tables of a runtime workspace — nothing else, and nothing is
written there — and reports what the repaired components make of the answers the canary of
2026-10-08 received: the robots files (F1), the access-control class of every answer (F2), the
channel documents (F4, F5), what the candidate budget turned away (F7), and which origins a next
canary would hold. No request is made; the output carries counts, digests and addresses, no content.

    python scripts/replay_canary_findings.py --workspace <RUNTIME root> --out <file.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coprepan import access_control, acquisition, canary_driver, core_pipeline, discovery, discovery_coverage, naming, pack, policy, robots  # noqa: E402
from coprepan.canonical import record_json, write_bytes_exclusive  # noqa: E402
from coprepan.extraction import ContentDecodingError, decode_content  # noqa: E402

REPLAY_SCHEMA = naming.schema_id("canary-findings-replay", 1)
PRODUCT_TOKEN_PLACEHOLDER = "*"   # the groups a file states for everyone; the crawler's own token is the registry's business


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    workspace = core_pipeline.Workspace(arguments.workspace)

    robots_files, answers, channel_documents = [], [], []
    for identifier in canary_driver.pack_ids(workspace):
        path = workspace.packs / f"{identifier}.warc.gz"
        for entry in pack.scan(path, identifier):
            record = pack.read_fetch_record(path, entry)
            if record["outcome"] != acquisition.OUTCOME_FETCHED:
                continue
            response = record["response"]
            headers = [(header[0], header[1]) for header in response["headers"]]
            body = pack.read_body(path, entry)
            coding = acquisition.content_encoding_of(headers)
            now = access_control.classify_response(response["status"], headers, body)
            if now != record["policy"]["access_class_observed"]:
                answers.append({"outlet_id": record["outlet_id"], "run_id": record["run_id"], "fetch_id": record["fetch_id"],
                                "url": response["final_url"], "status": response["status"], "body_sha256": record["body_sha256"],
                                "recorded_class": record["policy"]["access_class_observed"], "class_now": now,
                                "classifier_now": access_control.CLASSIFIER_VERSION})
            if record["fetch_kind"] == acquisition.FETCH_KIND_ROBOTS:
                as_received = robots.evidence_from_response(response["status"], body)
                decoded = robots.evidence_from_response(response["status"], body, coding)
                rules = decoded.rules
                robots_files.append({
                    "outlet_id": record["outlet_id"], "url": response["final_url"], "content_encoding": coding, "body_sha256": record["body_sha256"],
                    "parse_error_as_received": bool(as_received.rules and as_received.rules.parse_error),
                    "parse_error_now": bool(rules and rules.parse_error), "parser_now": robots.PARSER_VERSION,
                    "groups": {token: len(group) for token, group in (rules.groups.items() if rules else [])},
                    "sitemaps": list(rules.sitemaps) if rules else [], "crawl_delays": dict(rules.crawl_delays) if rules else {}})
            elif record["fetch_kind"] == acquisition.FETCH_KIND_CHANNEL_DOCUMENT and 200 <= response["status"] < 300:
                try:
                    parsed = discovery.parse_channel_document(decode_content(body, coding), document_url=response["final_url"],
                                                              declared_content_type=acquisition._content_type(headers))
                    outcome, kind, problems, entries = parsed.outcome, parsed.format, list(parsed.problems), parsed.entries
                except ContentDecodingError as error:
                    outcome, kind, problems, entries = "UNPARSEABLE", None, [error.reason], ()
                children = sorted((e for e in entries if e.relation == discovery.RELATION_CHILD_DOCUMENT and e.url), key=discovery.expansion_priority)
                channel_documents.append({
                    "outlet_id": record["outlet_id"], "channel_id": record["discovery"]["channel_id"], "url": response["final_url"],
                    "body_sha256": record["body_sha256"], "outcome_now": outcome, "format": kind, "problems": problems, "parser_now": discovery.PARSER_VERSION,
                    "item_entries": sum(1 for e in entries if e.relation == discovery.RELATION_ITEM),
                    "item_entries_with_url": sum(1 for e in entries if e.relation == discovery.RELATION_ITEM and e.url),
                    "child_documents": len(children), "expansion_order": discovery.EXPANSION_ORDER,
                    "first_children_in_read_order": [{"path": urlsplit(e.url).path, "lastmod": e.hints.get("lastmod")} for e in children[:5]]})

    # What the robots files, read correctly, say about the channel documents the canary would have asked for.
    robots_by_origin = {policy._origin(row["url"]): row for row in robots_files}
    tables = discovery.DiscoveryTables(workspace.root / "discovery")
    recorded_inputs = [{"channel_id": row["channel_id"], "document_url": row["document_url"], "outcome": row["outcome"], "problems": row["problems"],
                        "parser": row["parser"]} for row in tables.inputs]
    result = {
        "schema": REPLAY_SCHEMA,
        "what_this_is": "the preserved answers of the workspace read again by the current code; reproducibility of a repair, no new observation of any server",
        "robots_files": sorted(robots_files, key=lambda row: row["outlet_id"]),
        "robots_origins": sorted(origin for origin in robots_by_origin if origin),
        "answers_classified_differently_now": answers,
        "origins_held_for_a_next_canary": canary_driver.access_holds_from_evidence(workspace, reclassify=True),
        "origins_held_by_the_recorded_classes_alone": canary_driver.access_holds_from_evidence(workspace),
        "channel_documents": sorted(channel_documents, key=lambda row: (row["outlet_id"], row["url"])),
        "discovery_inputs_as_recorded": recorded_inputs,
        "discovery_coverage_as_recorded": discovery_coverage.coverage(tables),
        "candidates_by_outlet": {outlet: sum(1 for row in tables.candidates.values() if row["outlet_id"] == outlet)
                                 for outlet in sorted({row["outlet_id"] for row in tables.candidates.values()})},
    }
    write_bytes_exclusive(arguments.out, record_json(result))
    print(json.dumps({"out": arguments.out.name, "robots_files": len(robots_files), "reclassified": len(answers),
                      "channel_documents": len(channel_documents)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
