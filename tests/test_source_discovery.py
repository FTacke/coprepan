"""The source-discovery inventory and the registration proposal of the extended canary (CPD-0019 §7–§8).

The inventory is a join of evidence files: what is tested is that it is the join it says it is, that
its flags follow from the evidence and never from hope, and that nothing in it or in the proposal has
registered anything. The proposal is tested by applying it to a copy: what would be registered is a
valid registry, covered by a valid registration record, and gives a canary the driver can pin.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from coprepan import canary_driver as D, candidate_filter, policy as P, registry as R, registry_review as RR
from coprepan.canonical import record_json

REPO = Path(__file__).resolve().parents[1]
DISCOVERY = REPO / "config" / "source_discovery"
INVENTORY = DISCOVERY / "source_discovery_inventory_2026-10-09.1.json"
PROPOSAL = REPO / "config" / "registry_review" / "extended_canary_proposal_2026-10-09.json"
FIRST_CANARY = ("bo_el_deber", "do_diario_libre", "hn_proceso_digital", "py_la_nacion", "ve_efecto_cocuyo")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def inventory():
    return load(INVENTORY)


# --- the inventory -----------------------------------------------------------------------------------


def test_the_inventory_names_its_inputs_by_digest_and_they_are_the_tracked_files(inventory):
    inputs = inventory["inputs"]
    files = [inputs["legacy_audit"], inputs["canary_replay"], *inputs["prediscovery"]]
    assert len(inputs["prediscovery"]) == 3
    for entry in files:
        assert hashlib.sha256((DISCOVERY / entry["file"]).read_bytes()).hexdigest() == entry["sha256"], entry["file"]
    evidence = REPO / "docs" / "canary" / "evidence" / "acq1-20261008T203414628095Z-ed630d8e8a14"
    for key in ("canary_verification", "canary_measurement"):
        assert hashlib.sha256((evidence / inputs[key]["file"]).read_bytes()).hexdigest() == inputs[key]["sha256"]


def test_the_inventory_covers_every_outlet_and_every_channel_of_the_legacy_import(inventory):
    registry = load(REPO / "config" / "outlet_registry.json")
    report = load(REPO / "config" / "registry_review" / "legacy_registry_import_2026-10-07.json")
    assert [o["outlet_id"] for o in inventory["outlets"]] == sorted(row["proposed_outlet_id"] for row in report["legacy_name_to_outlet_id"])
    assert inventory["totals"]["outlets"] == 82 and inventory["totals"]["countries"] == 20
    legacy_urls = {(o["outlet_id"], c["legacy_observed"]["id"], c["url_history"][-1]["url"])
                   for o in registry["outlets"] for c in o["channels"] if c["legacy_observed"]}
    listed = {(o["outlet_id"], c["legacy_feed_id"], c["url"]) for o in inventory["outlets"] for c in o["channels"]}
    assert listed == legacy_urls and len(listed) == report["counts"]["proposed_channels"] == 352


def test_the_legacy_audit_found_the_import_complete(inventory):
    audit = load(DISCOVERY / "legacy_discovery_audit_2026-10-09.json")
    assert audit["schema"] == "coprepan-legacy-discovery-audit/v1" and audit["import_discrepancies"] == []
    assert len(audit["outlets"]) == 82 and sum(len(o["channels"]) for o in audit["outlets"].values()) == 352
    assert audit["inputs"]["database_copy"]["sha256"] == load(
        REPO / "config" / "registry_review" / "legacy_registry_import_2026-10-07.json")["input"]["database_sha256"]
    classes = inventory["totals"]["outlets_by_legacy_class"]
    assert sum(classes.values()) == 82 and classes == {name: sum(1 for o in audit["outlets"].values() if o["outlet_class"] == name) for name in classes}


def test_a_flag_follows_from_evidence_of_this_project_and_never_from_research(inventory):
    by_id = {o["outlet_id"]: o for o in inventory["outlets"]}
    # The inventory is a dated snapshot: its flags are those of the registry it was built from (the five outlets of the
    # first canary), not of the registry as it is after later registrations. Its inputs name that registry by digest.
    assert {i for i, o in by_id.items() if "REGISTERED" in o["flags"]} == set(FIRST_CANARY)
    assert len(inventory["inputs"]["registry"]["sha256"]) == 64
    measurement = load(REPO / "docs" / "canary" / "evidence" / "acq1-20261008T203414628095Z-ed630d8e8a14" / "measurement.json")
    verified = {i for i, row in measurement["outlets"].items() if row["items_fetched"] >= 5}
    assert {i for i, o in by_id.items() if "ACQUISITION_VERIFIED" in o["flags"]} == verified == {"do_diario_libre"}
    assert not any("OPERATIONALLY_STABLE" in o["flags"] for o in by_id.values())           # nothing has been observed twice
    for outlet in by_id.values():
        if "QUALIFIED" in outlet["flags"]:
            # only a channel document this project read from a real server qualifies, and the outlet was in the canary
            assert outlet["outlet_id"] in FIRST_CANARY
            assert any(c["v3_observation"] and c["v3_observation"]["item_entries_with_url"] > 0 for c in outlet["channels"])
        assert outlet["research"]["method"].startswith("passive web research; no request to any publisher")
        assert all(c["evidence_level"] in ("search_evidence", "legacy_evidence", "cms_pattern_inference", "unknown")
                   for c in outlet["research"]["candidate_channels"])
    assert by_id["hn_proceso_digital"]["route_class"] == "ACCESS_CONTROL_HOLD" and by_id["hn_proceso_digital"]["priority"]["score"] == 0
    assert {i for i, o in by_id.items() if o["route_class"] == "CLOSED"} == {"bo_pagina_siete", "gt_elperiodico"}
    assert all(p["status"] == "PROPOSAL_ONLY" for p in inventory["proposed_new_outlets"])
    assert not {p.get("origin") for p in inventory["proposed_new_outlets"]} & {origin for o in by_id.values() for origin in o["web_origins"]}


def test_the_inventory_page_is_the_page_of_the_inventory(inventory):
    page = script("build_source_discovery_inventory").render(inventory)
    assert page.encode("utf-8") == (REPO / "docs" / "corpus_supply" / "SOURCE_DISCOVERY_INVENTORY.md").read_bytes()


def test_an_inventory_version_is_written_once(tmp_path):
    if load(INVENTORY)["inputs"]["registry"]["sha256"] != hashlib.sha256((REPO / "config" / "outlet_registry.json").read_bytes()).hexdigest():
        pytest.skip("the registry has changed since this inventory version was built: a version is rebuilt only from its own inputs")
    builder = script("build_source_discovery_inventory")
    evidence = REPO / "docs" / "canary" / "evidence" / "acq1-20261008T203414628095Z-ed630d8e8a14"
    arguments = ["--registry", str(REPO / "config" / "outlet_registry.json"), "--legacy-audit", str(DISCOVERY / "legacy_discovery_audit_2026-10-09.json"),
                 "--prediscovery", *(str(DISCOVERY / f"prediscovery_2026-10-09_group{n}.json") for n in (1, 2, 3)),
                 "--canary-replay", str(DISCOVERY / "canary_replay_2026-10-09.json"), "--canary-verification", str(evidence / "verification.json"),
                 "--canary-measurement", str(evidence / "measurement.json"), "--version", "2026-10-09.1",
                 "--out-json", str(tmp_path / "inventory.json"), "--out-md", str(tmp_path / "inventory.md")]
    assert builder.main(arguments) == 0
    assert (tmp_path / "inventory.json").read_bytes() == INVENTORY.read_bytes()            # deterministic: the tracked file again
    with pytest.raises(SystemExit):
        builder.main(arguments)


# --- the proposal ------------------------------------------------------------------------------------


def checkout_copy(tmp_path: Path) -> Path:
    copy = tmp_path / "checkout"
    (copy / "config" / "registry_review").mkdir(parents=True)
    (copy / "docs" / "corpus_supply").mkdir(parents=True)
    for name in ("outlet_registry.json", "candidate_rules.json", "acquisition_policy.json"):
        shutil.copyfile(REPO / "config" / name, copy / "config" / name)
    return copy


def test_the_proposal_has_registered_nothing_and_is_written_for_the_tracked_registry():
    proposal = load(PROPOSAL)
    registry = R.load_registry(REPO / "config" / "outlet_registry.json")
    assert proposal["schema"] == "coprepan-registry-registration-proposal/v1" and proposal["status"].startswith("PROPOSAL")
    assert len(proposal["proposed"]) == 12 and len({e["outlet_id"][:2] for e in proposal["proposed"]}) == 10
    for entry in proposal["proposed"]:
        if registry.outlets[entry["outlet_id"]]["registration_status"] == "proposed":
            assert entry["evidence"] and all(item["source"] and item["how"] for item in entry["evidence"])
    # as long as none of it is applied, it is written for exactly this registry
    if all(registry.outlets[e["outlet_id"]]["registration_status"] == "proposed" for e in proposal["proposed"]):
        assert proposal["inputs"]["registry_sha256_before"] == hashlib.sha256((REPO / "config" / "outlet_registry.json").read_bytes()).hexdigest()
        assert candidate_filter.load_rules() == {} and not set(P.load_policy()["disabled_channels"]) & {
            c for e in proposal["proposed"] for c in e["channels_disabled_for_the_canary"]}


def test_applied_to_a_copy_the_proposal_gives_a_valid_registry_a_record_and_a_canary_the_driver_can_pin(tmp_path):
    proposal = load(PROPOSAL)
    if any(R.load_registry(REPO / "config" / "outlet_registry.json").outlets[e["outlet_id"]]["registration_status"] != "proposed" for e in proposal["proposed"]):
        pytest.skip("the proposal has been applied: its registration record is what the registry tests hold the registry against")
    applier = script("apply_registration_proposal")
    copy = checkout_copy(tmp_path)
    before = {name: (REPO / "config" / name).read_bytes() for name in ("outlet_registry.json", "candidate_rules.json", "acquisition_policy.json")}
    assert applier.main(["--proposal", str(PROPOSAL), "--approved-by", "a test", "--repository", str(copy)]) == 0       # a dry run writes nothing
    assert all((copy / "config" / name).read_bytes() == data for name, data in before.items())
    assert applier.main(["--proposal", str(PROPOSAL), "--approved-by", "a test", "--repository", str(copy), "--write"]) == 0
    assert all((REPO / "config" / name).read_bytes() == data for name, data in before.items())                           # the checkout is untouched

    registry = R.load_registry(copy / "config" / "outlet_registry.json")
    record = load(next((copy / "config" / "registry_review").glob("extended_canary_registration_*.json")))
    chosen = [entry["outlet_id"] for entry in proposal["proposed"]]
    assert record["schema"] == "coprepan-registry-registration/v1" and record["gate"] == "O-11" and "a test" in record["authority"]
    assert record["registry_sha256_after"] == hashlib.sha256((copy / "config" / "outlet_registry.json").read_bytes()).hexdigest()
    for entry in record["registered"]:                                           # what tests/test_registry.py asks of a registration record
        outlet = registry.resolve(entry["outlet_id"])
        assert all(outlet[field] == value for field, value in entry["attributes_set"].items())
        assert outlet["timezone"] != "unknown" and outlet["url_rules"]["version"] == entry["url_rules"]["version"] != "proposed"
        assert {channel["channel_id"] for channel in outlet["channels"]} == set(entry["channel_ids"].values())
        assert outlet["web_origins"] == entry["web_origins"] and outlet["review_notes"] == []
        assert all(outlet[field] == "unknown" for field in entry["attributes_left_unknown"])
    # no legacy channel was removed or changed; the eight new ones carry no legacy row
    old = {c["channel_id"]: c for o in load(REPO / "config" / "outlet_registry.json")["outlets"] for c in o["channels"]}
    new = {c["channel_id"]: c for o in registry.outlets.values() for c in o["channels"]}
    assert all(new[identifier] == channel for identifier, channel in old.items())
    assert len(new) - len(old) == 8 and all(new[identifier]["legacy_observed"] == {} for identifier in set(new) - set(old))
    assert sum(1 for o in registry.outlets.values() if o["registration_status"] == "registered") == 5 + 12
    RR.write_package(copy / "config" / "outlet_registry.json", tmp_path / "package.json", tmp_path / "page.md")          # the review package still builds
    assert (tmp_path / "package.json").read_bytes() == (copy / "config" / "registry_review" / "outlet_review_package.json").read_bytes()

    # the canary the driver would pin: twelve outlets, the hard ceiling kept, the channels the proposal means
    tracked_policy = P.load_policy(copy / "config" / "acquisition_policy.json")
    rules = candidate_filter.load_rules(copy / "config" / "candidate_rules.json")
    budget = D.canary_budget(len(chosen))
    pin = D.driver_pin(budget, registry, chosen, tracked_policy["disabled_channels"], rules)
    assert budget.item_requests_per_outlet == 8 and budget.item_requests_total == 96 <= D.HARD_ITEM_REQUESTS
    selected = pin["outlets"]
    assert selected["bo_lostiempos"] == ["bo_lostiempos:ch:rss_001", "bo_lostiempos:ch:section_page_r001"]               # a listing, by its allow rule
    assert selected["cl_el_mercurio"] == ["cl_el_mercurio:ch:sitemap_index_001"]                                         # photo and video indexes disabled
    assert selected["mx_la_jornada"] == ["mx_la_jornada:ch:rss_r001", "mx_la_jornada:ch:atom_r001"]
    assert selected["ni_confidencial"] == ["ni_confidencial:ch:rss_r001", "ni_confidencial:ch:sitemap_001"]
    assert selected["pa_laestrelladepanama"] == ["pa_laestrelladepanama:ch:sitemap_002", "pa_laestrelladepanama:ch:sitemap_index_001"]
    assert selected["es_el_mundo"] == ["es_el_mundo:ch:rss_r001"] and all(1 <= len(channels) <= 2 for channels in selected.values())
    # applying a proposal never touches the switch: it is what the tracked policy says, armed or not
    assert tracked_policy["policy_version"] == proposal["policy_version_after"]
    assert tracked_policy["external_acquisition"] == P.load_policy()["external_acquisition"]


def test_a_proposal_is_refused_for_another_registry_without_a_name_or_for_an_outlet_it_does_not_hold():
    applier = script("apply_registration_proposal")
    proposal = load(PROPOSAL)
    documents = [load(REPO / "config" / name) for name in ("outlet_registry.json", "candidate_rules.json", "acquisition_policy.json")]
    if proposal["inputs"]["registry_sha256_before"] != hashlib.sha256(record_json(documents[0])).hexdigest():
        pytest.skip("the proposal has been applied")
    with pytest.raises(applier.ProposalError):
        applier.apply(proposal, *documents, approved_by="  ", approved_on="2026-10-09")
    with pytest.raises(applier.ProposalError):
        applier.apply(proposal, *documents, approved_by="x", approved_on="2026-10-09", only=["uy_el_pais"])
    changed = json.loads(json.dumps(documents[0]))
    changed["outlets"][0]["city"] = "otra"
    with pytest.raises(applier.ProposalError):
        applier.apply(proposal, changed, *documents[1:], approved_by="x", approved_on="2026-10-09")
    part = applier.apply(proposal, *documents, approved_by="x", approved_on="2026-10-09", only=["ec_el_universo", "cl_el_mercurio"])
    assert [e["outlet_id"] for e in part["record"]["registered"]] == ["cl_el_mercurio", "ec_el_universo"] and len(part["record"]["deferred"]) == 10
    assert part["candidate_rules"]["outlets"] == {}                              # the listing rule belongs to an outlet that was struck


def test_the_second_canary_is_the_five_registered_outlets_with_the_channel_that_answered_404_left_out():
    registry = R.load_registry(REPO / "config" / "outlet_registry.json")
    tracked = P.load_policy()
    pin = D.driver_pin(D.canary_budget(5), registry, FIRST_CANARY, tracked["disabled_channels"], candidate_filter.load_rules())
    assert pin["driver"] == D.DRIVER_VERSION and pin["budget"]["other_requests_per_outlet"] == 8 and pin["budget"]["item_requests_total"] == 80
    assert pin["outlets"]["hn_proceso_digital"] == ["hn_proceso_digital:ch:rss_main", "hn_proceso_digital:ch:sitemap_index_main"]
    assert pin["outlets"]["ve_efecto_cocuyo"] == ["ve_efecto_cocuyo:ch:rss_main", "ve_efecto_cocuyo:ch:sitemap_index_main"]
    assert pin["outlets"]["py_la_nacion"] == ["py_la_nacion:ch:sitemap_arc_outboundfeeds_sitemap_outputtype_xml"]
    assert tracked["external_acquisition"] in ("disabled", "enabled")            # which of the two is the arming's business, not this test's


# --- the review of the proposal ----------------------------------------------------------------------

REVIEW = REPO / "config" / "registry_review" / "extended_canary_review_2026-10-09.json"


def test_the_review_covers_the_proposal_and_its_first_wave_applies_to_a_copy(tmp_path):
    review, proposal = load(REVIEW), load(PROPOSAL)
    labels = {"READY_FOR_REGISTRATION_REVIEW", "NEEDS_VERIFICATION", "DEFER"}
    assert [e["outlet_id"] for e in review["entries"]] == [e["outlet_id"] for e in sorted(proposal["proposed"], key=lambda e: [x["outlet_id"] for x in review["entries"]].index(e["outlet_id"]))]
    assert {e["outlet_id"] for e in review["entries"]} == {e["outlet_id"] for e in proposal["proposed"]}
    assert all(e["recommendation"] in labels and e["evidence"] and e["risks"] and e["legacy"] for e in review["entries"])
    ready = [e["outlet_id"] for e in review["entries"] if e["recommendation"] == "READY_FOR_REGISTRATION_REVIEW"]
    assert review["recommended_first_wave"] == sorted(ready)
    assert review["counts"] == {label: sum(1 for e in review["entries"] if e["recommendation"] == label) for label in labels}
    if any(R.load_registry(REPO / "config" / "outlet_registry.json").outlets[o]["registration_status"] != "proposed" for o in ready):
        pytest.skip("the proposal has been applied")
    applier = script("apply_registration_proposal")
    copy = checkout_copy(tmp_path)
    arguments = ["--proposal", str(PROPOSAL), "--approved-by", "a test", "--repository", str(copy), "--write"]
    for outlet in ready:
        arguments += ["--only", outlet]
    assert applier.main(arguments) == 0
    registry = R.load_registry(copy / "config" / "outlet_registry.json")
    struck = {e["outlet_id"] for e in proposal["proposed"]} - set(ready)
    assert all(registry.outlets[o]["registration_status"] == "proposed" for o in struck)
    # the wave carries no listing channel, no candidate rule, and leaves the policy as it is
    assert candidate_filter.load_rules(copy / "config" / "candidate_rules.json") == {}
    assert (copy / "config" / "acquisition_policy.json").read_bytes() == (REPO / "config" / "acquisition_policy.json").read_bytes()
    budget = D.canary_budget(len(ready))
    pin = D.driver_pin(budget, registry, ready, P.load_policy(copy / "config" / "acquisition_policy.json")["disabled_channels"], {})
    assert (budget.outlets, budget.item_requests_per_outlet, budget.item_requests_total) == (8, 12, 96)
    assert all(1 <= len(channels) <= 2 for channels in pin["outlets"].values())
    assert not [c for channels in pin["outlets"].values() for c in channels if ":ch:section_page" in c or ":ch:archive" in c]
    assert len({o[:2] for o in ready}) == 6
