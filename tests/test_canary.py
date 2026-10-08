"""The real-canary planner and its preflight: a reviewable proposal and a fail-closed gate.

No test here makes a request, registers an outlet or decides a policy. The "ready" case is built
entirely in ``tmp_path`` from invented configuration, to show that the gate opens when — and only
when — every precondition holds.
"""

import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import canary as CN
from coprepan import freeze as FZ
from coprepan import preservation_target as PT
from coprepan import registry as R

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 7, 22, 0, 0, tzinfo=timezone.utc)
COMMIT = "9e0a1c0539ffac46f565f6547b5a715cdb20c701"


def outlet(outlet_id, kind, outlet_type="national_reference", status="registered", timezone_="America/Montevideo", rules="rules/1"):
    host = outlet_id.replace("_", "-")
    return {"outlet_id": outlet_id, "country_id": outlet_id[:2], "registration_status": status,
            "display_names": [{"name": outlet_id, "valid_from": "unknown", "valid_to": "unknown"}],
            "outlet_type": outlet_type, "outlet_group": "unknown", "city": "unknown", "region": "unknown", "scope": "unknown",
            "access_model": "open", "medium": "web_only", "editions": [], "web_origins": [f"https://www.{host}.test"],
            "timezone": timezone_, "same_outlet_basis": "not_applicable",
            "url_rules": {"version": rules, "significant_query_params": [], "strip_path_prefixes": [], "strip_path_suffixes": []},
            "channels": [{"channel_id": f"{outlet_id}:ch:{kind}_main", "kind": kind,
                          "url_history": [{"url": f"https://www.{host}.test/{kind}", "valid_from": "unknown"}],
                          "legacy_observed": {}}] if kind else [],
            "legacy_aliases": [], "legacy_observed": {}, "review_notes": []}


def registry_of(*outlets):
    return R.validate_registry({"schema": "coprepan-outlet-registry/v1", "outlets": sorted(outlets, key=lambda o: o["outlet_id"])})


POOL = [outlet("ar_uno", "rss"), outlet("ar_dos", "sitemap", "regional"), outlet("cl_uno", "rss"), outlet("co_uno", "rss", "digital_native"),
        outlet("es_uno", "sitemap_index"), outlet("mx_uno", "rss", "popular_tabloid"), outlet("uy_uno", "atom"),
        outlet("pe_propuesto", "rss", status="proposed"), outlet("pe_sin_canal", None), outlet("pe_sin_zona", "rss", timezone_="unknown"),
        outlet("pe_reglas", "rss", rules="proposed")]


# --- planner ----------------------------------------------------------------------------------------


def test_the_tracked_registry_yields_exactly_the_registered_canary_subset():
    tracked = R.load_registry(REPO / "config" / "outlet_registry.json")
    registered = sorted(o["outlet_id"] for o in tracked.outlets.values() if o["registration_status"] == "registered")
    plan = CN.plan_canary(tracked, outlets_wanted=5, seed="canary-1")
    assert plan["sufficient"] is True and len(plan["selection"]) == 5
    assert {o["outlet_id"] for o in plan["selection"]} <= set(registered)
    assert len({o["country_id"] for o in plan["selection"]}) == 5
    assert len(plan["not_eligible"]) == len(tracked.outlets) - len(registered)
    assert all("not registered" in problems for problems in plan["not_eligible"].values())


def test_the_plan_spreads_over_countries_then_types_then_channel_kinds():
    plan = CN.plan_canary(registry_of(*POOL), outlets_wanted=5, seed="canary-1")
    selected = plan["selection"]
    assert plan["sufficient"] and len(selected) == 5
    assert len({o["country_id"] for o in selected}) == 5                       # five outlets, five countries
    assert len(plan["diversity"]["outlet_types"]) >= 3 and len(plan["diversity"]["channel_kinds"]) >= 3
    assert all(o["why_in_the_set"] for o in selected) and "adds country" in selected[0]["why_in_the_set"][0]
    assert all(c["url"].startswith("https://") for o in selected for c in o["channels"])
    assert plan["status"].startswith("PROPOSAL_FOR_REVIEW")                    # a proposal, never "the right five"
    assert sorted(plan["not_eligible"]) == ["pe_propuesto", "pe_reglas", "pe_sin_canal", "pe_sin_zona"]
    assert plan["not_eligible"]["pe_sin_zona"] == ["no time zone: its material could not be dated"]
    assert len(plan["not_selected_but_eligible"]) == 2                         # the reviewer sees the alternatives


def test_the_plan_is_deterministic_and_the_seed_only_breaks_ties():
    first = CN.plan_canary(registry_of(*POOL), outlets_wanted=5, seed="canary-1")
    assert first == CN.plan_canary(registry_of(*reversed(POOL)), outlets_wanted=5, seed="canary-1")
    other = CN.plan_canary(registry_of(*POOL), outlets_wanted=5, seed="canary-2")
    assert len({o["country_id"] for o in other["selection"]}) == 5 and other["plan_sha256"] != first["plan_sha256"]
    few = CN.plan_canary(registry_of(*POOL[:2]), outlets_wanted=5, seed="canary-1")
    assert (few["outlets_selected"], few["sufficient"]) == (2, False)
    with pytest.raises(ValueError):
        CN.plan_canary(registry_of(*POOL), outlets_wanted=0, seed="x")


# --- preflight --------------------------------------------------------------------------------------


def failed(report):
    return {check["check"]: check["gate"] for check in report["checks"] if check["status"] == "FAIL"}


def test_as_committed_the_canary_may_not_run_and_every_gate_says_why():
    report = CN.preflight(outlet_ids=["uy_el_pais"], tests_passed=None, tests_commit=None, code_commit=COMMIT,
                          approved_baseline=None, required_free_bytes=None, now=NOW, environment={})
    assert report["status"] == "NOT_READY" and report["schema"] == "coprepan-canary-preflight/v1"
    assert failed(report) == {
        "outlet_registered:uy_el_pais": "O-11", "acquisition_policy_decided": "O-1",
        "preservation_target_ready": "O-3", "runtime_workspace_configured": "O-3",
        "tests_green_on_this_commit": "engineering", "no_configuration_drift": "canary_approval"}
    assert report["open_by_gate"] == {"O-1": 1, "O-11": 1, "O-3": 2, "canary_approval": 1, "engineering": 1}
    # the policy is decided; what is still open under O-1 is the switch, turned when the canary is armed
    detail = {check["check"]: check["detail"] for check in report["checks"]}
    assert "status DECIDED, external acquisition disabled" in detail["acquisition_policy_decided"]
    registered = CN.preflight(outlet_ids=["bo_el_deber"], tests_passed=None, tests_commit=None, code_commit=COMMIT,
                              approved_baseline=None, required_free_bytes=None, now=NOW, environment={})
    assert "outlet_registered:bo_el_deber" not in failed(registered) and registered["status"] == "NOT_READY"
    assert "O-4" in report["not_a_precondition"]                               # the canary is what measures capacity
    assert CN.preflight(outlet_ids=[], tests_passed=1, tests_commit=COMMIT, code_commit=COMMIT, approved_baseline=None,
                        required_free_bytes=1, now=NOW, environment={})["status"] == "NOT_READY"


def test_the_command_exits_non_zero_until_everything_passes(capsys):
    assert CN.main(["preflight", "--outlet", "uy_el_pais", "--commit", COMMIT]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "NOT_READY"
    assert CN.main(["plan", "--outlets", "5", "--seed", "canary-1"]) == 0
    assert json.loads(capsys.readouterr().out)["outlets_selected"] == 5     # planning selects; it starts nothing


@pytest.fixture
def ready(tmp_path):
    """A complete, invented configuration in which every precondition holds."""
    repository = tmp_path / "checkout"
    shutil.copytree(REPO / "config", repository / "config")
    shutil.copytree(REPO / "docs" / "decisions", repository / "docs" / "decisions")
    (repository / "tests" / "fixtures").mkdir(parents=True)
    config = repository / "config"
    config.joinpath("outlet_registry.json").write_text(json.dumps({"schema": "coprepan-outlet-registry/v1", "outlets": [
        outlet("uy_uno", "rss")]}), encoding="utf-8")
    policy = json.loads(config.joinpath("acquisition_policy.json").read_text(encoding="utf-8"))
    policy.update(status="DECIDED", external_acquisition="enabled", policy_version="policy/2026.1",
                  robots={"mode": "enforce", "on_absent": "allow", "on_unreachable": "deny"},
                  rate_limit={"min_interval_seconds_per_origin": 10, "crawl_delay": "binding_minimum", "crawl_delay_max_seconds": 60})
    config.joinpath("acquisition_policy.json").write_text(json.dumps(policy), encoding="utf-8")
    config.joinpath("crawler_identity.json").write_text(json.dumps({
        "schema": "coprepan-crawler-identity/v1", "crawler_name": "coprepan-research", "organisation": "Universidad Ficticia",
        "contact_url": "https://corpus.uni-ficticia.es/crawler", "contact_email": "corpus@uni-ficticia.es"}), encoding="utf-8")
    schedule = json.loads(config.joinpath("schedule_policy.json").read_text(encoding="utf-8"))
    schedule.update({key: 3600 for key, value in schedule.items() if value == "not_decided"})
    schedule.update(status="DECIDED", version="schedule/2026.1", revisit_backoff_factor=2, failure_backoff_factor=2,
                    max_consecutive_failures=3, max_gone_rechecks=2, use_conditional_requests=True)
    config.joinpath("schedule_policy.json").write_text(json.dumps(schedule), encoding="utf-8")
    target, workspace = tmp_path / "preservation", tmp_path / "workspace"
    target.mkdir(), workspace.mkdir()
    PT.initialise_target(target, "target-a", operator="operator", now=NOW)
    environment = {"COPREPAN_PRESERVATION_ROOT": str(target), "COPREPAN_WORKSPACE_ROOT": str(workspace)}
    readiness = PT.check_readiness(target, required_free_bytes=1024, now=NOW)
    baseline = FZ.build_manifest(code_commit=COMMIT, created_at=NOW, operator="operator", test_baseline={"passed": 1},
                                 storage_target=readiness, repository=repository)
    arguments = dict(outlet_ids=["uy_uno"], tests_passed=700, tests_commit=COMMIT, code_commit=COMMIT, approved_baseline=baseline,
                     required_free_bytes=1024, now=NOW, environment=environment, repository=repository)
    return repository, arguments


def test_with_every_precondition_met_the_gate_opens_and_starts_nothing(ready):
    repository, arguments = ready
    report = CN.preflight(**arguments)
    assert report["status"] == "READY" and failed(report) == {} and report["open_by_gate"] == {}
    assert "starts nothing" in report["note"]
    assert arguments["approved_baseline"]["blocking"] == ["O-4: bytes per fetch have not been measured on real material"]


@pytest.mark.parametrize(
    "break_it, check",
    [(lambda a, r: a.update(outlet_ids=["uy_uno", "ar_falta"]), "outlet_registered:ar_falta"),
     (lambda a, r: a.update(tests_commit="0" * 40), "tests_green_on_this_commit"),
     (lambda a, r: a.update(tests_passed=0), "tests_green_on_this_commit"),
     (lambda a, r: a.update(required_free_bytes=10**18), "preservation_target_ready"),
     (lambda a, r: a.update(environment={**a["environment"], "COPREPAN_PRESERVATION_ROOT": ""}), "preservation_target_ready"),
     (lambda a, r: a.update(environment={k: v for k, v in a["environment"].items() if "WORKSPACE" not in k}), "runtime_workspace_configured"),
     (lambda a, r: a.update(approved_baseline={**a["approved_baseline"], "operator": "someone else"}), "no_configuration_drift"),
     (lambda a, r: a.update(code_commit="1" * 40, tests_commit="1" * 40), "no_configuration_drift")],
)
def test_any_single_missing_precondition_closes_the_gate(ready, break_it, check):
    repository, arguments = ready
    arguments = dict(arguments)
    break_it(arguments, repository)
    report = CN.preflight(**arguments)
    assert report["status"] == "NOT_READY" and check in failed(report)


@pytest.mark.parametrize(
    "file, change, check",
    [("acquisition_policy.json", lambda d: d["rate_limit"].update(min_interval_seconds_per_origin=1), "no_configuration_drift"),
     ("acquisition_policy.json", lambda d: d.update(external_acquisition="disabled"), "acquisition_policy_decided"),
     ("crawler_identity.json", lambda d: d.update(contact_email="otro@uni-ficticia.es"), "no_configuration_drift"),
     ("crawler_identity.json", lambda d: d.update(contact_email="research@university.edu"), "crawler_identity_configured"),
     ("schedule_policy.json", lambda d: d.update(status="NOT_DECIDED"), "schedule_policy_decided"),
     ("outlet_registry.json", lambda d: d["outlets"][0].update(registration_status="proposed"), "outlet_registered:uy_uno"),
     ("outlet_registry.json", lambda d: d["outlets"][0].update(timezone="unknown"), "outlet_registered:uy_uno"),
     ("candidate_rules.json", lambda d: d["outlets"].update({"uy_uno": {"version": "r1", "reject_path_prefixes": ["/tag"],
                                                                         "reject_path_patterns": [], "allow_path_patterns": []}}),
      "no_configuration_drift")],
)
def test_configuration_changed_after_approval_closes_the_gate(ready, file, change, check):
    repository, arguments = ready
    path = repository / "config" / file
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document), encoding="utf-8")
    report = CN.preflight(**arguments)
    assert report["status"] == "NOT_READY" and check in failed(report)
    assert "no_configuration_drift" in failed(report)  # whatever else fails, the drift from the approved baseline is seen


def test_a_target_that_stops_verifying_closes_the_gate(ready, tmp_path):
    repository, arguments = ready
    (tmp_path / "preservation" / PT.MARKER_NAME).write_text("{broken", encoding="utf-8")
    report = CN.preflight(**arguments)
    assert "preservation_target_ready" in failed(report) and "target_identity" in next(
        c["detail"] for c in report["checks"] if c["check"] == "preservation_target_ready")
