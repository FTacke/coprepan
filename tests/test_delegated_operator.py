"""The delegated operator authorisation (CPD-0023): the record, the check, and the operator tool's delegated mode.

The record and its check are tested as functions. The tool is run end to end against the temporary git repository
and bare remote of ``test_canary_operator`` with the same recorders — no request, nothing real armed. What is shown:
the delegated mode asks nothing and reads nothing typed; it takes the outlets from the record; it refuses a record
that is not written once, a scope the record does not cover, a used wave; every failure still ends disarmed; and the
interactive mode is unchanged and cannot be given a record on the side.

A pass here is not the real integration test: the driver and the preflight are recorders.
"""

from __future__ import annotations

import copy
import io
import json
from datetime import date

import pytest

import test_canary_operator as harness
from coprepan import canary_driver, delegation
from coprepan.canonical import sha256_bytes
from test_canary_operator import world  # noqa: F401  (the fixture: a temporary repository with a bare remote)

tool, git, OUTLETS, TODAY, DIGEST, RUN_ID = harness.tool, harness.git, harness.OUTLETS, harness.TODAY, harness.DIGEST, harness.RUN_ID
RECORD = "config/operator_authorizations/test-record.json"
PROPOSAL = "config/registry_review/a-proposal.json"
FIVE = canary_driver.canary_budget(5)
LIMITS = {"item_requests_total": 80, "item_requests_per_outlet": 16, "other_requests_per_outlet": 8, "total_requests_ceiling": 120}


def a_record(**changes) -> dict:
    record = {
        "schema": delegation.AUTHORIZATION_SCHEMA, "authorization_id": "DOA-TEST-1", "kind": delegation.MODE_DELEGATED,
        "issued_on": "2026-10-09", "issued_by": "An Operator", "issued_to": "an agent", "valid_until": "2026-10-11",
        "source": {"form": "a brief", "authorising_clauses": ["the brief says so"]}, "policy_versions": ["canary/2026-10-09.1"],
        "actions_authorized": ["one canary per wave"], "not_authorized": ["anything else"], "holds_in_force": [],
        "technical_gates": ["all of them"], "stop_conditions": ["any gate not met"], "disarming": "always, read back", "decisions": [],
        "waves": [{"label": "wave-t", "outlets": list(OUTLETS), "registration": None, "limits": dict(LIMITS), "canaries": 1, "note": ""},
                  {"label": "wave-r", "outlets": list(OUTLETS), "limits": dict(LIMITS), "canaries": 1, "note": "",
                   "registration": {"proposal": PROPOSAL, "proposal_sha256": sha256_bytes(b"{}\n"), "only": OUTLETS[:2]}}]}
    record.update(changes)
    return record


def checked(record, label="wave-t", **changes):
    arguments = {"outlets": OUTLETS, "budget": FIVE.as_record(), "total_requests_ceiling": FIVE.total_requests_ceiling,
                 "policy_version": "canary/2026-10-09.1", "today": TODAY, **changes}
    return delegation.check({**record, "_sha256": "s" * 64}, label, **arguments)


# --- the record ---------------------------------------------------------------------------------------------


def test_a_valid_record_validates_and_the_tracked_one_is_valid():
    delegation.validate(a_record())
    for path in sorted((harness.REPO / delegation.RECORDS).glob("*.json")):
        record = delegation.load(path)
        assert record["kind"] == "DELEGATED_OPERATOR_AUTHORIZATION" and record["_sha256"] == sha256_bytes(path.read_bytes())
        for wave in record["waves"]:                         # what a wave may ask never exceeds the hard ceiling of a canary
            assert wave["limits"]["item_requests_total"] <= canary_driver.HARD_ITEM_REQUESTS


@pytest.mark.parametrize("damage", [
    lambda r: r.pop("stop_conditions"), lambda r: r.update(force=True), lambda r: r.update(kind="INTERACTIVE_OPERATOR"),
    lambda r: r.update(schema="coprepan-operator-authorization/v2"), lambda r: r.update(issued_by=" "), lambda r: r.update(valid_until="soon"),
    lambda r: r.update(source={"form": "a brief", "authorising_clauses": []}), lambda r: r.update(policy_versions=[]),
    lambda r: r.update(not_authorized=[1]), lambda r: r.update(disarming=""), lambda r: r.update(waves=[]),
    lambda r: r["waves"][0].update(canaries=2), lambda r: r["waves"][0].update(outlets=[]), lambda r: r["waves"][0].update(outlets=["x", "x"]),
    lambda r: r["waves"][0].update(outlets=["Not An Id"]), lambda r: r["waves"][0]["limits"].update(item_requests_total=-1),
    lambda r: r["waves"][0]["limits"].update(item_requests_total=True), lambda r: r["waves"][0]["limits"].pop("total_requests_ceiling"),
    lambda r: r["waves"][0].update(force=True), lambda r: r["waves"][1].update(label="wave-t"),
    lambda r: r["waves"][1].update(registration={"proposal": PROPOSAL})])
def test_a_damaged_or_widened_record_is_not_an_authorisation(damage):
    record = a_record()
    damage(record)
    with pytest.raises(delegation.AuthorizationError):
        delegation.validate(record)


def test_a_record_that_cannot_be_read_is_refused(tmp_path):
    for content in (b"", b"not json", b"[]", b"\xff\xfe"):
        path = tmp_path / "r.json"
        path.write_bytes(content)
        with pytest.raises(delegation.AuthorizationError):
            delegation.load(path)
    with pytest.raises(delegation.AuthorizationError):
        delegation.load(tmp_path / "absent.json")


# --- the check: exactly this canary, in both directions -----------------------------------------------------


def test_the_check_returns_the_block_a_baseline_pins():
    assert checked(a_record()) == {"mode": "DELEGATED_OPERATOR_AUTHORIZATION", "authorization_id": "DOA-TEST-1", "authorization_sha256": "s" * 64,
                                   "wave": "wave-t", "issued_by": "An Operator", "issued_to": "an agent"}


@pytest.mark.parametrize("changes, said", [
    ({"outlets": [*OUTLETS, "bo_pagina_siete"]}, "not authorised: ['bo_pagina_siete']"),
    ({"outlets": OUTLETS[:4]}, "missing: ['ve_efecto_cocuyo']"),
    ({"outlets": [*OUTLETS[:4], "co_el_tiempo"]}, "co_el_tiempo"),
    ({"budget": {**FIVE.as_record(), "item_requests_per_outlet": 17}}, "exceeds the authorised limits"),
    ({"budget": {**FIVE.as_record(), "item_requests_total": 81}}, "exceeds the authorised limits"),
    ({"budget": {**FIVE.as_record(), "other_requests_per_outlet": 9}}, "exceeds the authorised limits"),
    ({"total_requests_ceiling": 121}, "exceeds the authorised limits"),
    ({"policy_version": "canary/2026-10-08.1"}, "is not one the authorisation names"),
    ({"today": date(2026, 10, 12)}, "valid from"), ({"today": date(2026, 10, 8)}, "valid from"),
    ({"waves_used": ["wave-t"]}, "has a frozen baseline already")])
def test_a_canary_the_record_does_not_cover_is_refused_with_the_reason(changes, said):
    with pytest.raises(delegation.AuthorizationError, match=said.replace("[", r"\[").replace("]", r"\]")):
        checked(a_record(), **changes)


def test_an_unknown_wave_is_refused_and_a_smaller_budget_is_covered():
    with pytest.raises(delegation.AuthorizationError, match="names no wave"):
        checked(a_record(), label="wave-x")
    assert checked(a_record(), budget={**FIVE.as_record(), "item_requests_per_outlet": 10, "item_requests_total": 50})["wave"] == "wave-t"


def test_a_wave_is_used_by_a_frozen_baseline_that_pins_it_and_not_by_the_baseline_being_run():
    baselines = [{"manifest_sha256": "a" * 64, "canary": {"authorization": {"authorization_id": "DOA-TEST-1", "wave": "wave-t"}}},
                 {"manifest_sha256": "b" * 64, "canary": {"authorization": {"authorization_id": "DOA-OTHER", "wave": "wave-r"}}},
                 {"manifest_sha256": "c" * 64, "canary": {}}, {"manifest_sha256": "d" * 64}]
    assert delegation.waves_used(baselines, "DOA-TEST-1") == ["wave-t"]
    assert delegation.waves_used(baselines, "DOA-TEST-1", except_manifest="a" * 64) == []
    assert delegation.waves_used(baselines, "DOA-NONE") == []


def test_the_block_is_built_only_from_a_record_in_its_place_and_a_damaged_baseline_is_not_an_absent_one(tmp_path):
    home = tmp_path / delegation.RECORDS
    home.mkdir(parents=True)
    (home / "r.json").write_text(json.dumps(a_record()), encoding="utf-8")
    (tmp_path / "elsewhere.json").write_text(json.dumps(a_record()), encoding="utf-8")
    arguments = {"repository": tmp_path, "outlets": OUTLETS, "budget": FIVE.as_record(), "total_requests_ceiling": FIVE.total_requests_ceiling,
                 "policy_version": "canary/2026-10-09.1", "today": TODAY}
    block = delegation.block_for(home / "r.json", "wave-t", **arguments)
    assert block["record"] == f"{delegation.RECORDS}/r.json" and block["authorization_sha256"] == sha256_bytes((home / "r.json").read_bytes())
    with pytest.raises(delegation.AuthorizationError, match="lies in"):
        delegation.block_for(tmp_path / "elsewhere.json", "wave-t", **arguments)
    frozen = tmp_path / "docs" / "canary"
    frozen.mkdir(parents=True)
    (frozen / "BASELINE_FROZEN_2026-10-10_wave-t.json").write_text(json.dumps({"manifest_sha256": "a" * 64, "canary": {"authorization": block}}), encoding="utf-8")
    with pytest.raises(delegation.AuthorizationError, match="frozen baseline already"):
        delegation.block_for(home / "r.json", "wave-t", **arguments)
    assert delegation.block_for(home / "r.json", "wave-t", **arguments, except_manifest="a" * 64) == block      # the run under that baseline
    (frozen / "BASELINE_FROZEN_2026-10-10_x.json").write_text("{", encoding="utf-8")
    with pytest.raises(delegation.AuthorizationError, match="not readable"):
        delegation.block_for(home / "r.json", "wave-r", **arguments)


# --- the driver: the block is a pin like any other -------------------------------------------------------------


def test_the_driver_states_who_armed_from_the_frozen_baseline_only():
    block = {"mode": delegation.MODE_DELEGATED, "authorization_id": "DOA-TEST-1", "wave": "wave-t"}
    assert canary_driver._operator_authorization({"canary": {"authorization": block}, "freeze": {"operator": "x"}}) == block
    assert canary_driver._operator_authorization({"canary": {}, "freeze": {"operator": "A Person"}}) == {
        "mode": "INTERACTIVE_OPERATOR", "operator": "A Person"}


def test_the_driver_stops_when_the_record_does_not_cover_the_canary(tmp_path, monkeypatch):
    home = tmp_path / delegation.RECORDS
    home.mkdir(parents=True)
    (home / "r.json").write_text(json.dumps(a_record()), encoding="utf-8")
    monkeypatch.setattr(canary_driver, "CHECKOUT", tmp_path)
    policy = {"policy_version": "canary/2026-10-09.1"}
    monkeypatch.setattr(canary_driver, "datetime", type("Fixed", (), {"now": staticmethod(lambda tz=None: __import__("datetime").datetime(2026, 10, 10, tzinfo=tz))}))
    assert canary_driver._authorization(home / "r.json", "wave-t", FIVE, OUTLETS, policy)["wave"] == "wave-t"
    with pytest.raises(canary_driver.CanaryStopped, match="does not cover this canary"):
        canary_driver._authorization(home / "r.json", "wave-t", FIVE, OUTLETS[:4], policy)
    with pytest.raises(canary_driver.CanaryStopped, match="does not cover this canary"):
        canary_driver._authorization(home / "r.json", "wave-t", FIVE, OUTLETS, {"policy_version": "production/1"})
    # a record edited after the baseline was frozen has another digest: the pinned block no longer equals the one re-derived
    before = canary_driver._authorization(home / "r.json", "wave-t", FIVE, OUTLETS, policy)
    (home / "r.json").write_text(json.dumps(a_record(valid_until="2026-12-31")), encoding="utf-8")
    assert canary_driver._authorization(home / "r.json", "wave-t", FIVE, OUTLETS, policy) != before


# --- a wave's limits cap the budget (CPD-0024) ------------------------------------------------------------------


def test_a_waves_limits_can_only_lower_the_budget_and_allow_a_canary_smaller_than_five():
    budget = canary_driver.canary_budget
    wave_b = {"item_requests_total": 100, "item_requests_per_outlet": 12, "other_requests_per_outlet": 8, "total_requests_ceiling": 164}
    wave_c1 = {"item_requests_total": 90, "item_requests_per_outlet": 10, "other_requests_per_outlet": 8, "total_requests_ceiling": 162}
    assert budget(8, wave_b) == budget(8) and budget(9, wave_c1) == budget(9)               # the waves already run: the same budget
    two = budget(2, {"item_requests_total": 20, "item_requests_per_outlet": 10, "other_requests_per_outlet": 8, "total_requests_ceiling": 36})
    assert (two.outlets, two.item_requests_per_outlet, two.item_requests_total, two.other_requests_per_outlet, two.total_requests_ceiling) == (2, 10, 20, 8, 36)
    generous = {"item_requests_total": 10_000, "item_requests_per_outlet": 500, "other_requests_per_outlet": 99, "total_requests_ceiling": 99_999}
    for outlets in range(1, 25):                                                               # a generous wave raises nothing
        capped = budget(outlets, generous)
        assert capped.item_requests_per_outlet <= 16 and capped.item_requests_total <= canary_driver.HARD_ITEM_REQUESTS and capped.other_requests_per_outlet == 8
    tight = budget(5, {"item_requests_total": 7, "item_requests_per_outlet": 3, "other_requests_per_outlet": 2, "total_requests_ceiling": 17})
    assert (tight.item_requests_per_outlet, tight.item_requests_total, tight.other_requests_per_outlet, tight.expansion_requests_reserved_per_outlet) == (3, 7, 2, 2)
    for outlets in (0, 25):
        with pytest.raises(canary_driver.CanaryStopped):
            budget(outlets, generous)
    for outlets in (1, 2, 4, 16):                                                              # without a wave nothing changed: five, or six to fifteen
        with pytest.raises(canary_driver.CanaryStopped):
            budget(outlets)
    # the tracked records: every wave's capped budget is covered by its own limits
    for path in sorted((harness.REPO / delegation.RECORDS).glob("*.json")):
        for wave in delegation.load(path)["waves"]:
            capped = budget(len(wave["outlets"]), wave["limits"])
            assert all(capped.as_record()[key] <= wave["limits"][key] for key in ("item_requests_total", "item_requests_per_outlet", "other_requests_per_outlet"))
            assert capped.total_requests_ceiling <= wave["limits"]["total_requests_ceiling"]


def test_a_delegated_canary_of_two_outlets_runs_under_its_waves_limits(world):  # noqa: F811
    record = a_record()
    record["waves"].append({"label": "wave-two", "outlets": OUTLETS[:2], "registration": None, "canaries": 1, "note": "",
                            "limits": {"item_requests_total": 20, "item_requests_per_outlet": 10, "other_requests_per_outlet": 8, "total_requests_ceiling": 36}})
    commission(world, record)
    assert delegate(world, wave="wave-two") == 0
    command = world.seen["baseline"][0]["command"]
    assert sorted(command[i + 1] for i, word in enumerate(command) if word == "--outlet") == sorted(OUTLETS[:2])
    harness.assert_disarmed(world)
    world.calls.clear()
    assert harness.operate(world, outlets=OUTLETS[:2]) == 1 and world.calls == []                # interactively, two outlets are still not a canary


# --- the operator tool, delegated ------------------------------------------------------------------------------


def commission(world, record=None, proposal=b"{}\n", push=True):  # noqa: F811
    """Commit an authorisation record (and the proposal a wave names) to the temporary repository, once."""
    for relative, content in ((RECORD, json.dumps(record or a_record(), indent=1).encode("utf-8")), (PROPOSAL, proposal)):
        path = world.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    git(world.work, "add", "--", RECORD, PROPOSAL)
    git(world.work, "commit", "-q", "-m", "the commission")
    if push:
        git(world.work, "push", "-q", "origin", "main")


def forget_manifests(world):  # noqa: F811
    """A stopped run leaves its unfrozen manifest in the runtime workspace (built once per label and day): a test that starts again removes it."""
    for path in world.scratch.glob("baseline-*.json"):
        path.unlink()


def delegate(world, wave="wave-t", stdin=None, extra=(), **fakes):  # noqa: F811
    return tool.main(["--authorization", str(world.work / RECORD), "--wave", wave, *extra], repository=world.work, scratch=world.scratch,
                     stdin=stdin if stdin is not None else io.StringIO(""), runner=harness.fake_runner(world, **fakes), today=TODAY)


def test_the_delegated_workflow_runs_the_same_steps_without_a_prompt_and_says_who_armed(world, capsys):  # noqa: F811
    commission(world)
    before = git(world.work, "rev-parse", "HEAD")
    assert delegate(world) == 0                                     # stdin is not a terminal and is empty: nothing was asked
    assert world.calls == ["tests", "baseline", "freeze", "preflight", "run", "verify", "measure", "tests"]
    subjects = git(world.work, "log", "--format=%s", "--reverse", f"{before}..HEAD").splitlines()
    by = " under DOA-TEST-1 (DELEGATED_OPERATOR_AUTHORIZATION, no typed confirmation)"
    assert subjects == ["Arm the wave-t canary: external_acquisition enabled (CPD-0016)" + by, "Baseline of the wave-t canary frozen (O-12, canary scope)" + by,
                        f"Evidence of the wave-t canary {RUN_ID}" + by, "Disarm after the canary: external_acquisition disabled"]
    pinned = git(world.work, "rev-list", "--reverse", f"{before}..HEAD").splitlines()[0]
    seen = world.seen
    assert seen["tests"][0]["head"] == pinned and seen["tests"][0]["file"] == "enabled" and seen["tests"][1]["file"] == "disabled"
    command = seen["baseline"][0]["command"]
    # the outlets are the record's; the operator named is the delegate under the record, never a person
    assert sorted(command[i + 1] for i, word in enumerate(command) if word == "--outlet") == sorted(OUTLETS)
    assert command[command.index("--wave") + 1] == "wave-t" and command[command.index("--commit") + 1] == pinned
    operator = command[command.index("--operator") + 1]
    assert operator == "an agent under DOA-TEST-1 (DELEGATED_OPERATOR_AUTHORIZATION; issued by An Operator)"
    frozen = json.loads((world.work / "docs" / "canary" / "BASELINE_FROZEN_2026-10-10_wave-t.json").read_text(encoding="utf-8"))
    assert frozen["freeze"]["operator"] == operator
    assert frozen["canary"]["authorization"] == {
        "mode": "DELEGATED_OPERATOR_AUTHORIZATION", "authorization_id": "DOA-TEST-1", "wave": "wave-t", "issued_by": "An Operator",
        "issued_to": "an agent", "record": RECORD, "authorization_sha256": sha256_bytes((world.work / RECORD).read_bytes())}
    harness.assert_disarmed(world)
    out = capsys.readouterr().out
    assert "Type ARM" not in out and "Type the digest" not in out
    assert "delegated mode" in out and "Freezing baseline " + DIGEST in out and "Tests on the disarmed tree: 1400 passed." in out


def test_a_wave_is_one_canary_and_a_second_start_is_refused_before_anything_is_armed(world):  # noqa: F811
    commission(world)
    assert delegate(world) == 0
    world.calls.clear()
    commits = git(world.work, "rev-list", "--count", "HEAD")
    assert delegate(world) == 1                                                       # same day: the baseline file exists
    later = tool.main(["--authorization", str(world.work / RECORD), "--wave", "wave-t"], repository=world.work, scratch=world.scratch,
                      stdin=io.StringIO(""), runner=harness.fake_runner(world), today=date(2026, 10, 11))
    assert later == 1                                                                 # another day: the frozen baseline pins the wave
    assert world.calls == [] and git(world.work, "rev-list", "--count", "HEAD") == commits
    harness.assert_disarmed(world)


@pytest.mark.parametrize("step", ["tests", "baseline", "freeze", "preflight", "run", "verify", "measure"])
def test_whichever_step_fails_the_delegated_run_ends_disarmed(world, step):  # noqa: F811
    commission(world)
    status = delegate(world, fail={step})
    assert status == 1
    harness.assert_disarmed(world)
    if step in ("tests", "baseline", "freeze"):
        assert "run" not in world.calls and "preflight" not in world.calls


def test_failing_tests_an_interruption_an_incomplete_run_and_git_trouble_are_handled_as_in_the_interactive_mode(world, capsys):  # noqa: F811
    commission(world)
    assert delegate(world, tests_output="2 failed, 1398 passed in 3.0s") == 1
    assert world.calls == ["tests", "tests"]                                          # no baseline, no request
    harness.assert_disarmed(world)
    world.calls.clear()
    assert delegate(world, interrupt="run") == 1
    harness.assert_disarmed(world)


def test_an_incomplete_delegated_run_keeps_its_evidence(world):  # noqa: F811
    commission(world)
    assert delegate(world, incomplete_receipt=True) == 1
    assert (world.work / "docs" / "canary" / "evidence" / RUN_ID / f"canary-receipt-{RUN_ID}.json").is_file()
    harness.assert_disarmed(world)


def test_a_failed_push_stops_and_an_unpushable_disarming_exits_2_and_is_recovered_by_disarm_only(world, capsys):  # noqa: F811
    commission(world)
    assert delegate(world, fail={"push1"}) == 1
    assert "preflight" not in world.calls and "run" not in world.calls
    harness.assert_disarmed(world)


def test_when_the_delegated_disarming_cannot_be_pushed_the_tool_exits_2_and_disarm_only_recovers(world, capsys):  # noqa: F811
    commission(world)
    assert delegate(world, fail={"push-from-2"}) == 2
    assert "NOT DISARMED CLEANLY" in capsys.readouterr().out
    assert harness.states(world)["origin"] == "enabled"
    assert tool.main(["--disarm-only"], repository=world.work, runner=harness.fake_runner(world), today=TODAY) == 0
    harness.assert_disarmed(world)


def test_a_baseline_that_does_not_pin_the_authorisation_is_not_frozen(world):  # noqa: F811
    commission(world)
    for pins in ({}, {"authorization": {"mode": "DELEGATED_OPERATOR_AUTHORIZATION", "authorization_id": "DOA-TEST-1", "wave": "wave-r"}}):
        world.calls.clear()
        assert delegate(world, pins=pins) == 1
        assert world.calls == ["tests", "baseline", "tests"]                         # stopped at the baseline, for that reason
        forget_manifests(world)
        assert not list((world.work / "docs" / "canary").glob("BASELINE_FROZEN_*"))
        harness.assert_disarmed(world)


def test_a_record_that_was_changed_is_untracked_or_lies_elsewhere_is_refused_before_arming(world, capsys):  # noqa: F811
    commission(world)
    commits = lambda: git(world.work, "rev-list", "--count", "HEAD")  # noqa: E731
    # a second commit touches the record: widened limits, pushed — written twice is not written once
    widened = a_record()
    widened["waves"][0]["limits"]["item_requests_total"] = 100
    (world.work / RECORD).write_text(json.dumps(widened, indent=1), encoding="utf-8")
    git(world.work, "commit", "-qam", "a wider commission, by the agent")
    git(world.work, "push", "-q", "origin", "main")
    count = commits()
    assert delegate(world) == 1
    assert "written once" in capsys.readouterr().out and world.calls == [] and commits() == count
    # a record outside its directory, and one that is not tracked
    stray = world.work / "config" / "stray.json"
    stray.write_text(json.dumps(a_record()), encoding="utf-8")
    git(world.work, "add", "--", "config/stray.json")
    git(world.work, "commit", "-q", "-m", "stray")
    git(world.work, "push", "-q", "origin", "main")
    arguments = {"repository": world.work, "scratch": world.scratch, "stdin": io.StringIO(""), "today": TODAY}
    assert tool.main(["--authorization", str(stray), "--wave", "wave-t"], runner=harness.fake_runner(world), **arguments) == 1
    assert tool.main(["--authorization", str(world.work.parent / "outside.json"), "--wave", "wave-t"], runner=harness.fake_runner(world), **arguments) == 1
    assert world.calls == []
    harness.assert_disarmed(world)


def test_an_edited_unpushed_or_invalid_record_is_refused_before_arming(world):  # noqa: F811
    commission(world, push=False)
    assert delegate(world) == 1 and world.calls == []                                 # HEAD is not origin/main: the record is not pushed
    git(world.work, "push", "-q", "origin", "main")
    (world.work / RECORD).write_text(json.dumps(a_record(valid_until="2027-01-01")), encoding="utf-8")
    assert delegate(world) == 1 and world.calls == []                                 # edited in the working tree: not clean
    git(world.work, "checkout", "--", RECORD)
    assert delegate(world, wave="wave-x") == 1 and world.calls == []                  # a wave the record does not name
    harness.assert_disarmed(world)


@pytest.mark.parametrize("change, wave", [
    (lambda r: r["waves"][0].update(outlets=[*OUTLETS[:4], "bo_pagina_siete"]), "wave-t"),               # an outlet that is not registered
    (lambda r: r["waves"][0]["limits"].update(total_requests_ceiling=119), "wave-t"),                # the one limit the cap does not lower (CPD-0024): refused
    (lambda r: r.update(policy_versions=["canary/2020-01-01.1"]), "wave-t"),
    (lambda r: r.update(valid_until="2026-10-09"), "wave-t"),                                      # out of date on the day of the run
    (lambda r: r["waves"][1]["registration"].update(proposal_sha256="0" * 64), "wave-r"),          # another proposal than the one named
    (lambda r: r["waves"][1]["registration"].update(proposal="config/registry_review/absent.json"), "wave-r"),
    (lambda r: r["waves"][1]["registration"].update(only=["bo_pagina_siete"]), "wave-r"),                # registers outside the wave
    (lambda r: r.update(kind="SOMETHING_ELSE"), "wave-t")])
def test_a_scope_the_record_does_not_cover_stops_before_arming(world, change, wave):  # noqa: F811
    record = copy.deepcopy(a_record())
    change(record)
    commission(world, record)
    commits = git(world.work, "rev-list", "--count", "HEAD")
    assert delegate(world, wave=wave) == 1
    assert world.calls == [] and git(world.work, "rev-list", "--count", "HEAD") == commits
    harness.assert_disarmed(world)


def test_a_wave_with_a_registration_runs_when_the_proposal_is_the_one_named(world):  # noqa: F811
    commission(world)
    assert delegate(world, wave="wave-r") == 0
    harness.assert_disarmed(world)


def test_the_delegated_mode_takes_nothing_else_and_offers_no_force(world):  # noqa: F811
    commission(world)
    record = str(world.work / RECORD)
    for arguments in (["--authorization", record], ["--wave", "wave-t"], ["--authorization", record, "--wave", "wave-t", "--outlet", "bo_pagina_siete"],
                      ["--authorization", record, "--wave", "wave-t", "--label", "other"], ["--authorization", record, "--wave", "wave-t", "--operator", "A Person"],
                      ["--authorization", record, "--wave", "wave-t", "--force"], ["--authorization", record, "--wave", "wave-t", "--skip-tests"],
                      ["--authorization", record, "--wave", "wave-t", "--budget", "200"], ["--authorization", record, "--wave", "wave-t", "--confirm", DIGEST],
                      ["--disarm-only", "--wave", "wave-t"]):
        with pytest.raises(SystemExit):
            tool.main(arguments, repository=world.work, scratch=world.scratch, runner=harness.fake_runner(world), today=TODAY)
    assert world.calls == []
    source = (harness.REPO / "scripts" / "canary_operator.py").read_text(encoding="utf-8")
    assert '"--force"' not in source and '"--yes"' not in source and '"--skip' not in source


def test_the_interactive_mode_still_asks_a_person_and_cannot_be_given_a_baseline_that_pins_a_record(world):  # noqa: F811
    commission(world)
    assert harness.operate(world, terminal="") == 1 and world.calls == []                     # no terminal answer: not armed
    block = {"authorization": {"mode": "DELEGATED_OPERATOR_AUTHORIZATION", "authorization_id": "DOA-TEST-1", "wave": "wave-t"}}
    assert harness.operate(world, pins=block) == 1                                            # typed ARM and digest, but the baseline claims a delegation
    assert world.calls == ["tests", "baseline", "tests"]
    harness.assert_disarmed(world)
    world.calls.clear()
    forget_manifests(world)
    assert harness.operate(world) == 0                                                        # and the ordinary interactive run is unchanged
    frozen = json.loads((world.work / "docs" / "canary" / "BASELINE_FROZEN_2026-10-10_second.json").read_text(encoding="utf-8"))
    assert "authorization" not in frozen["canary"] and frozen["freeze"]["operator"] == "A Tester"
    harness.assert_disarmed(world)
