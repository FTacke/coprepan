"""The vertical canary: recorded exchange → fetch record → sealed pack → preservation root →
document identity → extraction → document version, and back again by replay.

Everything is synthetic and local: invented pages of an invented outlet that exists only in this
file's in-memory registry. No network, no configured storage root, no real outlet.

Kinds of check: *reproducibility* (same inputs, same ids and bytes; replay) and *robustness*
(interruption, repetition, damaged stores). Nothing here says anything about extraction quality
or about any real outlet.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from coprepan import acquisition, core_pipeline as C, extraction, identity, pack, preservation, registry as R
from coprepan.acquisition import RecordedExchange
from coprepan.document_identity import IdentityTables, DocumentIdCollision
from coprepan.layer_store import FingerprintConflict

FIXTURES = Path(__file__).parent / "fixtures" / "canary"
OUTLET = "uy_diario_ejemplo"
WWW, MOBILE = "https://www.diario-ejemplo.test", "https://m.diario-ejemplo.test"
T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
HTML_HEADERS = (("Content-Type", "text/html; charset=utf-8"),)
ARTICLE = f"{WWW}/Economia/Puerto-crecimiento-2026.html"
REPUBLISHED = f"{WWW}/Regionales/puerto-separan-cargas"
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"


def fixture(name):
    return (FIXTURES / name).read_bytes()


def make_registry(status="registered"):
    return R.validate_registry({"schema": "coprepan-outlet-registry/v1", "outlets": [{
        "outlet_id": OUTLET, "country_id": "uy", "registration_status": status,
        "display_names": [{"name": "Diario Ejemplo", "valid_from": "unknown", "valid_to": "not_applicable"}],
        "outlet_type": "unknown", "outlet_group": "unknown", "city": "unknown", "region": "unknown",
        "scope": "unknown", "access_model": "unknown", "medium": "unknown", "editions": [],
        "web_origins": [WWW, MOBILE], "timezone": "America/Montevideo", "same_outlet_basis": "not_applicable",
        "url_rules": {"version": f"{OUTLET}-url-rules/v1", "significant_query_params": ["id"],
                      "strip_path_prefixes": ["/amp"], "strip_path_suffixes": []},
        "channels": [{"channel_id": f"{OUTLET}:ch:rss_001", "kind": "rss",
                      "url_history": [{"url": f"{WWW}/rss", "valid_from": "unknown"}], "legacy_observed": {}}],
        "legacy_aliases": [], "legacy_observed": {}, "review_notes": [],
    }]})


def ex(url, body, minutes, headers=HTML_HEADERS, **kwargs):
    start = T0 + timedelta(minutes=minutes)
    return RecordedExchange(requested_url=url, fetch_started_at=start, fetch_finished_at=start + timedelta(seconds=2),
                            status=200, response_headers=headers, body=body, channel_id=f"{OUTLET}:ch:rss_001", **kwargs)


def exchanges():
    v1, v2 = fixture("nota_v1.html"), fixture("nota_v2.html")
    return [
        ex(f"{ARTICLE}?utm_source=rss", v1, 0),                                        # 0 the article
        ex(f"{MOBILE}/amp/Economia/Puerto-crecimiento-2026.html#comentarios", v1, 10),  # 1 same bytes, variant URL
        ex(f"{ARTICLE}?utm_source=rss", v2, 360),                                      # 2 same URL, changed text
        ex(REPUBLISHED, fixture("nota_republicada.html"), 370),                        # 3 other URL, same body text
        ex(f"{WWW}/breves/123", fixture("sin_metadatos.html"), 380, headers=()),       # 4 no metadata at all
        ex(f"{WWW}/docs/informe.pdf", PDF, 390, headers=(("Content-Type", "application/pdf"),)),  # 5 not HTML
        RecordedExchange(requested_url=f"{WWW}/caida", fetch_started_at=T0 + timedelta(minutes=400),
                         fetch_finished_at=T0 + timedelta(minutes=401), failure_reason="timeout"),   # 6 nothing came back
        ex(f"{REPUBLISHED}?ref=viejo", v2, 410, final_url=ARTICLE, redirect_chain=(f"{REPUBLISHED}?ref=viejo",)),  # 7 moved
        ex("https://cdn.otro-sitio.test/embed/9", b"<html><body><p>Ajeno</p></body></html>", 420),  # 8 off-origin
    ]


class Canary:
    """One complete pass of the canary in its own workspace and preservation root."""

    def __init__(self, base: Path, items=None, extractor=extraction.BASELINE):
        self.workspace = C.Workspace(base / "workspace")
        self.root = base / "preservation_root"
        self.root.mkdir(parents=True)
        self.workspace.root.mkdir(parents=True)
        self.registry = make_registry()
        self.items = exchanges() if items is None else items
        self.run = C.recorded_replay_run(T0, [OUTLET], {"fixture_set": "canary"})
        self.pack_id = pack.pack_id(OUTLET, "20261007")
        self.extractor = extractor

    def acquire(self):
        return C.acquire_recorded(self.workspace, self.registry, self.run, OUTLET, self.items)

    def preserve(self):
        return C.seal_and_preserve(self.workspace, self.pack_id, preservation_root=self.root, now=T0 + timedelta(hours=8))

    def derive(self, extractor=None):
        return C.identify_and_extract(self.workspace, self.registry, preservation_root=self.root, identifier=self.pack_id,
                                      extractor=extractor or self.extractor, now=T0 + timedelta(hours=9))

    def all(self):
        self.acquired = self.acquire()
        self.promotion = self.preserve()
        self.results = self.derive()
        acquisition.close_run(self.workspace.root, self.run, finished_at=T0 + timedelta(hours=9), status="COMPLETED",
                              counts=self.acquired["counts"], pack_ids=[self.pack_id])
        return self

    def fetch_ids(self):
        return [acquisition.build_fetch_record(self.run, OUTLET, item)["fetch_id"] for item in self.items]


@pytest.fixture
def canary(tmp_path):
    return Canary(tmp_path).all()


def by_fetch(canary):
    return {result["fetch_id"]: result for result in canary.results}


# --- fixtures ---------------------------------------------------------------------------------------


def test_fixtures_are_the_pinned_bytes():
    manifest = json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))
    assert sorted(manifest["files"]) == sorted(path.name for path in FIXTURES.glob("*.html"))
    for name, pinned in manifest["files"].items():
        data = fixture(name)
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (pinned["sha256"], pinned["size_bytes"]), name


# --- the canary, end to end --------------------------------------------------------------------------


def test_canary_end_to_end(canary):
    assert canary.acquired["counts"] == {"fetched": 8, "fetch_failed": 1, "already_recorded": 0}
    assert canary.promotion.action == "promoted" and canary.promotion.state == "RAW_PRESERVED"
    states = canary.workspace.ledger().states()
    ids = canary.fetch_ids()
    assert [states[fid] for fid in ids] == ["RAW_PRESERVED"] * 6 + ["FETCH_FAILED"] + ["RAW_PRESERVED"] * 2

    results = by_fetch(canary)
    article, variant, updated, republished, bare, pdf, _failed, moved, foreign = (results.get(fid) for fid in ids)
    assert _failed is None  # nothing came back: a ledgered fetch, no document

    # one article: three observed URLs, one document, two textual states
    assert article["document_id"] == variant["document_id"] == updated["document_id"] == moved["document_id"]
    assert article["url_key"] == ARTICLE and {r["url_key_basis"] for r in (article, variant, updated)} == {"rel_canonical"}
    assert article["document_version_id"] == variant["document_version_id"] != updated["document_version_id"]
    assert (article["is_new_document"], variant["is_new_document"], updated["is_new_document"]) == (True, False, False)
    assert (article["is_new_version"], variant["is_new_version"], updated["is_new_version"]) == (True, False, True)
    assert moved["document_version_id"] == updated["document_version_id"] and moved["url_key_basis"] == "rel_canonical"

    # another document with the same body text: related, not merged
    assert republished["document_id"] != article["document_id"] and republished["duplicate_of"] == article["document_id"]
    assert republished["document_version_id"] != updated["document_version_id"]

    # labels instead of guesses
    assert bare["extraction_outcome"] == "EXTRACTED" and bare["document_version_id"] is not None
    assert pdf["extraction_outcome"] == "NOT_EXTRACTABLE" and pdf["document_id"] and pdf["document_version_id"] is None
    assert foreign["identity"] == "off_origin" and foreign["document_id"] is None

    tables = IdentityTables(canary.workspace.identity)
    assert len(tables.documents) == 4 and len(tables.versions) == 4
    assert tables.versions_of(article["document_id"]) == [article["document_version_id"], updated["document_version_id"]]
    assert sorted((r["relation"], r["document_id"], r["target_document_id"]) for r in tables.relations) == sorted([
        ("duplicate_of", republished["document_id"], article["document_id"]),
        ("moved_to", republished["document_id"], article["document_id"]),
    ])
    assert acquisition.unfinished_runs(canary.workspace.root) == []


def test_raw_bytes_are_unchanged_on_the_preservation_root(canary):
    preserved = C.open_preserved_pack(canary.root, canary.pack_id)
    for fetch_id, item in zip(canary.fetch_ids(), canary.items):
        if item.body is not None:
            assert preserved.body(fetch_id) == item.body
            assert preserved.fetch_record(fetch_id)["body_sha256"] == hashlib.sha256(item.body).hexdigest()
    master = canary.root / canary.promotion.relative_path
    assert canary.promotion.relative_path == f"preservation/raw/uy/{OUTLET}/{canary.pack_id}.warc.gz"
    assert hashlib.sha256(master.read_bytes()).hexdigest() == canary.promotion.sha256 == preserved.manifest["pack_sha256"]
    assert master.read_bytes() == (canary.workspace.packs / f"{canary.pack_id}.warc.gz").read_bytes()


def test_same_inputs_give_the_same_identities_and_bytes(tmp_path, canary):
    other = Canary(tmp_path / "second").all()
    assert other.results == canary.results          # fetch, document, version, fingerprint and artifact ids
    assert other.promotion.sha256 == canary.promotion.sha256  # the sealed pack, byte for byte
    assert other.run.run_id == canary.run.run_id
    for name in ("documents.jsonl", "observations.jsonl", "versions.jsonl", "relations.jsonl"):
        assert (other.workspace.identity / name).read_bytes() == (canary.workspace.identity / name).read_bytes()
    assert other.workspace.ledger_path.read_bytes() == canary.workspace.ledger_path.read_bytes()


def test_every_stage_can_be_repeated_without_a_second_effect(canary):
    def snapshot():
        return {path.relative_to(canary.workspace.root.parent).as_posix(): path.read_bytes()
                for path in canary.workspace.root.parent.rglob("*") if path.is_file()}

    before = snapshot()
    assert canary.preserve().action == "already_preserved"
    again = canary.derive()
    assert [{**r, "is_new_document": False, "is_new_version": False, "extraction_status": "ALREADY_STORED", "duplicate_of": None}
            if r["identity"] == "assigned" else r for r in canary.results] == \
           [{**r, "duplicate_of": None} if r["identity"] == "assigned" else r for r in again]
    assert snapshot() == before
    with pytest.raises(acquisition.RunStateError):
        canary.acquire()  # the run is finished; a new acquisition is a new run


def test_extraction_is_re_derived_from_preserved_bytes_alone(canary, tmp_path):
    results = by_fetch(canary)
    for fetch_id, result in results.items():
        if result["identity"] != "assigned":
            continue
        replay = C.replay_extraction(canary.workspace, preservation_root=canary.root, identifier=canary.pack_id, fetch_id=fetch_id)
        assert (replay["status"], replay["artifact_id"]) == ("ALREADY_STORED", result["extraction_artifact_id"])

    # with the workspace copy of the pack gone and an empty layer store, the answer is the same
    (canary.workspace.packs / f"{canary.pack_id}.warc.gz").rename(tmp_path / "moved-away.warc.gz")
    fresh = C.Workspace(tmp_path / "fresh")
    fresh.root.mkdir()
    fresh.ledger_path.parent.mkdir(parents=True)
    fresh.ledger_path.write_bytes(canary.workspace.ledger_path.read_bytes())
    rebuilt = C.identify_and_extract(fresh, canary.registry, preservation_root=canary.root, identifier=canary.pack_id)
    strip = lambda rows: [{k: v for k, v in r.items() if k != "extraction_status"} for r in rows]  # noqa: E731
    assert strip(rebuilt) == strip(canary.results)


def test_provenance_is_complete_from_stored_records_alone(canary):
    ids = canary.fetch_ids()
    version_id = by_fetch(canary)[ids[2]]["document_version_id"]
    tables = IdentityTables(canary.workspace.identity)

    version = tables.versions[version_id]                               # which text, by which extractor
    assert (version["extractor"], version["extractor_version"]) == ("baseline_html", "0.1.0")
    observation = tables.observations[version["fetch_id"]]              # which URL, keyed how
    assert observation["url_key_ruleset"] == "coprepan-url-key/v1" and observation["outlet_url_rules_version"].endswith("/v1")
    assert observation["requested_url"] == f"{ARTICLE}?utm_source=rss" and observation["head_scan"] == "head-scan/1"
    assert identity.document_id(OUTLET, observation["url_key"]) == version["document_id"]

    history = [r for r in canary.workspace.ledger().records() if r.subject == version["fetch_id"]]
    assert [r.new_state for r in history] == ["DISCOVERED", "FETCH_PLANNED", "FETCHED", "RAW_VERIFIED",
                                              "PRESERVATION_PENDING", "RAW_PRESERVED"]
    assert history[0].details == {"run_id": canary.run.run_id, "channel_id": f"{OUTLET}:ch:rss_001"}
    pack_id = history[-1].details["pack_id"]

    held = preservation.read_manifest(canary.root, "raw", pack_id)      # which bytes, where, verified how
    preserved = C.open_preserved_pack(canary.root, pack_id)
    record = preserved.fetch_record(version["fetch_id"])                # when, status, headers, run
    assert record["run_id"] == canary.run.run_id and record["response"]["status"] == 200
    assert held["sha256"] == preserved.manifest["pack_sha256"] and held["details"]["pack"]["writer"] == "pack-writer/1"
    run_record = json.loads((acquisition.run_directory(canary.workspace.root, record["run_id"]) / "run.json").read_text(encoding="utf-8"))
    assert run_record["software_version"] and run_record["component_versions"]["pack_writer"] == "pack-writer/1"

    store = canary.workspace.layer_store()                              # the extraction itself
    manifest = store.manifest("extraction", version["extraction_fingerprint"])
    stored = json.loads(store.read("extraction", version["extraction_fingerprint"]))
    assert manifest["execution_provenance"]["fetch_id"] == version["fetch_id"]
    assert stored["input"]["body_sha256"] == record["body_sha256"] == hashlib.sha256(preserved.body(version["fetch_id"])).hexdigest()
    assert stored["extracted_text_sha256"] == version["extracted_text_sha256"]
    assert identity.document_version_id(version["document_id"], stored["extracted_text_sha256"]) == version_id


def test_no_record_depends_on_where_the_run_happened(canary, tmp_path):
    here = [str(tmp_path), tmp_path.as_posix(), str(tmp_path).replace("\\", "\\\\")]
    checked = 0
    for path in tmp_path.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            text = path.read_text(encoding="utf-8")
            assert not any(location in text for location in here), path.name
            checked += 1
    assert checked > 15


# --- gates ------------------------------------------------------------------------------------------


def test_only_a_registered_outlet_is_acquired_for(tmp_path):
    canary = Canary(tmp_path)
    canary.registry = make_registry(status="proposed")
    with pytest.raises(R.UnregisteredOutlet):
        canary.acquire()
    assert not canary.workspace.ledger_path.exists() and not canary.workspace.packs.exists()


def test_derived_stages_read_only_what_is_preserved(tmp_path):
    canary = Canary(tmp_path)
    canary.acquire()
    with pytest.raises(C.NotPreserved):
        canary.derive()  # nothing on the preservation root yet
    pack.seal(canary.workspace.packs, canary.pack_id, sealed_at=T0)
    with pytest.raises(C.NotPreserved):
        canary.derive()  # sealed in the workspace is still not preserved
    canary.preserve()
    assert len(canary.derive()) == 8


def test_a_preserved_pack_that_no_longer_verifies_is_not_read(canary):
    master = canary.root / canary.promotion.relative_path
    data = bytearray(master.read_bytes())
    data[-10] ^= 0xFF
    master.write_bytes(bytes(data))
    with pytest.raises(preservation.PreservationError):
        canary.derive()
    with pytest.raises(preservation.PreservationError):
        C.replay_extraction(canary.workspace, preservation_root=canary.root, identifier=canary.pack_id,
                            fetch_id=canary.fetch_ids()[0])


# --- interruption (robustness) -----------------------------------------------------------------------


@pytest.mark.parametrize("crash_at", [1, 3, 6])
def test_an_interrupted_acquisition_resumes_without_loss_or_repetition(tmp_path, monkeypatch, canary, crash_at):
    interrupted = Canary(tmp_path / "interrupted")
    real_append, calls = pack.OpenPack.append, []

    def failing(self, record, body):
        calls.append(record["fetch_id"])
        if len(calls) == crash_at:
            raise OSError("process killed")
        real_append(self, record, body)

    with monkeypatch.context() as patched:
        patched.setattr(pack.OpenPack, "append", failing)
        with pytest.raises(OSError):
            interrupted.acquire()
    assert acquisition.unfinished_runs(interrupted.workspace.root) == [interrupted.run.run_id]
    stuck = calls[-1]
    assert interrupted.workspace.ledger().state(stuck) == "FETCH_PLANNED"  # planned, never claimed as fetched

    resumed = interrupted.acquire()
    assert resumed["counts"]["already_recorded"] == crash_at - 1
    assert resumed["counts"]["fetched"] + resumed["counts"]["fetch_failed"] == 9 - (crash_at - 1)
    interrupted.promotion = interrupted.preserve()
    interrupted.results = interrupted.derive()
    assert interrupted.results == canary.results
    assert interrupted.promotion.sha256 == canary.promotion.sha256  # the same pack as an uninterrupted run


def test_a_crash_between_pack_and_ledger_is_reconciled_on_resume(tmp_path, monkeypatch, canary):
    interrupted = Canary(tmp_path / "interrupted")
    from coprepan import ledger as L
    real_transition = L.Ledger.transition

    def failing(self, subject, new_state, **kwargs):
        if new_state == "FETCHED" and len(self) >= 8:
            raise OSError("killed after the bytes were written")
        return real_transition(self, subject, new_state, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(L.Ledger, "transition", failing)
        with pytest.raises(OSError):
            interrupted.acquire()
    interrupted.acquire()  # the fetch is already in the pack: only the ledger is completed
    interrupted.promotion = interrupted.preserve()
    assert interrupted.promotion.sha256 == canary.promotion.sha256
    assert interrupted.derive() == canary.results


def test_an_interrupted_promotion_leaves_fetches_pending_and_completes_later(tmp_path, monkeypatch, canary):
    interrupted = Canary(tmp_path / "interrupted")
    interrupted.acquire()

    def lost(*args, **kwargs):
        raise OSError("share went away")

    with monkeypatch.context() as patched:
        patched.setattr(preservation, "_land", lost)
        with pytest.raises(preservation.PreservationError):
            interrupted.preserve()
    states = set(interrupted.workspace.ledger().states().values())
    assert states == {"PRESERVATION_PENDING", "FETCH_FAILED"}  # pending is not preserved
    with pytest.raises(C.NotPreserved):
        interrupted.derive()
    assert interrupted.preserve().action == "promoted"
    assert interrupted.derive() == canary.results


# --- extractor versions -------------------------------------------------------------------------------


def variant_extractor(version, change):
    def function(body, **kwargs):
        record = json.loads(extraction.extract(body, **kwargs).payload)
        record["extractor"] = {"name": "baseline_html", "version": version}
        change(record)
        record["extracted_text_sha256"] = hashlib.sha256(extraction.extracted_text_bytes(record["blocks"])).hexdigest()
        record["body_text_sha256"] = hashlib.sha256(extraction.body_text(record["blocks"]).encode("utf-8")).hexdigest()
        return extraction.Extraction(record)

    return extraction.Extractor("baseline_html", version, function)


def test_a_new_extractor_version_is_a_new_answer_and_the_old_one_stays(canary):
    first = canary.fetch_ids()[0]
    old = by_fetch(canary)[first]
    store = canary.workspace.layer_store()
    old_payload = store.read("extraction", old["extraction_fingerprint"])

    def drop_captions(record):
        record["blocks"] = [b for b in record["blocks"] if b["kind"] != "caption"]

    newer = variant_extractor("0.2.0", drop_captions)
    new = {r["fetch_id"]: r for r in canary.derive(extractor=newer)}[first]
    assert new["extraction_fingerprint"] != old["extraction_fingerprint"] and new["extraction_status"] == "STORED"
    assert new["document_id"] == old["document_id"]                      # the document does not depend on the extractor
    assert new["document_version_id"] != old["document_version_id"]      # a different text is a different version
    assert store.read("extraction", old["extraction_fingerprint"]) == old_payload  # nothing was overwritten
    tables = IdentityTables(canary.workspace.identity)
    assert tables.versions[new["document_version_id"]]["extractor_version"] == "0.2.0"
    assert tables.versions[old["document_version_id"]]["extractor_version"] == "0.1.0"

    same_text = variant_extractor("0.3.0", lambda record: None)          # new version, same output
    unchanged = {r["fetch_id"]: r for r in canary.derive(extractor=same_text)}[first]
    assert unchanged["extraction_fingerprint"] != old["extraction_fingerprint"]
    assert unchanged["document_version_id"] == old["document_version_id"]  # content-addressed: same text, same version


def test_a_non_deterministic_extractor_is_an_error_not_a_new_version(canary):
    counter = []

    def unstable(record):
        counter.append(1)
        record["blocks"] = record["blocks"][: len(counter)]

    first = canary.fetch_ids()[0]
    flaky = variant_extractor("0.9.0", unstable)
    C.replay_extraction(canary.workspace, preservation_root=canary.root, identifier=canary.pack_id, fetch_id=first, extractor=flaky)
    with pytest.raises(FingerprintConflict):
        C.replay_extraction(canary.workspace, preservation_root=canary.root, identifier=canary.pack_id, fetch_id=first, extractor=flaky)


# --- identity tables ---------------------------------------------------------------------------------


def test_identity_tables_refuse_a_colliding_id_instead_of_merging(canary, monkeypatch):
    tables = IdentityTables(canary.workspace.identity)
    record = C.open_preserved_pack(canary.root, canary.pack_id).fetch_record(canary.fetch_ids()[4])
    victim = canary.fetch_ids()[0]
    existing = tables.observations[victim]["document_id"]
    monkeypatch.setattr("coprepan.document_identity.document_id", lambda outlet, key: existing)
    tables.observations.pop(record["fetch_id"])
    with pytest.raises(DocumentIdCollision):
        tables.assign_document(canary.registry.url_rules(OUTLET), record, fixture("sin_metadatos.html"))


def test_identity_tables_are_append_only_and_reload_to_the_same_state(canary):
    first = IdentityTables(canary.workspace.identity)
    second = IdentityTables(canary.workspace.identity)
    assert (first.documents, first.observations, first.versions, first.relations) == (
        second.documents, second.observations, second.versions, second.relations)
    with pytest.raises(identity.IdentityError):
        first.assign_version("uy_diario_ejemplo:doc:0000000000000000", canary.fetch_ids()[0], extracted_text_sha256="0" * 64,
                             body_text_sha256="0" * 64, extractor="x", extractor_version="1", extraction_fingerprint="0" * 64)
    with pytest.raises(identity.IdentityError):  # a fetch can only give a version to the document it was assigned to
        first.assign_version(by_fetch(canary)[canary.fetch_ids()[3]]["document_id"], canary.fetch_ids()[0],
                             extracted_text_sha256="0" * 64, body_text_sha256="0" * 64, extractor="x",
                             extractor_version="1", extraction_fingerprint="0" * 64)


# --- hard identity cases re-examined in the audit of CPD-0005 (2026-10-07) ----------------------------


def page(title, canonical=None, text="Texto."):
    link = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return f"<html><head>{link}</head><body><article><h1>{title}</h1><p>{text}</p></article></body></html>".encode("utf-8")


def test_a_canonical_on_another_site_is_recorded_and_never_keys_the_document(tmp_path):
    """Syndicated copy often names the agency's page as canonical. The document stays the
    outlet's own URL; the foreign canonical is kept as evidence for a later syndication layer.
    """
    items = [ex(f"{WWW}/mundo/cable-1", page("Cable", "https://agencia-ajena.test/cables/1"), 0),
             ex(f"{WWW}/mundo/cable-2?utm=x", page("Otro cable", "//agencia-ajena.test/cables/2"), 5)]
    canary = Canary(tmp_path, items=items).all()
    tables = IdentityTables(canary.workspace.identity)
    first, second = (by_fetch(canary)[fid] for fid in canary.fetch_ids())
    assert (first["url_key"], first["url_key_basis"]) == (f"{WWW}/mundo/cable-1", "final_url")
    assert second["url_key"] == f"{WWW}/mundo/cable-2" and first["document_id"] != second["document_id"]
    assert tables.observations[first["fetch_id"]]["rel_canonical"] == "https://agencia-ajena.test/cables/1"
    assert tables.observations[second["fetch_id"]]["rel_canonical"] == "https://agencia-ajena.test/cables/2"
    assert tables.canonical_collapse_suspects() == []


def test_pages_that_all_declare_one_canonical_collapse_and_the_collapse_is_detectable(tmp_path):
    """A known template defect: every article names the section page as its canonical. The
    key rule then files them all under one document. The rule is not bent to hide that; the
    observations keep each fetch's own URL key, and the collapse can be listed for review.
    """
    items = [ex(f"{WWW}/politica/nota-{n}", page(f"Nota {n}", f"{WWW}/politica/", f"Texto {n}."), n) for n in range(4)]
    items.append(ex(f"{ARTICLE}?utm_source=rss", fixture("nota_v1.html"), 10))  # a correct canonical: not a suspect
    canary = Canary(tmp_path, items=items).all()
    tables = IdentityTables(canary.workspace.identity)
    collapsed = {by_fetch(canary)[fid]["document_id"] for fid in canary.fetch_ids()[:4]}
    assert len(collapsed) == 1 and len(tables.versions_of(collapsed.pop())) == 4  # four articles as four "versions"
    suspects = tables.canonical_collapse_suspects()
    assert [s["url_key"] for s in suspects] == [f"{WWW}/politica/"]
    assert suspects[0]["distinct_final_url_keys"] == [f"{WWW}/politica/nota-{n}" for n in range(4)]
    assert tables.canonical_collapse_suspects(minimum_distinct_urls=5) == []
    # nothing is lost: every fetch's own key is on record, so the documents can be re-derived under a corrected rule
    assert sorted(o["requested_url_key"] for o in tables.observations.values())[1:] == [f"{WWW}/politica/nota-{n}" for n in range(4)]


def test_only_items_become_documents(tmp_path):
    feed = ex(f"{WWW}/rss", b"<rss><channel/></rss>", 0, headers=(("Content-Type", "application/rss+xml"),), fetch_kind="channel_document")
    robots_file = ex(f"{WWW}/robots.txt", b"User-agent: *\n", 1, headers=(("Content-Type", "text/plain"),), fetch_kind="robots_txt")
    canary = Canary(tmp_path, items=[feed, robots_file, ex(f"{WWW}/nota", page("Nota"), 2)]).all()
    assert set(canary.workspace.ledger().states().values()) == {"RAW_PRESERVED"}  # all three are preserved
    assert len(canary.results) == 1 and len(IdentityTables(canary.workspace.identity).documents) == 1


def test_a_content_coded_body_is_stored_as_sent_and_read_decoded(tmp_path):
    import gzip

    packed = gzip.compress(fixture("nota_v1.html"), mtime=0)
    headers = (("Content-Type", "text/html; charset=utf-8"), ("Content-Encoding", "gzip"))
    canary = Canary(tmp_path, items=[ex(f"{ARTICLE}?a=1", packed, 0, headers=headers),
                                     ex(f"{ARTICLE}?a=2", fixture("nota_v1.html"), 5),
                                     ex(f"{WWW}/roto", packed[:60], 9, headers=headers)]).all()
    coded, plain, broken = (by_fetch(canary)[fid] for fid in canary.fetch_ids())
    assert C.open_preserved_pack(canary.root, canary.pack_id).body(coded["fetch_id"]) == packed  # raw stays as sent
    assert coded["url_key_basis"] == "rel_canonical"                    # the head was read from the decoded bytes
    assert coded["document_version_id"] == plain["document_version_id"]  # same text, however it travelled
    assert coded["body_sha256"] != plain["body_sha256"] and coded["extraction_fingerprint"] != plain["extraction_fingerprint"]
    assert (broken["extraction_outcome"], broken["document_version_id"]) == ("NOT_EXTRACTABLE", None)
    store = canary.workspace.layer_store()
    assert json.loads(store.read("extraction", broken["extraction_fingerprint"]))["reason"] == "undecodable_content_encoding"


# --- ablation: what identifies an article? -------------------------------------------------------------


def legacy_article_id(url: str) -> str:
    """The legacy rule as read in the legacy code (lower-cased URL, fragment and trailing slash
    dropped, query kept). Reproduced here only as the comparison arm of this ablation.
    """
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url.strip().lower())
    path = parts.path if parts.path == "/" else parts.path.rstrip("/")
    return "sha256:" + hashlib.sha256(urlunsplit((parts.scheme, parts.netloc, path, parts.query, "")).encode()).hexdigest()


def test_ablation_url_as_identity_versus_canonical_key_plus_text(tmp_path):
    """Three candidate rules on one controlled set: (a) the observed URL, (b) the legacy
    lower-cased URL, (c) canonical URL key for the document plus text digest for the version.
    The set holds one article seen under four URLs in two textual states, and two different
    articles whose paths differ only in case.
    """
    upper = b"<html><body><article><h1>Final</h1><p>La final se juega el domingo en el Centenario.</p></article></body></html>"
    lower = b"<html><body><article><h1>final</h1><p>Glosario: final, el ultimo partido de un torneo.</p></article></body></html>"
    v1, v2 = fixture("nota_v1.html"), fixture("nota_v2.html")
    items = [
        ex(f"{ARTICLE}?utm_source=rss", v1, 0), ex(f"{ARTICLE}?utm_source=x&fbclid=1", v1, 5),
        ex(f"{MOBILE}/amp/Economia/Puerto-crecimiento-2026.html", v1, 10), ex(f"{ARTICLE}#comentarios", v2, 15),
        ex(f"{WWW}/Deportes/Final", upper, 20), ex(f"{WWW}/deportes/final", lower, 25),
    ]
    canary = Canary(tmp_path, items=items).all()
    results = [by_fetch(canary)[fid] for fid in canary.fetch_ids()]

    by_observed_url = len({item.requested_url for item in items})
    by_legacy_id = len({legacy_article_id(item.requested_url) for item in items})
    documents = len({r["document_id"] for r in results})
    versions = len({r["document_version_id"] for r in results})

    assert by_observed_url == 6     # (a) one article becomes four "articles"; its revision is not related to it
    assert by_legacy_id == 5        # (b) still splits the article four ways, and merges the two case-distinct pages
    assert legacy_article_id(f"{WWW}/Deportes/Final") == legacy_article_id(f"{WWW}/deportes/final")
    assert (documents, versions) == (3, 4)  # (c) three articles; the changed text is a second version of the first
    assert results[4]["document_id"] != results[5]["document_id"]
    assert results[0]["document_id"] == results[3]["document_id"] and results[0]["document_version_id"] != results[3]["document_version_id"]
