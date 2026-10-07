"""The first real acquisition canary: a reviewable plan and a fail-closed preflight (CPD-0007 §9).

Two instruments for the moment the operator decisions are in. Neither makes a request, and
neither takes a decision:

* :func:`plan_canary` proposes a small, diverse set of *registered* outlets — different countries
  first, then different outlet types, then different channel kinds — and says why each one is in
  the set. It is a **proposal for review**. Diversity of metadata is all it can see; whether an
  outlet is a sensible first target is a judgement about the outlet, which it does not have.
* :func:`preflight` answers one question — *may the canary run now?* — by checking every
  precondition against what is on disk. It fails closed: any check it cannot make is a failed
  check. Storage capacity (O-4) is deliberately not a precondition: the canary is what produces
  the measurement O-4 needs.

``python -m coprepan.canary preflight`` exits non-zero until every check passes.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import crawler_identity, freeze, naming, policy, preservation_target, registry, schedule, storage_roots
from .canonical import canonical_json, sha256_bytes
from .identity import format_instant
from .storage_roots import CHECKOUT

PLAN_SCHEMA = naming.schema_id("canary-plan", 1)
PREFLIGHT_SCHEMA = naming.schema_id("canary-preflight", 1)
PASS, FAIL = "PASS", "FAIL"
READY, NOT_READY = "READY", "NOT_READY"


def plan_canary(registry_document: registry.Registry, *, outlets_wanted: int, seed: str) -> dict[str, Any]:
    """A reviewable selection of registered outlets for the canary. Pure and deterministic.

    Greedy: each pick maximises, in this order, a country not yet in the set, an outlet type not
    yet in the set, channel kinds not yet in the set; ties are broken by a hash of ``seed`` and
    the outlet id, so that no outlet is preferred for its place in the alphabet.
    """
    if outlets_wanted < 1 or not seed:
        raise ValueError("a canary plan needs a positive number of outlets and a seed")
    eligible, excluded = [], []
    for outlet_id, outlet in registry_document.outlets.items():
        problems = []
        if outlet["registration_status"] != "registered":
            problems.append("not registered")
        if not outlet["channels"]:
            problems.append("no channel")
        if not outlet["web_origins"]:
            problems.append("no web origin")
        if outlet["url_rules"]["version"] == "proposed":
            problems.append("URL rules are still the import's placeholder")
        if outlet["timezone"] == registry.UNKNOWN:
            problems.append("no time zone: its material could not be dated")
        (excluded if problems else eligible).append((outlet_id, problems))

    chosen: list[str] = []
    countries: set[str] = set()
    types: set[str] = set()
    kinds: set[str] = set()
    reasons: dict[str, list[str]] = {}
    remaining = [outlet_id for outlet_id, _ in eligible]
    while remaining and len(chosen) < outlets_wanted:
        def gain(outlet_id: str) -> tuple:
            outlet = registry_document.outlets[outlet_id]
            new_kinds = {c["kind"] for c in outlet["channels"]} - kinds
            return (outlet["country_id"] not in countries, outlet["outlet_type"] not in types, len(new_kinds),
                    sha256_bytes(f"{seed}|{outlet_id}".encode("utf-8")))
        best = max(remaining, key=gain)
        outlet = registry_document.outlets[best]
        why = []
        if outlet["country_id"] not in countries:
            why.append(f"adds country {outlet['country_id']}")
        if outlet["outlet_type"] not in types:
            why.append(f"adds outlet type {outlet['outlet_type']}")
        new_kinds = sorted({c["kind"] for c in outlet["channels"]} - kinds)
        if new_kinds:
            why.append(f"adds channel kind(s) {', '.join(new_kinds)}")
        reasons[best] = why or ["adds no new country, type or channel kind: chosen by the seeded tie-break only"]
        chosen.append(best)
        remaining = [outlet_id for outlet_id in remaining if outlet_id != best]
        countries.add(outlet["country_id"])
        types.add(outlet["outlet_type"])
        kinds |= {c["kind"] for c in outlet["channels"]}

    selection = []
    for outlet_id in chosen:
        outlet = registry_document.outlets[outlet_id]
        selection.append({
            "outlet_id": outlet_id, "display_name": outlet["display_names"][0]["name"], "country_id": outlet["country_id"],
            "outlet_type": outlet["outlet_type"], "access_model": outlet["access_model"], "timezone": outlet["timezone"],
            "web_origins": list(outlet["web_origins"]), "url_rules_version": outlet["url_rules"]["version"],
            "channels": [{"channel_id": c["channel_id"], "kind": c["kind"], "url": c["url_history"][-1]["url"]} for c in outlet["channels"]],
            "why_in_the_set": reasons[outlet_id],
        })
    plan = {
        "schema": PLAN_SCHEMA,
        "status": "PROPOSAL_FOR_REVIEW — chosen for diversity of registry metadata only; whether each outlet is a sensible first target is the reviewer's judgement",
        "seed": seed, "outlets_wanted": outlets_wanted, "outlets_selected": len(selection),
        "sufficient": len(selection) >= outlets_wanted,
        "diversity": {"countries": sorted(countries), "outlet_types": sorted(types), "channel_kinds": sorted(kinds)},
        "selection": selection,
        "not_selected_but_eligible": sorted(remaining),
        "not_eligible": {outlet_id: problems for outlet_id, problems in sorted(excluded)},
        "run_inputs": {
            "run_kind": "http_fetch",
            "to_be_set_by_the_operator": ["FetchLimits (timeout, redirects, body bytes, attempts, backoff)",
                                          "DiscoveryBudget (depth, documents, candidates, bytes)",
                                          "max_item_fetches per outlet", "use_robots_sitemaps"],
            "required_outputs": ["stored body bytes per fetch and fetches per outlet (the measurement O-4 needs)",
                                 "every fetch traceable to a preserved body", "a restore test of one pack"],
        },
    }
    plan["plan_sha256"] = sha256_bytes(canonical_json(plan))
    return plan


def preflight(
    *,
    outlet_ids: Sequence[str],
    tests_passed: int | None,
    tests_commit: str | None,
    code_commit: str,
    approved_baseline: Mapping[str, Any] | None,
    required_free_bytes: int | None,
    now: datetime,
    environment: Mapping[str, str] | None = None,
    repository: Path = CHECKOUT,
) -> dict[str, Any]:
    """May the real canary run? Every precondition checked against what is on disk; fail closed.

    ``approved_baseline`` is the baseline manifest the operator reviewed when approving the
    canary. The configuration on disk must still be the one it describes: any drift fails.
    """
    checks: list[dict[str, str]] = []

    def check(name: str, gate: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "gate": gate, "status": PASS if ok else FAIL, "detail": detail})

    config = repository / "config"
    # O-11 — the chosen outlets are registered and complete enough to be acquired for.
    try:
        registered = registry.load_registry(config / "outlet_registry.json")
        if not outlet_ids:
            check("outlets_chosen", "O-11", False, "no outlet was named for the canary")
        for outlet_id in outlet_ids:
            try:
                outlet = registered.resolve(outlet_id)
                problems = [text for text, bad in (("no channel", not outlet["channels"]),
                                                   ("URL rules are a placeholder", outlet["url_rules"]["version"] == "proposed"),
                                                   ("no time zone", outlet["timezone"] == registry.UNKNOWN)) if bad]
                check(f"outlet_registered:{outlet_id}", "O-11", not problems, "; ".join(problems) or "registered, with channels, URL rules and time zone")
            except registry.UnregisteredOutlet as refusal:
                check(f"outlet_registered:{outlet_id}", "O-11", False, str(refusal))
    except registry.RegistryError as error:
        check("registry_readable", "O-11", False, str(error))

    # O-1 — the acquisition policy and the schedule policy are decided.
    try:
        decided = policy.load_policy(config / "acquisition_policy.json")
        ok = decided["status"] == policy.STATUS_DECIDED and decided["external_acquisition"] == "enabled"
        check("acquisition_policy_decided", "O-1", ok, f"status {decided['status']}, external acquisition {decided['external_acquisition']}, version {decided['policy_version']}")
    except policy.PolicyError as error:
        check("acquisition_policy_decided", "O-1", False, str(error))
    try:
        decided_schedule = schedule.load_schedule_policy(config / "schedule_policy.json")
        check("schedule_policy_decided", "O-1", True, f"version {decided_schedule.version}")
    except schedule.ScheduleNotDecided as refusal:
        check("schedule_policy_decided", "O-1", False, str(refusal))

    # O-2 — the crawler identity is complete.
    try:
        identity = crawler_identity.load_identity(config / "crawler_identity.json")
        check("crawler_identity_configured", "O-2", True, identity.user_agent)
    except crawler_identity.CrawlerIdentityNotConfigured as refusal:
        check("crawler_identity_configured", "O-2", False, str(refusal))

    # O-3 — a preservation target is configured, taken into service and READY.
    target_report: dict[str, Any] | None = None
    try:
        root = storage_roots.resolve_root("PRESERVATION", env=os.environ if environment is None else environment)
        if required_free_bytes is None:
            check("preservation_target_ready", "O-3", False, "no required free space was stated")
        else:
            target_report = preservation_target.check_readiness(root, required_free_bytes=required_free_bytes, now=now)
            failed = [c["check"] for c in target_report["checks"] if c["status"] == preservation_target.FAIL]
            check("preservation_target_ready", "O-3", target_report["status"] == preservation_target.READY,
                  f"target {target_report['target_id']}: {target_report['status']}" + (f" (failed: {', '.join(failed)})" if failed else ""))
    except storage_roots.StorageRefusal as refusal:
        check("preservation_target_ready", "O-3", False, str(refusal))
    try:
        storage_roots.resolve_root("RUNTIME", env=os.environ if environment is None else environment)
        check("runtime_workspace_configured", "O-3", True, "COPREPAN_WORKSPACE_ROOT resolves and is writable")
    except storage_roots.StorageRefusal as refusal:
        check("runtime_workspace_configured", "O-3", False, str(refusal))

    # Tests — the full suite passed on exactly this commit.
    check("tests_green_on_this_commit", "engineering",
          bool(tests_passed) and tests_commit == code_commit,
          f"{tests_passed} passed on {tests_commit}; code is at {code_commit}" if tests_passed else "no test result was supplied")

    # Drift — the configuration is still the one the operator approved.
    if approved_baseline is None:
        check("no_configuration_drift", "canary_approval", False, "no approved baseline manifest was supplied")
    elif not freeze.verify_manifest(approved_baseline):
        check("no_configuration_drift", "canary_approval", False, "the approved baseline does not match its own digest")
    else:
        current = freeze.build_manifest(code_commit=code_commit, created_at=now, operator="preflight",
                                        test_baseline={}, storage_target=target_report, repository=repository)
        drift = [name for name in ("registry", "policy", "crawler_identity", "schedule_policy", "candidate_rules")
                 if current[name]["sha256"] != approved_baseline.get(name, {}).get("sha256")]
        drift += [name for name in ("decisions", "schemas", "components") if current[name] != approved_baseline.get(name)]
        if approved_baseline["code"]["commit"] != code_commit:
            drift.append("code commit")
        check("no_configuration_drift", "canary_approval", not drift, "unchanged since approval" if not drift else "changed since approval: " + ", ".join(drift))

    report = {
        "schema": PREFLIGHT_SCHEMA, "checked_at": format_instant(now), "code_commit": code_commit,
        "outlet_ids": list(outlet_ids), "status": READY if checks and all(c["status"] == PASS for c in checks) else NOT_READY,
        "open_by_gate": dict(sorted(Counter(c["gate"] for c in checks if c["status"] == FAIL).items())),
        "checks": checks,
        "not_a_precondition": "O-4 (storage capacity): the canary is what measures it",
        "note": "READY permits the operator to start the canary. It starts nothing.",
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan the first real canary, or check whether it may run. Makes no request.")
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan")
    planner.add_argument("--outlets", type=int, required=True)
    planner.add_argument("--seed", required=True)
    checker = commands.add_parser("preflight")
    checker.add_argument("--outlet", action="append", default=[], help="an outlet of the canary (repeatable)")
    checker.add_argument("--commit", required=True, help="the commit this checkout is at")
    checker.add_argument("--tests-passed", type=int)
    checker.add_argument("--tests-commit")
    checker.add_argument("--approved-baseline", type=Path)
    checker.add_argument("--required-free-bytes", type=int)
    arguments = parser.parse_args(argv)
    if arguments.command == "plan":
        document = registry.load_registry(CHECKOUT / "config" / "outlet_registry.json")
        print(json.dumps(plan_canary(document, outlets_wanted=arguments.outlets, seed=arguments.seed), indent=2, ensure_ascii=False))
        return 0
    baseline = json.loads(arguments.approved_baseline.read_text(encoding="utf-8")) if arguments.approved_baseline else None
    report = preflight(outlet_ids=arguments.outlet, tests_passed=arguments.tests_passed, tests_commit=arguments.tests_commit,
                       code_commit=arguments.commit, approved_baseline=baseline,
                       required_free_bytes=arguments.required_free_bytes, now=datetime.now(timezone.utc))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
