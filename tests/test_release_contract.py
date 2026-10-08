"""``crosscorpus-release/v1``: bundle identity (PG1, PG3) and independent conformance (PG2).

The expected digests and verdicts are those of the pinned bundle's ``conformance/VECTORS.json`` —
the same file CO.RA.PAN's implementation is held to. Passing shows that two implementations
written separately agree on the mechanics, on synthetic data. It validates nothing scientific and
says nothing about any real export.
"""

from __future__ import annotations

import json
import shutil

import pytest

from coprepan import naming
from coprepan import release_contract as R
from coprepan.canonical import canonical_json, record_json, sha256_bytes
from support_release import (BUNDLE, CASES, PINS, REPO, VECTORS, change_document, change_release, fixtures_copy, mutate,
                             records_of, refreeze, releases_of, run_case, set_records)


@pytest.fixture(scope="module")
def contract() -> R.Contract:
    return R.load_contract()


@pytest.fixture
def root(tmp_path):
    return fixtures_copy(tmp_path)


def codes(verdict: R.Verdict) -> list[str]:
    return verdict.codes


# --- PG1 / PG3: one bundle, pinned, no local drift --------------------------------------------------


def test_the_copy_is_the_pinned_bundle():
    pin = R.read_pin(PINS)
    assert pin["path"] == R.BUNDLE_PATH
    assert R.bundle_digest(BUNDLE) == pin["bundle_sha256"]
    assert len(R.tree_listing(BUNDLE)) == pin["files"]
    assert R.bundle_problems(BUNDLE, pin["bundle_sha256"]) == []


def test_the_bundle_is_stored_verbatim():
    """Every bundle file is LF, and git is told not to touch it (contract §14.1)."""
    assert "contracts/** -text" in (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    with_carriage_return = [entry["path"] for entry in R.tree_listing(BUNDLE) if b"\r" in (BUNDLE / entry["path"]).read_bytes()]
    assert with_carriage_return == []


def test_the_pin_does_not_claim_a_joint_adoption():
    """`ADOPTED` is a joint state (contract §14.3). This repository's adoption is a local record."""
    pin = R.read_pin(PINS)
    assert pin["status"] == "DRAFT" and pin["canonical_home"] == "corapan"
    if "local_adoption" in pin:
        assert list((REPO / "docs" / "decisions").glob(f"{pin['local_adoption']}_*.md"))


@pytest.mark.parametrize("drift", ["byte_changed", "line_endings", "file_added", "file_deleted", "schema_missing"])
def test_a_drifted_copy_is_refused(tmp_path, drift):
    copy = shutil.copytree(BUNDLE, tmp_path / "bundle")
    text = copy / "CONTRACT.md"
    if drift == "byte_changed":
        text.write_bytes(text.read_bytes().replace(b"must not", b"may", 1))
    elif drift == "line_endings":
        text.write_bytes(text.read_bytes().replace(b"\n", b"\r\n"))
    elif drift == "file_added":
        (copy / "schemas" / "local-extension.schema.json").write_bytes(b"{}")
    elif drift == "file_deleted":
        (copy / "conformance" / "VECTORS.json").unlink()
    else:
        (copy / "schemas" / "release-freeze.schema.json").unlink()
    with pytest.raises(R.BundleRefused):
        R.load_contract(copy, PINS)


def test_a_bundle_without_a_pin_or_of_another_contract_is_refused(tmp_path):
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    other = tmp_path / "pins.json"
    other.write_bytes(record_json({**pins, "contracts": {"crosscorpus-release/v2": pins["contracts"][R.CONTRACT]}}))
    with pytest.raises(R.BundleRefused):
        R.load_contract(BUNDLE, other)
    with pytest.raises(R.BundleRefused):
        R.load_contract(BUNDLE, tmp_path / "absent.json")
    with pytest.raises(R.BundleRefused):
        R.load_contract(tmp_path / "no-bundle", PINS)
    # a copy that is internally consistent but whose vectors are those of another contract version
    copy = shutil.copytree(BUNDLE, tmp_path / "bundle")
    vectors = copy / "conformance" / "VECTORS.json"
    vectors.write_bytes(vectors.read_bytes().replace(b'"contract": "crosscorpus-release/v1"', b'"contract": "crosscorpus-release/v2"'))
    repinned = tmp_path / "repinned.json"
    pins["contracts"][R.CONTRACT]["bundle_sha256"] = R.bundle_digest(copy)
    repinned.write_bytes(record_json(pins))
    with pytest.raises(R.BundleRefused, match="vectors"):
        R.load_contract(copy, repinned)


def test_the_bundle_schemas_are_inside_the_subset(contract):
    assert sorted(contract.schemas) == sorted(R.SCHEMA_IDS)
    assert R.schema_subset_problems({"type": "object", "oneOf": []}) != []
    assert R.schema_subset_problems({"type": "object", "additionalProperties": True}) != []
    assert R.schema_subset_problems({"$ref": "other.json#/x"}) != []


# --- PG2: digests of fixed values and of the fixtures ----------------------------------------------


@pytest.mark.parametrize("vector", VECTORS["canonical_json"], ids=lambda vector: vector["utf8"][:24])
def test_canonical_json_vectors(vector):
    assert canonical_json(vector["value"]) == vector["utf8"].encode("utf-8")
    assert R.document_digest(vector["value"]) == vector["sha256"]


@pytest.mark.parametrize("vector", VECTORS["record_sets"], ids=lambda vector: vector["sha256"][:12])
def test_record_set_vectors(vector):
    assert R.record_set_digest(vector["records"]) == vector["sha256"]
    assert R.record_set_digest(list(reversed(vector["records"]))) == vector["sha256"]


@pytest.mark.parametrize("corpus", ["corapan", "coprepan"])
def test_fixture_digests(corpus):
    expected, package = VECTORS["fixtures"][corpus], BUNDLE / "fixtures" / corpus / "package"
    release, study = package / "release", BUNDLE / "fixtures" / corpus / "study"
    manifest = R.parse_strict((release / R.RELEASE_MANIFEST).read_bytes())
    assert manifest["release_id"] == expected["release_id"]
    assert R.release_manifest_digest(release) == expected["release_manifest_sha256"]
    assert R.record_set_digest(records_of(release / R.MEMBERS)) == expected["members_sha256"]
    assert R.record_set_digest(records_of(release / R.DOCUMENTS)) == expected["documents_sha256"]
    assert R.record_set_digest(records_of(release / R.COVERAGE)) == expected["coverage_sha256"]
    assert {name: R.tree_digest(package / "exports" / name) for name in expected["export_tree_sha256"]} == expected["export_tree_sha256"]
    assert R.record_set_digest(records_of(package / R.PACKAGE_FILES)) == expected["package_files_sha256"]
    assert R.document_digest(R.parse_strict((package / R.PACKAGE_MANIFEST).read_bytes())) == expected["package_manifest_sha256"]
    assert R.document_digest(R.parse_strict((study / R.STUDY_POPULATION).read_bytes())) == expected["study_population_sha256"]
    assert R.record_set_digest(records_of(study / R.SELECTED)) == expected["study_selected_sha256"]


def test_joint_fixture_digests():
    expected, study = VECTORS["fixtures"]["joint"], BUNDLE / "fixtures" / "joint" / "study"
    assert R.document_digest(R.parse_strict((study / R.STUDY_POPULATION).read_bytes())) == expected["study_population_sha256"]
    assert R.record_set_digest(records_of(study / R.SELECTED)) == expected["study_selected_sha256"]


def test_coverage_of_the_fixtures_is_what_the_documents_imply():
    for corpus in ("corapan", "coprepan"):
        release = BUNDLE / "fixtures" / corpus / "package" / "release"
        assert R.record_set_digest(R.derive_coverage(records_of(release / R.DOCUMENTS))) == VECTORS["fixtures"][corpus]["coverage_sha256"]


# --- PG2: every case verdict ------------------------------------------------------------------------


def test_the_vectors_use_only_codes_of_the_contract():
    assert {code for case in CASES for code in case["expect"]} <= set(R.CODES)
    assert len({case["id"] for case in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_conformance_case(root, contract, case):
    for mutation in case["mutations"]:
        mutate(root, mutation)
    verdict = run_case(root, case, contract)
    assert verdict.codes == sorted(case["expect"]), [objection for objection in verdict.objections]


def test_the_fixtures_verify_from_any_root_and_are_not_changed_by_a_check(tmp_path, contract):
    before = R.tree_digest(BUNDLE)
    for name in ("a", "deeper/b c"):
        root = shutil.copytree(BUNDLE / "fixtures", tmp_path / name / "fixtures")
        for case in (case for case in CASES if not case["mutations"]):
            assert run_case(root, case, contract).conformant
    assert R.tree_digest(BUNDLE) == before


# --- canonical values (§4.1) ------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    b'{"a": 1.5}', b'{"a": 2.0}', b'{"a": 1e3}', b'{"a": NaN}', b'{"a": Infinity}', b'{"a": 1, "a": 1}',
    b'{"a": 9007199254740992}', b'{"a": -9007199254740992}', "{\"a\": \"e\u0301\"}".encode("utf-8"),
    "{\"e\u0301\": 1}".encode("utf-8"), b'\xef\xbb\xbf{"a": 1}', b'{"a": "\\ud800"}', b"\xff", b"{", b"",
])
def test_what_has_no_canonical_form_is_refused(text):
    with pytest.raises(R.NonCanonical):
        R.parse_strict(text)


def test_canonical_values_at_the_limits():
    assert R.parse_strict(b'{"a": 9007199254740991, "b": [true, false, null], "c": "\xc3\xa9"}')["a"] == R.INTEGER_LIMIT
    for value in (1.0, float("nan"), b"bytes", {1: "x"}, (1, 2), {"a": {"b": [1, 2.5]}}):
        with pytest.raises(R.NonCanonical):
            R.document_digest(value)


def test_one_canonical_json_rule_in_the_repository():
    """The release contract hashes with the function CPD-0003 froze; no second serialisation exists."""
    assert R.canonical_json is canonical_json
    value = {"b": [1, {"z": None, "a": "ñ"}], "a": True}
    assert R.document_digest(value) == sha256_bytes(canonical_json(value))


def test_stored_form_and_order_carry_nothing():
    records = [{"id": "b", "n": 2}, {"id": "a", "n": 1}]
    stored = R.record_set_bytes(records)
    assert stored == b'{"id":"a","n":1}\n{"id":"b","n":2}\n'
    crlf = b'{ "n": 2, "id": "b" }\r\n\r\n{"id": "a", "n": 1}'
    assert R.record_set_digest(R.parse_records(crlf)) == R.record_set_digest(records) == sha256_bytes(stored)


# --- contract paths and the tree digest (§4.4, §4.5) ------------------------------------------------


@pytest.mark.parametrize("path", ["a", "a/b.json", "ü.txt", "a b/c", ".hidden", "a/.b/c..d"])
def test_contract_paths(path):
    assert R.is_contract_path(path)


@pytest.mark.parametrize("path", ["", "/a", "a/", "a//b", "a/./b", "a/../b", "..", "a\\b", "C" + ":/a", "a:b", " a", "a /b", "a.",
                                  "a/b./c", "a\tb", "a\x7fb", "e\u0301", 7, None])
def test_what_is_not_a_contract_path(path):
    assert not R.is_contract_path(path)


def test_paths_differing_only_by_case_collide():
    assert R.case_collisions(["a/B.txt", "a/b.txt", "c"]) == ["a/b.txt"]
    assert R.case_collisions(["a", "b"]) == []


def test_tree_digest_ignores_root_order_and_empty_directories(tmp_path):
    files = {"z.txt": b"z", "d/a.bin": b"\x00\x01", "d/e/ü.txt": "ü".encode("utf-8")}
    for name, order in (("first", list(files)), ("second/elsewhere", list(reversed(files)))):
        for path in order:
            target = tmp_path / name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(files[path])
    (tmp_path / "first" / "empty" / "dir").mkdir(parents=True)
    assert R.tree_digest(tmp_path / "first") == R.tree_digest(tmp_path / "second" / "elsewhere")
    assert sorted(entry["path"] for entry in R.tree_listing(tmp_path / "first")) == sorted(files)
    (tmp_path / "first" / "z.txt").write_bytes(b"z\n")
    assert R.tree_digest(tmp_path / "first") != R.tree_digest(tmp_path / "second" / "elsewhere")


def test_a_name_that_is_no_contract_path_is_not_skipped(tmp_path):
    (tmp_path / "tree").mkdir()
    (tmp_path / "tree" / " leading").write_bytes(b"x")
    with pytest.raises(R.PathInvalid):
        R.tree_listing(tmp_path / "tree")


# --- the schema subset (§12) ------------------------------------------------------------------------


def test_schema_evaluation_matches_json_schema_where_python_differs(contract):
    member = records_of(BUNDLE / "fixtures" / "coprepan" / "package" / "release" / R.MEMBERS)[0]
    assert contract.problems(R.MEMBER_SCHEMA, member) == []
    # `$` in a schema pattern ends the string; in Python it would also match before a line feed
    assert contract.problems(R.MEMBER_SCHEMA, {**member, "tree_sha256": member["tree_sha256"] + "\n"}) != []
    # true is not an integer; 0 is not false; an unknown field is an objection, not an extension point
    assert contract.problems(R.MEMBER_SCHEMA, {**member, "files": True}) != []
    assert contract.problems(R.MEMBER_SCHEMA, {**member, "note": "x"}) != []
    package = R.parse_strict((BUNDLE / "fixtures" / "coprepan" / "package" / R.PACKAGE_MANIFEST).read_bytes())
    assert contract.problems(R.PACKAGE_SCHEMA, package) == []
    assert contract.problems(R.PACKAGE_SCHEMA, {**package, "contains_source_media": 0}) != []
    assert contract.problems(R.PACKAGE_SCHEMA, {**package, "contains_source_media": True}) != []


# --- release semantics beyond the vectors -----------------------------------------------------------


def release_of(root, corpus="coprepan"):
    return root / corpus / "package" / "release"


def check(root, contract, corpus="coprepan", **arguments):
    package = root / corpus / "package"
    return R.verify_release(package / "release", exports_root=package / "exports", require_exports=True, contract=contract, **arguments)


def test_no_manifest_carries_its_own_digest(root, contract):
    """§4.3: the digest lives in the referrer. A self-hash field is an unknown field."""
    manifest = contract.schemas[R.MANIFEST_SCHEMA]
    assert not [name for name in manifest["properties"] if "sha256" in name]
    freeze = R.parse_strict((release_of(root) / R.RELEASE_FREEZE).read_bytes())
    assert freeze["release_manifest_sha256"] == R.release_manifest_digest(release_of(root))
    change_release(release_of(root), lambda document: document.update(manifest_sha256="0" * 64))
    assert codes(check(root, contract)) == ["SCHEMA_VIOLATION"]


def test_a_release_exists_only_with_its_freeze_record(root, contract):
    (release_of(root) / R.RELEASE_FREEZE).unlink()
    assert codes(check(root, contract)) == ["REFERENCE_MISSING"]


def test_a_freeze_record_of_another_release_does_not_freeze_this_one(root, contract):
    change_document(release_of(root) / R.RELEASE_FREEZE, lambda freeze: freeze.update(release_id="coprepan-0000.2"))
    assert codes(check(root, contract)) == ["FREEZE_MISMATCH"]


def test_a_check_without_exports_says_so(root, contract):
    shutil.rmtree(root / "coprepan" / "package" / "exports")
    verdict = R.verify_release(release_of(root), contract=contract)
    assert verdict.conformant and verdict.exports_checked is False
    assert check(root, contract).codes == ["EXPORT_MISSING"] and check(root, contract).exports_checked is True
    with pytest.raises(ValueError):
        R.verify_release(release_of(root), require_exports=True, contract=contract)


@pytest.mark.parametrize("corpus, release_id, kind, expected", [
    ("corapan", "corapan-2026-10", "release", []), ("coprepan", "coprepan-2027.1", "release", []),
    ("coprepan", "coprepan-legacy-2026-06", "release", []), ("coprepan", "corapan-2027.1", "release", ["RELEASE_ID_INVALID"]),
    ("coprepan", "coprepan-0000.7", "release", ["RELEASE_ID_INVALID"]), ("coprepan", "coprepan-2027.1", "fixture", ["RELEASE_ID_INVALID"]),
    ("coprepan", "coprepan-2027_1", "release", ["SCHEMA_VIOLATION"]), ("corapan", "corapan-0000-02", "fixture", []),
])
def test_release_ids_share_only_the_corpus_prefix(root, contract, corpus, release_id, kind, expected):
    """§5.4: `corapan-YYYY-MM` and `coprepan-YYYY.n` stand side by side; nothing parses a date out of an id."""
    pin = {"state": "known", "id": "policy", "sha256": "1" * 64} if kind == "release" else {"state": "not_available", "id": None, "sha256": None}
    change_release(release_of(root, corpus), lambda m: m.update(release_id=release_id, release_kind=kind, fixture=kind == "fixture", selection_policy=pin))
    change_document(release_of(root, corpus) / R.RELEASE_FREEZE, lambda freeze: freeze.update(release_id=release_id))
    assert codes(check(root, contract, corpus)) == expected


def test_coprepan_release_ids_keep_their_own_form():
    """The naming rule of CPD-0002 is narrower than the shared one and is not widened by the contract."""
    assert naming.is_release_id("coprepan-2027.1") and naming.is_release_id("coprepan-0000.1")
    assert naming.is_release_id(naming.LEGACY_RELEASE_ID)
    assert not naming.is_release_id("coprepan-2026-10") and not naming.is_release_id("corapan-2026-10", "corapan")


def test_a_release_pins_its_selection_policy(root, contract):
    change_release(release_of(root), lambda m: m.update(release_id="coprepan-2027.1", release_kind="release", fixture=False))
    change_document(release_of(root) / R.RELEASE_FREEZE, lambda freeze: freeze.update(release_id="coprepan-2027.1"))
    assert codes(check(root, contract)) == ["SCHEMA_VIOLATION"]


def test_a_provisional_export_has_no_freeze_record_and_needs_none(root, contract):
    change_document(release_of(root) / R.RELEASE_MANIFEST,
                    lambda m: m.update(release_id="coprepan-2027.1", release_kind="provisional_export", fixture=False))
    (release_of(root) / R.RELEASE_FREEZE).unlink()
    assert check(root, contract).conformant


def test_anchors_of_the_other_modality_are_refused(root, contract):
    change_release(release_of(root), lambda m: m["anchors"]["unit_kinds"].append("turn"))
    assert codes(check(root, contract)) == ["SCHEMA_VIOLATION"]
    change_release(release_of(root, "corapan"), lambda m: m["anchors"].update(time_reference=None, time_reference_state="not_applicable"))
    assert codes(check(root, contract, "corapan")) == ["SCHEMA_VIOLATION"]


def test_a_value_is_null_exactly_when_its_state_is_not_known(root, contract):
    change_release(release_of(root), lambda m: m["totals"].update(tokens_counted=None))
    assert codes(check(root, contract)) == ["SCHEMA_VIOLATION"]


def test_a_token_count_names_its_denominator(root, contract):
    """§5.2 rule 2. A release that cannot count says so at every level; it does not deliver another count."""
    release = release_of(root)
    change_release(release, lambda m: m.update(token_denominator=None, token_denominator_state="not_available"))
    assert codes(check(root, contract)) == ["SCHEMA_VIOLATION"]          # totals still state a known count
    change_release(release, lambda m: m["totals"].update(tokens_counted=None, tokens_counted_state="not_available"))
    assert codes(check(root, contract)) == ["DOCUMENT_INCONSISTENT"]     # the documents still do
    documents = [{**document, "tokens_counted": None, "tokens_counted_state": "not_available"} for document in records_of(release / R.DOCUMENTS)]
    set_records(release, "documents", R.DOCUMENTS, documents)
    set_records(release, "coverage", R.COVERAGE, R.derive_coverage(documents))
    refreeze(release)
    verdict = check(root, contract)
    assert verdict.conformant, verdict.objections                          # frozen, with the state explicit (contract §16 Q1)
    change_release(release, lambda m: m.update(token_denominator="other-token-rule/v1", token_denominator_state="known"))
    assert codes(check(root, contract)) == ["SCHEMA_VIOLATION"]


def test_a_partial_sum_is_never_a_total():
    rows = [{"n": 3, "n_state": "known"}, {"n": None, "n_state": "unknown"}]
    assert R.stateful_sum(rows[:1], "n") == (3, "known")
    assert R.stateful_sum(rows, "n") == (None, "not_available")
    assert R.stateful_sum(rows[1:] * 2, "n") == (None, "unknown")


def test_document_rules(root, contract):
    release = release_of(root)
    original = records_of(release / R.DOCUMENTS)
    dated = next(document for document in original if document["date_state"] == "known")

    def verdict_with(changed: dict) -> list[str]:
        copy = fixtures_copy(root.parent / f"case-{len(list(root.parent.iterdir()))}")
        documents = [changed if document["document_id"] == dated["document_id"] else document for document in original]
        set_records(release_of(copy), "documents", R.DOCUMENTS, documents)
        refreeze(release_of(copy))
        return codes(check(copy, contract))

    assert verdict_with({**dated, "date_basis": None, "date_basis_state": "unknown"}) == ["DOCUMENT_INCONSISTENT"]
    assert verdict_with({**dated, "date_basis": "crawl_date"}) == ["DOCUMENT_INCONSISTENT"]
    assert verdict_with({**dated, "date": "2026-02-30"}) == ["DOCUMENT_INCONSISTENT"]
    assert verdict_with({**dated, "country_id": "ar"}) == ["DOCUMENT_INCONSISTENT"]
    assert verdict_with({**dated, "audio_ms": 1000, "audio_ms_state": "known"}) == ["DOCUMENT_INCONSISTENT"]
    assert verdict_with({**dated, "export_id": "cpx-fixture-0009"}) == ["DOCUMENT_INCONSISTENT", "MEMBERSHIP_INCONSISTENT"]
    assert verdict_with({**dated, "source_sha256": None}) == ["DOCUMENT_INCONSISTENT"]


def test_totals_are_rederived(root, contract):
    change_release(release_of(root), lambda m: m["totals"].update(tokens_counted=22))
    assert codes(check(root, contract)) == ["TOTALS_MISMATCH"]


def test_a_member_of_an_undeclared_export_schema_is_refused(root, contract):
    change_release(release_of(root), lambda m: m["vocabularies"].update(export_schema=["coprepan-export/v1"]))
    assert codes(check(root, contract)) == ["MEMBERSHIP_INCONSISTENT"]


def test_a_first_release_adds_exactly_its_members(root, contract):
    change_release(release_of(root), lambda m: m["changes"].update(added=["cpx-fixture-0001"]))
    assert codes(check(root, contract)) == ["MEMBERSHIP_INCONSISTENT"]


# --- study and package semantics beyond the vectors -------------------------------------------------


def test_a_clause_on_a_stateful_field_is_not_satisfied_by_an_unknown_value():
    documents = records_of(BUNDLE / "fixtures" / "coprepan" / "package" / "release" / R.DOCUMENTS)
    undated = [document["document_id"] for document in documents if document["date_state"] != "known"]
    assert undated and not set(undated) & set(R.filter_documents(documents, [{"field": "date", "from": "0001-01-01"}]))
    assert R.filter_documents(documents, []) == sorted(document["document_id"] for document in documents)
    assert len(R.filter_documents(documents, [{"field": "tokens_counted", "min": 4, "max": 4}])) == 1
    assert len(R.filter_documents(documents, [{"field": "country_id", "in": ["es"]}, {"field": "outlet_id", "in": ["es_otro_diario"]}])) == 1


def test_a_study_whose_release_is_not_at_hand_is_not_restorable_by_guessing(root, contract):
    releases = releases_of(root)
    del releases["coprepan-0000.1"]
    assert codes(R.verify_study(root / "joint" / "study", releases, contract=contract)) == ["REFERENCE_MISSING"]


def test_a_study_names_its_inputs_by_release_digest_and_analysis_layer(root, contract):
    """What a study pins (§10.1): per corpus the release — id and release manifest digest — and the
    analysis bundle it read, if any. The two digests are different things.
    """
    study = root / "coprepan" / "study"
    document = R.parse_strict((study / R.STUDY_POPULATION).read_bytes())
    assert sorted(document["inputs"][0]) == ["analysis_layer", "corpus_id", "release_id", "release_manifest_sha256"]
    change_document(study / R.STUDY_POPULATION, lambda s: s["inputs"][0].update(
        analysis_layer={"state": "known", "contract": R.ANALYSIS_CONTRACT, "manifest_sha256": "a" * 64}))
    assert R.verify_study(study, releases_of(root), contract=contract).conformant
    change_document(study / R.STUDY_POPULATION, lambda s: s["inputs"][0]["analysis_layer"].update(contract="crosscorpus-analysis/v2"))
    assert codes(R.verify_study(study, releases_of(root), contract=contract)) == ["SCHEMA_VIOLATION"]
    change_document(study / R.STUDY_POPULATION, lambda s: s["inputs"][0]["analysis_layer"].update(contract=R.ANALYSIS_CONTRACT, manifest_sha256=None))
    assert codes(R.verify_study(study, releases_of(root), contract=contract)) == ["SCHEMA_VIOLATION"]


def test_an_id_is_selected_or_excluded_never_both(root, contract):
    study = root / "coprepan" / "study"
    selected = records_of(study / R.SELECTED)
    both = [{**selected[0], "reason": "syndicated_copy"}] + records_of(study / R.EXCLUDED)
    (study / R.EXCLUDED).write_bytes(R.record_set_bytes(both))
    change_document(study / R.STUDY_POPULATION, lambda s: s["excluded"].update(records=2, sha256=R.record_set_digest(both)))
    assert codes(R.verify_study(study, releases_of(root), contract=contract)) == ["POPULATION_SELECTION_MISMATCH"]


def test_a_package_lists_the_release_files_under_their_roles(root, contract):
    package = root / "coprepan" / "package"
    files = records_of(package / R.PACKAGE_FILES)
    wrong = [{**entry, "role": "documentation"} if entry["path"] == "release/MEMBERS.jsonl" else entry for entry in files]
    (package / R.PACKAGE_FILES).write_bytes(R.record_set_bytes(wrong))
    change_document(package / R.PACKAGE_MANIFEST, lambda p: p["files"].update(sha256=R.record_set_digest(wrong)))
    assert codes(R.verify_package(package, contract=contract)) == ["PACKAGE_INCOMPLETE"]


def test_a_package_of_another_release_is_refused(root, contract):
    package = root / "coprepan" / "package"
    change_document(package / R.PACKAGE_MANIFEST, lambda p: p["release"].update(release_manifest_sha256="0" * 64))
    assert codes(R.verify_package(package, contract=contract)) == ["RELEASE_PIN_MISMATCH"]


def test_an_archive_package_is_self_contained(root, contract):
    package = root / "coprepan" / "package"
    change_document(package / R.PACKAGE_MANIFEST, lambda p: p.update(exports="by_reference"))
    assert codes(R.verify_package(package, contract=contract)) == ["SCHEMA_VIOLATION"]


def test_no_package_file_carries_an_address():
    """Every path a fixture package lists is a contract path: relative, no drive, no root (§4.4, §11.3)."""
    for corpus in ("corapan", "coprepan"):
        for entry in records_of(BUNDLE / "fixtures" / corpus / "package" / R.PACKAGE_FILES):
            assert R.is_contract_path(entry["path"])


def test_command_line_reports_the_pinned_bundle_and_a_verdict(root, capsys):
    assert R.main(["bundle"]) == 0
    assert json.loads(capsys.readouterr().out)["bundle_sha256"] == R.read_pin(PINS)["bundle_sha256"]
    package = root / "coprepan" / "package"
    assert R.main(["verify-release", str(package / "release"), "--exports", str(package / "exports")]) == 0
    assert json.loads(capsys.readouterr().out)["exports_checked"] is True
    (package / "exports" / "cpx-fixture-0001" / "export.json").write_bytes(b"{}")
    assert R.main(["verify-package", str(package)]) == 1
    assert json.loads(capsys.readouterr().out)["codes"] == ["PACKAGE_INCOMPLETE"]
    assert R.main(["verify-study", str(root / "coprepan" / "study"), "--release", f"coprepan-0000.1={package / 'release'}"]) == 0
