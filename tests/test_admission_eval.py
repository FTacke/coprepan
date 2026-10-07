"""Admission labels, extractor lifecycle, the evaluation harness and the review package.

Everything here runs on the synthetic canary. The "references" used to exercise the scoring are
written in this file to test arithmetic; **they are not gold and no result here is a quality
measurement.**
"""

import hashlib
import json

import pytest

from coprepan import admission as A
from coprepan import core_pipeline as C
from coprepan import extraction as E
from coprepan import extraction_eval as EV
from test_core_pipeline import ARTICLE, OUTLET, PDF, WWW, Canary, by_fetch, ex, fixture, page, variant_extractor

LABELLED_AT = "2026-10-07T21:00:00.000000Z"


def labels_of(canary, extractor=E.BASELINE):
    return A.label_pack(canary.workspace, preservation_root=canary.root, identifier=canary.pack_id, results=canary.results,
                        extractor=extractor, labelled_at=LABELLED_AT)


@pytest.fixture
def canary(tmp_path):
    return Canary(tmp_path).all()


# --- admission labels -------------------------------------------------------------------------------


def test_every_fetched_item_gets_a_label_and_nothing_is_removed(canary):
    labels = labels_of(canary)
    assert len(labels) == 8 == len(canary.results)                       # failed fetches are not documents; nothing else is missing
    by_id = {label["fetch_id"]: label for label in labels}
    ids = canary.fetch_ids()
    article, variant, updated, republished, bare, pdf, _failed, moved, foreign = (by_id.get(i) for i in ids)
    assert _failed is None
    assert article["technical_status"] == "TECHNICALLY_USABLE" and article["blocking_reasons"] == []
    assert article["document_version_id"] == by_fetch(canary)[ids[0]]["document_version_id"]
    assert (pdf["technical_status"], pdf["blocking_reasons"]) == ("TECHNICALLY_UNUSABLE", ["not_extractable"])
    assert pdf["reasons"][0]["evidence"] == {"extraction_reason": "unsupported_content_type", "declared_content_type": "application/pdf"}
    assert (foreign["technical_status"], foreign["blocking_reasons"]) == ("TECHNICALLY_UNUSABLE", ["no_document"])
    assert "duplicate_body_of_other_document" in [r["reason"] for r in republished["reasons"]]
    assert republished["technical_status"] == "TECHNICALLY_USABLE"       # a duplicate is information, not a defect
    assert "moved_from_other_document" in [r["reason"] for r in moved["reasons"]]
    informing = {r["reason"] for r in bare["reasons"] if r["effect"] == "informs"}
    assert {"no_title", "publication_date_unknown", "author_unknown", "section_unknown", "language_undeclared"} <= informing
    assert bare["technical_status"] == "TECHNICALLY_USABLE"              # missing metadata never blocks
    # raw, extraction and identity are exactly as they were
    assert len(C.open_preserved_pack(canary.root, canary.pack_id).entries) == 9


def test_a_label_carries_status_reasons_evidence_rule_run_and_version(canary):
    label = labels_of(canary)[0]
    assert label["schema"] == "coprepan-admission-label/v1" and label["ruleset"] == "admission-technical/1"
    assert {"fetch_id", "run_id", "outlet_id", "document_id", "document_version_id", "technical_status", "blocking_reasons",
            "reasons", "measurements", "extraction_fingerprint", "extraction_payload_sha256", "labelled_at"} <= set(label)
    assert label["run_id"] == canary.run.run_id and label["labelled_at"] == LABELLED_AT
    assert all(set(reason) == {"reason", "effect", "evidence"} and reason["reason"] in A.REASONS for reason in label["reasons"])
    assert label["measurements"]["body_whitespace_tokens"] > 20 and label["measurements"]["non_body_blocks"] > 0


def test_measurements_are_recorded_and_no_threshold_is_applied(canary):
    short = Canary(canary.workspace.root.parent / "short", items=[ex(f"{WWW}/breve", page("Breve", text="Sí."), 0)]).all()
    label = labels_of(short)[0]
    assert label["measurements"]["body_whitespace_tokens"] == 1 and label["technical_status"] == "TECHNICALLY_USABLE"
    assert not any("short" in reason["reason"] or "length" in reason["reason"] for reason in label["reasons"])


def test_error_pages_redirect_answers_and_empty_bodies_are_labelled_not_dropped(tmp_path):
    items = [ex(f"{WWW}/no-existe", page("No encontrado", text="La página no existe."), 0, status=404),
             ex(f"{WWW}/caido", b"<html><body><p>Mantenimiento</p></body></html>", 1, status=503),
             ex(f"{WWW}/sale", b"", 2, status=302, redirect_not_followed="DENY: off_origin"),
             ex(f"{WWW}/vacio", b"", 3),
             ex(f"{WWW}/solo-titulo", b"<html><body><h1>Solo titulo</h1></body></html>", 4)]
    canary = Canary(tmp_path, items=items).all()
    labels = {label["fetch_id"]: label for label in labels_of(canary)}
    not_found, down, redirect, empty, title_only = (labels[i] for i in canary.fetch_ids())
    assert not_found["blocking_reasons"] == ["http_error_status"] and not_found["reasons"][0]["evidence"] == {"http_status": 404}
    assert not_found["measurements"]["body_blocks"] == 1                   # the error page's text is still there, labelled
    assert down["blocking_reasons"] == ["http_error_status"]
    assert redirect["blocking_reasons"] == ["http_redirect_answer", "not_extractable"]
    assert empty["blocking_reasons"] == ["not_extractable"] and title_only["blocking_reasons"] == ["no_body_text"]
    assert {label["technical_status"] for label in labels.values()} == {"TECHNICALLY_UNUSABLE"}
    assert len(labels) == 5


def test_labelling_is_idempotent_and_a_new_rule_set_would_write_beside_the_old(canary, monkeypatch):
    first = labels_of(canary)
    path = canary.workspace.root / "admission" / "labels.jsonl"
    before = path.read_bytes()
    assert labels_of(canary) == first and path.read_bytes() == before
    monkeypatch.setattr(A, "RULESET", "admission-technical/2")
    second = labels_of(canary)
    assert {label["ruleset"] for label in second} == {"admission-technical/2"}
    assert path.read_bytes().startswith(before) and len(path.read_bytes().splitlines()) == 16
    assert A.label_table(canary.workspace).of(first[0]["fetch_id"], "admission-technical/1") == first[0]


def test_only_a_fetched_item_can_be_labelled(canary):
    preserved = C.open_preserved_pack(canary.root, canary.pack_id)
    failed = preserved.fetch_record(canary.fetch_ids()[6])
    with pytest.raises(A.AdmissionError):
        A.label_fetch(failed, None, None)


def test_labels_are_not_scientific_categories():
    assert not any(word in reason for reason in A.REASONS for word in ("genre", "register", "opinion", "quality", "article"))
    assert set(A.REASONS.values()) == {"blocks", "informs"} and A.STATUSES == ("TECHNICALLY_USABLE", "TECHNICALLY_UNUSABLE")


# --- extractor lifecycle ----------------------------------------------------------------------------


def test_the_baseline_extractor_is_experimental_and_nothing_is_active(canary):
    assert E.BASELINE.lifecycle == "EXPERIMENTAL" and E.EXTRACTORS == {"baseline_html/0.1.0": E.BASELINE}
    assert [name for name, extractor in E.EXTRACTORS.items() if extractor.lifecycle == "ACTIVE"] == []
    with pytest.raises(E.ExtractorNotActive):
        E.BASELINE.require_active()
    with pytest.raises(E.ExtractionError):
        E.Extractor("x", "1", E.extract, "PRODUCTION")
    label = labels_of(canary)[0]
    flagged = [r for r in label["reasons"] if r["reason"] == "extractor_not_active"]
    assert flagged[0]["evidence"] == {"extractor": {"name": "baseline_html", "version": "0.1.0"}, "lifecycle": "EXPERIMENTAL"}
    assert flagged[0]["effect"] == "informs"


# --- evaluation harness -----------------------------------------------------------------------------

BODIES = {"c1": fixture("nota_v1.html"), "c2": fixture("nota_v2.html"), "c3": fixture("sin_metadatos.html"),
          "c4": fixture("nota_republicada.html"), "c5": PDF}


def frame():
    rows = []
    for case_id, body in BODIES.items():
        rows.append({"case_id": case_id, "fetch_id": "ft1:" + hashlib.sha256(case_id.encode()).hexdigest(),
                     "body_sha256": hashlib.sha256(body).hexdigest(), "pack_id": "pk1-uy_diario_ejemplo-20261007-000",
                     "outlet_id": OUTLET, "strata": {"country": "uy", "outlet": OUTLET, "page": "pdf" if case_id == "c5" else "html"},
                     "declared_content_type": "application/pdf" if case_id == "c5" else "text/html"})
    return rows


def manifest(cases=None, seed="seed-1"):
    return EV.sample_manifest(cases or frame(), sample_id="test-sample-1", strata=["country", "page"], seed=seed,
                              per_stratum=10, frame_description="synthetic canary fixtures")


def body_of(case):
    return BODIES[case["case_id"]]


NO_CAPTIONS = variant_extractor("0.2.0", lambda record: record.update(blocks=[b for b in record["blocks"] if b["kind"] != "caption"]))
EVERYTHING_IS_BODY = variant_extractor("0.3.0", lambda record: [b.update(role="body") for b in record["blocks"] if b["role"] == "non_body"])


def test_stratified_sampling_is_reproducible_and_independent_of_input_order():
    cases = frame()
    first = EV.draw_sample(cases, strata=["page"], per_stratum=2, seed="s1")
    assert EV.draw_sample(list(reversed(cases)), strata=["page"], per_stratum=2, seed="s1") == first
    assert [c["strata"]["page"] for c in first] == ["html", "html", "pdf"]    # a stratum with one case contributes one
    assert EV.draw_sample(cases, strata=["page"], per_stratum=2, seed="s2") != first or len(cases) < 4
    with pytest.raises(EV.EvaluationError):
        EV.draw_sample(cases, strata=["missing"], per_stratum=1, seed="s1")
    with pytest.raises(EV.EvaluationError):
        EV.draw_sample(cases, strata=["page"], per_stratum=0, seed="s1")


def test_a_sample_manifest_is_pinned_by_its_hash():
    m = manifest()
    EV.verify_sample(m)
    assert m == manifest() and m["schema"] == "coprepan-extraction-sample/v1" and len(m["cases"]) == 5
    assert manifest(seed="seed-2")["sample_sha256"] != m["sample_sha256"]
    with pytest.raises(EV.EvaluationError):
        EV.verify_sample({**m, "cases": m["cases"][:2]})
    with pytest.raises(EV.EvaluationError):
        EV.sample_manifest(frame() + frame()[:1], sample_id="x", strata=["page"], seed="s", per_stratum=1, frame_description="d")


def test_arms_are_run_on_the_same_bytes_and_compared(tmp_path):
    result = EV.evaluate(manifest(), [E.BASELINE, NO_CAPTIONS, EVERYTHING_IS_BODY], body_of)
    assert result["schema"] == "coprepan-extraction-evaluation/v1" and result["has_reference"] is False
    assert [arm["arm"] for arm in result["arms"]] == ["baseline_html/0.1.0", "baseline_html/0.2.0", "baseline_html/0.3.0"]
    assert {arm["lifecycle"] for arm in result["arms"]} == {"EXPERIMENTAL"}
    c1 = next(case for case in result["cases"] if case["case_id"] == "c1")
    same = c1["disagreements"]["baseline_html/0.1.0 | baseline_html/0.2.0"]
    assert same["same_body"] and same["same_title"] and same["metadata_differs"] == []  # captions are not body: no body difference
    wider = c1["disagreements"]["baseline_html/0.1.0 | baseline_html/0.3.0"]
    assert not wider["same_body"] and wider["body_tokens"][0] < wider["body_tokens"][1]
    assert wider["body_shared_share_of_first"] == 1.0 and wider["body_shared_share_of_second"] == 1.0 or wider["body_shared_share_of_second"] is not None
    pdf = next(case for case in result["cases"] if case["case_id"] == "c5")
    assert pdf["arms"]["baseline_html/0.1.0"]["outcome"] == "NOT_EXTRACTABLE"
    assert result["summary"]["arms"]["baseline_html/0.1.0"]["states"] == {"OK": 5}
    assert "Diagnostics only" in result["reading"]


def test_the_evaluation_is_deterministic(tmp_path):
    first = EV.public_record(EV.evaluate(manifest(), [E.BASELINE, NO_CAPTIONS], body_of))
    second = EV.public_record(EV.evaluate(manifest(), [E.BASELINE, NO_CAPTIONS], body_of))
    assert first == second and first["evaluation_sha256"] == second["evaluation_sha256"]
    json.dumps(first)


def test_a_changed_input_or_a_foreign_sample_stops_the_evaluation():
    with pytest.raises(EV.EvaluationError):
        EV.evaluate(manifest(), [E.BASELINE], lambda case: BODIES[case["case_id"]] + b" ")   # not the sample's bytes
    tampered = manifest()
    tampered["cases"][0]["body_sha256"] = "0" * 64
    with pytest.raises(EV.EvaluationError):
        EV.evaluate(tampered, [E.BASELINE], body_of)                                         # manifest no longer matches its hash
    with pytest.raises(EV.EvaluationError):
        EV.evaluate(manifest(), [E.BASELINE, E.BASELINE], body_of)
    with pytest.raises(EV.EvaluationError):
        EV.evaluate(manifest(), [], body_of)


def test_a_failing_or_missing_arm_is_a_result_not_a_dropped_case():
    def crash(body, **kwargs):
        raise RuntimeError("parser exploded")

    crashing = E.Extractor("crasher", "1.0", crash)
    legacy = EV.PrecomputedArm("legacy_text", "2026-06", {"c1": {"outcome": "EXTRACTED", "metadata": {}, "blocks": [
        {"index": 0, "kind": "paragraph", "role": "body", "text": "Montevideo. El crecimient o sostenido del movimiento."}]}})
    result = EV.evaluate(manifest(), [E.BASELINE, crashing, legacy], body_of)
    assert result["summary"]["arms"]["crasher/1.0"]["states"] == {"EXTRACTOR_ERROR": 5}
    assert result["summary"]["arms"]["legacy_text/2026-06"]["states"] == {"NO_OUTPUT": 4, "OK": 1}
    assert "parser exploded" in result["cases"][0]["arms"]["crasher/1.0"]["detail"]
    assert len(result["cases"]) == 5 and result["arms"][2]["kind"] == "precomputed"


def test_a_non_deterministic_arm_is_refused():
    calls = []

    def unstable(record):
        calls.append(1)
        record["blocks"] = record["blocks"][: len(calls)]

    with pytest.raises(EV.NonDeterministicArm):
        EV.evaluate(manifest(), [variant_extractor("0.9.0", unstable)], body_of)


# --- metrics (arithmetic on a hand-written reference; not gold) -------------------------------------


def test_overlap_and_boundary_arithmetic():
    reference = "uno dos tres cuatro cinco"
    assert EV.overlap(reference, reference) == {"reference_tokens": 5, "candidate_tokens": 5, "shared_tokens": 5,
                                                "retention": 1.0, "excess": 0.0}
    lost = EV.overlap("uno dos tres", reference)
    assert (lost["retention"], lost["excess"]) == (0.6, 0.0)                                 # text lost, nothing added
    padded = EV.overlap("Portada Deportes uno dos tres cuatro cinco Suscribite", reference)
    assert padded["retention"] == 1.0 and padded["excess"] == 0.375                          # everything kept, boilerplate added
    assert EV.overlap("", reference)["retention"] == 0.0 and EV.overlap("", reference)["excess"] is None
    assert EV.overlap("x", "")["retention"] is None                                           # nothing to retain: not a zero
    assert EV.boundary("uno dos tres cuatro cinco", reference, 2) == {"start_matches": True, "end_matches": True}
    assert EV.boundary("Portada uno dos tres cuatro", reference, 2) == {"start_matches": False, "end_matches": False}
    assert EV.boundary("x", "") == {"start_matches": None, "end_matches": None}


def test_scoring_against_a_reference_separates_the_dimensions():
    record = E.extract(BODIES["c1"], body_sha256=hashlib.sha256(BODIES["c1"]).hexdigest(), content_type="text/html").record
    body = E.body_text(record["blocks"])
    reference = {"state": "JUDGED", "title": "El crecimiento del puerto obliga a separar cargas", "body": body,
                 "metadata": {"author": "Ana Pérez", "section": "Deportes"}}
    score = EV.score_against_reference(record, reference, catastrophic_retention_below=0.5)
    assert (score["text_retention"], score["boilerplate_inclusion"], score["title_correct"]) == (1.0, 0.0, True)
    assert score["body_boundary"] == {"start_matches": True, "end_matches": True} and score["catastrophic"] == []
    assert score["metadata"]["author"]["correct"] and not score["metadata"]["section"]["correct"]

    everything = EVERYTHING_IS_BODY.run(BODIES["c1"], body_sha256=hashlib.sha256(BODIES["c1"]).hexdigest(), content_type="text/html").record
    wide = EV.score_against_reference(everything, reference, catastrophic_retention_below=0.5)
    assert wide["text_retention"] == 1.0 and wide["boilerplate_inclusion"] > 0.1 and not wide["body_boundary"]["start_matches"]

    half = {**record, "blocks": [b for b in record["blocks"] if b["role"] != "body"][:1] + [b for b in record["blocks"] if b["role"] == "body"][:1]}
    lossy = EV.score_against_reference(half, reference, catastrophic_retention_below=0.5)
    assert lossy["text_retention"] < 0.5 and lossy["catastrophic"] == ["body_mostly_lost"]
    assert EV.score_against_reference(None, reference, catastrophic_retention_below=0.5)["catastrophic"] == ["no_output"]
    pdf = E.extract(PDF, body_sha256=hashlib.sha256(PDF).hexdigest(), content_type="application/pdf").record
    assert EV.score_against_reference(pdf, reference, catastrophic_retention_below=0.5)["catastrophic"] == ["not_extracted"]
    for unjudged in ("NOT_AN_ARTICLE", "DAMAGED_SOURCE", "UNJUDGEABLE"):
        assert EV.score_against_reference(record, {"state": unjudged}, catastrophic_retention_below=0.5) == {
            "scored": False, "reference_state": unjudged}


def test_a_reference_needs_its_catastrophic_threshold_stated_in_advance():
    references = {"c1": {"state": "JUDGED", "title": "x", "body": "y", "metadata": {}}}
    with pytest.raises(EV.EvaluationError):
        EV.evaluate(manifest(), [E.BASELINE], body_of, references=references)
    result = EV.evaluate(manifest(), [E.BASELINE], body_of, references=references, catastrophic_retention_below=0.5)
    assert result["summary"]["arms"]["baseline_html/0.1.0"]["scored_cases"] == 1          # only cases with a reference are scored
    assert next(c for c in result["cases"] if c["case_id"] == "c2")["reference"] is None


# --- review package ---------------------------------------------------------------------------------


def test_review_package_is_blinded_complete_and_pre_fills_nothing(tmp_path):
    m = manifest()
    result = EV.evaluate(m, [E.BASELINE, EVERYTHING_IS_BODY], body_of)
    index = EV.review_package(m, result, body_of, tmp_path / "review", blind_seed="blind-1")
    assert index["cases"] == ["c1", "c2", "c3", "c4", "c5"] and index["blinded"] is True
    case = json.loads((tmp_path / "review" / "cases" / "c1.json").read_text(encoding="utf-8"))
    assert case["schema"] == "coprepan-extraction-review-case/v1" and case["source"]["body_sha256"] == m["cases"][0]["body_sha256"]
    assert sorted(case["candidates"]) == ["A", "B"]
    text = json.dumps(case)
    assert "baseline_html" not in text and "0.3.0" not in text                              # no arm name reaches the reviewer
    assert "Lea también: el dragado del canal de acceso." in case["visible_text"]           # the neutral side hides nothing
    assert "esto no es texto" not in case["visible_text"]                                   # except scripts
    for candidate in case["candidates"].values():
        assert set(candidate) == {"produced_output", "outcome", "title", "body", "other_blocks", "metadata"}
        assert candidate["metadata"]["author"] == {"value": "Ana Pérez", "basis": "json_ld"}
    decision = case["decision"]
    assert decision["state"] is None and decision["title"] is None and decision["body"] is None
    assert all(value is None for value in decision["metadata"].values())
    assert all(value is None for form in decision["per_candidate"].values() for value in form.values())
    key = json.loads((tmp_path / "review" / "blinding_key.json").read_text(encoding="utf-8"))
    assert sorted(key["labels"]["c1"].values()) == ["baseline_html/0.1.0", "baseline_html/0.3.0"]
    assert len({tuple(sorted(labels.items())) for labels in key["labels"].values()}) > 1     # labels are not fixed per arm
    assert (tmp_path / "review" / "index.html").read_text(encoding="utf-8").count("<li>") == 5
    with pytest.raises(FileExistsError):
        EV.review_package(m, result, body_of, tmp_path / "review", blind_seed="blind-1")     # never overwritten
    assert EV.reference_from_decisions(tmp_path / "review") == {}                            # nothing decided: no reference


def test_the_review_package_is_reproducible_and_bound_to_its_sample(tmp_path):
    m = manifest()
    result = EV.evaluate(m, [E.BASELINE, EVERYTHING_IS_BODY], body_of)
    for name in ("a", "b"):
        EV.review_package(m, result, body_of, tmp_path / name, blind_seed="blind-1")
    assert {p.name: p.read_bytes() for p in (tmp_path / "a" / "cases").iterdir()} == {
        p.name: p.read_bytes() for p in (tmp_path / "b" / "cases").iterdir()}
    with pytest.raises(EV.EvaluationError):
        EV.review_package(manifest(seed="other"), result, body_of, tmp_path / "c", blind_seed="blind-1")


def test_decisions_become_a_reference_only_when_a_reviewer_made_them(tmp_path):
    m = manifest()
    result = EV.evaluate(m, [E.BASELINE], body_of)
    EV.review_package(m, result, body_of, tmp_path / "review", blind_seed="blind-1")
    path = tmp_path / "review" / "cases" / "c5.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    case["decision"].update(state="NOT_AN_ARTICLE", reviewer="test-reviewer")               # a test fixture, not a judgement
    path.write_text(json.dumps(case), encoding="utf-8")
    reference = EV.reference_from_decisions(tmp_path / "review")
    assert list(reference) == ["c5"] and reference["c5"]["state"] == "NOT_AN_ARTICLE"
    case["decision"]["state"] = "LOOKS_FINE"
    path.write_text(json.dumps(case), encoding="utf-8")
    with pytest.raises(EV.EvaluationError):
        EV.reference_from_decisions(tmp_path / "review")


def test_visible_text_of_an_undecodable_source_says_so():
    assert EV.visible_text(b"\x1f\x8b broken", "gzip") == "[source could not be decoded: undecodable_content_encoding]"
    assert EV.visible_text(b"<p>Uno</p><script>x()</script><div>Dos <b>tres</b></div>") == "Uno\nDos tres"
