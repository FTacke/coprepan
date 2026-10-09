"""The source inventory after qualification, the intake-readiness configuration and the access-restriction review (CPD-0025, CPD-0026).

They are derived files. What is held here: that they are what their builder gives from the tracked evidence, that a stage
never claims more than the evidence shows, that the readiness configuration starts nothing, and that a held origin is in
no intake.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVENTORY = REPO / "config" / "source_discovery" / "source_inventory_2026-10-10.1.json"            # the version in force
INVENTORY_OF_THE_REVIEW = REPO / "config" / "source_discovery" / "source_inventory_2026-10-09.1.json"   # the snapshot the access review was written against
READINESS = REPO / "config" / "intake" / "intake_readiness_2026-10-10.1.json"
PAGE = REPO / "docs" / "corpus_supply" / "SOURCE_QUALIFICATION_2026-10-10.1.md"
REVIEW = REPO / "config" / "source_discovery" / "access_restriction_review_2026-10-09.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def builder():
    spec = importlib.util.spec_from_file_location("build_intake_readiness_under_test", REPO / "scripts" / "build_intake_readiness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_tracked_files_are_what_the_builder_gives_from_the_tracked_evidence(tmp_path):
    inventory = load(INVENTORY)
    registry_now = builder().sha256_bytes((REPO / "config" / "outlet_registry.json").read_bytes())
    policy_now = json.loads((REPO / "config" / "acquisition_policy.json").read_text(encoding="utf-8"))["policy_version"]
    if inventory["inputs"]["registry"]["sha256"] != registry_now or inventory["inputs"]["policy_version"] != policy_now:
        import pytest
        pytest.skip("the registry or the policy has changed since this inventory version was built: a version is rebuilt only from its own inputs")
    out = [tmp_path / "inventory.json", tmp_path / "readiness.json", tmp_path / "page.md"]
    assert builder().main(["--version", "2026-10-10.1", "--out-inventory", str(out[0]), "--out-readiness", str(out[1]), "--out-md", str(out[2])]) == 0
    assert [path.read_bytes() for path in out] == [INVENTORY.read_bytes(), READINESS.read_bytes(), PAGE.read_bytes()]


def test_a_stage_claims_what_the_evidence_shows_and_no_more():
    inventory = load(INVENTORY)
    outlets = inventory["outlets"]
    assert len(outlets) == len({o["outlet_id"] for o in outlets}) == inventory["totals"]["hypotheses"] == 145
    assert "OPERATIONALLY_STABLE" not in inventory["totals"]["by_stage"]                       # every run of the qualification was on one day
    for outlet in outlets:
        if outlet["stage"] == "ACQUISITION_VERIFIED":
            assert outlet["verified_runs"] and outlet["registration_status"] == "registered" and outlet["replay"] == "PASS"
            thresholds = [5 if run["item_budget"] >= 10 else 3 for run in outlet["runs"] if run["run_id"] in outlet["verified_runs"]]
            items = [run["items_2xx"] for run in outlet["runs"] if run["run_id"] in outlet["verified_runs"]]
            assert all(count >= floor for count, floor in zip(items, thresholds))
        elif outlet["stage"] == "NOT_REGISTERED":
            assert outlet["registration_status"] != "registered" and not outlet["runs"] and outlet["next_step"].startswith("deferred: ")
        else:
            assert outlet["restriction"]                                                        # registered and not verified: the reason is named
    assert inventory["totals"]["by_stage"]["ACQUISITION_VERIFIED"] == sum(o["stage"] == "ACQUISITION_VERIFIED" for o in outlets)
    assert all(run["verification"] in ("PASS", "FAIL") and run["verification_as_first_run"] in ("PASS", "FAIL") for run in inventory["inputs"]["runs"])
    # a run whose first verification failed is named with both files; neither is hidden
    again = [run for run in inventory["inputs"]["runs"] if run["verification_as_first_run"] != run["verification"]]
    assert all(run["verification_file"].startswith("verification_after_") for run in again)


def test_the_readiness_configuration_starts_nothing_and_holds_no_held_origin():
    readiness, inventory = load(READINESS), load(INVENTORY)
    assert readiness["status"].startswith("PREPARED") and "starts nothing" in readiness["status"]
    assert json.loads((REPO / "config" / "acquisition_policy.json").read_text(encoding="utf-8"))["external_acquisition"] in ("disabled", "enabled")
    ready = {entry["outlet_id"] for entry in readiness["outlets"]}
    by_id = {o["outlet_id"]: o for o in inventory["outlets"]}
    assert not ready & set(readiness["holds"]) and not ready & set(readiness["excluded"]) and "co_el_tiempo" in readiness["excluded"]
    for entry in readiness["outlets"]:
        outlet = by_id[entry["outlet_id"]]
        assert outlet["item_pages_2xx_all_runs"] > 0 and outlet["restriction"] != "HELD_ACCESS_CONTROL"
        assert entry["tier"] == ("A" if outlet["stage"] == "ACQUISITION_VERIFIED" else "B")
        assert entry["limits"]["min_interval_seconds_per_origin"] >= 10 and entry["limits"]["concurrent_requests_per_origin"] == 1
        assert entry["channels"] or entry["tier"] == "B"
    assert set(readiness["holds"]) == {o["outlet_id"] for o in inventory["outlets"] if o["restriction"] == "HELD_ACCESS_CONTROL"}


def test_the_access_restriction_review_covers_every_held_outlet_and_lifts_no_hold():
    review, inventory = load(REVIEW), load(INVENTORY_OF_THE_REVIEW)
    held = {o["outlet_id"] for o in inventory["outlets"] if o["restriction"] == "HELD_ACCESS_CONTROL"}
    rows = {row["outlet_id"]: row for row in review["outlets"]}
    assert set(rows) == held and review["totals"]["held"] == len(held)
    groups = review["totals"]["by_group"]
    assert sorted(sum(groups.values(), [])) == sorted(held) and groups["RECOVERABLE"] == ["mx_la_jornada"]
    for row in rows.values():
        assert row["observed"] and row["explanation"] and row["evidence_limits"] and row["permitted_solution"]
        assert row["repair_made"] <= row["own_technical_defect"]                                # a repair is of our own defect only
        assert row["intake_status"].startswith("excluded") or row["group"] == "RECOVERABLE"
        assert row["legacy"]["productive"] == bool(row["legacy"]["ok_articles"])
    assert rows["es_el_pais"]["legacy"]["ok_articles"] == 1142 and rows["es_el_pais"]["legacy"]["last_ok_fetch_day"] == "2026-02-21"
    assert rows["es_el_pais"]["group"] == "POTENTIALLY_RECOVERABLE" and rows["es_el_pais"]["further_access_decision_needed"]
    assert "no hold is lifted" in review["what_this_is"]


def test_no_outlet_of_the_readiness_file_has_a_held_origin_and_a_released_hold_is_not_a_verified_outlet():
    """CPD-0027: a hold has a scope. An outlet with a held origin is in no intake, however many pages it yielded before the
    control was met (es_el_pais: five articles, then a CAPTCHA); an outlet with one held route and a working one is."""
    holds = load(REPO / "config" / "source_discovery" / "access_holds_2026-10-10.json")
    readiness, inventory = load(READINESS), {o["outlet_id"]: o for o in load(INVENTORY)["outlets"]}
    assert readiness["held_origins"] == holds["held_origins"] and readiness["held_urls"] == holds["held_urls"]
    for entry in readiness["outlets"]:
        assert not set(entry["web_origins"]) & set(holds["held_origins"]), entry["outlet_id"]
        assert not {channel["url"] for channel in entry["channels"]} & set(holds["held_urls"]), entry["outlet_id"]
    ready = {entry["outlet_id"] for entry in readiness["outlets"]}
    assert inventory["es_el_pais"]["stage"] == "ACQUISITION_VERIFIED" and inventory["es_el_pais"]["restriction"] == "HELD_ACCESS_CONTROL" and "es_el_pais" not in ready
    assert "ve_efecto_cocuyo" in ready and inventory["ve_efecto_cocuyo"]["holds_in_force"]["urls"] == ["https://efectococuyo.com/sitemap.xml"]
    assert "mx_la_jornada" not in ready and inventory["mx_la_jornada"]["stage"] != "ACQUISITION_VERIFIED"     # released by the policy, refused by the server
    assert holds["classifier"] == "access-control/4" and holds["hold_scope"] == "access-hold-scope/1"
