"""The operator's canary workflow in one command (runbook §9; CPD-0020 §7).

A convenience for the **person** who arms a canary — never a way around that person. It runs the
steps of the runbook in order and stops twice for something only a person at a terminal can give:

1. before arming, the typed word ``ARM``;
2. before the freeze, the **baseline digest typed by hand** — the tool shows the manifest's summary
   and its digest and compares what is typed. That is the operator's act of CPD-0016 §4; a
   confirmation that is piped in, passed as an argument or given without a terminal is refused.

Then: preflight (must be ``READY``) → the canary → verify → measure → evidence copied into the
checkout → **disarm**, tests, commit, push. Once the switch has been turned on, the disarming is
attempted whatever happens in between — an error, an interruption, a refused preflight — and the
tool exits non-zero when the checkout could not be left disarmed.

It adds no permission and changes no check: every step is the command the runbook names, and the
driver's own refusals (preflight, drift, clean tree, pushed HEAD, empty spool) apply unchanged.

    python scripts/canary_operator.py --operator "<name>" --label second --outlet <id> --outlet <id> …
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
POLICY = REPOSITORY / "config" / "acquisition_policy.json"
SWITCH = re.compile(r'("external_acquisition":\s*")(enabled|disabled)(")')
REQUIRED_FREE_BYTES = 21474836480        # the runbook's value: 20 GiB on the interim target
PLANNED_FILESYSTEM_BYTES = 2000000000000  # the 2 TB the operator named; a statement, not a measurement


class Stop(RuntimeError):
    """The workflow stops here. Nothing further is attempted except the disarming."""


def run(*command: str, capture: bool = False) -> str:
    done = subprocess.run(command, cwd=REPOSITORY, text=True, capture_output=capture, env={**os.environ, "PYTHONPATH": "src"})
    if done.returncode != 0:
        raise Stop(f"{' '.join(command[:4])} … exited {done.returncode}" + (f"\n{done.stdout}\n{done.stderr}" if capture else ""))
    return done.stdout if capture else ""


def switch_state(text: str | None = None) -> str:
    found = SWITCH.findall(POLICY.read_text(encoding="utf-8") if text is None else text)
    if len(found) != 1:
        raise Stop("the acquisition policy does not hold exactly one external_acquisition switch")
    return found[0][1]


def set_switch(state: str) -> None:
    """Rewrite the one switch and nothing else; bytes otherwise untouched, LF kept."""
    data = POLICY.read_bytes().decode("utf-8")
    switch_state(data)
    POLICY.write_bytes(SWITCH.sub(lambda m: f"{m.group(1)}{state}{m.group(3)}", data).encode("utf-8"))


def typed_by_a_person(prompt: str, stdin=None) -> str:
    """One line typed at a terminal. Refused when there is no terminal: this is where a person is asked."""
    stdin = sys.stdin if stdin is None else stdin
    if stdin is None or not stdin.isatty():
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


def tests_passed() -> int:
    out = run(sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", capture=True)
    found = re.search(r"(\d+) passed", out.strip().splitlines()[-1])
    if not found or " failed" in out.strip().splitlines()[-1]:
        raise Stop("the test suite did not pass:\n" + "\n".join(out.strip().splitlines()[-15:]))
    return int(found.group(1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--operator", required=True, help="the person arming and freezing")
    parser.add_argument("--label", required=True, help="a word for commit messages and the baseline file, e.g. second")
    parser.add_argument("--outlet", action="append", required=True)
    arguments = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9-]{2,20}", arguments.label):
        raise SystemExit("--label is 2-20 characters of a-z, 0-9 and '-'")
    from coprepan import storage_roots

    outlets = [value for outlet in arguments.outlet for value in ("--outlet", outlet)]
    baseline = REPOSITORY / "docs" / "canary" / f"BASELINE_FROZEN_{date.today().isoformat()}_{arguments.label}.json"
    armed = False
    try:
        # §0 — before anything
        if run("git", "status", "--porcelain", capture=True).strip():
            raise Stop("the working tree is not clean")
        run("git", "fetch", "origin", "--quiet")
        if run("git", "rev-parse", "HEAD", capture=True) != run("git", "rev-parse", "origin/main", capture=True):
            raise Stop("HEAD is not origin/main")
        if switch_state() != "disabled" or baseline.exists():
            raise Stop("the switch is not `disabled`, or today's baseline file for this label exists already")
        roles = storage_roots.resolve_configured_roles(env=storage_roots.workstation_environment())
        scratch = roles["RUNTIME"] / "canary"
        scratch.mkdir(parents=True, exist_ok=True)
        manifest_path = scratch / f"baseline-{arguments.label}-{date.today().isoformat()}.json"
        if manifest_path.exists():
            raise Stop(f"{manifest_path.name} exists in the runtime workspace: a baseline is built once per label and day")

        # §1 — arm
        print(f"About to arm a canary of {len(arguments.outlet)} outlets: {', '.join(arguments.outlet)}")
        if typed_by_a_person("Type ARM to turn external acquisition on for this canary: ") != "ARM":
            raise Stop("not armed")
        set_switch("enabled")
        armed = True
        run("git", "add", "--", "config/acquisition_policy.json")
        run("git", "commit", "-q", "-m", f"Arm the {arguments.label} canary: external_acquisition enabled (CPD-0016)")
        pinned = run("git", "rev-parse", "HEAD", capture=True).strip()

        # §2 — tests on P;  §3 — baseline: build, the operator's digest, freeze, commit, push
        passed = tests_passed()
        run(sys.executable, "-m", "coprepan.canary_driver", "baseline", *outlets, "--commit", pinned, "--operator", arguments.operator,
            "--tests-passed", str(passed), "--required-free-bytes", str(REQUIRED_FREE_BYTES), "--out", str(manifest_path))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        confirm_digest(manifest)
        run(sys.executable, "-m", "coprepan.canary_driver", "freeze", "--manifest", str(manifest_path), "--operator", arguments.operator,
            "--confirm", manifest["manifest_sha256"], "--out", str(baseline))
        run("git", "add", "--", str(baseline.relative_to(REPOSITORY).as_posix()))
        run("git", "commit", "-q", "-m", f"Baseline of the {arguments.label} canary frozen (O-12, canary scope)")
        run("git", "push", "origin", "main")

        # §4 — preflight (the driver repeats it and refuses on anything else) and the run
        run(sys.executable, "-m", "coprepan.canary", "preflight", *outlets, "--commit", pinned, "--tests-passed", str(passed), "--tests-commit", pinned,
            "--required-free-bytes", str(REQUIRED_FREE_BYTES), "--approved-baseline", str(baseline))
        before = {path.name for path in scratch.glob("canary-receipt-*.json")}
        try:
            run(sys.executable, "-m", "coprepan.canary_driver", "run", *outlets, "--pinned-commit", pinned, "--approved-baseline", str(baseline),
                "--tests-passed", str(passed), "--required-free-bytes", str(REQUIRED_FREE_BYTES), "--receipt-dir", str(scratch))
        finally:
            receipts = sorted(path for path in scratch.glob("canary-receipt-*.json") if path.name not in before)

        # §5 — verify, measure, and the evidence of record into the checkout
        if len(receipts) != 1:
            raise Stop(f"{len(receipts)} new receipts in the runtime workspace: expected one")
        run_id = receipts[0].name[len("canary-receipt-"):-len(".json")]
        evidence = REPOSITORY / "docs" / "canary" / "evidence" / run_id
        evidence.mkdir(parents=True)
        for name, command in (("verification.json", "verify"), ("measurement.json", "measure")):
            extra = ["--new-filesystem-bytes", str(PLANNED_FILESYSTEM_BYTES)] if command == "measure" else []
            try:
                run(sys.executable, "-m", "coprepan.canary_driver", command, "--receipt", str(receipts[0]), *extra, "--out", str(evidence / name))
            except Stop as failure:              # a failed verification is a result to keep, not a reason to lose the rest
                print(f"NOTE: {command} did not pass: {failure}")
        for path in (receipts[0], scratch / f"canary-start-state-{run_id}.json"):
            shutil.copyfile(path, evidence / path.name)
        run("git", "add", "--", str(evidence.relative_to(REPOSITORY).as_posix()))
        run("git", "commit", "-q", "-m", f"Evidence of the {arguments.label} canary {run_id}")
        print(f"\nThe canary ran: {run_id}. Evidence: {evidence.relative_to(REPOSITORY).as_posix()}")
    except Stop as stop:
        print(f"\nSTOPPED: {stop}")
        status = 1
    except KeyboardInterrupt:
        print("\nINTERRUPTED")
        status = 1
    else:
        status = 0
    finally:
        # §6 — disarm, whatever happened after the arming
        if armed:
            try:
                if switch_state() != "disabled":
                    set_switch("disabled")
                    run("git", "add", "--", "config/acquisition_policy.json")
                    run("git", "commit", "-q", "-m", f"Disarm after the {arguments.label} canary: external_acquisition disabled")
                run("git", "push", "origin", "main")
                print("Disarmed: external_acquisition is `disabled`, committed and pushed.")
            except Stop as failure:
                print(f"\n!!! NOT DISARMED CLEANLY: {failure}\n!!! Set \"external_acquisition\": \"disabled\" in config/acquisition_policy.json, commit and push it now.")
                return 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
