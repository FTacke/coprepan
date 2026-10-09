"""Offline: what the candidate budget of a pass keeps of a preserved channel document, in document
order (the behaviour up to channel-parser/2) and newest-first (candidate-budget-order/1, CPD-0020).

Reads the packs of a runtime workspace and nothing else; writes nothing there; makes no request.
The comparison is between two allotments of the same preserved listing — reproducibility of a
design choice on one document of one evening, not a statement about any other listing.

    python scripts/replay_candidate_budget.py --workspace <RUNTIME root> --budget 200 --out <file.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coprepan import acquisition, canary_driver, core_pipeline, discovery, naming, pack  # noqa: E402
from coprepan.canonical import record_json, write_bytes_exclusive  # noqa: E402
from coprepan.extraction import decode_content  # noqa: E402

SCHEMA = naming.schema_id("candidate-budget-replay", 1)


def allotment(entries, budget: int, newest_first: bool) -> dict:
    """The first address of every item entry competes once; ``budget`` of them are kept."""
    first: dict[str, discovery.ChannelEntry] = {}
    for entry in entries:
        if entry.relation == discovery.RELATION_ITEM and entry.url and entry.url not in first:
            first[entry.url] = entry

    def rank(entry):
        stated = discovery.entry_instant(entry.hints)
        return (0 if stated is not None else 1, -stated.timestamp() if stated is not None else 0.0, entry.position)

    order = sorted(first.values(), key=rank if newest_first else (lambda entry: entry.position))
    kept, away = order[:budget], order[budget:]
    kept_at = [at for at in (discovery.entry_instant(e.hints) for e in kept) if at]
    away_at = [at for at in (discovery.entry_instant(e.hints) for e in away) if at]
    return {"kept": len(kept), "turned_away": len(away),
            "kept_oldest": min(kept_at).isoformat() if kept_at else None, "kept_newest": max(kept_at).isoformat() if kept_at else None,
            "turned_away_oldest": min(away_at).isoformat() if away_at else None, "turned_away_newest": max(away_at).isoformat() if away_at else None,
            "turned_away_newer_than_oldest_kept": sum(1 for at in away_at if at > min(kept_at)) if kept_at and away_at else 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    workspace = core_pipeline.Workspace(arguments.workspace)
    documents = []
    for identifier in canary_driver.pack_ids(workspace):
        path = workspace.packs / f"{identifier}.warc.gz"
        for entry in pack.scan(path, identifier):
            record = pack.read_fetch_record(path, entry)
            response = record["response"]
            if record["fetch_kind"] != acquisition.FETCH_KIND_CHANNEL_DOCUMENT or record["outcome"] != acquisition.OUTCOME_FETCHED or not 200 <= response["status"] < 300:
                continue
            headers = [(header[0], header[1]) for header in response["headers"]]
            parsed = discovery.parse_channel_document(decode_content(pack.read_body(path, entry), acquisition.content_encoding_of(headers)),
                                                      document_url=response["final_url"], declared_content_type=acquisition._content_type(headers))
            items = [e for e in parsed.entries if e.relation == discovery.RELATION_ITEM and e.url]
            if len({e.url for e in items}) <= arguments.budget:
                continue                                     # within the budget: the order of allotment changes nothing
            documents.append({"outlet_id": record["outlet_id"], "channel_id": record["discovery"]["channel_id"], "url": response["final_url"],
                              "body_sha256": record["body_sha256"], "format": parsed.format, "item_entries": len(items),
                              "distinct_addresses": len({e.url for e in items}),
                              "dated_entries": sum(1 for e in items if discovery.entry_instant(e.hints) is not None),
                              "document_order": allotment(parsed.entries, arguments.budget, False),
                              "newest_first": allotment(parsed.entries, arguments.budget, True)})
    result = {"schema": SCHEMA, "budget": arguments.budget, "parser": discovery.PARSER_VERSION, "order": discovery.BUDGET_ORDER,
              "what_this_is": "two allotments of the same preserved listings, each from an empty candidate table; no request, no new observation",
              "documents_over_budget": sorted(documents, key=lambda row: (row["outlet_id"], row["url"]))}
    write_bytes_exclusive(arguments.out, record_json(result))
    print(json.dumps(result["documents_over_budget"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
