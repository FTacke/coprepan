"""Conformance with the joint storage-management contract ``crosscorpus-storage/v1`` (CPD-0015).

Three layers:

* the **pinned bundle** — the local copy is the pinned one; needs no neighbouring checkout;
* the **decision functions** against the shared reference cases (``conformance/CASES.json``),
  whose expected values are written by hand in the contract's canonical home;
* this repository's **real code paths** against the invariants the cases only describe: an outage
  through the real preservation step of the acquisition path, the spool, drain and read-back, the
  interruption points between workspace, spool and primary, protection of the only copy, and a
  change of root.

Everything is under ``tmp_path``. A joint check with the sister checkout runs only when it is present.
"""

from __future__ import annotations

import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from coprepan import core_pipeline as C
from coprepan import outage_spool as O
from coprepan import pack
from coprepan import preservation as P
from coprepan import release_contract as RC
from coprepan import storage_contract as SC
from coprepan import storage_roots as S
from test_core_pipeline import Canary, T0

REPO = Path(__file__).resolve().parents[1]
CASES = SC.load_cases()
POLICY = O.SpoolPolicy(min_free_bytes=0, max_spool_bytes=10**9)
NOW = T0 + timedelta(hours=8)


# --- the bundle is the pinned one ---------------------------------------------------------------------


def test_the_storage_bundle_is_the_pinned_copy():
    assert SC.bundle_problems() == []
    pin = SC.read_pin()
    assert pin["canonical_home"] == "corapan" and pin["path"] == SC.BUNDLE_PATH
    assert RC.tree_digest(REPO / SC.BUNDLE_PATH) == pin["bundle_sha256"]
    for name in ("CONTRACT.md", "conformance/CASES.json"):
        assert b"\r" not in (REPO / SC.BUNDLE_PATH / name).read_bytes()
    assert CASES["contract"] == SC.CONTRACT


def test_a_drifted_copy_is_refused(tmp_path):
    copy = tmp_path / "checkout"
    shutil.copytree(REPO / SC.BUNDLE_PATH, copy / SC.BUNDLE_PATH)
    (copy / "config" / "crosscorpus").mkdir(parents=True)
    shutil.copy(REPO / SC.PINS_PATH, copy / SC.PINS_PATH)
    assert SC.bundle_problems(copy) == []
    with open(copy / SC.BUNDLE_PATH / "CONTRACT.md", "ab") as handle:
        handle.write(b"\nlocal edit\n")
    assert "drifted" in SC.bundle_problems(copy)[0]
    with pytest.raises(SC.BundleRefused):
        SC.load_cases(copy)


def test_the_release_contract_pin_is_untouched_by_the_storage_contract():
    pins = json.loads((REPO / SC.PINS_PATH).read_text(encoding="utf-8"))["contracts"]
    assert RC.tree_digest(REPO / RC.BUNDLE_PATH) == pins[RC.CONTRACT]["bundle_sha256"]


# --- the shared reference cases -------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES["role_separation"], ids=[case["id"] for case in CASES["role_separation"]])
def test_role_separation_case(case):
    found = SC.role_separation(case["roots"], volumes=case.get("volumes"), co_located=case.get("co_located", ()),
                               foreign_roots=case.get("foreign_roots", ()))
    assert found == case["expect"]


@pytest.mark.parametrize("case", CASES["namespace"], ids=[case["id"] for case in CASES["namespace"]])
def test_namespace_case(case):
    assert SC.namespace(case["provided_root"], case["corpus"], case["holding"]) == case["expect"]


@pytest.mark.parametrize("case", CASES["configuration_state"], ids=[case["id"] for case in CASES["configuration_state"]])
def test_configuration_state_case(case):
    names = ("declared", "value", "default", "usable", "reachable", "writable", "need_write")
    assert SC.configuration_state(**{name: case[name] for name in names}) == case["expect"]


@pytest.mark.parametrize("case", CASES["preservation_outcome"], ids=[case["id"] for case in CASES["preservation_outcome"]])
def test_preservation_outcome_case(case):
    names = ("content_ok", "primary", "primary_copy_verified", "record_written", "spool", "spool_has_capacity", "spool_copy_verified")
    assert SC.preservation_outcome(**{name: case[name] for name in names}) == case["expect"]


@pytest.mark.parametrize("case", CASES["cleanup"], ids=[case["id"] for case in CASES["cleanup"]])
def test_cleanup_case(case):
    names = ("pending", "on_primary", "regenerable", "verified_copy_on_primary", "named_by_frozen_release", "deletion_decision_recorded")
    assert SC.cleanup(**{name: case[name] for name in names}) == case["expect"]


@pytest.mark.parametrize("case", CASES["backup_status"], ids=[case["id"] for case in CASES["backup_status"]])
def test_backup_status_case(case):
    assert SC.backup_status(**{name: value for name, value in case.items() if name not in ("id", "expect", "why")}) == case["expect"]


def test_the_vocabularies_are_the_contracts():
    assert {code for case in CASES["role_separation"] for code in case["expect"]} == set(SC.SEPARATION_CODES)
    assert {case["expect"] for case in CASES["configuration_state"]} == set(SC.CONFIGURATION_STATES)
    assert {case["expect"] for case in CASES["backup_status"]} == set(SC.BACKUP_STATES)
    assert set(SC.CONTRACT_ROLE) == set(S.ROLES)


# --- the real resolver uses the contract's decision -----------------------------------------------------


def test_the_resolver_reports_the_contracts_codes_and_refuses(tmp_path):
    outer = tmp_path / "outer"
    (outer / "inner").mkdir(parents=True)
    assert S.separation_codes({"RUNTIME": outer, "SPOOL": outer}, checkout=tmp_path / "checkout") == ["ROLE_SHARED"]
    assert S.separation_codes({"RUNTIME": outer, "SPOOL": outer / "inner"}, checkout=tmp_path / "checkout") == ["ROLE_NESTED"]
    assert S.separation_codes({"RUNTIME": tmp_path / "coprepan_workspace", "SPOOL": tmp_path / "coprepan_storage"},
                              checkout=tmp_path / "coprepan") == []
    with pytest.raises(S.StorageRootUnusable, match="ROLE_NESTED"):
        S.validate_role_separation({"RUNTIME": outer, "SPOOL": outer / "inner"}, checkout=tmp_path / "checkout")


def test_a_root_under_the_sister_corpus_is_refused(tmp_path):
    sister = tmp_path / "share" / "Corapan"
    roots = {"PRESERVATION": sister / "coprepan"}
    assert S.separation_codes(roots, checkout=tmp_path / "coprepan", foreign_roots=[sister]) == ["FOREIGN_CORPUS_OVERLAP"]
    with pytest.raises(S.StorageRootUnusable, match="sister corpus"):
        S.validate_role_separation(roots, checkout=tmp_path / "coprepan", foreign_roots=[sister])
    namespace = tmp_path / "fs" / "projects" / "panhispanic_media_corpora"
    assert S.separation_codes({"PRESERVATION": namespace / "coprepan"}, checkout=tmp_path / "coprepan",
                              foreign_roots=[namespace / "corapan"]) == []


def test_the_tracked_example_configures_no_planned_target():
    example = (REPO / ".env.example").read_text(encoding="utf-8")
    values = {line.split("=", 1)[0]: line.split("=", 1)[1].strip() for line in example.splitlines() if "=" in line and not line.startswith("#")}
    assert values and all(value == "" for value in values.values()), "a planned root is never configured in a tracked file (§5.3)"


# --- an outage through the real preservation step -------------------------------------------------------


def unavailable():
    raise S.StorageRootUnreachable("PRESERVATION: not reachable")


class Site:
    """A canary workspace with a pack acquired and not yet preserved, a spool root and a primary."""

    def __init__(self, base: Path):
        self.canary = Canary(base)
        self.canary.acquire()
        self.workspace, self.pack_id, self.root = self.canary.workspace, self.canary.pack_id, self.canary.root
        self.spool = base / "spool_root"
        self.spool.mkdir()
        pack.seal(self.workspace.packs, self.pack_id, sealed_at=NOW)      # sealing is idempotent; the step seals again

    def preserve(self, root=None, **kwargs):
        kwargs.setdefault("spool_root", lambda: self.spool)
        kwargs.setdefault("spool_policy", POLICY)
        return C.preserve_pack(self.workspace, self.pack_id, preservation_root=root or (lambda: self.root), now=NOW, **kwargs)

    def drain(self, root=None):
        return C.drain_spooled_packs(self.workspace, spool_root=self.spool, preservation_root=root or (lambda: self.root), now=NOW)

    def states(self):
        return set(self.workspace.ledger().states().values())

    def workspace_copy(self):
        return (self.workspace.packs / f"{self.pack_id}.warc.gz").read_bytes()


@pytest.fixture
def site(tmp_path):
    return Site(tmp_path)


def test_with_the_primary_available_the_step_preserves_directly(site):
    outcome = site.preserve()
    assert (outcome.state, outcome.route, outcome.pending_location) == ("RAW_PRESERVED", "direct", None)
    assert site.states() == {"RAW_PRESERVED", "FETCH_FAILED"} and O.pending_records(site.spool) == []
    assert site.preserve().promotion.action == "already_preserved"


def test_an_outage_leaves_a_complete_spooled_copy_and_an_honest_pending_state(site):
    """P1, P4, P5: no success without the primary; the pack and its index are spooled, verified;
    every fetch stays PRESERVATION_PENDING; nothing of the workspace is touched."""
    before = site.workspace_copy()
    outcome = site.preserve(unavailable)
    assert (outcome.state, outcome.route, outcome.pending_location) == ("PRESERVATION_PENDING", "spooled", "SPOOL")
    assert site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}, "nothing is RAW_PRESERVED"
    records = O.pending_records(site.spool)
    assert sorted(record["area"] for record in records) == ["raw", "raw_index"] and {record["object_id"] for record in records} == {site.pack_id}
    for record in records:
        assert P.sha256_file(site.spool / record["spool_relative_path"])[0] == record["sha256"]
    assert site.workspace_copy() == before and list(site.root.iterdir()) == []
    with pytest.raises(C.NotPreserved):
        site.canary.derive()                                   # derived stages read only what is preserved
    assert site.preserve(unavailable).route == "spooled" and len(O.pending_records(site.spool)) == 2, "repeating is a no-op"


def test_drain_promotes_verifies_reads_back_and_only_then_retires_the_spool_copy(site, tmp_path):
    """P7: after the outage the drain promotes with the same function, re-reads the masters, marks the
    fetches RAW_PRESERVED, and the spool is empty. The derived stages then give what a direct run gives."""
    direct = Canary(tmp_path / "direct").all()
    before = site.workspace_copy()
    site.preserve(unavailable)
    assert site.drain(unavailable)["packs_pending"] == [site.pack_id] and len(O.pending_records(site.spool)) == 2, "still away: nothing released"
    report = site.drain()
    assert report["packs_preserved"] == [site.pack_id] and [row["action"] for row in report["drained"]] == ["preserved", "preserved"]
    assert O.pending_records(site.spool) == [] and O.spooled_bytes(site.spool) == 0
    assert site.states() == {"RAW_PRESERVED", "FETCH_FAILED"}
    preserved = C.open_preserved_pack(site.root, site.pack_id)             # read back through the normal read path
    assert preserved.path.read_bytes() == before
    assert site.canary.derive() == direct.results
    assert site.drain() == {"drained": [], "packs_preserved": [], "packs_pending": []}, "a second drain is a no-op"


def test_without_a_spool_the_pack_stays_pending_in_the_workspace(site):
    before = site.workspace_copy()
    outcome = site.preserve(unavailable, spool_root=None, spool_policy=None)
    assert (outcome.state, outcome.route, outcome.pending_location) == ("PRESERVATION_PENDING", "workspace", "WORKSPACE")
    assert site.workspace_copy() == before and site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}
    assert site.preserve().state == "RAW_PRESERVED", "a later call completes the step from the workspace copy"


def test_a_configured_but_unreachable_spool_deletes_nothing_and_claims_nothing(site):
    """P5: both the primary and the spool are away. The sealed pack stays where it is, pending."""
    def spool_away():
        raise S.StorageRootUnreachable("SPOOL: not reachable")
    before = sorted(path.name for path in site.workspace.packs.iterdir())
    data = site.workspace_copy()
    outcome = site.preserve(unavailable, spool_root=spool_away)
    assert (outcome.state, outcome.route, outcome.pending_location) == ("PRESERVATION_PENDING", "workspace", "WORKSPACE")
    assert "spool unavailable" in outcome.reason
    after = sorted(path.name for path in site.workspace.packs.iterdir())
    assert site.workspace_copy() == data and set(before) <= set(after) | {f"{site.pack_id}.open.warc.gz"}
    assert site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"} and O.pending_records(site.spool) == []


def test_a_full_spool_leaves_the_pack_pending_in_the_workspace(site):
    outcome = site.preserve(unavailable, spool_policy=O.SpoolPolicy(min_free_bytes=0, max_spool_bytes=10))
    assert (outcome.route, outcome.pending_location) == ("workspace", "WORKSPACE") and "spool full" in outcome.reason
    assert site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"} and O.pending_records(site.spool) == []


def test_an_io_failure_during_promotion_is_an_outage_and_a_content_refusal_is_not(site, monkeypatch):
    with monkeypatch.context() as patched:
        patched.setattr(P, "_land", lambda *a, **k: (_ for _ in ()).throw(OSError("share went away mid-copy")))
        outcome = site.preserve()
    assert outcome.route == "spooled" and outcome.reason.startswith("io_error")
    other = Site(site.canary.workspace.root.parent / "other")
    squatter = other.root / P.master_relative_path(C.AREA_PACKS, C.pack_relative_path(other.pack_id, ".warc.gz"))
    squatter.parent.mkdir(parents=True)
    squatter.write_bytes(b"other bytes")
    with pytest.raises(P.IdentityConflict):
        other.preserve()                                        # P6: about content, never spooled
    assert O.pending_records(other.spool) == [] and other.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}


# --- interruption points between workspace, spool and primary ---------------------------------------------


def test_interrupted_between_the_two_spooled_objects(site, monkeypatch):
    real, calls = O.spool_object, []

    def second_fails(source, **kwargs):
        calls.append(kwargs["area"])
        if len(calls) == 2:
            raise OSError("spool disk went away")
        return real(source, **kwargs)
    with monkeypatch.context() as patched:
        patched.setattr(O, "spool_object", second_fails)
        outcome = site.preserve(unavailable)
    assert outcome.route == "workspace" and len(O.pending_records(site.spool)) == 1, "one object spooled, the step is not 'spooled'"
    assert site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}
    assert site.preserve(unavailable).route == "spooled" and len(O.pending_records(site.spool)) == 2
    assert site.drain()["packs_preserved"] == [site.pack_id]


def test_interrupted_after_the_copy_and_before_the_pending_record(site, monkeypatch):
    def lost(*args, **kwargs):
        raise OSError("crash before the record")
    with monkeypatch.context() as patched:
        patched.setattr(O, "write_bytes_atomic", lost)
        assert site.preserve(unavailable).route == "workspace"
    assert O.pending_records(site.spool) == [] and site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}
    assert site.preserve(unavailable).route == "spooled" and len(O.pending_records(site.spool)) == 2
    assert site.drain()["packs_preserved"] == [site.pack_id] and O.spooled_bytes(site.spool) == 0


def test_interrupted_in_the_drain_between_promotion_and_release(site, monkeypatch):
    site.preserve(unavailable)

    def crash(*args, **kwargs):
        raise RuntimeError("killed between the verified promotion and the release")
    with monkeypatch.context() as patched:
        patched.setattr(O, "_release", crash)
        with pytest.raises(RuntimeError):
            site.drain()
    assert len(O.pending_records(site.spool)) == 2, "the spool copy is kept: nothing was released without its record being handled"
    assert site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}, "the ledger was not advanced by the interrupted drain"
    report = site.drain()
    assert report["packs_preserved"] == [site.pack_id] and O.pending_records(site.spool) == []
    assert site.states() == {"RAW_PRESERVED", "FETCH_FAILED"}


def test_interrupted_after_the_drain_and_before_the_ledger(site, monkeypatch):
    site.preserve(unavailable)
    with monkeypatch.context() as patched:
        patched.setattr(C, "_confirm_preserved", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("killed before the ledger")))
        with pytest.raises(RuntimeError):
            site.drain()
    assert O.pending_records(site.spool) == [] and site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}
    assert P.verify_master(site.root, C.AREA_PACKS, site.pack_id), "the master is on the primary; only the last transition is missing"
    assert site.drain()["packs_preserved"] == [site.pack_id] and site.states() == {"RAW_PRESERVED", "FETCH_FAILED"}


def test_a_master_that_does_not_verify_after_the_drain_releases_nothing(site, monkeypatch):
    site.preserve(unavailable)
    with monkeypatch.context() as patched:
        patched.setattr(P, "verify_master", lambda *a, **k: False)
        report = site.drain()
    assert all(row["action"] == "refused" for row in report["drained"]) and len(O.pending_records(site.spool)) == 2
    assert site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}


def test_only_one_object_of_a_pack_on_the_primary_is_not_a_preserved_pack(site):
    site.preserve(unavailable)
    index_record = next(record for record in O.pending_records(site.spool) if record["area"] == "raw_index")
    (site.spool / "state" / "pending" / O.record_name("raw_index", site.pack_id)).rename(site.spool / "held-back.json")
    report = site.drain()
    assert report["packs_preserved"] == [] and report["packs_pending"] == [site.pack_id]
    assert site.states() == {"PRESERVATION_PENDING", "FETCH_FAILED"}
    (site.spool / "held-back.json").rename(site.spool / "state" / "pending" / O.record_name("raw_index", site.pack_id))
    assert site.drain()["packs_preserved"] == [site.pack_id] and index_record["sha256"]


def test_a_pending_record_written_under_the_old_name_is_still_drained(site):
    site.preserve(unavailable)
    directory = site.spool / "state" / "pending"
    (directory / O.record_name("raw", site.pack_id)).rename(directory / f"{site.pack_id}.json")
    assert site.drain()["packs_preserved"] == [site.pack_id] and list(directory.iterdir()) == []


# --- the only copy is protected; nothing here deletes ---------------------------------------------------


def test_the_outage_path_has_no_deletion_and_the_spool_releases_only_after_verification():
    import ast
    source = (REPO / "src" / "coprepan" / "core_pipeline.py").read_text(encoding="utf-8")
    calls = {node.func.attr for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"unlink", "rmtree", "remove", "rmdir"}, "the pipeline deletes nothing"
    spool = (REPO / "src" / "coprepan" / "outage_spool.py").read_text(encoding="utf-8")
    assert spool.index("verified = preservation.verify_master") < spool.index("_release(spool_root, record)")
    assert SC.cleanup(pending=True, on_primary=False, regenerable=True, verified_copy_on_primary=False) == SC.CLEANUP_PROTECTED


# --- a change of root changes no identity ---------------------------------------------------------------


def test_after_a_verified_copy_the_same_references_resolve_on_another_root(site, tmp_path):
    site.preserve()
    first = RC.tree_listing(site.root)
    second = tmp_path / "new-fs" / "projects" / "panhispanic_media_corpora" / "coprepan"
    shutil.copytree(site.root, second)
    assert RC.tree_listing(second) == first                              # §11.2 step 6
    shutil.rmtree(site.root)
    moved = C.open_preserved_pack(second, site.pack_id)
    assert moved.path.read_bytes() == site.workspace_copy()
    for row in first:
        assert str(tmp_path) not in (second / row["path"]).read_bytes().decode("utf-8", "ignore"), "no root in a preserved record"


# --- the planning tool and the joint check ------------------------------------------------------------------


def _tool():
    import importlib.util
    spec = importlib.util.spec_from_file_location("storage_contract_tool", REPO / "scripts" / "storage_contract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_inventory_is_read_only_and_verification_finds_every_difference(tmp_path):
    tool = _tool()
    source, copy = tmp_path / "source", tmp_path / "copy"
    for name, data in (("preservation/raw/uy/a.warc.gz", b"1"), ("preservation/manifests/raw/a.json", b"{}")):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_bytes(data)
    inventory = tool.inventory(source)
    assert inventory["files"] == 2 and inventory["tree_sha256"] == RC.tree_digest(source) and str(tmp_path) not in json.dumps(inventory)
    assert sorted(path.name for path in source.iterdir()) == ["preservation"], "nothing was written into the root"
    shutil.copytree(source, copy)
    assert tool.compare(inventory, copy) == {"equal": True, "missing": [], "extra": [], "different": []}
    (copy / "preservation" / "raw" / "uy" / "a.warc.gz").write_bytes(b"2")
    (copy / "late.bin").write_bytes(b"x")
    assert tool.compare(inventory, copy) == {"equal": False, "missing": [], "extra": ["late.bin"], "different": ["preservation/raw/uy/a.warc.gz"]}
    text = (REPO / "scripts" / "storage_contract.py").read_text(encoding="utf-8")
    for forbidden in ("shutil.copy", "shutil.move", "rmtree", "unlink(", "os.rename", "os.replace", "os.remove"):
        assert forbidden not in text, f"the planning tool stays read-only: {forbidden}"


def test_the_joint_check_compares_pins_and_bundles_of_a_sister_checkout(tmp_path, monkeypatch):
    """The joint check itself, on a stand-in sister built here: a test of this repository never reads a
    reference repository (AGENTS.md §15). Against the real sister it is run as a command
    (``scripts/storage_contract.py compare-sister``) and by the sister's own suite."""
    tool = _tool()
    monkeypatch.setattr(tool.storage_roots, "workstation_environment", lambda: {})
    sister = tmp_path / "corapan"
    assert tool.compare_sister(sister)[0].startswith("SISTER_NOT_AVAILABLE")
    shutil.copytree(REPO / SC.BUNDLE_PATH, sister / SC.BUNDLE_PATH)
    (sister / "config" / "crosscorpus").mkdir(parents=True)
    pin = SC.read_pin()
    (sister / SC.PINS_PATH).write_text(json.dumps({"contracts": {SC.CONTRACT: {"bundle_sha256": pin["bundle_sha256"], "status": pin["status"]}}}), encoding="utf-8")
    assert tool.compare_sister(sister) == []
    (sister / SC.PINS_PATH).write_text(json.dumps({"contracts": {SC.CONTRACT: {"bundle_sha256": "0" * 64, "status": pin["status"]}}}), encoding="utf-8")
    assert any(problem.startswith("pins differ") for problem in tool.compare_sister(sister))
    with open(sister / SC.BUNDLE_PATH / "CONTRACT.md", "ab") as handle:
        handle.write(b"x")
    assert "the two bundle copies differ" in tool.compare_sister(sister)
