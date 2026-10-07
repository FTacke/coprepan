"""Extraction contract and the baseline extractor.

These tests pin *behaviour of the contract* (determinism, typed blocks, basis-carrying metadata,
labels instead of deletion). They do not measure extraction quality: the baseline extractor is not
validated and not adopted.
"""

import hashlib
import json
from pathlib import Path

import pytest

from coprepan import extraction as E

FIXTURES = Path(__file__).parent / "fixtures" / "canary"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(body: bytes, content_type="text/html", charset="unknown"):
    return E.extract(body, body_sha256=sha(body), content_type=content_type, declared_charset=charset)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def texts(result, role=None, kind=None):
    return [b["text"] for b in result.record["blocks"]
            if (role is None or b["role"] == role) and (kind is None or b["kind"] == kind)]


V1 = run(fixture("nota_v1.html"))


# --- contract -------------------------------------------------------------------------------------


def test_record_names_its_input_and_its_extractor_and_nothing_volatile():
    record = V1.record
    assert record["schema"] == "coprepan-extraction/v1" and record["outcome"] == "EXTRACTED"
    assert record["extractor"] == {"name": "baseline_html", "version": "0.1.0"}
    assert record["input"]["body_sha256"] == sha(fixture("nota_v1.html"))
    assert set(record) == {"schema", "extractor", "input", "outcome", "reason", "decoding", "metadata", "blocks",
                           "extracted_text_sha256", "body_text_sha256"}  # no timestamp, no path, no run id
    assert json.loads(V1.payload) == record


def test_extraction_is_deterministic():
    again = run(fixture("nota_v1.html"))
    assert again.payload == V1.payload and again.extracted_text_sha256 == V1.extracted_text_sha256


def test_the_digests_cover_what_they_name():
    blocks = V1.record["blocks"]
    expected = json.dumps([[b["kind"], b["role"], b["text"]] for b in blocks], sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert V1.extracted_text_sha256 == sha(expected)
    assert V1.body_text_sha256 == sha("\n\n".join(texts(V1, role="body")).encode("utf-8"))


def test_the_body_offered_must_be_the_body_named():
    with pytest.raises(E.ExtractionError):
        E.extract(b"<html></html>", body_sha256=sha(b"other"), content_type="text/html")
    with pytest.raises(E.ExtractionError):
        E.extract("<html></html>", body_sha256=sha(b""), content_type="text/html")
    with pytest.raises(E.ExtractionError):
        E.extract(b"x", body_sha256=sha(b"x"), content_type="")


# --- structure: TITLE, BODY, and what is kept beside them ------------------------------------------


def test_title_and_body_are_separate():
    assert texts(V1, role="title") == ["El crecimiento del puerto obliga a separar cargas"]
    body = texts(V1, role="body")
    assert body[0].startswith("Montevideo. El crecimiento sostenido") and "El crecimiento del puerto" not in V1.body_text
    assert [b["kind"] for b in V1.record["blocks"] if b["role"] == "body"] == [
        "paragraph", "paragraph", "heading", "paragraph", "list_item", "list_item", "quote_block", "paragraph"]
    assert [b["index"] for b in V1.record["blocks"]] == list(range(len(V1.record["blocks"])))


def test_no_paragraph_is_dropped_for_being_short_or_for_a_substring():
    body = V1.body_text
    assert "Fue ayer." in body                                        # no minimum length
    assert "preparar el muelle" in body and "reparar parte" in body   # the legacy filter cut every "…epa…"
    assert "Suscribite al boletín portuario" in body                  # prose is not paywall boilerplate
    assert "crecimiento sostenido" in body and "atención al cronograma" in body  # no word is split or merged
    assert "Dos turnos nuevos de descarga." in body and "Queremos que cada carga" in body  # lists and quotes are text


def test_non_body_blocks_are_kept_and_typed_not_deleted():
    non_body = texts(V1, role="non_body")
    assert "Foto: archivo del diario. Grúas en la terminal." in texts(V1, kind="caption")
    assert "Lea también: el dragado del canal de acceso." in non_body
    assert "© 2026 Diario Ejemplo. Todos los derechos reservados." in non_body
    assert "Diario Ejemplo — edición digital" in non_body and "Portada" in non_body
    for text in non_body:
        assert text not in V1.body_text


def test_scripts_are_not_text():
    assert not any("esto no es texto" in text or "tracking" in text for text in texts(V1))


def test_text_outside_block_elements_is_kept_as_unstructured_text():
    result = run(fixture("sin_metadatos.html"), content_type="unknown")
    assert texts(result, kind="unstructured_text") == [
        "Breve sin metadatos", "Texto suelto que no está en ningún párrafo y que no debe perderse."]
    assert texts(result, kind="paragraph") == ["Un único párrafo con énfasis y un enlace. Sigue en la misma oración."]
    assert texts(result, role="title") == [] and set(b["role"] for b in result.record["blocks"]) == {"body"}


def test_nested_and_unclosed_markup_loses_no_text():
    html = ("<html><body><article><p>Uno<p>Dos sin cerrar<blockquote><p>Cita interna</p> resto de la cita"
            "</blockquote><ul><li>Punto <em>uno</em><li>Punto dos</ul>cola<br>final</article></body></html>").encode()
    assert texts(run(html)) == ["Uno", "Dos sin cerrar", "Cita interna", "resto de la cita", "Punto uno", "Punto dos",
                                "cola final"]


# --- metadata with basis ----------------------------------------------------------------------------


def test_metadata_carries_value_basis_and_every_candidate():
    meta = V1.record["metadata"]
    assert set(meta) == set(E.METADATA_FIELDS)
    assert meta["title"]["value"] == "El crecimiento del puerto obliga a separar cargas" and meta["title"]["basis"] == "json_ld"
    assert [c["basis"] for c in meta["title"]["candidates"]] == ["json_ld", "open_graph", "html_h1", "html_title"]
    assert meta["title"]["candidates"][1]["value"].endswith("• Diario Ejemplo")  # kept as published, not "cleaned"
    assert meta["author"] == {"value": "Ana Pérez", "basis": "json_ld", "candidates": [
        {"value": "Ana Pérez", "basis": "json_ld"}, {"value": "Redacción Ejemplo", "basis": "html_meta"}]}
    assert meta["section"]["value"] == "Economía" and meta["language"] == {
        "value": "es-UY", "basis": "html_lang", "candidates": [{"value": "es-UY", "basis": "html_lang"}]}


def test_dates_are_stored_as_published_and_never_invented():
    meta = V1.record["metadata"]
    assert meta["publication_date"]["value"] == "2026-10-05T08:30:00-03:00"  # offset kept, nothing converted
    assert meta["modification_date"]["value"] == "2026-10-05T09:10:00-03:00"
    bare = run(fixture("sin_metadatos.html"), content_type="unknown").record["metadata"]
    for field in E.METADATA_FIELDS:
        assert bare[field] == {"value": "unknown", "basis": "unknown", "candidates": []}  # no default language, no crawl date


def test_broken_json_ld_breaks_nothing():
    html = ('<html><head><script type="application/ld+json">{not json</script>'
            '<script type="application/ld+json">{"@graph": [{"headline": "Desde el grafo", "author": "Agencia X"}]}</script>'
            "</head><body><p>Texto.</p></body></html>").encode()
    meta = run(html).record["metadata"]
    assert (meta["title"]["value"], meta["author"]["value"]) == ("Desde el grafo", "Agencia X")


# --- content types and decoding ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, content_type, reason",
    [(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj", "application/pdf", "unsupported_content_type"),
     (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg", "unsupported_content_type"),
     (b'{"a": 1}', "application/json", "unsupported_content_type"),
     (b"%PDF-1.7 no header", "unknown", "content_type_unknown_and_not_html"),
     (b"", "text/html", "empty_body")],
)
def test_what_cannot_be_extracted_is_labelled_not_guessed(body, content_type, reason):
    result = run(body, content_type=content_type)
    assert (result.outcome, result.record["reason"]) == ("NOT_EXTRACTABLE", reason)
    assert result.record["blocks"] == [] and result.record["input"]["body_sha256"] == sha(body)


def test_a_missing_content_type_is_sniffed_only_for_html():
    assert run(b"\xef\xbb\xbf  <!-- c --> <!DOCTYPE html><html><body><p>Hola</p></body></html>", content_type="unknown").outcome == "EXTRACTED"
    assert run(b"<?xml version='1.0'?><rss></rss>", content_type="unknown").outcome == "NOT_EXTRACTABLE"


def test_decoding_follows_bom_then_header_then_markup_then_utf8():
    text = "<html><head>{meta}</head><body><p>Año, niño, «cita»</p></body></html>"
    latin = text.format(meta='<meta charset="iso-8859-1">').encode("latin-1")
    from_markup = run(latin)
    assert texts(from_markup) == ["Año, niño, «cita»"]
    assert from_markup.record["decoding"] == {"charset": "iso8859-1", "basis": "html_meta", "replaced_characters": 0}
    from_header = run(text.format(meta="").encode("latin-1"), charset="iso-8859-1")
    assert texts(from_header) == ["Año, niño, «cita»"] and from_header.record["decoding"]["basis"] == "http_header"
    assert run(b"\xef\xbb\xbf" + text.format(meta="").encode("utf-8"), charset="iso-8859-1").record["decoding"]["basis"] == "byte_order_mark"
    assert run(text.format(meta="").encode("utf-8")).record["decoding"]["basis"] == "default_utf8"


def test_undecodable_bytes_are_counted_not_hidden():
    wrong = "<html><body><p>Año</p></body></html>".encode("latin-1")  # latin-1 bytes, nothing declared
    decoding = run(wrong).record["decoding"]
    assert decoding["basis"] == "default_utf8" and decoding["replaced_characters"] == 1
    assert run(wrong, charset="no-such-charset").record["decoding"]["basis"] == "default_utf8_after_unknown_declared_charset"


def test_charset_is_read_from_the_content_type_header():
    assert E.declared_charset_of([["Content-Type", 'text/html; charset="ISO-8859-1"']]) == "iso-8859-1"
    assert E.declared_charset_of([["content-type", "text/html"]]) == "unknown" == E.declared_charset_of([])


# --- versions ---------------------------------------------------------------------------------------


def test_a_changed_body_is_a_new_text_and_the_same_body_elsewhere_is_the_same_body_text():
    v2, republished = run(fixture("nota_v2.html")), run(fixture("nota_republicada.html"))
    assert v2.extracted_text_sha256 != V1.extracted_text_sha256 and v2.body_text_sha256 != V1.body_text_sha256
    assert republished.body_text_sha256 == v2.body_text_sha256          # same BODY under another title and chrome
    assert republished.extracted_text_sha256 != v2.extracted_text_sha256  # but not the same textual state


def test_an_extractor_must_sign_its_own_records():
    imposter = E.Extractor("other_extractor", "9.9.9", E.extract)
    body = fixture("nota_v1.html")
    with pytest.raises(E.ExtractionError):
        imposter.run(body, body_sha256=sha(body), content_type="text/html")
    assert E.BASELINE.run(body, body_sha256=sha(body), content_type="text/html").payload == V1.payload
    assert E.BASELINE.stage_version == "baseline_html/0.1.0"
