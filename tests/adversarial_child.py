"""Child process of the adversarial tests (``tests/test_crash_recovery.py``, ``test_concurrency.py``).

Never imported by a test: it is *run* as a separate Python process, so that a pipeline step can be
killed from outside at a chosen point and a second, independent process can then look at what is
on disk. Nothing here is production code and production code contains no crash hook: the
crashpoints are installed by wrapping functions **in this process only**.

    python adversarial_child.py pipeline <base> [crashpoint]     the recorded-replay canary
    python adversarial_child.py http <base> [crashpoint]         one HTTP pass against a loopback server
    python adversarial_child.py diagnose|repair|state <base>
    python adversarial_child.py replay <base>                    replay with every socket forbidden
    python adversarial_child.py race <kind> <base> <worker> <gate>

At a crashpoint the process writes ``<base>/AT_CRASHPOINT`` and then blocks; the parent kills it.
A crashpoint is ``name`` or ``name@n`` (the n-th time the point is reached, default 1).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE)]

from coprepan import acquisition, core_pipeline as C, document_identity, extraction, jsonl, layer_store, ledger, pack  # noqa: E402
from coprepan import preservation  # noqa: E402

T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
_REAL_WRITE, _REAL_OPEN = os.write, open


# --- crashpoints ------------------------------------------------------------------------------------


class Crash:
    def __init__(self, base: Path, spec: str | None) -> None:
        self.base, self.count = base, 0
        self.name, _, nth = (spec or "").partition("@")
        self.nth = int(nth or 1)

    def at(self, name: str) -> None:
        if name != self.name:
            return
        self.count += 1
        if self.count == self.nth:
            sys.stdout.flush()
            with _REAL_OPEN(self.base / "AT_CRASHPOINT", "w", encoding="utf-8") as handle:
                handle.write(name)
            time.sleep(3600)                      # the parent kills this process here


class _HalfWriter:
    """A file object that writes the first half of what it is given, then reaches the crashpoint."""

    def __init__(self, handle, crash: Crash, name: str) -> None:
        self._handle, self._crash, self._name = handle, crash, name

    def write(self, data):
        self._handle.write(data[: len(data) // 2])
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._crash.at(self._name)
        return self._handle.write(data[len(data) // 2:])

    def __getattr__(self, name):
        return getattr(self._handle, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._handle.__exit__(*exc)


def install(crash: Crash) -> None:
    """Wrap the functions a crashpoint lies in. Only the named crashpoint ever fires."""
    if not crash.name:
        return

    def before(owner, attribute, name, when=lambda *a, **k: True):
        original = getattr(owner, attribute)

        def wrapper(*args, **kwargs):
            if when(*args, **kwargs):
                crash.at(name)
            return original(*args, **kwargs)
        setattr(owner, attribute, wrapper)

    def after(owner, attribute, name):
        original = getattr(owner, attribute)

        def wrapper(*args, **kwargs):
            result = original(*args, **kwargs)
            crash.at(name)
            return result
        setattr(owner, attribute, wrapper)

    def half_os_write(owner, attribute, name, when=lambda *a, **k: True):
        """Inside ``owner.attribute`` an ``os.write`` puts half its bytes on disk, then the crashpoint."""
        original = getattr(owner, attribute)

        def wrapper(*args, **kwargs):
            if not when(*args, **kwargs):
                return original(*args, **kwargs)

            def write(descriptor, data):
                written = _REAL_WRITE(descriptor, data[: len(data) // 2])
                os.fsync(descriptor)
                crash.at(name)
                return written + _REAL_WRITE(descriptor, data[len(data) // 2:])
            os.write = write
            try:
                return original(*args, **kwargs)
            finally:
                os.write = _REAL_WRITE
        setattr(owner, attribute, wrapper)

    def half_open(module, name, wanted):
        previous = getattr(module, "open", _REAL_OPEN)   # shims chain: several crashpoints may sit in one module

        def shim(path, mode="r", *args, **kwargs):
            handle = previous(path, mode, *args, **kwargs)
            return _HalfWriter(handle, crash, name) if "b" in mode and any(c in mode for c in "xwa") and wanted(str(path)) else handle
        module.open = shim

    # acquisition
    from coprepan import canonical, fetcher, http_acquisition
    # run.json is written under a staging name and renamed: half of it is half of the staging file
    half_open(canonical, "run_record_partial", lambda path: "run.json.part-" in path)
    half_open(pack, "warcinfo_partial", lambda path: path.endswith(".open"))
    half_os_write(pack.OpenPack, "append", "pack_append_partial")
    after(pack.OpenPack, "append", "after_pack_append")
    half_os_write(ledger.Ledger, "_append", "ledger_line_torn")
    for state in ("FETCHED", "RAW_VERIFIED", "PRESERVATION_PENDING", "RAW_PRESERVED"):
        before(ledger.Ledger, "transition", f"before_ledger_{state}", lambda self, subject, new_state, **k: new_state == state)
    # seal
    before(pack, "write_bytes_atomic", "seal_before_index", lambda final, data: str(final).endswith(".index.jsonl"))
    before(pack, "write_bytes_atomic", "seal_before_manifest", lambda final, data: str(final).endswith(".pack.json"))
    # promotion
    before(preservation, "promote", "before_promotion")
    before(preservation, "write_bytes_exclusive", "after_master_before_manifest")
    before(preservation, "verify_master", "before_raw_preserved")
    real_copy = preservation.shutil.copyfileobj

    class _Shutil:
        @staticmethod
        def copyfileobj(reader, writer, length=0):
            if crash.name == "promotion_partial_copy":
                writer.write(reader.read()[:200])
                writer.flush()
                os.fsync(writer.fileno())
                crash.at("promotion_partial_copy")
            return real_copy(reader, writer, length)
    preservation.shutil = _Shutil
    # identity, extraction, layers
    before(C, "_extract_stored", "after_identity_before_extraction")
    before(document_identity.IdentityTables, "assign_version", "adopt_mid_derive",
           lambda self, *a, **k: ".rebuild-" in str(self._versions))   # only inside the store an adoption is building
    before(document_identity.IdentityTables, "assign_version", "after_extraction_before_version")
    before(document_identity.IdentityTables, "_relate", "after_rows_before_relation")
    # modules import append_row by name, so the wrapper goes where it is called
    half_os_write(document_identity, "append_row", "table_row_torn", lambda path, schema, row: str(path).endswith("versions.jsonl"))
    half_os_write(http_acquisition, "append_chained", "request_row_torn", lambda path, schema, row: row.get("event") == "FINISHED")
    half_open(layer_store, "layer_payload_partial", lambda path: path.endswith("payload"))
    half_open(layer_store, "layer_before_metadata", lambda path: path.endswith("manifest.json"))
    real_rename = os.rename

    def rename(source, target, *args, **kwargs):
        if ".staging" in str(source):
            crash.at("layer_before_publish")
        result = real_rename(source, target, *args, **kwargs)
        if ".replaced-" in str(target):
            crash.at("adopt_after_move_aside")   # the old identity directory is aside, the rebuilt one not yet in place
        return result
    os.rename = rename
    # http
    before(fetcher.HttpFetcher, "fetch", "after_intent_before_request",
           lambda self, request, **k: request.fetch_kind == acquisition.FETCH_KIND_ITEM)
    before(http_acquisition, "record_exchange", "after_response_before_record",
           lambda workspace, ledger_, packs, run, outlet, exchange: "robots" not in exchange.requested_url and ".xml" not in exchange.requested_url)


# --- scenarios --------------------------------------------------------------------------------------


def canary(base: Path):
    from test_core_pipeline import OUTLET, Canary, exchanges, make_registry
    one = Canary.__new__(Canary)
    one.workspace, one.root = C.Workspace(base / "workspace"), base / "preservation_root"
    for directory in (one.workspace.root, one.root):
        directory.mkdir(parents=True, exist_ok=True)
    one.registry, one.items = make_registry(), exchanges()
    one.run = C.recorded_replay_run(T0, [OUTLET], {"fixture_set": "canary"})
    one.pack_id, one.extractor = pack.pack_id(OUTLET, "20261007"), extraction.BASELINE
    return one


def pipeline(base: Path) -> dict:
    one = canary(base)
    finished = acquisition.read_run_result(one.workspace.root, one.run.run_id) is not None
    acquired = None if finished else one.acquire()   # a finished run is not opened again; its later stages can be repeated
    one.preserve()
    results = one.derive()
    if not finished:
        acquisition.close_run(one.workspace.root, one.run, finished_at=T0 + timedelta(hours=9), status="COMPLETED",
                              counts=acquired["counts"], pack_ids=[one.pack_id])
    return {"results": len(results), "versions": sorted({r["document_version_id"] for r in results if r.get("document_version_id")})}


def http(base: Path, start_minutes: int = 0) -> dict:
    from support_http import LocalSite
    from test_offline_e2e import Pass, script
    with LocalSite() as site:
        script(site)
        one = Pass(base, site, start=T0 + timedelta(minutes=start_minutes))
        one.acquire()
        one.preserve()
        one.derive()
        return {"summary": one.summary, "requested_paths": site.paths()}


def snapshot(base: Path) -> dict:
    """What is on disk, read by this process alone. Every reading that fails is reported as text."""
    workspace, root = C.Workspace(base / "workspace"), base / "preservation_root"

    def attempt(function):
        try:
            return function()
        except Exception as error:  # noqa: BLE001 - a snapshot reports, it does not judge
            return f"{type(error).__name__}: {str(error)[:140]}"

    def tables():
        t = document_identity.IdentityTables(workspace.identity)
        return {"documents": sorted(t.documents), "observations": sorted(t.observations),
                "versions": sorted(t.version_observations), "relations": sorted(
                    (r["relation"], r["document_id"], r["target_document_id"]) for r in t.relations)}

    def layers():
        if not workspace.layers.is_dir():
            return []
        return sorted(path.parent.name for path in workspace.layers.glob("extraction/*/*/*/PROMOTED"))

    def masters():
        out = {}
        for manifest in sorted(root.glob("preservation/manifests/*/*.json")):
            area, object_id = manifest.parent.name, manifest.stem
            out[f"{area}/{object_id}"] = [json.loads(manifest.read_text(encoding="utf-8"))["sha256"],
                                         preservation.verify_master(root, area, object_id)]
        return out

    return {
        "ledger": attempt(lambda: dict(sorted(workspace.ledger().states().items()))),
        "ledger_states": attempt(lambda: dict(sorted(Counter(workspace.ledger().states().values()).items()))),
        "identity": attempt(tables), "layers": attempt(layers), "masters": attempt(masters),
        "runs_unfinished": attempt(lambda: acquisition.unfinished_runs(workspace.root)),
        "orphans": {
            "part_files": len(list(base.rglob("*.part-*"))),
            "layer_staging": len(list((workspace.layers / ".staging").glob("*"))) if (workspace.layers / ".staging").is_dir() else 0,
            "torn_sidecars": sorted(path.name.split(".torn-")[0] for path in base.rglob("*.torn-*")),
        },
    }


def replay_without_network(base: Path) -> dict:
    """Replay every extraction with socket creation forbidden, and prove the preserved bytes did not change."""
    import socket

    def forbidden(*args, **kwargs):
        raise RuntimeError("replay tried to open a socket")
    socket.socket = forbidden
    socket.create_connection = forbidden
    workspace, root = C.Workspace(base / "workspace"), base / "preservation_root"
    files = lambda: {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}  # noqa: E731
    before, statuses = files(), Counter()
    for identifier in sorted(path.stem for path in root.glob("preservation/manifests/raw/*.json")):
        preserved = C.open_preserved_pack(root, identifier)
        for fetch_id, entry in preserved.entries.items():
            if entry.body_sha256 is not None and preserved.fetch_record(fetch_id)["fetch_kind"] == acquisition.FETCH_KIND_ITEM:
                statuses[C.replay_extraction(workspace, preservation_root=root, identifier=identifier, fetch_id=fetch_id,
                                             now=T0 + timedelta(days=1))["status"]] += 1
    return {"replayed": dict(statuses), "preserved_files_unchanged": files() == before, "files": len(before)}


# --- races ------------------------------------------------------------------------------------------


def race(kind: str, base: Path, number: int, gate: Path) -> dict:
    out: dict = {"worker": number, "ok": 0, "errors": {}, "outcomes": {}}

    def note(key: str) -> None:
        out["outcomes"][key] = out["outcomes"].get(key, 0) + 1

    def attempt(function, label=None):
        try:
            result = function()
            out["ok"] += 1
            note(label(result) if label else "ok")
        except Exception as error:  # noqa: BLE001 - the worker reports what the code did
            out["errors"][type(error).__name__] = out["errors"].get(type(error).__name__, 0) + 1

    while not gate.exists():
        time.sleep(0.001)
    if kind == "ledger":
        book = ledger.Ledger(base / "ledger.jsonl", ledger.PRESERVATION)
        for i in range(150):
            attempt(lambda: book.transition(f"w{number}-s{i}", "DISCOVERED", at=T0))
    elif kind == "chained":
        for i in range(120):
            attempt(lambda: jsonl.append_chained(base / "t.jsonl", "coprepan-x/v2", {"w": number, "i": i, "pad": "x" * 300}))
    elif kind == "table":
        for i in range(150):
            attempt(lambda: jsonl.append_row(base / "t.jsonl", "coprepan-x/v1", {"w": number, "i": i, "pad": "x" * 300}))
    elif kind in ("layer_same", "layer_conflict"):
        store = layer_store.LayerStore(base)
        for i in range(25):
            fingerprint = layer_store.fingerprint("extraction", "x/1", {"body": hashlib.sha256(str(i).encode()).hexdigest()})
            payload = b"same answer" if kind == "layer_same" else f"answer of worker {number}".encode()
            attempt(lambda: store.put("extraction", fingerprint, payload), lambda stored: stored.status)
    elif kind == "promote":
        source = base / "source.bin"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        for i in range(10):
            attempt(lambda: preservation.promote(source, root=base / "root", area="raw", object_id="the-object",
                                                 relative_path="uy/the-object.bin", declared_sha256=digest, now=T0),
                    lambda result: result.action)
    elif kind == "promote_conflict":     # one identity, another content per process
        source = base / f"source{number}.bin"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        attempt(lambda: preservation.promote(source, root=base / "root", area="raw", object_id="the-object",
                                             relative_path="uy/the-object.bin", declared_sha256=digest, now=T0),
                lambda result: result.action)
        out["sha256"] = digest
    elif kind == "pipeline":
        attempt(lambda: pipeline(base))
        if out["errors"]:
            out["refused"] = list(out["errors"])
    elif kind == "plan":
        from test_offline_e2e import SCHEDULE
        from coprepan import http_acquisition as H, schedule
        workspace = C.Workspace(base / "workspace")
        due, _ = schedule.plan(H.discovery_tables(workspace).candidates, H.request_rows(workspace), SCHEDULE,
                               now=T0 + timedelta(days=30), current_policy_version="loopback-test/1", limit=50)
        out["plan"] = [[state.candidate_id, state.state, state.as_row()["due_at"]] for state in due]
    return out


def main(argv: list[str]) -> int:
    command, base = argv[1], Path(argv[2] if argv[1] != "race" else argv[3])
    if command in ("pipeline", "http"):
        install(Crash(base, argv[3] if len(argv) > 3 else None))
        result = pipeline(base) if command == "pipeline" else http(base, int(argv[4]) if len(argv) > 4 else 0)
    elif command == "state":
        result = snapshot(base)
    elif command in ("diagnose", "repair"):
        from coprepan import recovery
        root = base / "preservation_root"
        result = (recovery.diagnose(base / "workspace", root if root.is_dir() else None) if command == "diagnose"
                  else recovery.repair(base / "workspace"))
    elif command in ("diagnose_full", "verify", "adopt"):
        # with the registry and the root: the identity tables are held against the preserved evidence
        from coprepan import identity_rebuild, recovery
        one = canary(base)
        if command == "diagnose_full":
            result = recovery.diagnose(base / "workspace", base / "preservation_root", registry=one.registry)
        elif command == "verify":
            result = identity_rebuild.verify(one.workspace, one.registry, preservation_root=one.root)
        else:
            install(Crash(base, argv[3] if len(argv) > 3 else None))
            result = identity_rebuild.adopt(one.workspace, one.registry, preservation_root=one.root,
                                            replace_conflicting=len(argv) > 4 and argv[4] == "replace")
    elif command == "recover":
        # One independent process after a kill: say what is there, repair torn tails, run the
        # interrupted pipeline to its end, run it once more, and report every step.
        from coprepan import recovery
        scenario = pipeline if argv[3] == "pipeline" else http
        result = {"diagnosis": recovery.diagnose(base / "workspace", base / "preservation_root")}
        result["repair"] = recovery.repair(base / "workspace")
        result["after_repair"] = recovery.diagnose(base / "workspace", base / "preservation_root")["classification"]
        result["resumed"] = scenario(base)
        result["state"] = snapshot(base)
        result["again"] = scenario(base)
        result["state_again"] = snapshot(base)
        result["final"] = recovery.diagnose(base / "workspace", base / "preservation_root")
    elif command == "hold":
        # Take the workspace's writer lock, say so, and keep it until killed.
        from coprepan.exclusive import exclusive
        with exclusive(base / "workspace", "held by a test"):
            with _REAL_OPEN(base / "AT_CRASHPOINT", "w", encoding="utf-8") as handle:
                handle.write("holding")
            time.sleep(3600)
        result = {}
    elif command == "replay":
        result = replay_without_network(base)
    elif command == "race":
        result = race(argv[2], base, int(argv[4]), Path(argv[5]))
    else:
        raise SystemExit(f"unknown command {command!r}")
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
