"""The operator's canary workflow, run end to end against a real temporary git repository and a bare remote,
with the driver, the test suite and the preflight replaced by recorders (CPD-0021).

What is tested is the *wrapper*: the order of the steps, which commit is pinned, that the tests run on the
arming commit and again on the disarmed tree, that the digest is shown before it is asked for, that no
confirmation can be passed in, and above all that after **any** failure, interruption or refusal the switch
is `disabled` in the file, in HEAD and on the remote — or the tool says in plain words that it is not and exits 2.

It makes no request and arms nothing real. A pass here is **not** the later real integration test: the
driver, the preflight and the pytest run it replaces are exactly what a first real use exercises.
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIGEST = "ab" * 32
OUTLETS = ["bo_el_deber", "do_diario_libre", "hn_proceso_digital", "py_la_nacion", "ve_efecto_cocuyo"]
TODAY = date(2026, 10, 10)
RUN_ID = "acq1-20261010T100000000000Z-aaaaaaaaaaaa"


def load_tool():
    spec = importlib.util.spec_from_file_location("canary_operator_under_test", REPO / "scripts" / "canary_operator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


class Terminal(io.StringIO):
    def isatty(self):
        return True


def git(repository, *arguments):
    return subprocess.run(["git", *arguments], cwd=repository, text=True, capture_output=True, check=True).stdout.strip()


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
    (work / "config").mkdir()
    for name in ("outlet_registry.json", "candidate_rules.json", "acquisition_policy.json"):
        shutil.copyfile(REPO / "config" / name, work / "config" / name)
    # The temporary repository starts disarmed whatever the checkout's switch says: this suite is also run on the
    # arming commit, where the tracked policy is `enabled` (the operator's run of 2026-10-09 stopped on exactly that).
    tool.set_switch("disabled", work / "config" / "acquisition_policy.json")
    (work / "docs" / "canary").mkdir(parents=True)
    (work / "docs" / "canary" / "RUNBOOK.md").write_text("runbook\n", encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "start")
    git(work, "push", "-q", "origin", "main")
    return type("World", (), {"work": work, "remote": remote, "scratch": tmp_path / "runtime", "calls": [], "seen": {}})()


def switch_in(text: str) -> str:
    return tool.switch_state(text)


def states(world) -> dict:
    return {"file": switch_in((world.work / "config" / "acquisition_policy.json").read_text(encoding="utf-8")),
            "HEAD": switch_in(git(world.work, "show", "HEAD:config/acquisition_policy.json")),
            "origin": switch_in(subprocess.run(["git", "show", "main:config/acquisition_policy.json"], cwd=world.remote, text=True,
                                               capture_output=True, check=True).stdout)}


def fake_runner(world, fail=(), interrupt=None, tests_output="1400 passed, 8 skipped in 1.0s", incomplete_receipt=False, pins=None):
    """Real git in the temporary repository; the driver, the preflight and pytest are recorders."""
    real = tool.make_runner(world.work)
    pushes = [0]

    def run(*command, capture=False):
        if command[0] == "git":
            if command[1] == "push":
                pushes[0] += 1
                name = f"push{pushes[0]}"
                if name in fail or "push-from-2" in fail and pushes[0] >= 2:
                    world.calls.append(name + ":failed")
                    raise tool.Stop(f"git push failed ({name})")
            return real(*command, capture=capture)
        flag = command[command.index("-m") + 1] if "-m" in command else None
        step = ("tests" if flag == "pytest" else flag.rsplit(".", 1)[-1] + ":" + command[command.index(flag) + 1]) if flag else "?"
        step = {"canary:preflight": "preflight"}.get(step, step.replace("canary_driver:", ""))
        world.calls.append(step)
        world.seen.setdefault(step, []).append({"file": states(world)["file"], "head": git(world.work, "rev-parse", "HEAD"), "command": list(command)})
        if step in fail:
            raise tool.Stop(f"{step} failed")
        if interrupt == step:
            raise KeyboardInterrupt()
        option = lambda name: command[command.index(name) + 1]  # noqa: E731
        if step == "tests":
            return tests_output
        if step == "baseline":
            # Under a delegated authorisation the real driver pins the record's block; the recorder does the same with
            # the real check, so that the wrapper is tested against what the driver would write (or against `pins`).
            pinned = {}
            if "--authorization" in command:
                from coprepan import canary_driver, delegation
                named = [command[i + 1] for i, word in enumerate(command) if word == "--outlet"]
                budget = canary_driver.canary_budget(len(named))
                pinned = {"authorization": delegation.block_for(
                    Path(option("--authorization")), option("--wave"), repository=world.work, outlets=named, budget=budget.as_record(),
                    total_requests_ceiling=budget.total_requests_ceiling, policy_version=json.loads(
                        (world.work / "config" / "acquisition_policy.json").read_text(encoding="utf-8"))["policy_version"], today=TODAY)}
            if pins is not None:
                pinned = pins
            Path(option("--out")).write_text(json.dumps({
                "state": "READY_TO_FREEZE", "blocking": [], "manifest_sha256": DIGEST, "code": {"commit": option("--commit")},
                "operator": option("--operator"), "policy": {"sha256": "p" * 64}, "registry": {"sha256": "r" * 64},
                "canary": {**pinned, "driver": {"driver": "canary-driver/4", "budget": {}, "outlets": {}},
                           "storage_target": {"target_id": "interim"}}}), encoding="utf-8")
        elif step == "freeze":
            manifest = json.loads(Path(option("--manifest")).read_text(encoding="utf-8"))
            Path(option("--out")).write_text(json.dumps({"state": "FROZEN", "manifest_sha256": DIGEST, "canary": manifest["canary"],
                                                         "freeze": {"operator": option("--operator")}}) + "\n", encoding="utf-8")
        elif step == "run":
            directory = Path(option("--receipt-dir"))
            (directory / f"canary-start-state-{RUN_ID}.json").write_text("{}\n", encoding="utf-8")
            (directory / f"canary-receipt-{RUN_ID}.json").write_text('{"status": "COMPLETE"}\n', encoding="utf-8")
            if incomplete_receipt:
                raise tool.Stop("run exited 1 (INCOMPLETE_PENDING)")
        elif step in ("verify", "measure"):
            Path(option("--out")).write_text("{}\n", encoding="utf-8")
        return ""
    return run


def operate(world, terminal="ARM\n" + DIGEST + "\n", outlets=OUTLETS, **fakes):
    arguments = ["--operator", "A Tester", "--label", "second", *[value for outlet in outlets for value in ("--outlet", outlet)]]
    return tool.main(arguments, repository=world.work, scratch=world.scratch, stdin=Terminal(terminal),
                     runner=fake_runner(world, **fakes), today=TODAY)


def assert_disarmed(world):
    assert states(world) == {"file": "disabled", "HEAD": "disabled", "origin": "disabled"}
    assert git(world.work, "status", "--porcelain") == ""


# --- the whole procedure ---------------------------------------------------------------------------------


def test_the_workflow_runs_the_runbook_in_order_on_the_right_commits_and_ends_disarmed(world, capsys):
    before = git(world.work, "rev-parse", "HEAD")
    assert operate(world) == 0
    assert world.calls == ["tests", "baseline", "freeze", "preflight", "run", "verify", "measure", "tests"]
    arming = git(world.work, "log", "--format=%H %s", "--reverse", f"{before}..HEAD").splitlines()
    assert [line.split(" ", 1)[1] for line in arming] == [
        "Arm the second canary: external_acquisition enabled (CPD-0016)", "Baseline of the second canary frozen (O-12, canary scope)",
        "Evidence of the second canary " + RUN_ID, "Disarm after the canary: external_acquisition disabled"]
    pinned = arming[0].split(" ")[0]
    seen = world.seen
    # the tests, the baseline and the pinned commit are the arming commit; the switch is on for them and off for the last tests
    assert seen["tests"][0]["head"] == pinned and seen["tests"][0]["file"] == "enabled"
    assert seen["baseline"][0]["command"][seen["baseline"][0]["command"].index("--commit") + 1] == pinned
    for step in ("preflight", "run"):
        command = seen[step][0]["command"]
        assert command[command.index("--tests-commit" if step == "preflight" else "--pinned-commit") + 1] == pinned
        assert command[command.index("--commit") + 1 if step == "preflight" else 0] in (pinned, command[0])
        assert seen[step][0]["file"] == "enabled"
    assert seen["tests"][1]["file"] == "disabled"
    assert [c[c.index("--tests-passed") + 1] for c in (seen["baseline"][0]["command"], seen["run"][0]["command"])] == ["1400", "1400"]
    # the baseline was frozen with the digest of the manifest, committed and pushed before the run
    frozen = world.work / "docs" / "canary" / "BASELINE_FROZEN_2026-10-10_second.json"
    assert json.loads(frozen.read_text(encoding="utf-8"))["manifest_sha256"] == DIGEST
    assert seen["freeze"][0]["command"][seen["freeze"][0]["command"].index("--confirm") + 1] == DIGEST
    evidence = world.work / "docs" / "canary" / "evidence" / RUN_ID
    assert sorted(path.name for path in evidence.iterdir()) == [f"canary-receipt-{RUN_ID}.json", f"canary-start-state-{RUN_ID}.json",
                                                                "measurement.json", "verification.json"]
    assert_disarmed(world)
    # the digest was on the screen before it was asked for, and the scope with its budget before `ARM`
    out = capsys.readouterr().out
    assert out.index(DIGEST) < out.index("Disarmed") and out.index("total_request_ceiling") < out.index(DIGEST)
    assert '"item_requests_total": 80' in out and "hn_proceso_digital:ch:rss_main" in out
    assert "Tests on the disarmed tree: 1400 passed." in out


@pytest.mark.parametrize("step", ["tests", "baseline", "freeze", "preflight", "run", "verify", "measure"])
def test_whichever_step_fails_the_switch_is_off_in_the_file_in_head_and_on_the_remote(world, step, capsys):
    status = operate(world, fail={step})
    assert status != 0 and status != 2
    assert_disarmed(world)
    assert "Disarmed: external_acquisition is `disabled`" in capsys.readouterr().out
    if step in ("tests", "baseline", "freeze"):
        assert "run" not in world.calls and "preflight" not in world.calls        # nothing was asked before the baseline was frozen
    if step == "tests":
        assert "baseline" not in world.calls
    if step in ("verify", "measure"):                                             # a failed check is kept as a result, the rest goes on
        assert (world.work / "docs" / "canary" / "evidence" / RUN_ID).is_dir()


def test_an_incomplete_run_keeps_its_evidence_and_is_reported_not_hidden(world, capsys):
    assert operate(world, incomplete_receipt=True) == 1
    assert (world.work / "docs" / "canary" / "evidence" / RUN_ID / f"canary-receipt-{RUN_ID}.json").is_file()
    assert world.calls[-3:] == ["verify", "measure", "tests"]
    assert_disarmed(world)
    assert "the run did not complete cleanly" in capsys.readouterr().out


def test_an_interrupted_run_is_disarmed(world):
    assert operate(world, interrupt="run") == 1
    assert_disarmed(world)


def test_the_tests_failing_on_the_arming_commit_is_not_mistaken_for_a_pass(world):
    assert operate(world, tests_output="3 failed, 1397 passed in 3.0s") == 1
    assert_disarmed(world)
    assert world.calls == ["tests", "tests"]          # the second is the run on the disarmed tree; no baseline, no request in between


# --- the confirmations --------------------------------------------------------------------------------------


def test_no_confirmation_can_be_passed_in_and_nothing_is_armed_without_one(world):
    commits = git(world.work, "rev-list", "--count", "HEAD")
    for not_a_person in (io.StringIO("ARM\n" + DIGEST + "\n"), io.StringIO("")):
        arguments = ["--operator", "x", "--label", "second", *[v for o in OUTLETS for v in ("--outlet", o)]]
        assert tool.main(arguments, repository=world.work, scratch=world.scratch, stdin=not_a_person, runner=fake_runner(world), today=TODAY) == 1
    assert world.calls == [] and git(world.work, "rev-list", "--count", "HEAD") == commits
    assert states(world) == {"file": "disabled", "HEAD": "disabled", "origin": "disabled"}
    for answer in ("arm\n", "\n", "yes\n", "ARM NOW\n"):
        assert operate(world, terminal=answer) == 1
    assert world.calls == [] and git(world.work, "rev-list", "--count", "HEAD") == commits


@pytest.mark.parametrize("typed", ["", "yes", DIGEST.upper(), DIGEST[:-1], "cd" * 32])
def test_a_wrong_digest_freezes_nothing_and_disarms(world, typed):
    assert operate(world, terminal=f"ARM\n{typed}\n") == 1
    assert "freeze" not in world.calls and "run" not in world.calls
    assert not list((world.work / "docs" / "canary").glob("BASELINE_FROZEN_*"))
    assert_disarmed(world)


def test_the_scope_is_refused_before_anything_is_armed(world, capsys):
    commits = git(world.work, "rev-list", "--count", "HEAD")
    assert operate(world, outlets=["bo_el_deber"]) == 1                                  # one outlet is not a canary
    assert operate(world, outlets=[*OUTLETS[:4], "ar_clarin"]) == 1                      # proposed, not registered
    assert operate(world, outlets=[*OUTLETS, "bo_el_deber"]) == 1                        # named twice
    assert world.calls == [] and git(world.work, "rev-list", "--count", "HEAD") == commits
    assert capsys.readouterr().out.count("STOPPED") == 3


def test_a_dirty_tree_an_unpushed_head_an_armed_switch_or_a_used_label_stops_before_arming(world):
    (world.work / "stray.txt").write_text("x", encoding="utf-8")
    assert operate(world) == 1 and world.calls == []
    (world.work / "stray.txt").unlink()
    (world.work / "docs" / "canary" / "BASELINE_FROZEN_2026-10-10_second.json").write_text("{}", encoding="utf-8")
    git(world.work, "add", "-A")
    git(world.work, "commit", "-q", "-m", "a baseline of today exists")
    git(world.work, "push", "-q", "origin", "main")
    assert operate(world) == 1 and world.calls == []
    git(world.work, "rm", "-q", "docs/canary/BASELINE_FROZEN_2026-10-10_second.json")
    git(world.work, "commit", "-q", "-m", "unpushed")
    assert operate(world) == 1 and world.calls == []
    git(world.work, "push", "-q", "origin", "main")
    tool.set_switch("enabled", world.work / "config" / "acquisition_policy.json")
    git(world.work, "commit", "-qam", "armed by hand")
    assert operate(world) == 1 and world.calls == []                                    # refuses, and says how to disarm


# --- trouble with git, a killed process ---------------------------------------------------------------------


def test_a_failed_push_of_the_baseline_is_a_stop_that_still_disarms(world):
    assert operate(world, fail={"push1"}) == 1
    assert "preflight" not in world.calls and "run" not in world.calls
    assert_disarmed(world)


def test_when_the_disarming_cannot_be_pushed_the_tool_says_so_and_exits_2(world, capsys):
    assert operate(world, fail={"push-from-2"}) == 2
    out = capsys.readouterr().out
    assert "NOT DISARMED CLEANLY" in out and "the push" in out and "--disarm-only" in out
    assert states(world)["file"] == "disabled" and states(world)["HEAD"] == "disabled"      # locally it is off ...
    assert states(world)["origin"] == "enabled"                                              # ... and the remote still says what it says
    capture = tool.main(["--disarm-only"], repository=world.work, runner=fake_runner(world), today=TODAY)
    assert capture == 0 and states(world) == {"file": "disabled", "HEAD": "disabled", "origin": "disabled"}


def test_disarm_only_recovers_a_killed_run_whatever_state_it_left(world):
    path = world.work / "config" / "acquisition_policy.json"
    # killed after the arming commit was pushed
    tool.set_switch("enabled", path)
    git(world.work, "commit", "-qam", "armed")
    git(world.work, "push", "-q", "origin", "main")
    assert tool.main(["--disarm-only"], repository=world.work, runner=fake_runner(world)) == 0
    assert_disarmed(world)
    # killed after the file was changed and before it was committed
    tool.set_switch("enabled", path)
    assert tool.main(["--disarm-only"], repository=world.work, runner=fake_runner(world)) == 0
    assert_disarmed(world)
    # nothing to do: still a success, and it starts nothing
    assert tool.main(["--disarm-only"], repository=world.work, runner=fake_runner(world)) == 0
    assert world.calls == []
    with pytest.raises(SystemExit):
        tool.main(["--disarm-only", "--outlet", "bo_el_deber"], repository=world.work, runner=fake_runner(world))


def test_the_command_line_offers_no_way_to_pass_a_confirmation_or_widen_the_scope(world):
    for extra in (["--confirm", DIGEST], ["--yes"], ["--arm"], ["--digest", DIGEST], ["--approved-baseline", "x"], ["--budget", "99"]):
        with pytest.raises(SystemExit):
            tool.main(["--operator", "x", "--label", "second", "--outlet", "bo_el_deber", *extra], repository=world.work, runner=fake_runner(world))
    assert world.calls == []


def test_the_test_summary_counts_a_pass_only_when_nothing_failed_or_errored():
    assert tool.test_summary("....\n1382 passed, 8 skipped in 333.75s (0:05:33)\n") == 1382
    for bad in ("3 failed, 1397 passed in 3.0s", "1 error in 0.5s", "1380 passed, 2 errors in 1s", "no tests ran in 0.1s", ""):
        with pytest.raises(tool.Stop):
            tool.test_summary(bad)


def test_the_null_device_and_a_file_are_not_a_terminal(tmp_path, monkeypatch):
    """Found by starting the tool with `< /dev/null`: on Windows `isatty()` is true for NUL, and the prompt was shown."""
    import os
    import sys

    for source in (os.devnull, tmp_path / "answers.txt"):
        Path(source).write_text("ARM\n", encoding="utf-8") if source != os.devnull else None
        with open(source, "r", encoding="utf-8") as stream:
            monkeypatch.setattr(sys, "stdin", stream)
            assert tool.is_console(stream) is False
            with pytest.raises(tool.Stop, match="person at a terminal"):
                tool.typed_by_a_person("? ")
