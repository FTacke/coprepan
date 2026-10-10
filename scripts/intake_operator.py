"""The workflow of a bounded, timed intake (decision CPD-0029; runbook §12).

An intake runs for hours and must not depend on the session that started it. So the workflow is in
three parts, and each is a command of this tool:

``plan``     build the plan of an intake from an intake-readiness file. Deterministic; no request.

``start``    under a committed **intake authorisation record**: check everything, arm, run the full
             test suite on the arming commit, build and freeze the baseline, run the preflight, write
             the intake's state (the clock starts there, and the deadline is fixed) and hand the
             intake to a scheduled task of the operating system. It returns as soon as the controller
             runs. Anything that fails before the state is written disarms again.

``tick``     what the scheduled task runs every few minutes, and the only thing that makes requests:
             while the intake is ``RUNNING`` and its deadline has not come, be the controller (or
             leave at once when another process is); afterwards finalize — preserve, verify, receipt,
             measurement, report — **disarm**, and remove the task. Restartable at every point.

``status``, ``stop``, ``import-report`` — read the state; ask a running controller to stop; copy a
finished intake's report from the runtime workspace into the checkout (it commits nothing).

It asks nothing and accepts nothing typed: what stands in the place of the person is the record, as in
the delegated canary mode (CPD-0023). There is no force option. The only git operations it makes
unattended are the ones a canary makes — the commit of the one switch and a plain push, never a
forced one, never a rebase, never another file; when the push is refused the report says so, and the
file on disk, which is what the controller obeys, is ``disabled`` either way.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

import canary_operator as O  # noqa: E402

POLICY_RELATIVE = O.POLICY_RELATIVE
REQUIRED_FREE_BYTES = O.REQUIRED_FREE_BYTES
TICK_MINUTES = 5
MAX_CONTROLLER_FALLS = 6     # a controller that fell is started again by the next tick; after this many falls the intake ends as FAILED and is finalized
PINNED_FILES = ("registry", "policy", "crawler_identity", "schedule_policy", "candidate_rules")
Stop = O.Stop


NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)       # a windowless task must not open a console for every git call


def make_runner(repository: Path):
    """The canary tool's runner, for a process that may have no console: output is always captured, and no window opens."""
    def run(*command: str, capture: bool = False) -> str:
        done = subprocess.run(command, cwd=repository, text=True, capture_output=True, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
                              env={**os.environ, "PYTHONPATH": "src"}, encoding="utf-8", errors="replace")
        if done.returncode != 0:
            raise Stop(f"{' '.join(command[:4])} … exited {done.returncode}\n{done.stdout[-1500:]}\n{done.stderr[-1500:]}")
        return done.stdout
    return run


def task_name(intake_id: str) -> str:
    return f"coprepan-intake-{intake_id}"


def state_directory(runtime: Path, intake_id: str) -> Path:
    return Path(runtime) / "intake" / intake_id


# --- the environment of a controller ---------------------------------------------------------------------------


def load_environment(repository: Path):
    """Everything a controller or a finalizer runs against, as this checkout and this workstation configure it."""
    from coprepan import candidate_filter, core_pipeline, crawler_identity, intake, policy, registry, schedule, storage_roots
    from coprepan import canary_driver

    roles = storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())
    environment = intake.Environment(
        workspace=core_pipeline.Workspace(roles["RUNTIME"]), registry=registry.load_registry(repository / "config" / "outlet_registry.json"),
        policy=policy.load_policy(repository / "config" / "acquisition_policy.json"), identity=crawler_identity.load_identity(repository / "config" / "crawler_identity.json"),
        schedule_policy=schedule.load_schedule_policy(repository / "config" / "schedule_policy.json"),
        candidate_rules=candidate_filter.load_rules(repository / "config" / "candidate_rules.json"),
        preservation_root=lambda: storage_roots.resolve_root("PRESERVATION", env=storage_roots.workstation_environment()),
        spool_root=(lambda: roles["SPOOL"]) if roles.get("SPOOL") is not None else None, spool_policy=canary_driver.CANARY_SPOOL)
    return environment, roles


def permission(repository: Path, baseline: dict, plan_path: Path, plan_sha256: str):
    """``None`` while the intake may go on, or the reason it may not: the switch, and every file the baseline pins.
    Read from disk each time it is asked — turning the switch off in the file stops a running intake at its next request.
    """
    from coprepan.canonical import record_json, sha256_bytes

    files = {name: repository / baseline[name]["path"] for name in PINNED_FILES}

    def check() -> str | None:
        try:
            if O.switch_state(policy=repository / POLICY_RELATIVE) != "enabled":
                return "external_acquisition is `disabled` in the policy file"
            for name, path in files.items():
                if sha256_bytes(path.read_bytes()) != baseline[name]["sha256"]:
                    return f"{baseline[name]['path']} is not the file the baseline pins"
            if sha256_bytes(record_json(json.loads(plan_path.read_text(encoding="utf-8")))) != plan_sha256:
                return "the plan file is not the plan the intake was started with"
        except (OSError, ValueError, Stop) as error:
            return f"the pinned configuration cannot be read: {error}"
        return None
    return check


def code_unchanged(run, pinned_commit: str) -> str | None:
    """``None`` when the code is the code of the pinned commit: HEAD may have moved on by documents only, and nothing
    under ``src``, ``scripts`` or ``config`` is modified in the working tree (the switch at the end excepted: it is checked by itself).
    """
    try:
        changed = [name for name in run("git", "diff", "--name-only", pinned_commit, "HEAD", capture=True).splitlines() if not name.startswith("docs/")]
        dirty = [line[3:] for line in run("git", "status", "--porcelain", "--", "src", "scripts", "config", capture=True).splitlines()]
    except Stop as failure:
        return f"git could not be asked: {failure}"
    if changed or dirty:
        return f"the checkout differs from the pinned commit beyond documents: {(changed + dirty)[:6]}"
    return None


# --- disarming --------------------------------------------------------------------------------------------------


def disarm(run, repository: Path, intake_id: str) -> list[str]:
    """Turn the switch off in the file — first, and whatever else fails — then commit that one file and push.
    Never raises, never forces, never touches another path. Returns what could not be done; the state reported is read back.
    """
    policy, problems = repository / POLICY_RELATIVE, []
    try:
        if O.switch_state(policy=policy) != "disabled":
            O.set_switch("disabled", policy)
    except (Stop, OSError) as failure:
        problems.append(f"the file: {failure}")
    try:
        if run("git", "rev-parse", "--abbrev-ref", "HEAD", capture=True).strip() != "main":
            problems.append("the checkout is not on main: the switch is off in the file and was not committed")
        else:
            if O.git_changed(run, POLICY_RELATIVE):
                # A commit of this path and no other: whatever else is staged or modified stays as it is.
                run("git", "commit", "-q", "-m", f"Disarm after the intake {intake_id}: external_acquisition disabled", "--", POLICY_RELATIVE)
            try:
                run("git", "push", "origin", "main")
            except Stop as failure:
                problems.append(f"the push (a plain push, not forced; the file and the local commit are fine): {str(failure)[:200]}")
    except Stop as failure:
        problems.append(f"the commit: {str(failure)[:200]}")
    try:
        if O.switch_state(policy=policy) != "disabled":
            problems.append("the file on disk still says `enabled`")
        for reference in ("HEAD", "origin/main"):
            if O.switch_state(run("git", "show", f"{reference}:{POLICY_RELATIVE}", capture=True)) != "disabled":
                problems.append(f"{reference} still says `enabled`")
    except Stop as failure:
        problems.append(f"reading the state back: {failure}")
    return problems


# --- the scheduled task -----------------------------------------------------------------------------------------


def _powershell(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          creationflags=NO_WINDOW, encoding="utf-8", errors="replace")


def interpreter() -> str:
    """The interpreter a task runs: the windowless one beside this interpreter, where there is one."""
    windowless = Path(sys.executable).with_name("pythonw.exe")
    return str(windowless if windowless.exists() else sys.executable)


def register_task(repository: Path, intake_id: str) -> str | None:
    """Register and start the task that keeps the intake alive and ends it. ``None``, or why it could not be done."""
    script = repository / "scripts" / "intake_operator.py"
    command = (
        f"$a = New-ScheduledTaskAction -Execute '{interpreter()}' -Argument '\"{script}\" tick --intake {intake_id}' -WorkingDirectory '{repository}'; "
        f"$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes {TICK_MINUTES}) -RepetitionDuration (New-TimeSpan -Days 3); "
        "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero); "
        f"Register-ScheduledTask -TaskName '{task_name(intake_id)}' -Action $a -Trigger $t -Settings $s -Description 'CO.PRE.PAN intake {intake_id}: resume and finalize (removes itself)' -Force | Out-Null; "
        f"Start-ScheduledTask -TaskName '{task_name(intake_id)}'")
    done = _powershell(command)
    return None if done.returncode == 0 else (done.stderr or done.stdout).strip()[:600]


def remove_task(intake_id: str) -> str | None:
    done = _powershell(f"if (Get-ScheduledTask -TaskName '{task_name(intake_id)}' -ErrorAction SilentlyContinue) {{ Unregister-ScheduledTask -TaskName '{task_name(intake_id)}' -Confirm:$false }}")
    return None if done.returncode == 0 else (done.stderr or done.stdout).strip()[:300]


def task_exists(intake_id: str) -> bool:
    return _powershell(f"if (Get-ScheduledTask -TaskName '{task_name(intake_id)}' -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 3 }}").returncode == 0


def stay_awake() -> None:
    """Ask the system not to sleep while this process runs (Windows; released when the process ends)."""
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)       # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


# --- plan ------------------------------------------------------------------------------------------------------


def command_plan(arguments, repository: Path) -> int:
    from coprepan import intake, policy
    from coprepan.canonical import record_json, sha256_bytes

    readiness_bytes = arguments.readiness.read_bytes()
    budget = intake.IntakeBudget(
        duration_seconds=arguments.duration_seconds, cycle_seconds=arguments.cycle_seconds, item_requests_per_outlet=arguments.item_requests_per_outlet,
        item_requests_per_outlet_hour=arguments.item_requests_per_outlet_hour, item_requests_per_origin=arguments.item_requests_per_origin,
        total_requests=arguments.total_requests, items_per_outlet_cycle=arguments.items_per_outlet_cycle,
        backlog_items_per_outlet_cycle=arguments.backlog_items_per_outlet_cycle)
    plan = intake.build_plan(json.loads(readiness_bytes.decode("utf-8")), intake_id=arguments.intake_id, budget=budget,
                             policy=policy.load_policy(repository / "config" / "acquisition_policy.json"),
                             registry_sha256=sha256_bytes((repository / "config" / "outlet_registry.json").read_bytes()),
                             readiness_sha256=sha256_bytes(readiness_bytes), outlets=arguments.outlet or None)
    if arguments.out.exists():
        raise SystemExit(f"{arguments.out.name} exists: a plan is written once")
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_bytes(record_json(plan))
    print(json.dumps({"plan": arguments.out.as_posix(), "plan_sha256": sha256_bytes(record_json(plan)), "totals": plan["totals"], "left_out": plan["left_out"],
                      "bulk_channels_not_polled": {o["outlet_id"]: o["bulk_channels_not_polled"] for o in plan["outlets"] if o["bulk_channels_not_polled"]}}, indent=2))
    return 0


# --- start -----------------------------------------------------------------------------------------------------


def authorized_plan(run, repository: Path, record_path: Path, today):
    """The record, the plan it names and the block a baseline pins — or a stop. Nothing is armed here."""
    from coprepan import intake

    try:
        relative = record_path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError as failure:
        raise Stop("the authorisation record is not a file of this checkout") from failure
    if not relative.startswith(intake.AUTHORIZATION_RECORDS + "/"):
        raise Stop(f"an intake authorisation lies in {intake.AUTHORIZATION_RECORDS}/")
    commits = run("git", "log", "--format=%H", "--", relative, capture=True).split()
    if len(commits) != 1:
        raise Stop(f"an authorisation record is written once: {len(commits)} commits touched {relative}")
    record_bytes = (repository / relative).read_bytes()
    record = json.loads(record_bytes.decode("utf-8"))
    try:
        intake.validate_authorization(record)
        plan_relative = record["intake"]["plan"]
        if len(run("git", "log", "--format=%H", "--", plan_relative, capture=True).split()) != 1:
            raise Stop(f"a plan is written once: {plan_relative} is not committed exactly once")
        plan = json.loads((repository / plan_relative).read_text(encoding="utf-8"))
        intake.check_authorization(record, plan, plan_path=plan_relative, policy_version=plan["policy_version"], today=today)
    except intake.IntakeStopped as refusal:
        raise Stop(f"the authorisation does not cover this intake: {refusal}") from refusal
    return record, plan, plan_relative, intake.authorization_block(record, relative, record_bytes)


def other_intake_running(runtime: Path) -> str | None:
    for path in sorted((Path(runtime) / "intake").glob("*/state.json")):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return f"{path.parent.name}: its state cannot be read"
        if state.get("finalized") is None:
            return f"{path.parent.name} is {state.get('status')} and not finalized"
    return None


def command_start(arguments, repository: Path, run, today=None, register=register_task) -> int:
    from coprepan import canary, canary_driver, freeze, intake, outage_spool, policy, preservation_target, recovery, registry, storage_roots
    from coprepan.canonical import record_json, sha256_bytes, write_bytes_exclusive

    day = today or datetime.now().astimezone().date()
    policy_path = repository / POLICY_RELATIVE
    armed, started, status, intake_id = False, False, 0, "start"
    try:
        # §0 — before anything; nothing is armed yet
        if run("git", "status", "--porcelain", capture=True).strip():
            raise Stop("the working tree is not clean")
        run("git", "fetch", "origin", "--quiet")
        if run("git", "rev-parse", "HEAD", capture=True).strip() != run("git", "rev-parse", "origin/main", capture=True).strip():
            raise Stop("HEAD is not origin/main")
        if O.switch_state(policy=policy_path) != "disabled":
            raise Stop("the switch is `enabled`: something else is armed, or was not disarmed")
        record, plan, plan_relative, block = authorized_plan(run, repository, arguments.authorization, day)
        intake_id = plan["intake_id"]
        environment, roles = load_environment(repository)
        state_dir = state_directory(roles["RUNTIME"], intake_id)
        baseline_path = repository / "docs" / "intake" / f"BASELINE_FROZEN_{day.isoformat()}_{intake_id}.json"
        if state_dir.exists() or baseline_path.exists():
            raise Stop(f"{intake_id} was started before: an intake is started once, under its own authorisation")
        busy = other_intake_running(roles["RUNTIME"])
        if busy:
            raise Stop(f"another intake is not finished: {busy}")
        if roles.get("SPOOL") is not None and roles["SPOOL"].is_dir() and outage_spool.pending_records(roles["SPOOL"]):
            raise Stop("the spool holds pending objects: they are drained before an intake starts")
        print("Reading the holds from every preserved answer, and the state of the workspace …", flush=True)
        holds = canary_driver.access_holds_from_evidence(environment.workspace, reclassify=True)
        try:
            intake.validate_plan(plan, environment.registry, environment.policy, holds)
        except (intake.IntakeStopped, registry.UnregisteredOutlet) as refusal:
            raise Stop(f"the plan cannot be run as things are: {refusal}") from refusal
        diagnosis = recovery.diagnose(roles["RUNTIME"])
        if diagnosis["classification"] != recovery.CLEAN:
            raise Stop(f"the workspace is {diagnosis['classification']}, not CLEAN")
        by = f" under {record['authorization_id']} ({intake.MODE_DELEGATED_INTAKE}, no typed confirmation)"
        operator = f"{record['issued_to']} under {record['authorization_id']} ({intake.MODE_DELEGATED_INTAKE}; issued by {record['issued_by']})"
        print(json.dumps({"intake_id": intake_id, "totals": plan["totals"], "budget": plan["budget"], "policy_version": plan["policy_version"],
                          "authorization": block, "held_keys_now": len(holds)}, indent=2))

        # §1 — arm
        print(f"Arming{by}: the record covers exactly this intake.")
        armed = True
        O.set_switch("enabled", policy_path)
        run("git", "commit", "-q", "-m", f"Arm the intake {intake_id}: external_acquisition enabled (CPD-0029){by}", "--", POLICY_RELATIVE)
        pinned = run("git", "rev-parse", "HEAD", capture=True).strip()

        # §2 — the full suite on the arming commit;  §3 — baseline, freeze, commit, push
        print("Running the full test suite on the arming commit …", flush=True)
        passed = O.test_summary(run(sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", capture=True))
        environment, roles = load_environment(repository)                                   # the policy as armed
        now = datetime.now(timezone.utc)
        readiness = preservation_target.check_readiness(roles["PRESERVATION"], required_free_bytes=REQUIRED_FREE_BYTES, now=now)
        manifest = freeze.build_manifest(
            code_commit=pinned, created_at=now, operator=operator, test_baseline={"suite": "python -m pytest", "passed": passed}, storage_target=readiness,
            scope=freeze.SCOPE_CANARY, repository=repository,
            canary=intake.intake_pin(plan, plan_relative, block, environment.registry, roles["PRESERVATION"], environment.policy, repository))
        if manifest["state"] != freeze.READY_TO_FREEZE or manifest["blocking"]:
            raise Stop(f"the baseline is not ready to freeze on the arming commit: {manifest['blocking']}")
        baseline = freeze.freeze(manifest, operator=operator, confirmed_at=datetime.now(timezone.utc), confirmation=manifest["manifest_sha256"])
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        write_bytes_exclusive(baseline_path, record_json(baseline))
        print(f"Baseline {baseline['manifest_sha256']} frozen{by}.")
        run("git", "add", "--", baseline_path.relative_to(repository).as_posix())
        run("git", "commit", "-q", "-m", f"Baseline of the intake {intake_id} frozen (O-12, canary scope){by}", "--", baseline_path.relative_to(repository).as_posix())
        run("git", "push", "origin", "main")

        # §4 — preflight: every precondition against what is on disk
        report = canary.preflight(outlet_ids=[o["outlet_id"] for o in plan["outlets"]], tests_passed=passed, tests_commit=pinned, code_commit=pinned,
                                  approved_baseline=baseline, required_free_bytes=REQUIRED_FREE_BYTES, now=datetime.now(timezone.utc),
                                  environment=storage_roots.workstation_environment(), repository=repository)
        if report["status"] != canary.READY:
            raise Stop("the preflight is not READY: " + "; ".join(f"{c['check']}: {c['detail']}" for c in report["checks"] if c["status"] != "PASS")[:900])
        refusal = permission(repository, baseline, repository / plan_relative, sha256_bytes(record_json(plan)))() or code_unchanged(run, pinned)
        if refusal:
            raise Stop(refusal)

        # §5 — the state: the clock starts here, and the deadline is fixed
        started_at = datetime.now(timezone.utc)
        state = intake.initial_state(plan, started_at=started_at, baseline={
            "manifest_sha256": baseline["manifest_sha256"], "file": baseline_path.relative_to(repository).as_posix(), "pinned_commit": pinned,
            "plan": plan_relative, "authorization": block, "tests_passed": passed, "preflight": report["status"]})
        state["disarmed"] = None
        state_dir.mkdir(parents=True)
        intake.write_state(state_dir, state)
        started = True
        print(json.dumps({"intake_id": intake_id, "started_at_utc": state["started_at_utc"], "deadline_at_utc": state["deadline_at_utc"],
                          "started_at_local": state["started_at_local"], "deadline_at_local": state["deadline_at_local"], "state": str(state_dir / intake.STATE_FILE)}, indent=2))

        # §6 — hand over to the scheduled task: from here on the intake does not need this process
        problem = register(repository, intake_id)
        if problem:
            raise Stop(f"the scheduled task could not be registered: {problem}")
        print(f"Scheduled task `{task_name(intake_id)}` registered and started: it resumes the controller every {TICK_MINUTES} minutes if it is not running, "
              "finalizes after the deadline, disarms and removes itself.")
    except Stop as stop:
        print(f"\nSTOPPED: {stop}")
        status = 1
    except KeyboardInterrupt:
        print("\nINTERRUPTED")
        status = 1
    finally:
        if armed and status != 0:
            # Whatever failed after the arming: nothing is left armed. A state that was already written is marked, so that no tick takes it up.
            if started:
                state = intake.read_state(state_dir)
                state["status"], state["stopped_because"] = intake.BLOCKED, "the start did not complete: the intake was never handed to its controller"
                state["finalized"], state["disarmed"] = {"at": None, "outcome": intake.BLOCKED, "verification": "not applicable: no request was made"}, True
                intake.write_state(state_dir, state)
            problems = disarm(run, repository, intake_id)
            print("Disarmed: external_acquisition is `disabled` in the file, in HEAD and on origin/main." if not problems
                  else "\n!!! NOT DISARMED CLEANLY:\n!!! " + "\n!!! ".join(problems))
            status = 2 if problems else status
    return status


# --- tick ------------------------------------------------------------------------------------------------------


def command_tick(arguments, repository: Path, run, unregister=remove_task, loader=None) -> int:
    """Be the controller while the intake runs; afterwards finalize, disarm and remove the task. Safe to run at any time, any number of times."""
    from coprepan import intake, intake_report
    from coprepan.canonical import record_json, write_bytes_atomic
    from coprepan.exclusive import WorkspaceBusy

    environment, roles = (loader or load_environment)(repository)
    state_dir = state_directory(roles["RUNTIME"], arguments.intake)
    log = open(state_dir / "tick.log", "a", encoding="utf-8", buffering=1)                    # a windowless interpreter has no console to write to
    sys.stdout = sys.stderr = log
    stamp = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    try:
        state = intake.read_state(state_dir)
        plan_path = repository / state["baseline"]["plan"]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        baseline = json.loads((repository / state["baseline"]["file"]).read_text(encoding="utf-8"))
        if state["status"] == intake.RUNNING:
            environment.still_permitted = permission(repository, baseline, plan_path, state["plan_sha256"])
            refusal = code_unchanged(run, state["baseline"]["pinned_commit"])
            if refusal is not None:
                with_lock_state = intake.read_state(state_dir)
                with_lock_state["status"], with_lock_state["stopped_because"] = intake.BLOCKED, refusal
                intake.write_state(state_dir, with_lock_state)
                print(f"{stamp()} BLOCKED before any request: {refusal}")
            else:
                stay_awake()
                try:
                    state = intake.run(plan, state_dir, environment)
                except WorkspaceBusy:
                    return 0                                                                    # the controller is running in another process: nothing to do
                except Exception as error:  # noqa: BLE001 - a controller that fell is started again by the next tick, but not for ever
                    print(f"{stamp()} the controller fell:\n{traceback.format_exc()}")
                    fallen = intake.read_state(state_dir)
                    fallen["controller_falls"] = fallen.get("controller_falls", 0) + 1
                    fallen["errors"].append({"at": stamp(), "cycle": fallen["cycle"], "outlet_id": None, "error": f"controller: {type(error).__name__}: {str(error)[:300]}"})
                    if fallen["controller_falls"] >= MAX_CONTROLLER_FALLS:
                        fallen["status"], fallen["stopped_because"] = intake.FAILED, f"the controller fell {MAX_CONTROLLER_FALLS} times: a systemic fault"
                    intake.write_state(state_dir, fallen)
        state = intake.read_state(state_dir)
        if state["status"] == intake.RUNNING:
            return 0
        if state.get("finalized") is None or not (state_dir / "report" / "FINAL_REPORT.md").exists():
            print(f"{stamp()} finalizing ({state['status']})")
            failure = None
            try:
                receipt = intake.finalize(plan, state_dir, environment)
                state = intake.read_state(state_dir)
                measurement = intake_report.measure(roles["RUNTIME"], plan, state)
            except WorkspaceBusy:
                return 0
            except Exception as error:  # noqa: BLE001 - whatever the finalization meets, the disarming below still happens
                failure = f"{type(error).__name__}: {error}"
                print(f"{stamp()} the finalization failed: {failure}\n{traceback.format_exc()}")
            problems = disarm(run, repository, arguments.intake)
            state = intake.read_state(state_dir)
            state["disarmed"] = {"at": stamp(), "clean": not problems, "problems": problems}
            if failure is not None:
                state["finalization_failure"] = failure
                intake.write_state(state_dir, state)
                return 1                                                                        # the task stays: the next tick tries the finalization again
            report = state_dir / "report"
            report.mkdir(exist_ok=True)
            write_bytes_atomic(report / "receipt.json", record_json(receipt))
            write_bytes_atomic(report / "measurement.json", record_json(measurement))
            write_bytes_atomic(report / "review_package.json", record_json(intake_report.review_package(measurement)))
            write_bytes_atomic(report / "plan.json", record_json(plan))
            intake.write_state(state_dir, state)
            write_bytes_atomic(report / "state.json", record_json(state))
            write_bytes_atomic(report / "FINAL_REPORT.md", intake_report.render(receipt, measurement, plan, problems).encode("utf-8"))
            print(f"{stamp()} finalized: {receipt['outcome']}, verification {receipt['verification']['status']}; disarmed {'cleanly' if not problems else 'NOT cleanly: ' + '; '.join(problems)}")
        elif not state.get("disarmed") or not (state["disarmed"] is True or state["disarmed"].get("clean")):
            problems = disarm(run, repository, arguments.intake)                                # a disarming that was not clean is tried again
            state["disarmed"] = {"at": stamp(), "clean": not problems, "problems": problems}
            intake.write_state(state_dir, state)
            if problems:
                return 1
        problem = unregister(arguments.intake)
        print(f"{stamp()} " + ("the scheduled task is removed: nothing of this intake runs any more" if not problem else f"the scheduled task could not be removed: {problem}"))
        return 0 if not problem else 1
    except Exception:  # noqa: BLE001 - a tick never dies silently
        print(f"{stamp()} tick failed:\n{traceback.format_exc()}")
        return 1
    finally:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        log.close()


# --- status, stop, import-report -----------------------------------------------------------------------------


def command_status(arguments, repository: Path) -> int:
    from coprepan import intake, storage_roots

    runtime = storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())["RUNTIME"]
    found = sorted((Path(runtime) / "intake").glob("*/state.json")) if arguments.intake is None else [state_directory(runtime, arguments.intake) / "state.json"]
    for path in found:
        state = intake.read_state(path.parent)
        line = intake.status_line(state, datetime.now(timezone.utc))
        line.update({"switch_in_file": O.switch_state(policy=repository / POLICY_RELATIVE), "disarmed": state.get("disarmed"), "state_file": str(path),
                     "scheduled_task": task_exists(state["intake_id"]) if os.name == "nt" else None, "stopped_because": state.get("stopped_because")})
        print(json.dumps(line, indent=2, ensure_ascii=False))
    return 0


def command_stop(arguments, repository: Path) -> int:
    from coprepan import intake, storage_roots

    state_dir = state_directory(storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())["RUNTIME"], arguments.intake)
    intake.read_state(state_dir)
    (state_dir / intake.STOP_FILE).write_text(f"stop requested at {datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")
    print("Stop requested: the controller ends after the request it is making; the next tick finalizes and disarms.")
    return 0


def command_import(arguments, repository: Path) -> int:
    """Copy a finished intake's report into the checkout. Deterministic; it commits nothing."""
    from coprepan import storage_roots

    source = state_directory(storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())["RUNTIME"], arguments.intake) / "report"
    target = repository / "docs" / "intake" / "reports" / arguments.intake
    if not (source / "FINAL_REPORT.md").exists():
        raise SystemExit("this intake has no final report yet")
    if target.exists():
        raise SystemExit(f"{target.relative_to(repository).as_posix()} exists: a report is imported once")
    target.mkdir(parents=True)
    for name in ("FINAL_REPORT.md", "receipt.json", "measurement.json", "review_package.json", "plan.json", "state.json"):
        shutil.copyfile(source / name, target / name)
    print(f"Imported into {target.relative_to(repository).as_posix()}. Nothing was committed.")
    return 0


def main(argv: list[str] | None = None, *, repository: Path = REPOSITORY, runner=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="build the plan of an intake from an intake-readiness file (no request)")
    plan.add_argument("--readiness", type=Path, required=True)
    plan.add_argument("--intake-id", required=True)
    plan.add_argument("--out", type=Path, required=True)
    plan.add_argument("--outlet", action="append", default=[], help="only these outlets (a pilot); default: every outlet of the readiness file")
    for name, default in (("duration-seconds", 86400), ("cycle-seconds", 3600), ("item-requests-per-outlet", 120), ("item-requests-per-outlet-hour", 10),
                          ("item-requests-per-origin", 150), ("total-requests", 12000), ("items-per-outlet-cycle", 3), ("backlog-items-per-outlet-cycle", 1)):
        plan.add_argument(f"--{name}", type=int, default=default)
    start = commands.add_parser("start", help="under an intake authorisation: arm, test, freeze, preflight, start. Makes real requests through its controller")
    start.add_argument("--authorization", type=Path, required=True)
    for name, text in (("tick", "the scheduled task's command: be the controller, or finalize, disarm and remove the task"), ("stop", "ask a running controller to stop"),
                       ("import-report", "copy a finished intake's report into docs/intake/reports/ (commits nothing)")):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--intake", required=True)
    status = commands.add_parser("status", help="the state of an intake (or of all)")
    status.add_argument("--intake", default=None)
    arguments = parser.parse_args(argv)
    run = runner or make_runner(repository)
    if arguments.command == "plan":
        return command_plan(arguments, repository)
    if arguments.command == "start":
        return command_start(arguments, repository, run)
    if arguments.command == "tick":
        return command_tick(arguments, repository, run)
    if arguments.command == "status":
        return command_status(arguments, repository)
    if arguments.command == "stop":
        return command_stop(arguments, repository)
    return command_import(arguments, repository)


if __name__ == "__main__":
    raise SystemExit(main())
