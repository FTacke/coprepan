"""Incremental workspace checks (CPD-0037): what was appended since the last verified point is checked, nothing else.

``recovery.diagnose`` reads the whole workspace: every table from its first line, every sealed pack re-hashed, every layer
re-read, every closed run's anchors against whole tables. That is the full audit, and it stays exactly as it is. A writer that
checks the workspace between its stages (the canary driver at each outlet, the intake controller at each cycle) needs to know
something narrower: **did anything I or an interrupted predecessor wrote since the last check leave the workspace in a state
that is not CLEAN or resumable?** Because every store of a workspace is append-only or write-once, that question has an answer
that depends only on what is new:

* an append-only table is checked from an **anchor** -- its size, row count and the SHA-256 and length of its last verified
  line. The anchor line is re-read and must still be there; only the bytes after it are parsed and, for a chained table,
  authenticated against the anchor's hash. A shorter table or a different anchor line is a finding;
* a sealed pack is write-once: once verified (manifest, pack hash, index against a fresh scan), its entries are kept in the
  check state and it is not re-hashed on the fast path. Open packs are scanned every time (there are few);
* derived tables (candidates, identity) are checked row by row as they grow, against the derivation state of every earlier
  row (by hash), with the same rules as the full check;
* a closed run's evidence heads are checked against the anchors and the tail lines read in the same pass.

Bit rot of old, unchanged objects is not visible to an incremental check -- only a re-read proves fixity, and only for the
moment of that re-read. Two things cover it: a **rotating audit** that re-verifies a bounded number of the longest-unaudited
sealed packs and layer answers at every incremental check (a guaranteed share, never starved), and the **full audit**
(``recovery.diagnose``) whenever there is no valid check state or the last full audit is older than ``FULL_EVERY``.

Any finding of an incremental check -- a broken anchor, a torn tail, a chain break, a pack that does not verify, a ledger
transition that does not fit, an unsupported candidate -- is never classified here: the full ``recovery.diagnose`` runs and
its result is returned. The incremental check only ever answers CLEAN or INCOMPLETE_RESUMABLE by itself.

The check state is kept in ``checks/verified-<n>.state`` of the workspace (JSON lines, deliberately not ``*.jsonl``: it is no
table of the workspace, and a damaged state must never make the workspace look damaged): chained rows, one per check (a full row after a
full audit, a delta row after an incremental check). It is a cache of verification evidence, never primary evidence: a
missing, torn, broken or foreign state file only means that the next check is a full audit. It is loaded once per process and
extended in memory; a check costs what was appended since the last one (plus the name listings of the pack and layer
directories, which read names, not files).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from . import acquisition, discovery, evidence, identity, layer_store, naming, pack, recovery
from .canonical import canonical_json, sha256_bytes
from .core_pipeline import Workspace
from .identity import format_instant
from .jsonl import CHAIN_FIELD, JsonlError, append_chained, read_chained
from .ledger import LEDGER_RECORD_SCHEMA, PRESERVATION

CHECK_VERSION = "incremental-check/1"
STATE_SCHEMA = naming.schema_id("check-state", 1)
STATE_DIRECTORY = "checks"
FULL_EVERY = timedelta(days=7)
LEDGER = evidence.LEDGER
_HELD = ("FETCHED", "RAW_VERIFIED", "PRESERVATION_PENDING", "RAW_PRESERVED")
_IDENTITY = ("documents", "observations", "versions", "relations")


@dataclass(frozen=True)
class AuditBudget:
    """The rotating audit of one incremental check: at most this many of the longest-unaudited sealed packs (and their bytes)
    and layer answers are re-verified. Measured at about 13 ms per pack on the workstation (2,275 packs, 30 s)."""
    packs: int = 8
    pack_bytes: int = 64 * 1024 * 1024
    layers: int = 32


class Finding(Exception):
    """Something an incremental check does not classify: the full audit decides."""


def _h(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def _without_schema(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "schema"}


# --- the check state ------------------------------------------------------------------------------------------


@dataclass
class CheckState:
    valid: bool = False
    reason: str | None = "no check state yet"
    full_at: str | None = None
    path: Path | None = None
    file_size: int = 0
    tables: dict[str, dict[str, Any]] = field(default_factory=dict)       # relative path -> anchor
    ledger_seq: int = 0
    ledger_states: dict[str, str] = field(default_factory=dict)
    packs: dict[str, dict[str, Any]] = field(default_factory=dict)        # sealed and verified: entries, audited_at
    held_by: dict[str, str] = field(default_factory=dict)                 # fetch -> verified sealed pack holding it
    runs: set[str] = field(default_factory=set)                           # closed and verified
    missing: set[str] = field(default_factory=set)                        # candidates the evidence gives and the table lacks
    layers: dict[str, str] = field(default_factory=dict)                  # "stage/fingerprint" -> audited_at
    planned_in_pack: set[str] = field(default_factory=set)
    planned_without_bytes: set[str] = field(default_factory=set)
    unfinished: dict[str, list[str]] = field(default_factory=dict)       # request id -> [url, kind]
    repeated: dict[str, list[str]] = field(default_factory=dict)
    inputs: set[str] = field(default_factory=set)                         # "channel|input_fetch_id"
    first_events: set[str] = field(default_factory=set)                  # candidates whose first event has been read
    derived: dict[str, list[str]] = field(default_factory=dict)          # candidate -> hashes of the rows the evidence gives
    stored: dict[str, str] = field(default_factory=dict)                 # candidate -> hash of its stored row
    documents: dict[str, str] = field(default_factory=dict)              # document -> row hash
    document_keys: dict[str, str] = field(default_factory=dict)          # "outlet|url_key" -> document
    observations: dict[str, str] = field(default_factory=dict)           # fetch -> row hash
    observation_documents: dict[str, str] = field(default_factory=dict)  # fetch -> document
    versions: dict[str, list[str]] = field(default_factory=dict)         # version -> [document, text sha]

    def apply(self, delta: dict[str, Any]) -> None:
        if delta.get("kind") == "full":
            fresh = CheckState(path=self.path, file_size=self.file_size)
            self.__dict__.update(fresh.__dict__)
            self.full_at = delta["at"]
        self.valid, self.reason = True, None
        self.tables.update(delta.get("tables", {}))
        self.ledger_seq = delta.get("ledger_seq", self.ledger_seq)
        self.ledger_states.update(delta.get("ledger_states", {}))
        for identifier, entry in delta.get("packs", {}).items():
            self.packs[identifier] = entry
            self.held_by.update({fetch: identifier for fetch, _ in entry["entries"]})
        for identifier, at in delta.get("audited_packs", {}).items():
            if identifier in self.packs:
                self.packs[identifier]["audited_at"] = at
        self.runs.update(delta.get("runs", []))
        self.layers.update(delta.get("layers", {}))
        for name in ("planned_in_pack", "planned_without_bytes", "missing"):
            if name in delta:
                getattr(self, name).difference_update(delta[name]["out"])
                getattr(self, name).update(delta[name]["in"])
        if "unfinished" in delta:
            self.unfinished, self.repeated = dict(delta["unfinished"]), dict(delta["repeated"])
        self.inputs.update(delta.get("inputs", []))
        self.first_events.update(delta.get("first_events", []))
        for candidate, hashes in delta.get("derived", {}).items():
            self.derived.setdefault(candidate, [])
            self.derived[candidate] += [h for h in hashes if h not in self.derived[candidate]]
        self.stored.update(delta.get("stored", {}))
        self.documents.update(delta.get("documents", {}))
        self.document_keys.update(delta.get("document_keys", {}))
        self.observations.update(delta.get("observations", {}))
        self.observation_documents.update(delta.get("observation_documents", {}))
        self.versions.update(delta.get("versions", {}))


def _state_files(root: Path) -> list[Path]:
    directory = Path(root) / STATE_DIRECTORY
    if not directory.is_dir():
        return []
    found = []
    for path in directory.glob("verified-*.state"):
        number = path.stem.split("-", 1)[1]
        if number.isdigit():
            found.append((int(number), path))
    return [path for _, path in sorted(found)]


def load(root: Path) -> CheckState:
    """The check state of a workspace, replayed from its newest state file. Anything unreadable is no state."""
    files = _state_files(root)
    state = CheckState(path=files[-1] if files else None)
    if not files:
        return state
    try:
        rows = read_chained(files[-1], STATE_SCHEMA)
    except (JsonlError, OSError, ValueError) as error:
        return CheckState(path=None, reason=f"the check state is unreadable: {error}")
    if not rows or rows[0].get("kind") != "full":
        return CheckState(path=None, reason="the check state does not begin with a full audit")
    for row in rows:
        if row.get("check_version") != CHECK_VERSION:
            return CheckState(path=None, reason=f"the check state was written by {row.get('check_version')}")
        state.apply(row)
    state.path, state.file_size = files[-1], files[-1].stat().st_size
    return state


def _persist(root: Path, state: CheckState, delta: dict[str, Any]) -> None:
    """Append the row. A state file that another process extended since this one read it is not extended: this process's
    state is then no longer the file's, and it is dropped (the next check is a full audit)."""
    delta = {"check_version": CHECK_VERSION, **delta}
    if delta["kind"] == "full" or state.path is None:
        files = _state_files(root)
        number = (int(files[-1].stem.split("-", 1)[1]) + 1) if files else 0
        state.path = Path(root) / STATE_DIRECTORY / f"verified-{number}.state"   # a new file; the old ones are kept
        state.file_size = 0
    size = state.path.stat().st_size if state.path.exists() else 0
    if size != state.file_size:
        state.valid, state.reason = False, "another process extended the check state"
        return
    append_chained(state.path, STATE_SCHEMA, delta)
    state.file_size = state.path.stat().st_size


# --- reading what is new --------------------------------------------------------------------------------------


def _tables(root: Path) -> list[str]:
    """The append-only line files of a workspace, as ``recovery._tables`` names them, found without walking packs or layers."""
    out = []
    for directory, subdirectories, files in os.walk(root):
        relative = Path(directory).relative_to(root)
        if relative.parts[:1] in (("packs",), ("layers",), (STATE_DIRECTORY,)) or any(".rebuild-" in p or ".replaced-" in p for p in relative.parts):
            subdirectories[:] = []
            continue
        subdirectories[:] = [d for d in subdirectories if not (relative == Path(".") and d in ("packs", "layers", STATE_DIRECTORY))]
        out += [(relative / name).as_posix() for name in files if name.endswith(".jsonl") and ".torn-" not in name]
    return sorted(out)


def _tail(root: Path, relative: str, anchor: dict[str, Any] | None) -> tuple[list[bytes], dict[str, Any]]:
    """The complete lines after the anchor, and the anchor after them. A torn tail or a changed anchor is a finding."""
    path = Path(root) / relative
    size = path.stat().st_size
    with open(path, "rb") as handle:
        start = 0
        if anchor is not None:
            if size < anchor["size"]:
                raise Finding(f"{relative}: {size} bytes, {anchor['size']} were verified")
            if anchor["size"]:
                handle.seek(anchor["size"] - anchor["last_len"])
                last = handle.read(anchor["last_len"])
                if sha256_bytes(last) != anchor["last_sha"] or not last.endswith(b"\n"):
                    raise Finding(f"{relative}: the last verified line is no longer where it was")
            start = anchor["size"]
        handle.seek(start)
        data = handle.read(size - start)
    if data and not data.endswith(b"\n"):
        raise Finding(f"{relative}: torn tail")
    lines = data.split(b"\n")[:-1]
    if not lines:
        return [], dict(anchor or {"size": 0, "rows": 0, "last_sha": None, "last_len": 0})
    last = lines[-1] + b"\n"
    return lines, {"size": start + len(data), "rows": (anchor["rows"] if anchor else 0) + len(lines),
                   "last_sha": sha256_bytes(last), "last_len": len(last)}


def _rows(relative: str, lines: list[bytes], schema: str | None, chained_after: str | None | bool) -> list[dict[str, Any]]:
    """Parse lines; for a chained table (``chained_after`` is the hash the first line must name, ``False`` for unchained)
    authenticate each against the one before."""
    rows, previous = [], chained_after
    for line in lines:
        try:
            row = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise Finding(f"{relative}: a line is not a record: {error}") from error
        if not isinstance(row, dict):
            raise Finding(f"{relative}: a line is not a record")
        if schema is not None and row.get("schema") != schema:
            raise Finding(f"{relative}: a row of schema {row.get('schema')!r}")
        if chained_after is not False:
            if row.get(CHAIN_FIELD) != previous:
                raise Finding(f"{relative}: a new row does not follow the row before it")
            previous = sha256_bytes(line + b"\n")
        rows.append(row)
    return rows


# --- the incremental check --------------------------------------------------------------------------------------


def _incremental(root: Path, state: CheckState, *, now: datetime, audit: AuditBudget, verify_objects: bool = True) -> tuple[dict, dict]:
    workspace = Workspace(Path(root))
    at = format_instant(now)
    delta: dict[str, Any] = {"kind": "delta", "at": at}
    resumable: list[str] = []
    scope = {"tables_read_from_anchor": 0, "new_lines": 0, "packs_new": 0, "packs_open_scanned": 0, "packs_audited": 0,
             "layers_new": 0, "layers_audited": 0, "runs_checked": 0, "packs_skipped_as_verified": 0, "layers_skipped_as_verified": 0}
    chained = evidence.chained_tables()

    # --- tables: anchors and tails --------------------------------------------------------------------------
    tails: dict[str, list[bytes]] = {}
    anchors: dict[str, dict[str, Any]] = {}
    present = _tables(root)
    for relative in set(state.tables) - set(present):
        raise Finding(f"{relative}: a verified table is gone")
    for relative in present:
        lines, anchor = _tail(root, relative, state.tables.get(relative))
        tails[relative], anchors[relative] = lines, anchor
        scope["tables_read_from_anchor"] += relative in state.tables
        scope["new_lines"] += len(lines)
    from . import document_identity as D
    schemas = {"discovery/candidates.jsonl": discovery.CANDIDATE_SCHEMA, "identity/documents.jsonl": D.DOCUMENT_SCHEMA,
               "identity/observations.jsonl": D.OBSERVATION_SCHEMA, "identity/versions.jsonl": D.VERSION_SCHEMA,
               "identity/relations.jsonl": D.RELATION_SCHEMA}
    rows: dict[str, list[dict[str, Any]]] = {}
    for relative, lines in tails.items():
        before = state.tables.get(relative)
        if relative in chained:
            rows[relative] = _rows(relative, lines, chained[relative], before["last_sha"] if before else None)
        else:
            rows[relative] = _rows(relative, lines, schemas.get(relative), False)
    delta["tables"] = {k: v for k, v in anchors.items() if v != state.tables.get(k)}

    # --- ledger ---------------------------------------------------------------------------------------------
    seq, chain = state.ledger_seq, (state.tables.get(LEDGER) or {}).get("last_sha")
    states_changed: dict[str, str] = {}
    for line, row in zip(tails.get(LEDGER, []), rows.get(LEDGER, [])):
        try:
            if row["schema"] != LEDGER_RECORD_SCHEMA or row["machine"] != PRESERVATION.name:
                raise ValueError("schema or machine")
            if row["previous_record_sha256"] != chain:
                raise ValueError("does not follow the record before it")
            if row["seq"] != seq:
                raise ValueError(f"seq {row['seq']}, expected {seq}")
            current = states_changed.get(row["subject"], state.ledger_states.get(row["subject"]))
            if row["previous_state"] != current:
                raise ValueError("previous state")
            PRESERVATION.check(current, row["new_state"])
        except Exception as error:  # noqa: BLE001 -- any misfit of a ledger row is the full audit's to classify
            raise Finding(f"ledger: {error}") from error
        states_changed[row["subject"]] = row["new_state"]
        seq += 1
        chain = sha256_bytes(line + b"\n")
    delta["ledger_seq"], delta["ledger_states"] = seq, states_changed

    def ledger_state(fetch_id: str) -> str | None:
        return states_changed.get(fetch_id, state.ledger_states.get(fetch_id))

    # --- packs ----------------------------------------------------------------------------------------------
    listed = recovery._pack_ids(workspace.packs)
    gone = set(state.packs) - set(listed)
    if gone:
        raise Finding(f"verified packs are gone: {sorted(gone)[:5]}")
    in_pack_new: dict[str, str] = {}
    open_entries: dict[str, str] = {}
    new_packs: dict[str, dict[str, Any]] = {}
    for identifier in listed:
        if identifier in state.packs:
            scope["packs_skipped_as_verified"] += 1
            continue
        paths = pack._paths(workspace.packs, identifier)
        try:
            if paths["manifest"].exists():
                if verify_objects:
                    pack.verify_sealed(workspace.packs, identifier)
                entries = pack.read_index(workspace.packs, identifier)
                new_packs[identifier] = {"entries": [[e.fetch_id, e.outcome] for e in entries], "audited_at": at}
                in_pack_new.update({e.fetch_id: identifier for e in entries})
                scope["packs_new"] += 1
            elif paths["sealed"].exists():
                entries = pack.scan(paths["sealed"], identifier)
                open_entries.update({e.fetch_id: identifier for e in entries})
                resumable.append(f"{identifier}: sealing was interrupted after the rename; seal again")
            elif paths["open"].exists() and paths["open"].stat().st_size == 0:
                pass
            else:
                entries = pack.scan(paths["open"], identifier)
                open_entries.update({e.fetch_id: identifier for e in entries})
                scope["packs_open_scanned"] += 1
        except (pack.PackError, OSError, ValueError, KeyError) as error:
            raise Finding(f"{identifier}: {error}") from error
    delta["packs"] = new_packs
    audited: dict[str, str] = {}
    if verify_objects and audit.packs:
        budget = audit.pack_bytes
        for identifier in sorted(state.packs, key=lambda i: (state.packs[i].get("audited_at") or "", i))[:audit.packs]:
            paths = pack._paths(workspace.packs, identifier)
            try:
                size = paths["sealed"].stat().st_size
                if audited and size > budget:
                    break
                pack.verify_sealed(workspace.packs, identifier)
                if [[e.fetch_id, e.outcome] for e in pack.read_index(workspace.packs, identifier)] != state.packs[identifier]["entries"]:
                    raise pack.PackError("the index is not the one verified before")
            except (pack.PackError, OSError, ValueError, KeyError) as error:
                raise Finding(f"audit: {identifier}: {error}") from error
            budget -= size
            audited[identifier] = at
    delta["audited_packs"] = audited
    scope["packs_audited"] = len(audited)

    # --- ledger against packs: only the fetches whose state or pack is new ----------------------------------------
    def held(fetch_id: str) -> bool:
        return fetch_id in in_pack_new or fetch_id in open_entries or fetch_id in state.held_by

    touched = set(states_changed) | set(in_pack_new) | set(open_entries)
    moves = {"planned_in_pack": {"in": [], "out": []}, "planned_without_bytes": {"in": [], "out": []}}
    for fetch_id in sorted(touched):
        current = ledger_state(fetch_id)
        has = held(fetch_id)
        for name in moves:
            if fetch_id in getattr(state, name):
                moves[name]["out"].append(fetch_id)
        if current == "FETCH_PLANNED":
            moves["planned_in_pack" if has else "planned_without_bytes"]["in"].append(fetch_id)
        elif current in _HELD and not has:
            raise Finding(f"EVIDENCE LOST: the ledger records fetched bytes for {fetch_id} that no pack holds")
    delta.update(moves)
    planned_in_pack = (state.planned_in_pack - set(moves["planned_in_pack"]["out"])) | set(moves["planned_in_pack"]["in"])
    planned_without = (state.planned_without_bytes - set(moves["planned_without_bytes"]["out"])) | set(moves["planned_without_bytes"]["in"])
    if planned_in_pack:
        resumable.append("fetches are in a pack while the ledger says FETCH_PLANNED; sealing reconciles them")
    if planned_without:
        resumable.append("fetches were planned and nothing was recorded: interrupted before any bytes; they can be planned again")

    # --- runs -----------------------------------------------------------------------------------------------
    runs_dir = Path(root) / "runs"
    verified_runs = []
    if runs_dir.is_dir():
        for directory in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            if directory.name in state.runs:
                continue
            if not (directory / "run.json").exists():
                resumable.append("a run directory without a run record: the start itself was interrupted; start the run again")
                continue
            scope["runs_checked"] += 1
            try:
                record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
                if record.get("run_id") != directory.name or not acquisition.verify_run_record(record):
                    raise Finding(f"{directory.name}: the run record does not verify")
                result = acquisition.read_run_result(root, directory.name)
            except (OSError, ValueError, AttributeError, acquisition.AcquisitionError, acquisition.RunStateError) as error:
                raise Finding(f"{directory.name}: {error}") from error
            if result is None:
                resumable.append("runs without a result: interrupted or still running")
                continue
            for relative, head in sorted(result.get("evidence_heads", {}).items()):
                _check_head(root, relative, head, state.tables.get(relative), tails.get(relative, []), directory.name)
            verified_runs.append(directory.name)
    delta["runs"] = verified_runs

    # --- requests: intents without an end -------------------------------------------------------------------------
    unfinished, repeated = dict(state.unfinished), dict(state.repeated)
    for row in rows.get("requests/requests.jsonl", []):
        if row.get("event") == "PLANNED":
            unfinished[row["request_id"]] = [row["url"], row["fetch_kind"]]
        elif row.get("event") == "FINISHED":
            unfinished.pop(row["request_id"], None)
            repeated.pop(row["request_id"], None)
            for other, (url, kind) in list(unfinished.items()):
                if (url, kind) == (row["url"], row["fetch_kind"]):
                    repeated[other] = unfinished.pop(other)
    delta["unfinished"], delta["repeated"] = unfinished, repeated
    if unfinished:
        resumable.append("requests were planned and have no end on record: the request may or may not have been sent")

    # --- candidates: what the evidence gives, row by row -------------------------------------------------------
    new_inputs = [f"{r['channel_id']}|{r['input_fetch_id']}" for r in rows.get("discovery/inputs.jsonl", [])]
    if set(new_inputs) & state.inputs:
        raise Finding("a discovery input recorded a second time")
    # An event is written right after its input, in the same discovery call; an event id is derived from its input. So an
    # event of a new input cannot collide with an earlier event, and an event of an earlier input is not checked here.
    known_inputs = set(new_inputs)
    derived: dict[str, list[str]] = {}

    def derive(candidate: str, row_hash: str) -> None:
        held_hashes = state.derived.get(candidate, []) + derived.get(candidate, [])
        if row_hash not in held_hashes:
            derived.setdefault(candidate, []).append(row_hash)

    seen_events: dict[str, str] = {}
    first_now: set[str] = set()
    for row in rows.get("discovery/events.jsonl", []):
        if f"{row['channel_id']}|{row['input_fetch_id']}" not in known_inputs:
            raise Finding(f"discovery event {row['event_id']} of an input not read since the verified point")
        digest = _h(row)
        if seen_events.setdefault(row["event_id"], digest) != digest:
            raise Finding(f"discovery events: two different rows for {row['event_id']}")
        candidate = row.get("candidate_id")
        if candidate is not None and candidate not in state.first_events and candidate not in first_now:
            first_now.add(candidate)                      # the first event of a candidate gives its row
            derive(candidate, _h(_without_schema(discovery.candidate_from_event(row))))
    channel_of = {r["request_id"]: r["channel_id"] for r in rows.get("requests/requests.jsonl", []) if r.get("event") == "PLANNED"}
    for row in rows.get("requests/requests.jsonl", []):
        result = row.get("result") or {}
        if row.get("event") == "FINISHED" and result.get("moved_permanently_to") and row.get("attributed_from") is None:
            target = result["moved_permanently_to"]
            if row["request_id"] not in channel_of:
                raise Finding(f"a redirect of request {row['request_id']} planned before the verified point")
            derive(target, _h({"candidate_id": target, "outlet_id": row["candidate_id"].split(":cand:")[0], "url_key": result["final_url_key"],
                               "fetch_url": result["final_url"], "first_event_id": None, "first_channel_id": channel_of.get(row["request_id"]),
                               "first_listed_at": row["finished_at"], "discovered_via": "permanent_redirect", "redirected_from": row["candidate_id"]}))
    stored: dict[str, str] = {}
    for row in rows.get("discovery/candidates.jsonl", []):
        candidate, digest = row["candidate_id"], _h(_without_schema(row))
        before = state.stored.get(candidate) or stored.get(candidate)
        if before is not None and before != digest:
            raise Finding(f"candidates: two different rows for {candidate}")
        if digest not in state.derived.get(candidate, []) + derived.get(candidate, []):
            raise Finding(f"candidate row the discovery evidence does not support or contradicts: {candidate}")
        stored[candidate] = digest
    missing_in = [c for c in derived if c not in state.stored and c not in stored]
    missing_out = [c for c in stored if c in state.missing]
    if (state.missing - set(missing_out)) or missing_in:
        resumable.append("candidates the evidence gives are missing from the table: complete_candidates")
    delta["inputs"], delta["derived"], delta["stored"] = new_inputs, derived, stored
    delta["first_events"] = sorted(first_now)
    delta["missing"] = {"in": missing_in, "out": missing_out}

    # --- identity tables ------------------------------------------------------------------------------------------
    store = workspace.layer_store() if workspace.layers.is_dir() else None
    ident: dict[str, dict[str, Any]] = {"documents": {}, "document_keys": {}, "observations": {}, "observation_documents": {}, "versions": {}}
    for row in rows.get("identity/documents.jsonl", []):
        document, digest = row["document_id"], _h(row)
        before = state.documents.get(document) or ident["documents"].get(document)
        if before is not None and before != digest:
            raise Finding(f"identity documents: two different rows for {document}")
        if identity.document_id(row["outlet_id"], row["url_key"]) != document:
            raise Finding(f"identity: the id of {document} does not fit its row")
        key = f"{row['outlet_id']}|{row['url_key']}"
        if (state.document_keys.get(key) or ident["document_keys"].get(key) or document) != document:
            raise Finding(f"identity documents: {row['url_key']!r} is filed under two ids")
        ident["documents"][document], ident["document_keys"][key] = digest, document
    known_documents = lambda d: d in state.documents or d in ident["documents"]  # noqa: E731
    for row in rows.get("identity/observations.jsonl", []):
        fetch_id, digest = row["fetch_id"], _h(row)
        before = state.observations.get(fetch_id) or ident["observations"].get(fetch_id)
        if before is not None and before != digest:
            raise Finding(f"identity observations: two different rows for {fetch_id}")
        if not known_documents(row["document_id"]):
            raise Finding("identity rows that name documents the tables do not hold")
        ident["observations"][fetch_id], ident["observation_documents"][fetch_id] = digest, row["document_id"]
    for row in rows.get("identity/versions.jsonl", []):
        version = row["document_version_id"]
        first = state.versions.get(version) or ident["versions"].get(version)
        if first is not None and first != [row["document_id"], row["extracted_text_sha256"]]:
            raise Finding(f"versions: {version} stands for two texts or two documents")
        if identity.document_version_id(row["document_id"], row["extracted_text_sha256"]) != version:
            raise Finding(f"identity: the id of {version} does not fit its row")
        if not known_documents(row["document_id"]):
            raise Finding("identity rows that name documents the tables do not hold")
        if ledger_state(row["fetch_id"]) != "RAW_PRESERVED":
            raise Finding("document versions rest on fetches that are not RAW_PRESERVED")
        if verify_objects:
            from . import extraction
            try:
                if store is None or store.get(extraction.STAGE, row["extraction_fingerprint"]) is None:
                    raise Finding("document versions whose extraction layer is missing")
                stored_layer = json.loads(store.read(extraction.STAGE, row["extraction_fingerprint"]).decode("utf-8"))
                if (stored_layer.get("extracted_text_sha256"), stored_layer.get("body_text_sha256")) != (row["extracted_text_sha256"], row["body_text_sha256"]):
                    raise Finding("document versions whose extraction layer is not the text they name")
            except (layer_store.LayerStoreError, ValueError, TypeError) as error:
                raise Finding(f"version {version}: {error}") from error
        ident["versions"][version] = [row["document_id"], row["extracted_text_sha256"]]
    delta.update(ident)

    # --- layers: new slots verified, a rotating share of the old ones re-read ---------------------------------------
    new_layers: dict[str, str] = {}
    audited_layers = 0
    if workspace.layers.is_dir():
        slots = []
        for stage_dir in sorted(p for p in workspace.layers.iterdir() if p.is_dir() and p.name != ".staging"):
            for prefix in sorted(p for p in stage_dir.iterdir() if p.is_dir()):
                slots += [(stage_dir.name, slot) for slot in sorted(prefix.iterdir()) if slot.is_dir()]
        oldest = sorted((at_, key) for key, at_ in state.layers.items())[:audit.layers] if verify_objects else []
        recheck = {key for _, key in oldest}
        for stage, slot in slots:
            key = f"{stage}/{slot.name}"
            if key in state.layers and key not in recheck:
                scope["layers_skipped_as_verified"] += 1
                continue
            if not verify_objects:            # a rebase right after the full audit: the audit read every answer
                if any((answer / layer_store.MARKER_NAME).is_file() for answer in slot.iterdir()):
                    new_layers[key] = at
                continue
            if sum(1 for answer in slot.iterdir() if (answer / layer_store.MARKER_NAME).is_file()) > 1:
                raise Finding("layer slots holding more than one answer")
            try:
                if store.get(stage, slot.name) is not None:
                    store.read(stage, slot.name)
                elif any(slot.iterdir()):
                    raise Finding(f"a stored layer answer that does not verify: {key[:24]}")
                else:
                    continue
            except (layer_store.LayerStoreError, ValueError) as error:
                raise Finding(f"a stored layer answer that does not verify: {key[:24]}: {error}") from error
            new_layers[key] = at
            if key in state.layers:
                audited_layers += 1
            else:
                scope["layers_new"] += 1
        gone_layers = set(state.layers) - {f"{stage}/{slot.name}" for stage, slot in slots}
        if gone_layers:
            raise Finding(f"verified layer answers are gone: {sorted(gone_layers)[:3]}")
    elif state.layers:
        raise Finding("the layer store is gone")
    delta["layers"] = new_layers
    scope["layers_audited"] = audited_layers

    classification = recovery.RESUMABLE if resumable else recovery.CLEAN
    return delta, {"schema": recovery.DIAGNOSIS_SCHEMA, "classification": classification, "resumable": sorted(set(resumable)),
                   "needs_repair": [], "damaged": [], "check": {"mode": "incremental", "version": CHECK_VERSION, "scope": scope,
                   "not_checked_here": "fixity of unchanged verified objects outside the rotating audit; leftovers (staging "
                                       "files, sidecars), which never decide a classification"}}


def _check_head(root: Path, relative: str, head: dict[str, Any], anchor: dict[str, Any] | None, tail: list[bytes], run_id: str) -> None:
    """A closed run's anchor of one table, checked against the verified anchor and the tail read in this pass."""
    rows_before = anchor["rows"] if anchor else 0
    wanted = head["rows"]
    if wanted == rows_before and anchor is not None:
        ok = anchor["last_sha"] == head["head_sha256"]
    elif rows_before < wanted <= rows_before + len(tail):
        ok = sha256_bytes(tail[wanted - rows_before - 1] + b"\n") == head["head_sha256"]
    elif wanted > rows_before + len(tail):
        raise Finding(f"{run_id}: {relative} has fewer rows than were recorded at its close")
    else:
        ok = not evidence.mismatches(root, {relative: head})       # a run closed before the verified point: read the table
    if not ok:
        raise Finding(f"{run_id}: {relative}: the row recorded at the close is not the row there")


# --- the entry point -------------------------------------------------------------------------------------------


def checkpoint(workspace_root: Path, state: CheckState | None = None, *, now: datetime | None = None,
               audit: AuditBudget = AuditBudget(), full_every: timedelta = FULL_EVERY) -> tuple[dict[str, Any], CheckState]:
    """The check a writer makes between its stages. Returns the diagnosis (``recovery.diagnose``'s schema) and the state.

    Full audit (``recovery.diagnose``) when there is no valid state, the last full audit is older than ``full_every``, or the
    incremental check meets anything it does not classify. Otherwise only what is new, plus the rotating audit.
    """
    root = Path(workspace_root)
    now = now or datetime.now(timezone.utc)
    state = state if state is not None else load(root)
    why = None
    if not state.valid:
        why = state.reason or "no check state"
    elif state.full_at is None or now - datetime.fromisoformat(state.full_at.replace("Z", "+00:00")) > full_every:
        why = f"the last full audit is older than {full_every.days} days"
    if why is None:
        try:
            delta, diagnosis = _incremental(root, state, now=now, audit=audit)
        except Exception as finding:  # noqa: BLE001 -- whatever the incremental check cannot classify, the full audit does
            diagnosis = recovery.diagnose(root)
            diagnosis["check"] = {"mode": "full", "version": CHECK_VERSION, "why": f"the incremental check found: {finding}"}
            if diagnosis["classification"] in (recovery.CLEAN, recovery.RESUMABLE):
                _rebase(root, state, now, diagnosis)
            else:
                state.valid, state.reason = False, f"after a {diagnosis['classification']} full audit"
            return diagnosis, state
        state.apply(delta)
        _persist(root, state, delta)
        return diagnosis, state
    diagnosis = recovery.diagnose(root)
    diagnosis["check"] = {"mode": "full", "version": CHECK_VERSION, "why": why}
    if diagnosis["classification"] in (recovery.CLEAN, recovery.RESUMABLE):
        _rebase(root, state, now, diagnosis)
    return diagnosis, state


def _rebase(root: Path, state: CheckState, now: datetime, diagnosis: dict[str, Any]) -> None:
    """After a full audit that found nothing to repair: take the whole workspace as the verified point. Objects are not
    re-hashed (the audit just did); the tables are read to build the derivation state."""
    fresh = CheckState()
    try:
        delta, _ = _incremental(root, fresh, now=now, audit=AuditBudget(packs=0, layers=0), verify_objects=False)
    except Exception as finding:  # noqa: BLE001   # the full audit and the incremental reading disagree: no state, and the next check is full again
        diagnosis["check"]["rebase"] = f"refused: {finding}"
        state.valid, state.reason = False, f"rebase refused: {finding}"
        return
    delta["kind"] = "full"
    delta["at"] = format_instant(now)
    state.path = None
    state.apply(delta)
    _persist(root, state, delta)
    diagnosis["check"]["rebase"] = "the workspace as audited is the new verified point"


__all__ = ["AuditBudget", "CheckState", "checkpoint", "load", "CHECK_VERSION", "FULL_EVERY"]
