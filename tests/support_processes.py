"""Test support: run ``adversarial_child.py`` as real, separate processes — and kill them.

A killed child is killed from outside (``TerminateProcess`` / ``SIGKILL``) while it stands at a
crashpoint: no ``finally`` runs, no buffer is flushed, no handle is closed by its own code. What
the next process finds is what a real interruption leaves. (A power failure can lose more — data
the system had not yet written out. That is not simulated here, and not claimed.)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

CHILD = Path(__file__).with_name("adversarial_child.py")
ENVIRONMENT = {**{k: v for k, v in os.environ.items() if not (k.startswith("COPREPAN_") and k.endswith("_ROOT"))},
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}


class ChildFailed(AssertionError):
    pass


def start(*arguments) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(CHILD), *map(str, arguments)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=ENVIRONMENT)


def finish(process: subprocess.Popen, timeout: float = 120) -> dict:
    out, err = process.communicate(timeout=timeout)
    if process.returncode != 0:
        raise ChildFailed(err.decode("utf-8", "replace").strip().splitlines()[-1] if err.strip() else f"exit {process.returncode}")
    return json.loads(out.decode("utf-8").strip().splitlines()[-1])


def child(*arguments, timeout: float = 120) -> dict:
    """Run one child to its end and return what it printed. A child that fails fails the test."""
    return finish(start(*arguments), timeout)


def kill_at(scenario: str, base: Path, crashpoint: str, *extra) -> None:
    """Start a scenario, wait until it stands at the crashpoint, and kill it there."""
    base.mkdir(parents=True, exist_ok=True)
    process = start(scenario, base, crashpoint, *extra)
    marker, deadline = base / "AT_CRASHPOINT", time.monotonic() + 90
    while not marker.exists():
        if process.poll() is not None:
            raise ChildFailed(f"{crashpoint} was never reached (exit {process.returncode}): "
                              + process.stderr.read().decode("utf-8", "replace")[-300:])
        if time.monotonic() > deadline:
            process.kill()
            raise ChildFailed(f"{crashpoint} was not reached in time")
        time.sleep(0.005)
    time.sleep(0.05)              # the marker is written just before the child blocks
    process.kill()
    process.wait(timeout=30)
    assert process.returncode != 0
    os.replace(marker, base / "WAS_KILLED_AT")   # the next process must not mistake it for its own


def race(kind: str, base: Path, workers: int) -> list[dict]:
    """Start ``workers`` processes that wait at a gate, open the gate, and collect what each did."""
    base.mkdir(parents=True, exist_ok=True)
    gate = base / "GO"
    processes = [start("race", kind, base, number, gate) for number in range(workers)]
    time.sleep(1.0)               # every worker has imported and is polling the gate
    gate.write_text("go", encoding="utf-8")
    return [finish(process) for process in processes]
