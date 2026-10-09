"""Amend the registration of outlets that are already registered (gate O-11; CPD-0025).

A registration record is written once and says what an outlet was registered as. What a real run then
shows about a registered outlet — its articles live on a second origin, its addresses carry their
identity in the query — changes the registry by an **amendment**: a dated record beside the
registration records that names the outlet, what is added, the evidence and the authority. Nothing is
removed by an amendment: an origin may be added, never dropped or reordered; the URL rules get a new
version; channels may be added.

    python scripts/amend_registration.py --amendment <file> --approved-by "<name>" [--write]

Without ``--write`` it is a dry run. The amendment file (``coprepan-registry-amendment/v1``) becomes
the record, with the approval and the registry digests added.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import registry, registry_review  # noqa: E402
from coprepan.canonical import record_json, sha256_bytes  # noqa: E402

AMENDMENT_SCHEMA = "coprepan-registry-amendment/v1"
_ENTRY_KEYS = {"outlet_id", "reason", "add_web_origins", "url_rules", "add_channels", "evidence"}


class AmendmentError(ValueError):
    """The amendment cannot be applied to this registry as it stands."""


def apply(amendment: Mapping[str, Any], registry_document: Mapping[str, Any], *, approved_by: str, approved_on: str) -> dict[str, Any]:
    """Pure: the registry after the amendment, validated, and the record. Raises instead of guessing."""
    if amendment.get("schema") != AMENDMENT_SCHEMA or amendment.get("gate") != "O-11" or not amendment.get("amendments"):
        raise AmendmentError(f"not a {AMENDMENT_SCHEMA} for gate O-11 with at least one amendment")
    if not approved_by.strip():
        raise AmendmentError("an amendment names who approved it")
    new_registry = copy.deepcopy(dict(registry_document))
    outlets = {outlet["outlet_id"]: outlet for outlet in new_registry["outlets"]}
    seen = set()
    for entry in amendment["amendments"]:
        if set(entry) != _ENTRY_KEYS:
            raise AmendmentError(f"an amendment entry has exactly {sorted(_ENTRY_KEYS)}")
        identifier = entry["outlet_id"]
        outlet = outlets.get(identifier)
        if outlet is None or outlet["registration_status"] != "registered" or identifier in seen:
            raise AmendmentError(f"{identifier}: an amendment is for a registered outlet, once per record")
        seen.add(identifier)
        if not entry["reason"] or not entry["evidence"] or not all(item.get("claim") and item.get("how") and item.get("source") for item in entry["evidence"]):
            raise AmendmentError(f"{identifier}: an amendment states its reason and its evidence (claim, how, source)")
        if not (entry["add_web_origins"] or entry["url_rules"] or entry["add_channels"]):
            raise AmendmentError(f"{identifier}: nothing is amended")
        for origin in entry["add_web_origins"]:
            if origin in outlet["web_origins"]:
                raise AmendmentError(f"{identifier}: {origin} is an origin already")
            holders = [other["outlet_id"] for other in new_registry["outlets"] if origin in other["web_origins"]]
            if holders:
                raise AmendmentError(f"{identifier}: {origin} is an origin of {holders}")
            outlet["web_origins"].append(origin)                     # added at the end: the canonical origin stays the first
        if entry["url_rules"]:
            rules = entry["url_rules"]
            if set(rules) != {"version", "significant_query_params", "basis"} or rules["version"] == outlet["url_rules"]["version"]:
                raise AmendmentError(f"{identifier}: new URL rules carry a new version, the significant query parameters and their basis")
            outlet["url_rules"] = {**outlet["url_rules"], "version": rules["version"], "significant_query_params": list(rules["significant_query_params"])}
        existing = {channel["channel_id"] for channel in outlet["channels"]}
        for channel in entry["add_channels"]:
            if channel["channel_id"] in existing or not channel["channel_id"].startswith(identifier + ":ch:"):
                raise AmendmentError(f"{channel['channel_id']}: a new channel of {identifier} with an id of its own")
            outlet["channels"].append({"channel_id": channel["channel_id"], "kind": channel["kind"], "legacy_observed": {},
                                       "url_history": [{"url": channel["url"], "valid_from": channel["valid_from"]}]})
            existing.add(channel["channel_id"])
    registry.validate_registry(new_registry)
    record = {**amendment, "reviewed_on": approved_on,
              "authority": f"reviewed and approved by {approved_by.strip()}; amendment {amendment['prepared_on']} prepared by an agent run (CPD-0025)",
              "registry_sha256_before": sha256_bytes(record_json(dict(registry_document))),
              "registry_sha256_after": sha256_bytes(record_json(new_registry))}
    return {"registry": new_registry, "record": record}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--repository", type=Path, default=REPOSITORY)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args(argv)
    config = arguments.repository / "config"
    amendment = json.loads(arguments.amendment.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    result = apply(amendment, json.loads((config / "outlet_registry.json").read_text(encoding="utf-8")), approved_by=arguments.approved_by, approved_on=today)
    record_path = config / "registry_review" / f"{amendment['record_stem']}_amendment_{today}.json"
    if arguments.write:
        if record_path.exists():
            raise AmendmentError(f"{record_path.name} exists: an amendment record is written once")
        (config / "outlet_registry.json").write_bytes(record_json(result["registry"]))
        record_path.write_bytes(record_json(result["record"]))
        registry_review.write_package(config / "outlet_registry.json", config / "registry_review" / "outlet_review_package.json",
                                      arguments.repository / "docs" / "corpus_supply" / "REGISTRY_REVIEW_PACKAGE.md")
    print(json.dumps({"amended": [entry["outlet_id"] for entry in amendment["amendments"]], "record": record_path.name, "written": bool(arguments.write)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
