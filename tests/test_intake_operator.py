"""The intake's operator tool and report, offline (CPD-0029): the authorisation it starts under, what it pins and
re-checks, how it disarms, and the whole of a tick — controller, finalizer, report, disarming, removal of the task —
against a real temporary git repository and the scripted loopback outlet of ``test_intake``.

It arms nothing real and registers no task: the scheduled task is a recorder here. A pass is not the real pilot.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from coprepan import intake as I, intake_report as R
from coprepan.canonical import record_json, sha256_bytes
from test_fetcher import OUTLET, WWW
from test_intake import BUDGET, STOCK, T0, Bench, make_plan, serve, site  # noqa: F401 - `site` is a fixture

REPO = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 10)
PLAN_PATH, RECORD_PATH = "config/intake/plans/in1-test.json", "config/intake/authorizations/2026-10-10_test.json"


def load_tool():
    spec = importlib.util.spec_from_file_location("intake_operator_under_test", REPO / "scripts" / "intake_operator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def git(repository, *arguments):
    return subprocess.run(["git", *arguments], cwd=repository, text=True, capture_output=True, check=True).stdout.strip()


def record_for(plan, **changes):
    record = {"schema": I.AUTHORIZATION_SCHEMA, "authorization_id": "DIA-TEST-1", "kind": I.MODE_DELEGATED_INTAKE, "issued_on": "2026-10-10",
              "issued_by": "An Operator", "issued_to": "an agent", "source": {"commission": "a test commission"}, "valid_until": "2026-10-11",
              "policy_versions": [plan["policy_version"]], "conditions": ["a test"],
              "intake": {"intake_id": plan["intake_id"], "plan": PLAN_PATH, "plan_sha256": sha256_bytes(record_json(plan)),
                         "ceilings": {"duration_seconds": 86400, "item_requests_per_outlet": 120, "item_requests_per_outlet_hour": 10,
                                      "item_requests_per_origin": 150, "total_requests": 12000}, "excluded_outlets": ["es_el_pais", "co_el_tiempo"]}}
    record.update(changes)
    return record


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(name, "A Tester")
    for name in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(name, "tester@example.test")
    remote, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    git(work, "checkout", "-q", "-b", "main")
    git(work, "config", "core.autocrlf", "false")
    (work / "config" / "intake" / "plans").mkdir(parents=True)
    (work / "config" / "intake" / "authorizations").mkdir(parents=True)
    for name in ("outlet_registry.json", "candidate_rules.json", "acquisition_policy.json", "schedule_policy.json", "crawler_identity.json"):
        shutil.copyfile(REPO / "config" / name, work / "config" / name)
    tool.O.set_switch("enabled", work / "config" / "acquisition_policy.json")          # an intake is running: the tree is armed
    plan = make_plan()
    (work / PLAN_PATH).write_bytes(record_json(plan))
    (work / RECORD_PATH).write_bytes(record_json(record_for(plan)))
    (work / "src").mkdir()
    (work / "src" / "code.py").write_text("x = 1\n", encoding="utf-8")
    (work / "docs").mkdir()
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "armed")
    git(work, "push", "-q", "origin", "main")
    baseline = {name: {"path": f"config/{file}", "sha256": sha256_bytes((work / "config" / file).read_bytes())} for name, file in (
        ("registry", "outlet_registry.json"), ("policy", "acquisition_policy.json"), ("crawler_identity", "crawler_identity.json"),
        ("schedule_policy", "schedule_policy.json"), ("candidate_rules", "candidate_rules.json"))}
    return SimpleNamespace(work=work, remote=remote, plan=plan, baseline=baseline, run=tool.make_runner(work), pinned=git(work, "rev-parse", "HEAD"))


def states(world) -> dict:
    switch = tool.O.switch_state
    return {"file": switch((world.work / "config" / "acquisition_policy.json").read_text(encoding="utf-8")),
            "HEAD": switch(git(world.work, "show", "HEAD:config/acquisition_policy.json")),
            "origin": switch(subprocess.run(["git", "show", "main:config/acquisition_policy.json"], cwd=world.remote, text=True, capture_output=True, check=True).stdout)}


# --- the authorisation -----------------------------------------------------------------------------------------


def test_an_authorisation_covers_exactly_one_plan_within_its_ceilings_and_its_days():
    plan = make_plan()
    record = record_for(plan)
    check = lambda r=record, p=plan, **k: I.check_authorization(r, p, **{"plan_path": PLAN_PATH, "policy_version": plan["policy_version"], "today": TODAY, **k})  # noqa: E731
    check()
    for changed, said in ((dict(today=TODAY + timedelta(days=2)), "valid from"), (dict(today=TODAY - timedelta(days=1)), "valid from"),
                          (dict(policy_version="other/1"), "does not hold under"), (dict(plan_path="config/intake/plans/other.json"), "another plan file")):
        with pytest.raises(I.IntakeStopped, match=said):
            check(**changed)
    bigger = make_plan(I.IntakeBudget(**{**BUDGET.as_record(), "total_requests": 12001}))
    with pytest.raises(I.IntakeStopped, match="digest"):
        check(p=bigger)
    with pytest.raises(I.IntakeStopped, match="exceeds the authorised ceiling of: total_requests"):
        check(r=record_for(bigger), p=bigger)
    with pytest.raises(I.IntakeStopped, match="excludes"):
        check(r={**record, "intake": {**record["intake"], "excluded_outlets": [OUTLET]}})
    for broken in ({**record, "kind": "DELEGATED_OPERATOR_AUTHORIZATION"}, {k: v for k, v in record.items() if k != "conditions"}, {**record, "force": True},
                   {**record, "source": {}}, {**record, "intake": {**record["intake"], "ceilings": {"total_requests": 5}}}, {**record, "valid_until": "soon"}):
        with pytest.raises(I.IntakeStopped):
            I.validate_authorization(broken)


def test_a_record_and_its_plan_are_files_committed_exactly_once(world):
    record, plan, plan_relative, block = tool.authorized_plan(world.run, world.work, world.work / RECORD_PATH, TODAY)
    assert plan == world.plan and plan_relative == PLAN_PATH
    assert block == {"mode": I.MODE_DELEGATED_INTAKE, "authorization_id": "DIA-TEST-1", "record": RECORD_PATH, "issued_by": "An Operator", "issued_to": "an agent",
                     "intake_id": "in1-test", "record_sha256": sha256_bytes((world.work / RECORD_PATH).read_bytes())}
    (world.work / PLAN_PATH).write_bytes(record_json({**plan, "left_out": {"x": "y"}}))
    git(world.work, "commit", "-q", "-am", "the plan was changed")
    with pytest.raises(tool.Stop, match="a plan is written once"):
        tool.authorized_plan(world.run, world.work, world.work / RECORD_PATH, TODAY)
    with pytest.raises(tool.Stop, match="lies in"):
        tool.authorized_plan(world.run, world.work, world.work / PLAN_PATH, TODAY)


# --- what is checked again and again -----------------------------------------------------------------------------


def test_the_permission_is_read_from_disk_every_time_and_ends_with_the_switch_or_any_pinned_file(world):
    permitted = tool.permission(world.work, world.baseline, world.work / PLAN_PATH, sha256_bytes(record_json(world.plan)))
    assert permitted() is None
    rules = world.work / "config" / "candidate_rules.json"
    kept = rules.read_bytes()
    rules.write_bytes(kept + b"\n")
    assert "candidate_rules.json is not the file the baseline pins" in permitted()
    rules.write_bytes(kept)
    (world.work / PLAN_PATH).write_bytes(record_json({**world.plan, "left_out": {"x": "y"}}))
    assert "not the plan the intake was started with" in permitted()
    (world.work / PLAN_PATH).write_bytes(record_json(world.plan))
    assert permitted() is None
    tool.O.set_switch("disabled", world.work / "config" / "acquisition_policy.json")
    assert permitted() == "external_acquisition is `disabled` in the policy file"


def test_the_code_of_a_restart_is_the_pinned_code_and_documents_may_have_moved_on(world):
    assert tool.code_unchanged(world.run, world.pinned) is None
    (world.work / "docs" / "launch.md").write_text("launched\n", encoding="utf-8")
    git(world.work, "add", "--", "docs/launch.md")
    git(world.work, "commit", "-q", "-m", "launch report")
    assert tool.code_unchanged(world.run, world.pinned) is None
    (world.work / "src" / "code.py").write_text("x = 2\n", encoding="utf-8")
    assert "beyond documents" in tool.code_unchanged(world.run, world.pinned)                # modified, not committed
    git(world.work, "commit", "-q", "-am", "code changed")
    assert "src/code.py" in tool.code_unchanged(world.run, world.pinned)


# --- disarming ---------------------------------------------------------------------------------------------------


def test_disarming_commits_the_one_switch_and_nothing_else_and_reads_the_state_back(world):
    (world.work / "docs" / "note.md").write_text("someone's work in progress\n", encoding="utf-8")
    git(world.work, "add", "--", "docs/note.md")                                               # staged by someone else, not by the intake
    (world.work / "src" / "code.py").write_text("x = 3\n", encoding="utf-8")                  # modified, unstaged
    assert tool.disarm(world.run, world.work, "in1-test") == []
    assert states(world) == {"file": "disabled", "HEAD": "disabled", "origin": "disabled"}
    assert git(world.work, "show", "--name-only", "--format=%s", "HEAD").splitlines() == ["Disarm after the intake in1-test: external_acquisition disabled", "",
                                                                                         "config/acquisition_policy.json"]
    assert git(world.work, "status", "--porcelain").splitlines() == ["A  docs/note.md", " M src/code.py"]    # as they were
    assert tool.disarm(world.run, world.work, "in1-test") == []                                 # again: nothing to do, nothing wrong


def test_a_refused_push_is_reported_and_never_forced_and_the_file_is_off_all_the_same(world, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(world.remote), str(other)], check=True, capture_output=True)
    (other / "theirs.md").write_text("someone else's commit\n", encoding="utf-8")
    git(other, "add", "-A")
    git(other, "-c", "user.name=B", "-c", "user.email=b@example.test", "commit", "-q", "-m", "theirs")
    git(other, "push", "-q", "origin", "main")
    theirs = git(other, "rev-parse", "HEAD")
    problems = tool.disarm(world.run, world.work, "in1-test")
    assert any(text.startswith("the push") for text in problems) and "origin/main still says `enabled`" in problems
    assert states(world)["file"] == "disabled" and states(world)["HEAD"] == "disabled"
    assert subprocess.run(["git", "rev-parse", "main"], cwd=world.remote, text=True, capture_output=True, check=True).stdout.strip() == theirs    # nothing of theirs was overwritten


def test_off_main_the_switch_is_turned_off_in_the_file_and_nothing_is_committed(world):
    git(world.work, "checkout", "-q", "-b", "elsewhere")
    head = git(world.work, "rev-parse", "HEAD")
    problems = tool.disarm(world.run, world.work, "in1-test")
    assert any("not on main" in text for text in problems) and states(world)["file"] == "disabled" and git(world.work, "rev-parse", "HEAD") == head


# --- a start that must not happen -------------------------------------------------------------------------------


def test_a_start_is_refused_before_anything_is_armed(world, capsys):
    arguments = SimpleNamespace(authorization=world.work / RECORD_PATH)
    assert tool.command_start(arguments, world.work, world.run, today=TODAY) == 1                # the tree is armed already
    assert "the switch is `enabled`" in capsys.readouterr().out and states(world)["HEAD"] == "enabled"   # and it was not this tool that would disarm another's run
    tool.disarm(world.run, world.work, "x")
    (world.work / "docs" / "dirty.md").write_text("x\n", encoding="utf-8")
    assert tool.command_start(arguments, world.work, world.run, today=TODAY) == 1
    assert "not clean" in capsys.readouterr().out and states(world)["file"] == "disabled"


# --- a whole tick ------------------------------------------------------------------------------------------------


def test_a_tick_is_the_controller_then_the_finalizer_and_it_disarms_and_removes_the_task(world, tmp_path, site):  # noqa: F811
    serve(site, [STOCK, STOCK + [("/n10", T0 + timedelta(hours=1, minutes=5))]])
    bench = Bench(tmp_path / "bench", site, plan=world.plan)
    runtime = bench.workspace.root
    state_dir = tool.state_directory(runtime, "in1-test")
    state = I.initial_state(world.plan, started_at=bench.clock(), baseline={"manifest_sha256": "b" * 64, "file": "docs/baseline.json", "pinned_commit": world.pinned,
                                                                              "plan": PLAN_PATH, "authorization": {}, "tests_passed": 1, "preflight": "READY"})
    state["disarmed"] = None
    I.write_state(state_dir, state)
    (world.work / "docs" / "baseline.json").write_bytes(record_json(world.baseline))
    git(world.work, "add", "--", "docs/baseline.json")
    git(world.work, "commit", "-q", "-m", "baseline")
    git(world.work, "push", "-q", "origin", "main")
    removed = []
    arguments = SimpleNamespace(intake="in1-test")
    loader = lambda repository: (bench.environment, {"RUNTIME": runtime})  # noqa: E731
    assert tool.command_tick(arguments, world.work, world.run, unregister=lambda intake_id: removed.append(intake_id), loader=loader) == 0
    final = I.read_state(state_dir)
    assert final["status"] == I.COMPLETED and final["finalized"]["verification"] == "PASS" and final["disarmed"]["clean"] is True
    assert states(world) == {"file": "disabled", "HEAD": "disabled", "origin": "disabled"} and removed == ["in1-test"]
    report = state_dir / "report"
    assert sorted(path.name for path in report.iterdir()) == ["FINAL_REPORT.md", "measurement.json", "plan.json", "receipt.json", "review_package.json", "state.json"]
    measurement = json.loads((report / "measurement.json").read_text(encoding="utf-8"))
    receipt = json.loads((report / "receipt.json").read_text(encoding="utf-8"))
    outlet = measurement["outlets"][OUTLET]
    assert outlet["items_requested"] == receipt["requests"]["item"] == len(bench.items()) and outlet["items_2xx"] == receipt["item_pages_2xx"]
    assert outlet["items_2xx_by_novelty"][I.NEW_IN_WINDOW] == 1 and measurement["totals"]["new_dated_in_window_2xx"] == 1          # /n10, and only it
    assert outlet["candidates_first_listed_in_the_intake"] == {I.FIRST_POLL_UNDATED: 2, I.NEW_IN_WINDOW: 1, I.OLDER: 2}
    assert outlet["channels"][f"{OUTLET}:ch:rss_001"]["polls"] == 4 and measurement["countries"]["uy"]["outlets"] == 1
    text = (report / "FINAL_REPORT.md").read_text(encoding="utf-8")
    assert "Outcome: **COMPLETED**" in text and "Verification: **PASS**" in text and "`disabled` in the file, in HEAD and on origin/main" in text
    package = json.loads((report / "review_package.json").read_text(encoding="utf-8"))
    assert package["pages"] == min(R.REVIEW_PER_OUTLET, outlet["items_2xx"]) and all(set(row["human_review"].values()) == {None} for row in package["sample"])
    requests = len(site.requests)
    assert tool.command_tick(arguments, world.work, world.run, unregister=lambda intake_id: removed.append(intake_id), loader=loader) == 0     # a late tick: nothing left to do
    assert len(site.requests) == requests and removed == ["in1-test", "in1-test"] and R.review_package(measurement) == package


def test_a_tick_on_changed_code_blocks_the_intake_makes_no_request_and_still_disarms(world, tmp_path, site):  # noqa: F811
    serve(site, [STOCK])
    bench = Bench(tmp_path / "bench", site, plan=world.plan)
    state_dir = tool.state_directory(bench.workspace.root, "in1-test")
    state = I.initial_state(world.plan, started_at=bench.clock(), baseline={"manifest_sha256": "b" * 64, "file": "docs/baseline.json", "pinned_commit": world.pinned,
                                                                              "plan": PLAN_PATH, "authorization": {}, "tests_passed": 1, "preflight": "READY"})
    I.write_state(state_dir, {**state, "disarmed": None})
    (world.work / "docs" / "baseline.json").write_bytes(record_json(world.baseline))
    (world.work / "src" / "code.py").write_text("x = 9\n", encoding="utf-8")
    git(world.work, "add", "-A")
    git(world.work, "commit", "-q", "-m", "baseline, and a change of code under a running intake")
    git(world.work, "push", "-q", "origin", "main")
    assert tool.command_tick(SimpleNamespace(intake="in1-test"), world.work, world.run, unregister=lambda intake_id: None,
                             loader=lambda repository: (bench.environment, {"RUNTIME": bench.workspace.root})) == 0
    final = I.read_state(state_dir)
    assert site.requests == [] and final["status"] == I.BLOCKED and "beyond documents" in final["stopped_because"]
    assert states(world) == {"file": "disabled", "HEAD": "disabled", "origin": "disabled"}


# --- the flags ---------------------------------------------------------------------------------------------------


def test_a_flag_is_a_mechanical_hint_from_the_url_and_the_extraction():
    label = lambda characters, *reasons: {"measurements": {"body_characters": characters}, "reasons": [{"reason": name} for name in reasons]}  # noqa: E731
    article = f"{WWW}/politica/2026/10/10/el-congreso-aprueba-la-ley.html"
    assert R.flags_of(article, 200, label(3200)) == []
    assert R.flags_of(article, 404, None) == ["not_a_2xx_answer"]
    assert R.flags_of(article, 200, label(120)) == ["very_short_text"] and R.flags_of(article, 200, label(0, "no_body_text")) == ["empty_extraction"]
    assert R.flags_of(article, 200, label(900, "not_extractable", "no_title")) == ["extractor_error", "no_title"]
    assert R.flags_of(f"{WWW}/autor/maria-perez/", 200, label(900)) == ["author_page_url"]
    assert R.flags_of(f"{WWW}/seccion/politica", 200, label(900)) == ["section_or_listing_url"]
    assert R.flags_of(f"{WWW}/videos/2026/10/el-discurso-completo", 200, label(900)) == ["gallery_or_video_url"]
    assert R.flags_of(f"{WWW}/contenido-patrocinado/2026/una-marca-presenta", 200, label(900)) == ["sponsored_url"]
    assert R.flags_of(f"{WWW}/deportes", 200, label(900)) == ["front_or_top_level_page_url"] and R.flags_of(article, 200, None) == ["no_label"]
