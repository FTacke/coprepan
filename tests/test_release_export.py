"""CO.PRE.PAN's native export object and its way into ``crosscorpus-release/v1`` (CPD-0011; PG3).

Everything here is synthetic: the invented pages of the canary go through the real code path —
recorded exchange → sealed pack → preservation → document identity → extraction → admission label
— and from there into an export, a fixture release, a package and a study population. The "parsed
dates" are written by hand. **No corpus release is built, and none can be**: an export of kind
``corpus`` is refused while no extractor is adopted.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone

import pytest

from coprepan import admission, analysis_contract, core_pipeline, extraction, identity
from coprepan import release_contract as R
from coprepan import release_export as X
from support_crosscorpus import press_bundle
from support_release import change_document, records_of
from test_core_pipeline import OUTLET, WWW, Canary, ex, page

COMMIT = "0" * 39 + "1"
CREATED = datetime(2026, 10, 8, 0, 0, 0, tzinfo=timezone.utc)
LABELLED_AT = "2026-10-08T00:00:00.000000Z"
PARSER = "fixture-date-parser/0"   # no date parser exists; the dates below are written by hand
METADATA = {
    "title": "CO.PRE.PAN fixture release (synthetic; not corpus data)", "description": "Synthetic. Not a corpus, not a deposit.",
    "resource_type": "Dataset", "version": "set by the builder", "languages": ["es"],
    "creators": [{"name": "Fixture, Person", "orcid": None, "orcid_state": "not_available", "affiliation": None, "affiliation_state": "not_available"}],
    "publisher": None, "publisher_state": "undecided", "publication_year": None, "publication_year_state": "not_available",
    "identifier": {"scheme": "doi", "value": None, "value_state": "not_available"},
    "rights": {"licence": None, "licence_state": "undecided"}, "access": {"level": None, "level_state": "undecided"},
    "related_identifiers": [], "funding": [],
    "source_media_statement": "The release derives from preserved web pages. No fetched page is part of this package.",
}


def tree_state(directory) -> str:
    """A digest of every file below a directory, whatever its name — to show that nothing changed."""
    digest = hashlib.sha256()
    for path in sorted(p for p in directory.rglob("*") if p.is_file() and p.name != ".writer.lock"):
        digest.update(path.relative_to(directory).as_posix().encode("utf-8") + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class Pipeline:
    """One pass of the synthetic canary with labels, and what an export is built from."""

    def __init__(self, base, items=None):
        self.canary = Canary(base, items=items).all()
        self.labels = admission.label_pack(self.canary.workspace, preservation_root=self.canary.root, identifier=self.canary.pack_id,
                                           results=self.canary.results, extractor=extraction.BASELINE, labelled_at=LABELLED_AT)
        self.exports = base / "exports"

    def inputs(self, dates=None, usable_only=True) -> list[dict]:
        """One entry per document version: its first observation in the pack."""
        store, labels = self.canary.workspace.layer_store(), {label["fetch_id"]: label for label in self.labels}
        seen, out = set(), []
        for result in self.canary.results:
            version, label = result.get("document_version_id"), labels.get(result["fetch_id"])
            if version is None or version in seen or not result.get("extraction_fingerprint"):
                continue
            if usable_only and label["technical_status"] != admission.TECHNICALLY_USABLE:
                continue
            seen.add(version)
            entry = {"document_id": result["document_id"], "document_version_id": version,
                     "extraction_payload": store.read(extraction.STAGE, result["extraction_fingerprint"]),
                     "extraction_fingerprint": result["extraction_fingerprint"], "admission_label": label,
                     "source": {"fetch_id": result["fetch_id"], "body_sha256": result["body_sha256"], "pack_id": result["pack_id"]}}
            if dates and version in dates:
                entry["date"] = dates[version]
            out.append(entry)
        return out

    def export(self, documents=None, **arguments):
        arguments = {"outlet_id": OUTLET, "code_commit": COMMIT, "export_kind": X.KIND_FIXTURE, **arguments}
        return X.build_export(self.exports, documents=self.inputs() if documents is None else documents, **arguments)


@pytest.fixture
def pipeline(tmp_path):
    return Pipeline(tmp_path / "run")


def dated(pipeline) -> dict:
    """Hand-written dates for the two versions of the article; the other pages stay undated."""
    versions = [entry["document_version_id"] for entry in pipeline.inputs()]
    return {versions[0]: {"date": "2026-09-04", "basis": "json_ld"}, versions[1]: {"date": "2026-10-02", "basis": "open_graph"}}


def release(pipeline, export_ids, release_id="coprepan-0000.1", freeze=True, **arguments):
    directory = pipeline.exports.parent / "releases" / release_id
    digest = X.build_release(directory, release_id=release_id, release_kind="fixture", exports_root=pipeline.exports, export_ids=export_ids,
                             created_at=CREATED, code_commit=COMMIT, **arguments)
    if freeze:
        X.freeze_release(directory, exports_root=pipeline.exports, frozen_by="fixture", frozen_at=CREATED, confirmation=digest)
    return directory, digest


# --- the export object (Q4) -------------------------------------------------------------------------


def test_an_export_is_built_from_the_real_data_model_and_verifies(pipeline):
    identifier, status = pipeline.export()
    directory = pipeline.exports / identifier
    assert status == X.STORED and X.is_export_id(identifier) and X.export_problems(directory) == []
    manifest, records = X.read_export(directory)
    assert manifest["schema"] == "coprepan-export/v1" and manifest["layers"] == ["extraction"] and manifest["outlet_id"] == OUTLET
    assert manifest["components"]["extractors"] == ["baseline_html/0.1.0"]
    assert manifest["components"]["extractor_lifecycles"] == {"baseline_html/0.1.0": "EXPERIMENTAL"} and manifest["export_kind"] == "fixture"
    assert len(records) == 4                                  # two textual states of the article, the republished page, the bare page
    assert len({record["document_id"] for record in records}) == 3
    files = sorted(entry["path"] for entry in R.tree_listing(directory))
    assert files[:2] == ["DOCUMENTS.jsonl", "EXPORT_MANIFEST.json"] and all(path.startswith("extraction/") for path in files[2:])
    assert len(files) == 2 + len({record["extraction"]["path"] for record in records})


def test_the_id_covers_the_whole_object_and_no_document_contains_its_own_digest(pipeline):
    identifier, _ = pipeline.export()
    manifest, _ = X.read_export(pipeline.exports / identifier)
    assert "export_id" not in manifest and not [name for name in manifest if name.endswith("manifest_sha256")]
    assert X.export_id(manifest) == identifier == f"cpx1-{R.document_digest(manifest)[:32]}"
    other, _ = pipeline.export(code_commit="0" * 39 + "2")   # provenance is part of the object
    assert other != identifier
    fewer, _ = pipeline.export(documents=pipeline.inputs()[:2])
    assert fewer not in (identifier, other)


def test_the_same_material_gives_the_same_export_on_another_machine(tmp_path, pipeline):
    """No clock, no host, no location enters: two independent passes in two places agree byte for byte."""
    identifier, _ = pipeline.export()
    elsewhere = Pipeline(tmp_path / "another" / "place")
    again, _ = elsewhere.export()
    assert again == identifier
    assert R.tree_digest(elsewhere.exports / again) == R.tree_digest(pipeline.exports / identifier)
    assert X.member_record(elsewhere.exports / again) == X.member_record(pipeline.exports / identifier)


def test_an_export_holds_no_fetched_page_no_path_and_no_workspace_state(tmp_path, pipeline):
    identifier, _ = pipeline.export()
    for entry in R.tree_listing(pipeline.exports / identifier):
        data = (pipeline.exports / identifier / entry["path"]).read_bytes()
        assert b"<html" not in data.lower() and b"<article" not in data.lower()          # extracted text, never the page
        text = data.decode("utf-8")
        for fragment in (str(tmp_path), tmp_path.as_posix(), tmp_path.name, "workspace", "preservation_root", ":\\", ".warc"):
            assert fragment not in text, (entry["path"], fragment)
        assert R.is_contract_path(entry["path"])
    _, records = X.read_export(pipeline.exports / identifier)
    for record in records:
        assert identity.is_fetch_id(record["source"]["fetch_id"]) and record["source"]["pack_id"] == pipeline.canary.pack_id


def test_an_export_is_written_once(pipeline):
    identifier, _ = pipeline.export()
    before = tree_state(pipeline.exports)
    assert pipeline.export() == (identifier, X.ALREADY_STORED)
    assert tree_state(pipeline.exports) == before
    stored = next((pipeline.exports / identifier / "extraction").rglob("*.json"))
    stored.write_bytes(stored.read_bytes() + b"\n")
    with pytest.raises(X.ExportConflict):
        pipeline.export()                                     # a different tree under the id is never overwritten
    assert not list(pipeline.exports.glob("*.part-*"))


@pytest.mark.parametrize("damage", ["byte_appended", "file_added", "file_deleted", "renamed", "manifest_edited", "records_edited"])
def test_a_changed_export_does_not_verify(pipeline, damage):
    identifier, _ = pipeline.export()
    directory = pipeline.exports / identifier
    payload = next((directory / "extraction").rglob("*.json"))
    if damage == "byte_appended":
        payload.write_bytes(payload.read_bytes() + b" ")
    elif damage == "file_added":
        (directory / "raw.html").write_bytes(b"<html></html>")
    elif damage == "file_deleted":
        payload.unlink()
    elif damage == "renamed":
        directory = directory.rename(pipeline.exports / "cpx1-00000000000000000000000000000000")
    elif damage == "manifest_edited":
        change_document(directory / X.EXPORT_MANIFEST, lambda manifest: manifest.update(export_kind="corpus"))
    else:
        records = records_of(directory / X.EXPORT_DOCUMENTS)
        records[0]["admission"]["technical_status"] = "TECHNICALLY_UNUSABLE"
        (directory / X.EXPORT_DOCUMENTS).write_bytes(R.record_set_bytes(records))
    assert X.export_problems(directory) != []
    with pytest.raises(X.ExportRefused):
        X.member_record(directory)


def test_an_export_of_another_schema_version_is_refused_by_name(pipeline):
    identifier, _ = pipeline.export()
    change_document(pipeline.exports / identifier / X.EXPORT_MANIFEST, lambda manifest: manifest.update(schema="coprepan-export/v2"))
    assert "refused by name" in X.export_problems(pipeline.exports / identifier)[0]


# --- gates the export does not go around ------------------------------------------------------------


def test_corpus_text_is_not_exported_from_an_extractor_that_is_not_adopted(pipeline):
    """The gate of CPD-0007 §7 holds here too: today nothing can become a corpus export."""
    assert extraction.BASELINE.lifecycle == extraction.LIFECYCLE_EXPERIMENTAL
    with pytest.raises(extraction.ExtractorNotActive):
        pipeline.export(export_kind=X.KIND_CORPUS)
    assert not pipeline.exports.exists()


def test_a_technically_unusable_fetch_is_labelled_and_not_exported(tmp_path):
    error_page = Pipeline(tmp_path / "errors", items=[ex(f"{WWW}/no-existe", page("No encontrado", text="La página no existe."), 0, status=404)])
    documents = error_page.inputs(usable_only=False)
    assert len(documents) == 1 and documents[0]["admission_label"]["blocking_reasons"] == ["http_error_status"]
    with pytest.raises(X.ExportRefused, match="technically unusable"):
        error_page.export(documents=documents)


def test_what_does_not_belong_together_is_refused(pipeline):
    documents = pipeline.inputs()
    first, second = documents[0], documents[1]
    for broken in (
        {**first, "admission_label": second["admission_label"]},                              # the label of another fetch
        {**first, "extraction_payload": second["extraction_payload"]},                        # another text under this version id
        {**first, "source": {**first["source"], "body_sha256": "0" * 64}},                    # not the preserved body
        {**first, "source": {**first["source"], "pack_id": "pk1-es_otro_diario-20261007-000"}},  # a pack of another outlet
        {**first, "extraction_payload": first["extraction_payload"].replace(b"\n", b"\r\n")},  # not the stored bytes
        {**first, "date": {"date": "2026-09-04", "basis": "html_lang"}},                      # not a basis of a date
    ):
        with pytest.raises((X.ExportRefused, ValueError)):
            pipeline.export(documents=[broken, second], date_parser=PARSER if "date" in broken else None)
    with pytest.raises(X.ExportRefused):
        pipeline.export(documents=[first, first])
    with pytest.raises(X.ExportRefused):
        pipeline.export(documents=[])
    with pytest.raises(X.ExportRefused):
        pipeline.export(documents=documents, code_commit="HEAD")
    with pytest.raises(X.ExportRefused):
        pipeline.export(documents=documents, date_parser=PARSER)    # a parser named, and no date parsed
    with pytest.raises(X.ExportRefused):
        pipeline.export(documents=documents, outlet_id="es_otro_diario")


def test_building_exports_changes_nothing_it_reads(pipeline):
    """Preserved bytes, ledger, evidence tables, identity tables and layers are read, never written."""
    workspace, preservation = tree_state(pipeline.canary.workspace.root), tree_state(pipeline.canary.root)
    identifier, _ = pipeline.export()
    release(pipeline, [identifier])
    assert tree_state(pipeline.canary.workspace.root) == workspace and tree_state(pipeline.canary.root) == preservation


def test_every_exported_text_leads_back_to_preserved_evidence(pipeline):
    """From the export alone: the fetch, the preserved body by hash, the pack — and the same text again by replay."""
    identifier, _ = pipeline.export()
    canary, directory = pipeline.canary, pipeline.exports / identifier
    preserved = core_pipeline.open_preserved_pack(canary.root, canary.pack_id)
    for record in X.read_export(directory)[1]:
        source = record["source"]
        assert canary.workspace.ledger().state(source["fetch_id"]) == "RAW_PRESERVED"
        assert hashlib.sha256(preserved.body(source["fetch_id"])).hexdigest() == source["body_sha256"]
        replayed = core_pipeline.replay_extraction(canary.workspace, preservation_root=canary.root, identifier=canary.pack_id,
                                                   fetch_id=source["fetch_id"])
        assert replayed["status"] == "ALREADY_STORED" and replayed["payload_sha256"] == record["extraction"]["sha256"]
        assert (replayed["fingerprint"], replayed["artifact_id"]) == (record["extraction"]["fingerprint"], record["extraction"]["artifact_id"])
        assert (directory / record["extraction"]["path"]).read_bytes() == canary.workspace.layer_store().read("extraction", replayed["fingerprint"])


# --- export → member → manifest → freeze → package → study population (PG3) -------------------------


def test_the_document_index_states_what_is_known_and_guesses_nothing(pipeline):
    identifier, _ = pipeline.export()
    documents = X.document_records(pipeline.exports / identifier)
    native = {record["document_version_id"]: record for record in X.read_export(pipeline.exports / identifier)[1]}
    assert {document["document_id"] for document in documents} == set(native)
    for document in documents:
        assert identity.is_document_version_id(document["document_id"])
        assert document["source_sha256"] == native[document["document_id"]]["extracted_text_sha256"]
        assert (document["outlet_id"], document["country_id"], document["export_id"]) == (OUTLET, "uy", identifier)
        assert (document["audio_ms"], document["audio_ms_state"]) == (None, "not_applicable")
        assert (document["tokens_counted"], document["tokens_counted_state"]) == (None, "not_available")
        assert document["date"] is None and document["cohort"] is None
    # a page value nobody parsed is not_available; a page without one is unknown; a crawl date is never a date
    assert sorted({document["date_state"] for document in documents}) == ["not_available", "unknown"]
    assert all(document["date_state"] == document["date_basis_state"] == document["cohort_state"] for document in documents)
    assert R.load_contract().problems(R.DOCUMENT_SCHEMA, documents[0]) == []


def test_a_parsed_date_enters_with_its_basis_and_its_cohort(pipeline):
    dates = dated(pipeline)
    identifier, _ = pipeline.export(documents=pipeline.inputs(dates), date_parser=PARSER)
    documents = {document["document_id"]: document for document in X.document_records(pipeline.exports / identifier)}
    first, second = (documents[version] for version in dates)
    assert (first["date"], first["date_basis"], first["cohort"], first["cohort_state"]) == ("2026-09-04", "json_ld", "2026-Q3", "known")
    assert (second["date"], second["date_basis"], second["cohort"]) == ("2026-10-02", "open_graph", "2026-Q4")
    assert X.read_export(pipeline.exports / identifier)[0]["components"]["date_parser"] == PARSER
    with pytest.raises(ValueError):
        pipeline.export(documents=pipeline.inputs({**dates, next(iter(dates)): {"date": "2026-02-30", "basis": "json_ld"}}), date_parser=PARSER)


def test_the_whole_way_from_native_export_to_study_population(tmp_path, pipeline):
    contract = R.load_contract()
    identifier, _ = pipeline.export(documents=pipeline.inputs(dated(pipeline)), date_parser=PARSER)
    directory, digest = release(pipeline, [identifier])
    verdict = R.verify_release(directory, exports_root=pipeline.exports, require_exports=True, contract=contract)
    assert verdict.conformant and verdict.exports_checked, verdict.objections
    manifest = R.parse_strict((directory / R.RELEASE_MANIFEST).read_bytes())
    assert R.release_manifest_digest(directory) == digest and "manifest_sha256" not in manifest
    assert manifest["vocabularies"] == {"date_basis": ["json_ld", "open_graph", "html_meta"], "export_schema": ["coprepan-export/v1"]}
    assert manifest["anchors"]["document_kind"] == "document_version" and manifest["anchors"]["source_included"] is False
    assert (manifest["token_denominator"], manifest["token_denominator_state"]) == (None, "not_available")
    assert manifest["totals"] == {"exports": 1, "documents": 4, "tokens_counted": None, "tokens_counted_state": "not_available",
                                  "audio_ms": None, "audio_ms_state": "not_applicable"}
    assert manifest["provenance"]["member_code_commits"] == [COMMIT] and manifest["changes"]["added"] == [identifier]
    assert records_of(directory / R.MEMBERS) == [X.member_record(pipeline.exports / identifier)]
    assert len(records_of(directory / R.COVERAGE)) == 3      # 2026-Q3, 2026-Q4, and one cell of documents without a date

    package = tmp_path / "packages" / "coprepan-0000.1-archive"
    X.build_package(package, release_directory=directory, exports_root=pipeline.exports, package_kind="archive",
                    package_id="coprepan-0000.1-archive-fixture", created_at=CREATED, metadata=METADATA,
                    extra_files={"README.md": ("documentation", b"Synthetic. Not corpus data.\n")})
    assert R.verify_package(package, contract=contract).conformant
    for entry in records_of(package / R.PACKAGE_FILES):
        assert R.is_contract_path(entry["path"]) and not entry["path"].endswith((".html", ".warc", ".warc.gz"))

    study = tmp_path / "studies" / "fixture_study"
    undated = [document["document_id"] for document in X.document_records(pipeline.exports / identifier) if document["date_state"] != "known"]
    first = next(iter(dated(pipeline)))
    X.build_study_population(
        study, study_id="fixture_study", population_id="main", created_at=CREATED, releases={"coprepan": directory},
        selection={"kind": "declarative_filter", "tool": {"id": X.BUILDER_TOOL, "version": X.BUILDER_VERSION},
                   "filters": [{"corpus_id": "coprepan", "all": [{"field": "date", "from": "2026-07-01", "to": "2026-12-31"}]}],
                   "description": "fixture: one filter, one stated exclusion"},
        excluded=[{"level": "document", "id_kind": "document_version", "id": first, "document_id": first, "reason": "earlier_textual_state"}])
    assert R.verify_study(study, {"coprepan-0000.1": package / "release"}, contract=contract).conformant   # restored from the package alone
    population = R.parse_strict((study / R.STUDY_POPULATION).read_bytes())
    selected = [record["id"] for record in records_of(study / R.SELECTED)]
    assert len(selected) == 1 and not set(selected) & set(undated)     # an undated document is in no date range, by no default
    assert population["inputs"][0]["release_manifest_sha256"] == digest and population["exclusion_reasons"] == ["earlier_textual_state"]
    assert population["totals"] == [{"corpus_id": "coprepan", "selected_records": 1, "documents": 1, "tokens_counted": None,
                                     "tokens_counted_state": "not_available", "audio_ms": None, "audio_ms_state": "not_applicable"}]


def test_the_whole_way_is_deterministic(tmp_path):
    """Two independent passes — acquisition to study population — give the same digests at every step."""
    digests = []
    for name in ("one", "two/elsewhere"):
        run = Pipeline(tmp_path / name)
        identifier, _ = run.export(documents=run.inputs(dated(run)), date_parser=PARSER)
        directory, digest = release(run, [identifier])
        package = X.build_package(tmp_path / name / "package", release_directory=directory, exports_root=run.exports, package_kind="archive",
                                  package_id="p", created_at=CREATED, metadata=METADATA)
        study = X.build_study_population(
            tmp_path / name / "study", study_id="s", population_id="main", created_at=CREATED, releases={"coprepan": directory},
            selection={"kind": "declarative_filter", "tool": {"id": "t", "version": "1"}, "description": "d",
                       "filters": [{"corpus_id": "coprepan", "all": [{"field": "outlet_id", "in": [OUTLET]}]}]})
        digests.append((identifier, digest, package, study, R.tree_digest(tmp_path / name / "package")))
    assert digests[0] == digests[1]


def test_a_release_exists_only_after_an_explicit_freeze(pipeline):
    identifier, _ = pipeline.export()
    directory, digest = release(pipeline, [identifier], freeze=False)
    before = (directory / R.RELEASE_MANIFEST).read_bytes()
    assert R.verify_release(directory, exports_root=pipeline.exports, require_exports=True).codes == ["REFERENCE_MISSING"]
    arguments = dict(exports_root=pipeline.exports, frozen_by="fixture", frozen_at=CREATED)
    with pytest.raises(X.FreezeRefused):
        X.freeze_release(directory, confirmation="yes", **arguments)             # confirmed by stating the digest, nothing else
    assert not (directory / R.RELEASE_FREEZE).exists()
    record = X.freeze_release(directory, confirmation=digest, **arguments)
    assert record["release_manifest_sha256"] == digest and record["state"] == "FROZEN"
    assert (directory / R.RELEASE_MANIFEST).read_bytes() == before               # the manifest never contains its digest
    with pytest.raises(X.FreezeRefused):
        X.freeze_release(directory, confirmation=digest, **arguments)            # frozen once
    assert R.verify_release(directory, exports_root=pipeline.exports, require_exports=True).conformant


def test_a_release_is_not_frozen_while_an_export_it_names_does_not_verify(pipeline):
    identifier, _ = pipeline.export()
    directory, digest = release(pipeline, [identifier], freeze=False)
    payload = next((pipeline.exports / identifier / "extraction").rglob("*.json"))
    payload.write_bytes(payload.read_bytes() + b" ")
    with pytest.raises(X.FreezeRefused, match="EXPORT_TREE_MISMATCH"):
        X.freeze_release(directory, exports_root=pipeline.exports, frozen_by="fixture", frozen_at=CREATED, confirmation=digest)
    assert not (directory / R.RELEASE_FREEZE).exists()


def test_a_frozen_release_notices_any_change_of_what_it_names(pipeline):
    identifier, _ = pipeline.export()
    directory, _ = release(pipeline, [identifier])

    def codes() -> list[str]:
        return R.verify_release(directory, exports_root=pipeline.exports, require_exports=True).codes

    manifest = (directory / R.RELEASE_MANIFEST).read_bytes()
    (directory / R.RELEASE_MANIFEST).write_bytes(manifest.replace(b"2026-10-08T00:00:00.000000Z", b"2026-10-09T00:00:00.000000Z"))
    assert codes() == ["FREEZE_MISMATCH"]
    (directory / R.RELEASE_MANIFEST).write_bytes(manifest)
    (pipeline.exports / identifier / X.EXPORT_MANIFEST).write_bytes((pipeline.exports / identifier / X.EXPORT_MANIFEST).read_bytes() + b"\n")
    assert codes() == ["EXPORT_TREE_MISMATCH"]                                   # provenance is bound, not only the text
    shutil.rmtree(pipeline.exports / identifier)
    assert codes() == ["EXPORT_MISSING"]                                         # a manifest reconstructs nothing by itself


def test_fixture_material_cannot_become_anything_but_a_fixture_release(pipeline):
    identifier, _ = pipeline.export()
    arguments = dict(exports_root=pipeline.exports, export_ids=[identifier], created_at=CREATED, code_commit=COMMIT)
    for release_id, kind in (("coprepan-2027.1", "release"), ("coprepan-2027.1", "provisional_export"), ("coprepan-2027.1", "fixture"),
                             ("coprepan-0000.1", "release"), ("coprepan-legacy-2026-06", "release"), ("corapan-0000-01", "fixture")):
        with pytest.raises(X.ExportRefused):
            X.build_release(pipeline.exports.parent / "r" / f"{release_id}-{kind}", release_id=release_id, release_kind=kind, **arguments)
    assert not (pipeline.exports.parent / "r").exists()


def test_a_document_version_is_delivered_by_exactly_one_member(pipeline):
    documents = pipeline.inputs()
    one, _ = pipeline.export(documents=documents[:3])
    two, _ = pipeline.export(documents=documents[2:])
    with pytest.raises(X.ExportRefused, match="exactly one member"):
        release(pipeline, [one, two])
    disjoint, _ = pipeline.export(documents=documents[3:])
    directory, _ = release(pipeline, [one, disjoint])
    assert R.verify_release(directory, exports_root=pipeline.exports, require_exports=True).conformant


def test_two_textual_states_of_one_article_are_two_documents_of_a_release(pipeline):
    """The sampled unit is the document version (contract §8). That two of them are one article is
    stated by the native record (`document_id`), not by the release document index.
    """
    identifier, _ = pipeline.export()
    directory, _ = release(pipeline, [identifier])
    native = X.read_export(pipeline.exports / identifier)[1]
    article = [record for record in native if [r["document_id"] for r in native].count(record["document_id"]) == 2]
    assert len(article) == 2 and article[0]["extracted_text_sha256"] != article[1]["extracted_text_sha256"]
    index = records_of(directory / R.DOCUMENTS)
    assert len(index) == 4 and "editorial_id" not in index[0] and "document_version_id" not in index[0]


def test_a_correction_is_a_new_export_in_a_later_release_and_the_earlier_one_stays(pipeline):
    documents = pipeline.inputs()
    old, _ = pipeline.export(documents=[documents[0], documents[2]])                 # the article in its first textual state
    kept, _ = pipeline.export(documents=[documents[3]])
    first, first_digest = release(pipeline, [old, kept])
    before = tree_state(pipeline.exports / old)
    new, _ = pipeline.export(documents=[documents[1], documents[2]])                 # the corrected text: a new object, a new id
    assert new != old and tree_state(pipeline.exports / old) == before
    second, _ = release(pipeline, [new, kept], release_id="coprepan-0000.2", previous_directory=first,
                        replaced=[{"old": old, "new": new, "reason": "the publisher corrected the article"}])
    manifest = R.parse_strict((second / R.RELEASE_MANIFEST).read_bytes())
    assert manifest["previous_release"] == {"state": "known", "release_id": "coprepan-0000.1", "release_manifest_sha256": first_digest}
    assert manifest["changes"] == {"added": [], "removed": [], "replaced": [{"old": old, "new": new, "reason": "the publisher corrected the article"}]}
    check = dict(exports_root=pipeline.exports, require_exports=True)
    assert R.verify_release(second, previous_directory=first, **check).conformant
    assert R.verify_release(first, **check).conformant                                # the earlier release is still what it was
    # a difference nobody accounted for, and a predecessor that is not the named one
    silent = pipeline.exports.parent / "releases" / "coprepan-0000.3"
    with pytest.raises(X.ExportRefused, match="MEMBERSHIP_INCONSISTENT"):
        X.build_release(silent, release_id="coprepan-0000.3", release_kind="fixture", exports_root=pipeline.exports, export_ids=[new],
                        created_at=CREATED, code_commit=COMMIT, previous_directory=first)
    other, _ = release(pipeline, [kept], release_id="coprepan-0000.4")
    assert R.verify_release(second, previous_directory=other, **check).codes == ["PREVIOUS_RELEASE_MISMATCH"]


# --- package and distribution: mechanics only -------------------------------------------------------


def test_a_package_never_takes_a_fetched_page_or_source_media(tmp_path, pipeline):
    identifier, _ = pipeline.export()
    directory, _ = release(pipeline, [identifier])
    arguments = dict(release_directory=directory, exports_root=pipeline.exports, package_kind="distribution", package_id="p",
                     created_at=CREATED, metadata=METADATA)
    for path in ("raw/pk1-uy_diario_ejemplo-20261007-000.warc.gz", "raw/page.WARC", "media/clip.mp3", "release/NOTES.md",
                 "exports/extra.json", "PACKAGE_FILES.jsonl"):
        with pytest.raises(X.ExportRefused):
            X.build_package(tmp_path / "refused", extra_files={path: ("documentation", b"x")}, **arguments)
    assert not (tmp_path / "refused").exists()
    with pytest.raises(X.ExportRefused):                       # an unfrozen manifest is not a release; there is nothing to package
        unfrozen, _ = release(pipeline, [identifier], release_id="coprepan-0000.2", freeze=False)
        X.build_package(tmp_path / "unfrozen", **{**arguments, "release_directory": unfrozen})


def test_a_distribution_package_may_name_its_exports_by_reference(tmp_path, pipeline):
    identifier, _ = pipeline.export()
    directory, _ = release(pipeline, [identifier])
    package = tmp_path / "distribution"
    X.build_package(package, release_directory=directory, exports_root=pipeline.exports, package_kind="distribution", package_id="p",
                    created_at=CREATED, metadata=METADATA, exports="by_reference")
    assert not (package / "exports").exists()
    without = R.verify_package(package)
    assert without.conformant and without.exports_checked is False     # proves the manifest side only, and says so
    assert R.verify_package(package, exports_root=pipeline.exports).exports_checked is True
    with pytest.raises(X.ExportRefused):
        X.build_package(tmp_path / "archive", release_directory=directory, exports_root=pipeline.exports, package_kind="archive",
                        package_id="p", created_at=CREATED, metadata=METADATA, exports="by_reference")


# --- what a study pins (Q2) -------------------------------------------------------------------------


def test_a_study_pins_the_release_and_the_analysis_bundle_as_two_different_digests(tmp_path, pipeline):
    """The release manifest digest identifies the corpus state; the analysis bundle's own
    `manifest_sha256` identifies the tables that were read. A study names both; neither stands in
    for the other (CPD-0012, amending CPD-0008 §7).
    """
    identifier, _ = pipeline.export()
    bundle = press_bundle()
    sealed = bundle["release"]["manifest_sha256"]
    layer = {"state": "known", "contract": analysis_contract.CONTRACT, "manifest_sha256": sealed}
    directory, digest = release(pipeline, [identifier], analysis_layer=layer)
    assert analysis_contract.CONTRACT == R.ANALYSIS_CONTRACT and sealed != digest
    assert "manifest_sha256" in bundle["release"]            # the projection keeps its own sealing
    assert digest not in json.dumps(bundle["release"])       # and never contains the digest of what names it
    version = X.document_records(pipeline.exports / identifier)[0]["document_id"]
    unit = identity.unit_id(version, 0)
    X.build_study_population(
        tmp_path / "study", study_id="pins", population_id="main", created_at=CREATED, releases={"coprepan": directory},
        analysis_layers={"coprepan": layer}, selection={"kind": "enumerated", "tool": {"id": "by-hand", "version": "0"}, "description": "one unit"},
        selected=[{"level": "unit", "id_kind": "paragraph", "id": unit, "document_id": version}])
    pinned = R.parse_strict((tmp_path / "study" / R.STUDY_POPULATION).read_bytes())["inputs"][0]
    assert pinned == {"corpus_id": "coprepan", "release_id": "coprepan-0000.1", "release_manifest_sha256": digest, "analysis_layer": layer}
    with pytest.raises(X.ExportRefused, match="ANCHOR_KIND_INVALID"):
        X.build_study_population(
            tmp_path / "turns", study_id="pins", population_id="turns", created_at=CREATED, releases={"coprepan": directory},
            selection={"kind": "enumerated", "tool": {"id": "by-hand", "version": "0"}, "description": "a turn is not a paragraph"},
            selected=[{"level": "unit", "id_kind": "turn", "id": unit, "document_id": version}])


def test_a_population_names_only_what_its_releases_contain(tmp_path, pipeline):
    identifier, _ = pipeline.export()
    directory, _ = release(pipeline, [identifier])
    with pytest.raises(X.ExportRefused):
        X.build_study_population(
            tmp_path / "study", study_id="s", population_id="main", created_at=CREATED, releases={"coprepan": directory},
            selection={"kind": "enumerated", "tool": {"id": "by-hand", "version": "0"}, "description": "d"},
            selected=[{"level": "document", "id_kind": "document_version", "id": "not-in-the-release", "document_id": "not-in-the-release"}])
    assert not (tmp_path / "study").exists()
