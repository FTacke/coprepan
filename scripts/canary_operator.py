"""The operator's canary workflow in one command (runbook §9; CPD-0020 §7, amended by CPD-0021).

A convenience for the **person** who arms a canary — never a way around that person. It runs the
steps of the runbook in order and stops twice for something only a person at a terminal can give:

1. before arming, the typed word ``ARM``, after the scope and the budget have been shown;
2. before the freeze, the **baseline digest typed by hand** — the tool shows the manifest's summary
   and its digest and compares what is typed. That is the operator's act of CPD-0016 §4; a
   confirmation that is piped in, passed as an argument or given without a terminal is refused.

Then: preflight (must be ``READY``) → the canary → verify → measure → evidence copied into the
checkout → **disarm**, commit, push, and the tests on the disarmed tree. Once the switch has been
turned on, the disarming is attempted whatever happens in between — an error, an interruption, a
refused preflight, SIGTERM — and the tool exits 2 when the checkout could not be left disarmed.
If the process itself is killed (a closed console window, a power cut), the next command is::

    python scripts/canary_operator.py --disarm-only

which turns the switch off, commits and pushes, and starts nothing.

It adds no permission and changes no check: every step is the command the runbook names, and the
driver's own refusals (preflight, drift, clean tree, pushed HEAD, empty spool) apply unchanged.
A terminal is not proof of a person — a program can open a pseudo-terminal — so the guarantee is
that no confirmation can be *passed* to the tool, not that none can be *simulated*; simulating one
is what the repository's rules forbid an agent to do.

    python scripts/canary_operator.py --operator "<name>" --label second --outlet <id> --outlet <id> …

**The delegated mode (CPD-0023).** An agent the operator has commissioned runs the same workflow under
a versioned *authorisation record* instead of the two typed confirmations::

    python scripts/canary_operator.py --authorization config/operator_authorizations/<record>.json --wave <label>

It asks nothing and accepts nothing typed. What stands in the place of the person is the record, and
the tool takes everything from it: the outlets, the limits, the wave. It refuses a record that is not
committed exactly once, unmodified and pushed; a wave whose registration is not the one the record
names; a canary that is not exactly the wave's outlets or exceeds one of its limits; a wave that has a
frozen baseline already. Every technical gate is the interactive mode's — the tests on the arming
commit, the baseline and its digest, the preflight, the budgets, the holds, the verification, the
disarming and its read-back — and none can be switched off: there is no force option. Nothing is
recorded as typed or confirmed by a person; the baseline, the start state, the receipt and the commit
messages say ``DELEGATED_OPERATOR_AUTHORIZATION`` and name the record.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from datetime import date
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
POLICY = REPOSITORY / "config" / "acquisition_policy.json"
POLICY_RELATIVE = "config/acquisition_policy.json"
SWITCH = re.compile(r'("external_acquisition":\s*")(enabled|disabled)(")')
REQUIRED_FREE_BYTES = 21474836480        # the runbook's value: 20 GiB on the interim target
PLANNED_FILESYSTEM_BYTES = 2000000000000  # the 2 TB the operator named; a statement, not a measurement


class Stop(RuntimeError):
    """The workflow stops here. Nothing further is attempted except the disarming."""


def make_runner(repository: Path):
    def run(*command: str, capture: bool = False) -> str:
        done = subprocess.run(command, cwd=repository, text=True, capture_output=capture, env={**os.environ, "PYTHONPATH": "src"})
        if done.returncode != 0:
            raise Stop(f"{' '.join(command[:4])} … exited {done.returncode}" + (f"\n{done.stdout}\n{done.stderr}" if capture else ""))
        return done.stdout if capture else ""
    return run


def switch_state(text: str | None = None, policy: Path | None = None) -> str:
    found = SWITCH.findall((policy or POLICY).read_text(encoding="utf-8") if text is None else text)
    if len(found) != 1:
        raise Stop("the acquisition policy does not hold exactly one external_acquisition switch")
    return found[0][1]


def set_switch(state: str, policy: Path | None = None) -> None:
    """Rewrite the one switch and nothing else; bytes otherwise untouched, LF kept."""
    path = policy or POLICY
    data = path.read_bytes().decode("utf-8")
    switch_state(data)
    path.write_bytes(SWITCH.sub(lambda m: f"{m.group(1)}{state}{m.group(3)}", data).encode("utf-8"))


def is_console(stream) -> bool:
    """Whether a stream is a terminal. ``isatty()`` alone is not enough on Windows, where it is true for the
    ``NUL`` device (found by starting the tool with ``< /dev/null``): there the console mode must be readable.
    """
    if stream is None or not stream.isatty():
        return False
    if os.name == "nt" and stream is sys.stdin:
        import ctypes

        mode = ctypes.c_uint32()
        handle = ctypes.windll.kernel32.GetStdHandle(-10)         # STD_INPUT_HANDLE
        return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    return True


def typed_by_a_person(prompt: str, stdin=None) -> str:
    """One line typed at a terminal. Refused when there is no terminal: this is where a person is asked."""
    stdin = sys.stdin if stdin is None else stdin
    if not is_console(stdin):
        raise Stop("this step needs a person at a terminal: no confirmation is accepted from a pipe, a file or a script")
    print(prompt, end="", flush=True)
    return stdin.readline().strip()


def confirm_digest(manifest: dict, stdin=None) -> None:
    """Show what is about to be frozen and require its digest, typed. The operator's act (CPD-0016 §4)."""
    canary = manifest["canary"]
    print(json.dumps({"state": manifest["state"], "blocking": manifest["blocking"], "code_commit": manifest["code"]["commit"],
                      "policy_sha256": manifest["policy"]["sha256"], "registry_sha256": manifest["registry"]["sha256"],
                      "driver": canary["driver"]["driver"], "budget": canary["driver"]["budget"], "outlets_and_channels": canary["driver"]["outlets"],
                      "storage_target": canary["storage_target"]["target_id"]}, indent=2))
    print(f"\nBaseline digest:\n  {manifest['manifest_sha256']}\n")
    typed = typed_by_a_person("Type the digest to freeze this baseline (anything else stops): ", stdin)
    if typed != manifest["manifest_sha256"]:
        raise Stop("the digest typed is not the digest of the manifest: nothing was frozen")


def test_summary(output: str) -> int:
    """The number passed, from the last line of a ``pytest -q`` run — and only when nothing failed or errored."""
    last = output.strip().splitlines()[-1] if output.strip() else ""
    found = re.search(r"(\d+) passed", last)
    if not found or re.search(r"\b\d+ (failed|errors?)\b", last):
        raise Stop("the test suite did not pass:\n" + "\n".join(output.strip().splitlines()[-15:]))
    return int(found.group(1))


def git_changed(run, path: str) -> bool:
    return bool(run("git", "status", "--porcelain", "--", path, capture=True).strip())


def disarm(run, repository: Path, policy: Path) -> list[str]:
    """Turn the switch off in the file, commit it when HEAD differs, push. Never raises: the problems found
    are returned, and a state is reported only after it has been read back (file, HEAD, origin/main).
    """
    problems: list[str] = []
    try:
        if switch_state(policy=policy) != "disabled":
            set_switch("disabled", policy)
        if git_changed(run, POLICY_RELATIVE):
            run("git", "add", "--", POLICY_RELATIVE)
            run("git", "commit", "-q", "-m", "Disarm after the canary: external_acquisition disabled")
    except Stop as failure:
        problems.append(f"the file or its commit: {failure}")
    try:
        run("git", "push", "origin", "main")
    except Stop as failure:
        problems.append(f"the push (the file and the local commit may be fine): {failure}")
    try:
        if switch_state(policy=policy) != "disabled":
            problems.append("the file on disk still says `enabled`")
        for reference in ("HEAD", "origin/main"):
            if switch_state(run("git", "show", f"{reference}:{POLICY_RELATIVE}", capture=True)) != "disabled":
                problems.append(f"{reference} still says `enabled`")
    except Stop as failure:
        problems.append(f"reading the state back: {failure}")
    return problems


def scope_summary(repository: Path, outlets: list[str], limits: dict | None = None) -> dict:
    """What a canary of these outlets would be, before anything is armed (no request). Refuses an unknown or unregistered outlet and a wrong count.
    ``limits``: those of the wave of a delegated authorisation; they cap the budget and can only lower it (CPD-0024)."""
    from coprepan import canary_driver, candidate_filter, policy as policy_module, registry

    unique = sorted(set(outlets))
    if len(unique) != len(outlets):
        raise Stop("an outlet is named twice")
    try:
        budget = canary_driver.canary_budget(len(unique), limits)
        registered = registry.load_registry(repository / "config" / "outlet_registry.json")
        decided = policy_module.load_policy(repository / "config" / "acquisition_policy.json")
        rules = candidate_filter.load_rules(repository / "config" / "candidate_rules.json")
        for outlet_id in unique:
            registered.resolve(outlet_id)
        pin = canary_driver.driver_pin(budget, registered, unique, decided["disabled_channels"], rules)
    except (canary_driver.CanaryStopped, registry.RegistryError, registry.UnregisteredOutlet, policy_module.PolicyError,
            candidate_filter.CandidateRulesError, OSError, ValueError) as failure:
        raise Stop(f"the scope cannot be pinned: {failure}") from failure
    return {"outlets": unique, "budget": budget.as_record(), "channels": pin["outlets"], "policy_version": decided["policy_version"],
            "total_request_ceiling": budget.total_requests_ceiling}


def delegated_scope(run, repository: Path, record_path: Path, wave_label: str, today: date) -> dict:
    """What a delegated canary is, read from the authorisation record — or a stop. Nothing is armed here.

    The record must be this checkout's, written once (exactly one commit ever touched it), unmodified
    and pushed (the caller has already required a clean tree and ``HEAD == origin/main``). The wave's
    registration, where it names one, must be the proposal with the digest the record states, and
    every outlet it registers must be registered. The coverage itself — outlets, limits, policy,
    validity, a wave used once — is :func:`coprepan.delegation.check`, repeated by the driver when it
    builds the baseline and again before the first request.
    """
    from coprepan import delegation
    from coprepan.canonical import sha256_bytes

    try:
        relative = record_path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError as failure:
        raise Stop("the authorisation record is not a file of this checkout") from failure
    if not relative.startswith(delegation.RECORDS + "/") or relative.count("/") != delegation.RECORDS.count("/") + 1:
        raise Stop(f"an authorisation record lies in {delegation.RECORDS}/")
    if not run("git", "ls-files", "--", relative, capture=True).strip():
        raise Stop("the authorisation record is not tracked")
    commits = run("git", "log", "--format=%H", "--", relative, capture=True).split()
    if len(commits) != 1:
        raise Stop(f"an authorisation record is written once: {len(commits)} commits touched {relative}. A changed scope is a new record from a new commission")
    try:
        record = delegation.load(repository / relative)
        wave = delegation.wave_of(record, wave_label)
        registration = wave["registration"]
        if registration is not None:
            proposal = repository / registration["proposal"]
            if not proposal.is_file() or sha256_bytes(proposal.read_bytes()) != registration["proposal_sha256"]:
                raise Stop(f"{wave_label}: the registration proposal is not the one the authorisation names (path or digest)")
            if not set(registration["only"]) <= set(wave["outlets"]):
                raise Stop(f"{wave_label}: the registration names outlets outside the wave")
        scope = scope_summary(repository, list(wave["outlets"]), dict(wave["limits"]))
        block = delegation.block_for(repository / relative, wave_label, repository=repository, outlets=scope["outlets"], budget=scope["budget"],
                                     total_requests_ceiling=scope["total_request_ceiling"], policy_version=scope["policy_version"], today=today)
    except delegation.AuthorizationError as refusal:
        raise Stop(f"the authorisation does not cover this canary: {refusal}") from refusal
    return {**scope, "authorization": block, "record": relative, "record_commit": commits[0], "limits": dict(wave["limits"]),
            "operator": f"{record['issued_to']} under {record['authorization_id']} ({delegation.MODE_DELEGATED}; issued by {record['issued_by']})"}


def main(argv: list[str] | None = None, *, repository: Path = REPOSITORY, scratch: Path | None = None, stdin=None, runner=None,
         today: date | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--operator", help="the person arming and freezing")
    parser.add_argument("--label", help="a word for commit messages and the baseline file, e.g. second")
    parser.add_argument("--outlet", action="append", default=[])
    parser.add_argument("--authorization", type=Path, help="delegated mode (CPD-0023): the authorisation record; with --wave, and nothing else")
    parser.add_argument("--wave", help="delegated mode: the wave of the record this canary is")
    parser.add_argument("--disarm-only", action="store_true", help="after a killed run: turn the switch off, commit, push; starts nothing")
    arguments = parser.parse_args(argv)
    run = runner or make_runner(repository)
    policy = repository / POLICY_RELATIVE
    delegated = arguments.authorization is not None or arguments.wave is not None

    if arguments.disarm_only:
        if arguments.outlet or arguments.label or arguments.operator or delegated:
            raise SystemExit("--disarm-only takes no other argument")
        problems = disarm(run, repository, policy)
        print("Disarmed: external_acquisition is `disabled` in the file, in HEAD and on origin/main." if not problems
              else "!!! NOT DISARMED CLEANLY:\n!!! " + "\n!!! ".join(problems))
        return 2 if problems else 0

    if delegated:
        # The record says who, what and how much: none of it can also be given on the command line.
        if arguments.authorization is None or arguments.wave is None or arguments.outlet or arguments.label or arguments.operator:
            raise SystemExit("the delegated mode takes --authorization and --wave, and nothing else: the outlets, the label and the operator are the record's")
        arguments.label = arguments.wave
    elif not arguments.operator or not arguments.label or not arguments.outlet:
        raise SystemExit("--operator, --label and at least the outlets of the canary are required")
    if not re.fullmatch(r"[a-z0-9-]{2,20}", arguments.label):
        raise SystemExit("--label is 2-20 characters of a-z, 0-9 and '-'")

    day = today or date.today()
    today = day.isoformat()
    mode = "delegated" if delegated else "interactive"
    baseline = repository / "docs" / "canary" / f"BASELINE_FROZEN_{today}_{arguments.label}.json"
    armed, status = False, 0
    previous = {}
    for name in ("SIGTERM", "SIGBREAK"):                     # a terminated or broken-out process still disarms
        if hasattr(signal, name):
            try:
                previous[name] = signal.signal(getattr(signal, name), lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
            except ValueError:                               # not in the main thread: no handler, the rest is unchanged
                pass
    try:
        # §0 — before anything; nothing is armed yet, so nothing needs disarming if this stops
        if run("git", "status", "--porcelain", capture=True).strip():
            raise Stop("the working tree is not clean")
        run("git", "fetch", "origin", "--quiet")
        if run("git", "rev-parse", "HEAD", capture=True).strip() != run("git", "rev-parse", "origin/main", capture=True).strip():
            raise Stop("HEAD is not origin/main")
        if switch_state(policy=policy) != "disabled":
            raise Stop("the switch is `enabled`: a previous run did not disarm. Run `python scripts/canary_operator.py --disarm-only`")
        if baseline.exists():
            raise Stop(f"{baseline.name} exists: a baseline is frozen once per label and day")
        if scratch is None:
            from coprepan import storage_roots

            scratch = storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())["RUNTIME"] / "canary"
        scratch.mkdir(parents=True, exist_ok=True)
        manifest_path = scratch / f"baseline-{arguments.label}-{today}.json"
        if manifest_path.exists():
            raise Stop(f"{manifest_path.name} exists in the runtime workspace: a baseline is built once per label and day")
        if delegated:
            scope = delegated_scope(run, repository, arguments.authorization, arguments.wave, day)
            arguments.operator, arguments.outlet = scope["operator"], scope["outlets"]
            authorized = ["--authorization", str(repository / scope["record"]), "--wave", arguments.wave]
            by = f" under {scope['authorization']['authorization_id']} ({scope['authorization']['mode']}, no typed confirmation)"
        else:
            scope = scope_summary(repository, arguments.outlet)
            authorized, by = [], ""
        outlets = [value for outlet in arguments.outlet for value in ("--outlet", outlet)]

        # §1 — arm, after the scope has been shown
        print(json.dumps(scope, indent=2))
        print(f"\nAbout to arm a canary of {len(scope['outlets'])} outlets under policy {scope['policy_version']} ({mode} mode).")
        if delegated:
            print(f"Arming{by}: the record covers exactly this canary.")
        elif typed_by_a_person("Type ARM to turn external acquisition on for exactly this canary: ", stdin) != "ARM":
            raise Stop("not armed")
        armed = True                                          # before the write: a half-written switch is also disarmed
        set_switch("enabled", policy)
        run("git", "add", "--", POLICY_RELATIVE)
        run("git", "commit", "-q", "-m", f"Arm the {arguments.label} canary: external_acquisition enabled (CPD-0016){by}")
        pinned = run("git", "rev-parse", "HEAD", capture=True).strip()

        # §2 — tests on P;  §3 — baseline: build, the operator's digest, freeze, commit, push
        print("Running the full test suite on the arming commit …", flush=True)
        passed = test_summary(run(sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", capture=True))
        run(sys.executable, "-m", "coprepan.canary_driver", "baseline", *outlets, "--commit", pinned, "--operator", arguments.operator,
            "--tests-passed", str(passed), "--required-free-bytes", str(REQUIRED_FREE_BYTES), "--out", str(manifest_path), *authorized)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["code"]["commit"] != pinned or manifest["state"] != "READY_TO_FREEZE" or manifest["blocking"]:
            raise Stop("the baseline is not ready to freeze on the arming commit")
        if delegated:
            # In the place of the typed digest: the manifest must pin exactly the authorisation this run was started
            # under — the record's digest, the wave — and must be the operator the record names. Nothing is typed.
            if manifest["canary"].get("authorization") != scope["authorization"] or manifest.get("operator") != arguments.operator:
                raise Stop("the baseline does not pin the authorisation this run was started under: nothing was frozen")
            print(f"Freezing baseline {manifest['manifest_sha256']}{by}.")
        else:
            if "authorization" in manifest["canary"]:
                raise Stop("an interactive baseline pins no delegated authorisation: nothing was frozen")
            confirm_digest(manifest, stdin)
        run(sys.executable, "-m", "coprepan.canary_driver", "freeze", "--manifest", str(manifest_path), "--operator", arguments.operator,
            "--confirm", manifest["manifest_sha256"], "--out", str(baseline))
        run("git", "add", "--", baseline.relative_to(repository).as_posix())
        run("git", "commit", "-q", "-m", f"Baseline of the {arguments.label} canary frozen (O-12, canary scope){by}")
        run("git", "push", "origin", "main")

        # §4 — preflight (the driver repeats it and refuses on anything else) and the run
        run(sys.executable, "-m", "coprepan.canary", "preflight", *outlets, "--commit", pinned, "--tests-passed", str(passed), "--tests-commit", pinned,
            "--required-free-bytes", str(REQUIRED_FREE_BYTES), "--approved-baseline", str(baseline))
        before = {path.name for path in scratch.glob("canary-receipt-*.json")}
        run_failure = None
        try:
            run(sys.executable, "-m", "coprepan.canary_driver", "run", *outlets, "--pinned-commit", pinned, "--approved-baseline", str(baseline),
                "--tests-passed", str(passed), "--required-free-bytes", str(REQUIRED_FREE_BYTES), "--receipt-dir", str(scratch))
        except Stop as failure:                              # an incomplete run still wrote a receipt: its evidence is kept
            run_failure = failure
            print(f"NOTE: the run did not complete cleanly: {failure}")
        receipts = sorted(path for path in scratch.glob("canary-receipt-*.json") if path.name not in before)
        if len(receipts) != 1:
            raise run_failure or Stop(f"{len(receipts)} new receipts in the runtime workspace: expected one")

        # §5 — verify, measure, and the evidence of record into the checkout
        run_id = receipts[0].name[len("canary-receipt-"):-len(".json")]
        evidence = repository / "docs" / "canary" / "evidence" / run_id
        evidence.mkdir(parents=True)
        for name, command in (("verification.json", "verify"), ("measurement.json", "measure")):
            extra = ["--new-filesystem-bytes", str(PLANNED_FILESYSTEM_BYTES)] if command == "measure" else []
            try:
                run(sys.executable, "-m", "coprepan.canary_driver", command, "--receipt", str(receipts[0]), *extra, "--out", str(evidence / name))
            except Stop as failure:                          # a failed verification is a result to keep, not a reason to lose the rest
                print(f"NOTE: {command} did not pass: {failure}")
                status = 1
        for path in (receipts[0], scratch / f"canary-start-state-{run_id}.json"):
            shutil.copyfile(path, evidence / path.name)
        run("git", "add", "--", evidence.relative_to(repository).as_posix())
        run("git", "commit", "-q", "-m", f"Evidence of the {arguments.label} canary {run_id}{by}")
        print(f"\nThe canary ran: {run_id}. Evidence: {evidence.relative_to(repository).as_posix()}")
        if run_failure is not None:
            status = 1
    except Stop as stop:
        print(f"\nSTOPPED: {stop}")
        status = 1
    except KeyboardInterrupt:
        print("\nINTERRUPTED")
        status = 1
    finally:
        # §6 — disarm, whatever happened after the arming
        if armed:
            problems = disarm(run, repository, policy)
            if problems:
                print("\n!!! NOT DISARMED CLEANLY:\n!!! " + "\n!!! ".join(problems)
                      + "\n!!! Then: `python scripts/canary_operator.py --disarm-only`, or set \"external_acquisition\": \"disabled\" by hand, commit and push.")
                status = 2
            else:
                print("Disarmed: external_acquisition is `disabled` in the file, in HEAD and on origin/main.")
        for name, handler in previous.items():
            signal.signal(getattr(signal, name), handler)
    if armed and status != 2:
        try:                                                  # §6: the tests on the disarmed tree
            print("Running the full test suite on the disarmed tree …", flush=True)
            print(f"Tests on the disarmed tree: {test_summary(run(sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', '-q', capture=True))} passed.")
        except Stop as failure:
            print(f"NOTE: {failure}")
            status = status or 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
