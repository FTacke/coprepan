"""One writer per workspace (decision CPD-0009 §2).

The ledger, the request log and every append-only table of a workspace assume a single writer.
Two processes writing one workspace lose records without either noticing (measured 2026-10-08:
600 ledger transitions reported, 389 on disk, the ledger unreadable afterwards). This module
makes the assumption a fact: an operation that writes a workspace holds its lock, and a second
process is refused at once — it does not wait, and it does not write.

The lock is an **operating-system lock on an open file**, not the existence of a file. When the
holder dies, however it dies, the system releases it: there is no stale lock to detect, to age
or to break. The lock file itself is empty, is never removed, and means nothing by being there.
(Nothing about the holder is written into the workspace: a process id and a wall-clock time
would make two otherwise identical workspaces differ.)
"""

from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

LOCK_NAME = ".writer.lock"
_held: dict[str, int] = {}  # this process's locks: resolved path → nesting depth


class WorkspaceBusy(RuntimeError):
    """Another process is writing this workspace."""


def _lock(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)   # byte 0 of an empty file: lockable beyond its end
    else:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def writes_workspace(purpose: str):
    """Decorator for an operation whose first argument is a workspace (anything with ``.root``):
    the operation runs holding that workspace's writer lock.
    """
    def decorate(function):
        @functools.wraps(function)
        def wrapper(workspace, *args, **kwargs):
            with exclusive(workspace.root, purpose):
                return function(workspace, *args, **kwargs)
        return wrapper
    return decorate


@contextmanager
def exclusive(directory: Path, purpose: str) -> Iterator[None]:
    """Hold the writer lock of a workspace for the duration of one operation.

    Re-entrant within a process (a pipeline step may call another). Raises :class:`WorkspaceBusy`
    immediately when another process holds it. Closing the descriptor releases the lock, and so
    does the end of the process, whatever ended it.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    key = str(directory.resolve())
    if key in _held:
        _held[key] += 1
        try:
            yield
        finally:
            _held[key] -= 1
        return
    descriptor = os.open(directory / LOCK_NAME, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0))
    try:
        _lock(descriptor)
    except OSError as error:
        os.close(descriptor)
        raise WorkspaceBusy(f"{directory.name}: another process is writing this workspace; refused: {purpose}") from error
    _held[key] = 1
    try:
        yield
    finally:
        del _held[key]
        os.close(descriptor)
