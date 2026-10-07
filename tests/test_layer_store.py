"""Write-once layer store: fingerprint ≠ artifact id ≠ execution provenance."""

import hashlib
import json
from datetime import datetime, timezone

import pytest

from coprepan import layer_store as LS
from coprepan.layer_store import FingerprintConflict, LayerStore, LayerStoreError

NOW = datetime(2026, 10, 7, 20, 0, 0, tzinfo=timezone.utc)
BODY = hashlib.sha256(b"body").hexdigest()
RULES = hashlib.sha256(b"rules").hexdigest()


def fp(**overrides):
    arguments = {"stage": "extraction", "stage_version": "extractor/1.0.0",
                 "inputs": {"body": BODY, "outlet_rules": RULES}, "parameters": {"keep_captions": True}}
    return LS.fingerprint(**{**arguments, **overrides})


@pytest.fixture
def store(tmp_path):
    return LayerStore(tmp_path)


def files(root):
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


# --- fingerprint and artifact id ------------------------------------------------------------------


def test_fingerprint_preimage_is_pinned():
    preimage = (
        '{"inputs":{"body":"' + BODY + '","outlet_rules":"' + RULES + '"},'
        '"parameters":{"keep_captions":true},'
        '"schema":"coprepan-layer-fingerprint/v1",'
        '"stage":"extraction","stage_version":"extractor/1.0.0"}'
    ).encode("utf-8")
    assert fp() == hashlib.sha256(preimage).hexdigest()


def test_fingerprint_ignores_the_order_things_were_written_in():
    assert fp(inputs={"outlet_rules": RULES, "body": BODY}) == fp()
    assert fp(parameters={"b": 1, "a": {"y": 2, "x": 1}}) == fp(parameters={"a": {"x": 1, "y": 2}, "b": 1})


def test_fingerprint_changes_with_anything_that_was_asked():
    variants = {
        fp(),
        fp(stage="normalisation"),
        fp(stage_version="extractor/1.0.1"),
        fp(inputs={"body": RULES, "outlet_rules": RULES}),
        fp(inputs={"body": BODY}),
        fp(parameters={"keep_captions": False}),
        fp(parameters={}),
    }
    assert len(variants) == 7


@pytest.mark.parametrize(
    "overrides",
    [{"stage": "Extraction"}, {"stage": ""}, {"stage_version": ""}, {"inputs": {"body": "abc"}},
     {"inputs": {"": BODY}}, {"parameters": {"x": float("nan")}}, {"parameters": {"x": object()}}],
)
def test_a_malformed_question_has_no_fingerprint(overrides):
    with pytest.raises((LayerStoreError, ValueError)):
        fp(**overrides)


def test_artifact_id_is_pinned_and_depends_on_question_and_answer():
    payload = hashlib.sha256(b"answer").hexdigest()
    expected = "ar1-" + hashlib.sha256(f"{fp()}:{payload}".encode("ascii")).hexdigest()[:32]
    assert LS.artifact_id(fp(), payload) == expected and LS.is_artifact_id(expected)
    assert LS.artifact_id(fp(), BODY) != expected
    assert LS.artifact_id(fp(stage_version="extractor/1.0.1"), payload) != expected
    assert not LS.is_artifact_id(expected.upper()) and not LS.is_artifact_id("ar1-abc")


# --- store ----------------------------------------------------------------------------------------


def test_put_stores_payload_manifest_and_marker(store, tmp_path):
    result = store.put("extraction", fp(), b"answer", provenance={"run_id": "r1", "host": "ws"}, now=NOW)
    assert result.status == "STORED"
    base = f"extraction/{fp()[:2]}/{fp()}/{result.artifact_id}"
    assert files(tmp_path) == [f"{base}/PROMOTED", f"{base}/manifest.json", f"{base}/payload"]
    assert store.read("extraction", fp()) == b"answer"
    assert store.manifest("extraction", fp()) == {
        "schema": "coprepan-layer-manifest/v1",
        "stage": "extraction",
        "fingerprint": fp(),
        "artifact_id": result.artifact_id,
        "payload_sha256": hashlib.sha256(b"answer").hexdigest(),
        "payload_bytes": 6,
        "stored_at": "2026-10-07T20:00:00.000000Z",
        "execution_provenance": {"run_id": "r1", "host": "ws"},
    }


def test_an_unknown_fingerprint_has_no_answer(store):
    assert store.get("extraction", fp()) is None
    with pytest.raises(LayerStoreError):
        store.read("extraction", fp())


def test_a_rerun_with_the_same_answer_is_a_no_op(store, tmp_path):
    first = store.put("extraction", fp(), b"answer", provenance={"run_id": "r1"}, now=NOW)
    before = {name: (tmp_path / name).read_bytes() for name in files(tmp_path)}
    again = store.put("extraction", fp(), b"answer", provenance={"run_id": "r2"}, now=NOW.replace(hour=23))
    assert again.status == "ALREADY_STORED" and again.artifact_id == first.artifact_id
    assert {name: (tmp_path / name).read_bytes() for name in files(tmp_path)} == before


def test_execution_provenance_is_not_identity(tmp_path):
    ids = []
    for name, provenance, hour in (("a", {"run_id": "r1", "host": "ws1"}, 1), ("b", {"run_id": "r2", "host": "ws2"}, 2)):
        (tmp_path / name).mkdir()
        ids.append(LayerStore(tmp_path / name).put("extraction", fp(), b"answer", provenance=provenance,
                                                   now=NOW.replace(hour=hour)).artifact_id)
    assert ids[0] == ids[1]


def test_a_different_answer_for_the_same_fingerprint_is_an_error_not_a_version(store, tmp_path):
    store.put("extraction", fp(), b"answer", now=NOW)
    before = files(tmp_path)
    with pytest.raises(FingerprintConflict):
        store.put("extraction", fp(), b"another answer", now=NOW)
    assert files(tmp_path) == before and store.read("extraction", fp()) == b"answer"


def test_the_same_fingerprint_under_two_stages_is_two_slots(store):
    store.put("extraction", fp(), b"answer", now=NOW)
    assert store.get("normalisation", fp()) is None


def test_an_abandoned_write_is_never_an_answer(store, tmp_path):
    abandoned = tmp_path / "extraction" / fp()[:2] / fp() / "ar1-00000000000000000000000000000000"
    abandoned.mkdir(parents=True)
    (abandoned / "payload").write_bytes(b"half")
    assert store.get("extraction", fp()) is None
    assert store.put("extraction", fp(), b"answer", now=NOW).status == "STORED"
    assert (abandoned / "payload").read_bytes() == b"half"  # left in place, not tidied away


def corrupt(store, tmp_path, name, data):
    result = store.put("extraction", fp(), b"answer", now=NOW)
    (result.directory / name).write_bytes(data)


def test_a_changed_payload_is_detected_on_read(store, tmp_path):
    corrupt(store, tmp_path, "payload", b"tampered")
    with pytest.raises(LayerStoreError):
        store.read("extraction", fp())


def test_a_changed_manifest_is_detected(store, tmp_path):
    corrupt(store, tmp_path, "manifest.json", b"{}\n")
    with pytest.raises(LayerStoreError):
        store.get("extraction", fp())


def test_a_manifest_rewritten_with_a_matching_marker_still_has_to_fit_its_identity(store, tmp_path):
    result = store.put("extraction", fp(), b"answer", now=NOW)
    manifest = json.loads((result.directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["payload_sha256"] = BODY
    forged = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (result.directory / "manifest.json").write_bytes(forged)
    (result.directory / "PROMOTED").write_bytes((hashlib.sha256(forged).hexdigest() + "\n").encode("ascii"))
    with pytest.raises(LayerStoreError):
        store.get("extraction", fp())


def test_two_promoted_answers_under_one_fingerprint_are_a_corrupt_store(store, tmp_path):
    first = store.put("extraction", fp(), b"answer", now=NOW)
    second = first.directory.with_name("ar1-ffffffffffffffffffffffffffffffff")
    second.mkdir()
    (second / "PROMOTED").write_bytes(b"x\n")
    with pytest.raises(FingerprintConflict):
        store.get("extraction", fp())


def test_the_store_needs_an_existing_root_and_bytes(tmp_path, store):
    with pytest.raises(LayerStoreError):
        LayerStore(tmp_path / "absent")
    with pytest.raises(LayerStoreError):
        store.put("extraction", fp(), "text", now=NOW)
    with pytest.raises(ValueError):
        store.put("extraction", "not-a-fingerprint", b"x", now=NOW)
