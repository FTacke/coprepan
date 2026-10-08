"""Wrappers of the classical extractor candidates (CPD-0018): pins, record shape, determinism, blinding.

The tools are not runtime dependencies. The tests that need them run in the environment of the comparison
(extra ``phase3``) and are skipped elsewhere; the tests of the pins and of the refusal run everywhere.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import tomllib
from pathlib import Path

import pytest

from coprepan import extraction, extraction_eval, extractor_candidates as EC

REPO = Path(__file__).resolve().parents[1]
ARMS = list(EC.CANDIDATES.values())
needs_tools = pytest.mark.skipif(not all(EC.available(name) for name in EC.PINS),
                                 reason="the candidate tools are not installed in their pinned versions (extra 'phase3')")

PARAGRAPHS = [
    "El gobierno municipal anunció este jueves un plan de obras para los barrios del norte de la ciudad, que incluye "
    "la reparación de calles, la ampliación del alumbrado y la construcción de dos centros comunitarios durante el próximo año.",
    "Según explicó la alcaldesa en una rueda de prensa, los trabajos comenzarán en enero y se financiarán con fondos propios "
    "y con un préstamo que ya fue aprobado por el concejo, aunque la oposición ha pedido que se publiquen todos los contratos.",
    "Los vecinos consultados por este diario dijeron que esperan desde hace años una solución para las inundaciones que se "
    "producen cada temporada de lluvias, y que no creerán en el plan hasta que vean a las máquinas trabajando en sus calles.",
]
PAGE = ("<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>Plan de obras para el norte | Diario de Prueba</title>"
        "<meta name=\"author\" content=\"Redacción\"></head><body>"
        "<nav><ul><li><a href=\"/\">Portada</a></li><li><a href=\"/politica\">Política</a></li><li><a href=\"/deportes\">Deportes</a></li></ul></nav>"
        "<article><h1>Plan de obras para el norte</h1>" + "".join(f"<p>{text}</p>" for text in PARAGRAPHS) + "</article>"
        "<aside><p><a href=\"/a\">Lea también: otra noticia</a></p></aside>"
        "<footer><p>Diario de Prueba. Todos los derechos reservados.</p></footer></body></html>").encode("utf-8")


def arguments(body: bytes, **changes):
    return {**dict(body_sha256=hashlib.sha256(body).hexdigest(), content_type="text/html", declared_charset="utf-8",
                   content_encoding="identity"), **changes}


def test_the_pins_of_the_wrappers_are_the_pins_of_the_extra_and_nothing_is_a_runtime_dependency():
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == []
    assert sorted(project["optional-dependencies"]["phase3"]) == sorted(f"{name}=={version}" for name, version in EC.PINS.items())
    assert set(EC.DISTRIBUTION_OF) == set(EC.CANDIDATES) and set(EC.DISTRIBUTION_OF.values()) == set(EC.PINS) == set(EC.MAPPING)


def test_no_candidate_is_adopted_or_registered_as_an_extractor_of_the_pipeline():
    assert all(arm.lifecycle == extraction.LIFECYCLE_EXPERIMENTAL for arm in ARMS)
    assert not set(EC.CANDIDATES) & set(extraction.EXTRACTORS)
    for arm in ARMS:
        with pytest.raises(extraction.ExtractorNotActive):
            arm.require_active()


def test_a_wrapper_refuses_without_its_tool_in_the_pinned_version(monkeypatch):
    def other_version(name):
        return "0.0.0"
    monkeypatch.setattr(EC.importlib.metadata, "version", other_version)
    for arm in ARMS:
        assert not EC.available(EC.DISTRIBUTION_OF[arm.stage_version])
        with pytest.raises(EC.CandidateUnavailable):
            arm.run(PAGE, **arguments(PAGE))


def test_a_wrapper_checks_the_body_against_its_digest_before_anything_else():
    for arm in ARMS:
        with pytest.raises(extraction.ExtractionError):
            arm.run(PAGE, **arguments(PAGE, body_sha256="0" * 64))


@needs_tools
@pytest.mark.parametrize("arm", ARMS, ids=lambda arm: arm.name)
def test_a_candidate_gives_a_signed_record_of_the_contracts_shape_and_the_same_answer_twice(arm):
    first, second = arm.run(PAGE, **arguments(PAGE)), arm.run(PAGE, **arguments(PAGE))
    record = first.record
    assert first.payload == second.payload
    assert record["schema"] == extraction.EXTRACTION_SCHEMA and record["extractor"] == {"name": arm.name, "version": arm.version}
    assert record["outcome"] == extraction.OUTCOME_EXTRACTED and record["decoding"]["charset"] == "utf-8"
    tool = EC.DISTRIBUTION_OF[arm.stage_version]
    assert record["candidate"]["tool"] == tool and record["candidate"]["tool_version"] == EC.PINS[tool] and record["candidate"]["mapping"]
    assert [block["index"] for block in record["blocks"]] == list(range(len(record["blocks"])))
    assert all(block["kind"] in extraction.BLOCK_KINDS and block["role"] in extraction.ROLES and block["text"] for block in record["blocks"])
    assert set(record["metadata"]) == set(extraction.METADATA_FIELDS)
    assert all(value["basis"] == extraction.UNKNOWN for value in record["metadata"].values())   # no tool states where a value came from
    body = first.body_text
    assert all(text in body for text in PARAGRAPHS)                    # the article's paragraphs, unchanged
    assert record["body_text_sha256"] == hashlib.sha256(body.encode("utf-8")).hexdigest()


@needs_tools
@pytest.mark.parametrize("arm", ARMS, ids=lambda arm: arm.name)
def test_a_candidate_reads_the_stored_bytes_in_their_content_coding_and_refuses_what_the_baseline_refuses(arm):
    packed = gzip.compress(PAGE, mtime=0)
    plain, coded = arm.run(PAGE, **arguments(PAGE)), arm.run(packed, **arguments(packed, content_encoding="gzip"))
    assert coded.record["blocks"] == plain.record["blocks"] and coded.record["input"]["body_sha256"] != plain.record["input"]["body_sha256"]
    for body, changes in ((b"", {}), (b"%PDF-1.7", {"content_type": "application/pdf"}), (b"\x00\x01", {"content_encoding": "gzip"})):
        ours, theirs = arm.run(body, **arguments(body, **changes)), extraction.BASELINE.run(body, **arguments(body, **changes))
        assert ours.outcome == theirs.outcome == extraction.OUTCOME_NOT_EXTRACTABLE and ours.record["reason"] == theirs.record["reason"]
        assert ours.record["blocks"] == []


@needs_tools
def test_the_blinded_review_package_of_all_arms_names_no_arm_and_decides_nothing(tmp_path):
    cases = [{"case_id": "case-one", "fetch_id": "ft1:" + "0" * 64, "body_sha256": hashlib.sha256(PAGE).hexdigest(), "pack_id": None,
              "outlet_id": "xx_test", "strata": {"outlet": "xx_test"}, "declared_content_type": "text/html", "declared_charset": "utf-8",
              "content_encoding": "identity"}]
    manifest = extraction_eval.sample_manifest(cases, sample_id="test", strata=["outlet"], seed="s", per_stratum=1, frame_description="synthetic")
    arms = [extraction.BASELINE, *ARMS]
    result = extraction_eval.evaluate(manifest, arms, lambda case: PAGE)
    assert {arm["state"] for case in result["cases"] for arm in case["arms"].values()} == {extraction_eval.ARM_OK}
    extraction_eval.review_package(manifest, result, lambda case: PAGE, tmp_path / "package", blind_seed="b")
    case_file = (tmp_path / "package" / "cases" / "case-one.json").read_bytes()
    assert not any(mark in case_file.lower() for mark in (b"trafilatura", b"readability", b"justext", b"baseline_html"))
    case = json.loads(case_file)
    assert sorted(case["candidates"]) == ["A", "B", "C", "D"] and case["decision"]["state"] is None
    key = json.loads((tmp_path / "package" / "blinding_key.json").read_text(encoding="utf-8"))
    assert sorted(key["labels"]["case-one"].values()) == sorted(arm.stage_version for arm in arms)
