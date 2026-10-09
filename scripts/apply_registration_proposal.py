"""Apply a reviewed registration proposal to the registry (gate O-11; CPD-0013 §1, CPD-0019 §8).

A proposal (``coprepan-registry-registration-proposal/v1``) registers nothing. This script is the
operator's step after reviewing one: it checks the proposal against the registry it was written for,
builds the registry, the candidate rules, the policy's list of disabled channels and the registration
record that would result, validates all of them — and writes them only with ``--write``.

    python scripts/apply_registration_proposal.py --proposal <file> --approved-by "<name>" [--only <outlet_id> …] [--write]

Without ``--write`` it is a dry run that prints what would change. ``--only`` registers a subset: an
outlet the operator strikes from the proposal stays ``proposed``. No legacy channel is removed or
changed; a new channel has an empty ``legacy_observed``. After ``--write`` the registry review package
is regenerated, because it is derived from the registry.
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

from coprepan import candidate_filter, policy, registry, registry_review  # noqa: E402
from coprepan.canonical import record_json, sha256_bytes  # noqa: E402

PROPOSAL_SCHEMA = "coprepan-registry-registration-proposal/v1"
RECORD_SCHEMA = "coprepan-registry-registration/v1"


class ProposalError(ValueError):
    """The proposal cannot be applied to this registry as it stands."""


def apply(proposal: Mapping[str, Any], registry_document: Mapping[str, Any], rules_document: Mapping[str, Any],
          policy_document: Mapping[str, Any], *, approved_by: str, approved_on: str,
          only: list[str] | None = None) -> dict[str, Any]:
    """Pure: the four documents after the proposal, validated. Raises instead of guessing."""
    if proposal.get("schema") != PROPOSAL_SCHEMA or proposal.get("gate") != "O-11":
        raise ProposalError(f"not a {PROPOSAL_SCHEMA} for gate O-11")
    if not approved_by.strip():
        raise ProposalError("a registration names who approved it")
    before = sha256_bytes(record_json(registry_document))
    if proposal["inputs"]["registry_sha256_before"] != before:
        raise ProposalError("the registry is not the registry this proposal was written for")
    chosen = [entry for entry in proposal["proposed"] if only is None or entry["outlet_id"] in only]
    if only is not None and {entry["outlet_id"] for entry in chosen} != set(only):
        raise ProposalError("--only names an outlet the proposal does not hold")
    if not chosen:
        raise ProposalError("nothing to register")

    new_registry, new_rules, new_policy = copy.deepcopy(dict(registry_document)), copy.deepcopy(dict(rules_document)), copy.deepcopy(dict(policy_document))
    outlets = {outlet["outlet_id"]: outlet for outlet in new_registry["outlets"]}
    registered = []
    for entry in chosen:
        outlet = outlets.get(entry["outlet_id"])
        if outlet is None or outlet["registration_status"] != "proposed":
            raise ProposalError(f"{entry['outlet_id']}: not a proposed outlet of the registry")
        if entry["web_origins"][: len(outlet["web_origins"])] != outlet["web_origins"]:
            raise ProposalError(f"{entry['outlet_id']}: the proposal may add an origin, never drop or reorder one")
        existing = {channel["channel_id"] for channel in outlet["channels"]}
        for channel in entry["new_channels"]:
            if channel["channel_id"] in existing:
                raise ProposalError(f"{channel['channel_id']}: already a channel")
            outlet["channels"].append({"channel_id": channel["channel_id"], "kind": channel["kind"], "legacy_observed": {},
                                       "url_history": [{"url": channel["url"], "valid_from": channel["valid_from"]}]})
        by_id = {channel["channel_id"]: channel for channel in outlet["channels"]}
        if sorted(entry["channel_order"]) != sorted(by_id):
            raise ProposalError(f"{entry['outlet_id']}: channel_order names exactly the channels of the outlet")
        outlet["channels"] = [by_id[identifier] for identifier in entry["channel_order"]]
        for field in entry["attributes_left_unknown"]:
            if outlet[field] != "unknown":
                raise ProposalError(f"{entry['outlet_id']}: {field} is not unknown in the registry")
        outlet.update(entry["attributes_set"])
        outlet["web_origins"] = list(entry["web_origins"])
        outlet["url_rules"] = {"version": entry["url_rules"]["version"], "significant_query_params": [],
                               "strip_path_prefixes": [], "strip_path_suffixes": []}
        cleared, outlet["review_notes"] = list(outlet["review_notes"]), []
        outlet["registration_status"] = "registered"
        unknown_disabled = set(entry["channels_disabled_for_the_canary"]) - set(by_id)
        if unknown_disabled:
            raise ProposalError(f"{entry['outlet_id']}: disabled channels that are not channels: {sorted(unknown_disabled)}")
        new_policy["disabled_channels"] = sorted(set(new_policy["disabled_channels"]) | set(entry["channels_disabled_for_the_canary"]))
        if entry["outlet_id"] in proposal.get("candidate_rules", {}):
            new_rules["outlets"][entry["outlet_id"]] = proposal["candidate_rules"][entry["outlet_id"]]
        registered.append({
            "outlet_id": entry["outlet_id"], "display_name": entry["display_name"], "attributes_set": entry["attributes_set"],
            "attributes_left_unknown": entry["attributes_left_unknown"], "web_origins": entry["web_origins"],
            "url_rules": entry["url_rules"], "channel_ids": {identifier: identifier for identifier in entry["channel_order"]},
            "new_channels": entry["new_channels"], "channels_disabled_for_the_canary": entry["channels_disabled_for_the_canary"],
            "review_notes_cleared": cleared, "judgements_decided_by_the_reviewer": entry["judgements_for_the_reviewer"],
            "evidence": entry["evidence"]})
    if new_policy["disabled_channels"] != policy_document["disabled_channels"]:
        new_policy["policy_version"] = proposal["policy_version_after"]

    registry.validate_registry(new_registry)
    for outlet_id, rules in new_rules["outlets"].items():
        candidate_filter.validate_outlet_rules(outlet_id, rules)
    policy.validate_policy(new_policy)
    record = {
        "schema": RECORD_SCHEMA, "gate": "O-11", "reviewed_on": approved_on,
        "authority": f"reviewed and approved by {approved_by.strip()}; proposal {proposal['prepared_on']} prepared by an agent run (CPD-0019)",
        "scope": proposal["purpose"], "selection_rule": proposal["selection_rule"], "not_a_claim": proposal["not_a_claim"],
        "timezone_basis": proposal["timezone_basis"], "proposal_sha256": sha256_bytes(record_json(dict(proposal))),
        "deferred": {entry["outlet_id"]: "struck from the proposal by the reviewer" for entry in proposal["proposed"] if entry not in chosen},
        "registry_sha256_before": before, "registry_sha256_after": sha256_bytes(record_json(new_registry)), "registered": registered}
    return {"registry": new_registry, "candidate_rules": new_rules, "policy": new_policy, "record": record}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--approved-by", required=True, help="the person who reviewed the proposal")
    parser.add_argument("--only", action="append", help="register this outlet of the proposal only (repeatable)")
    parser.add_argument("--repository", type=Path, default=REPOSITORY)
    parser.add_argument("--write", action="store_true", help="write the registry, the rules, the policy and the registration record")
    arguments = parser.parse_args(argv)
    config = arguments.repository / "config"
    paths = {"registry": config / "outlet_registry.json", "candidate_rules": config / "candidate_rules.json", "policy": config / "acquisition_policy.json"}
    proposal = json.loads(arguments.proposal.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    result = apply(proposal, *(json.loads(paths[name].read_text(encoding="utf-8")) for name in ("registry", "candidate_rules", "policy")),
                   approved_by=arguments.approved_by, approved_on=today, only=arguments.only)
    record_path = config / "registry_review" / f"extended_canary_registration_{today}.json"
    summary = {"registered": [entry["outlet_id"] for entry in result["record"]["registered"]],
               "new_channels": sum(len(entry["new_channels"]) for entry in result["record"]["registered"]),
               "disabled_channels": result["policy"]["disabled_channels"], "policy_version": result["policy"]["policy_version"],
               "candidate_rules_for": sorted(result["candidate_rules"]["outlets"]), "record": record_path.name,
               "written": bool(arguments.write)}
    if arguments.write:
        if record_path.exists():
            raise ProposalError(f"{record_path.name} exists: a registration record is written once")
        paths["registry"].write_bytes(record_json(result["registry"]))
        for name in ("candidate_rules", "policy"):
            paths[name].write_bytes((json.dumps(result[name], indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        record_path.write_bytes(record_json(result["record"]))
        registry_review.write_package(paths["registry"], config / "registry_review" / "outlet_review_package.json",
                                      arguments.repository / "docs" / "corpus_supply" / "REGISTRY_REVIEW_PACKAGE.md")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
