"""Human gold independent of the extractors (CPD-0044): the model-independent text view, the gold package (no machine output in
it), events on segment ranges and spans, the freeze (gold without publisher text; nothing accepted after), predictions only against
committed frozen gold, the word alignment, the design-based estimators, the per-outlet holdout draw, the holdout's separation from
development, and the loopback server. Synthetic pages only.
"""

import gzip
import hashlib
import http.client
import json
import math
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from coprepan import docview
from coprepan import gold_review as G
from coprepan import gold_score as GS
from coprepan import survey_stats as SS

REPOSITORY = Path(__file__).resolve().parents[1]
P1 = "La alcaldía anunció este lunes un plan de obras para los barrios del sur de la ciudad, con una inversión de diez millones."
P2 = "Los vecinos pidieron que las obras comiencen antes de fin de año y que se consulte a las juntas de cada barrio afectado."
P3 = "El concejo votará el presupuesto la próxima semana, según informaron fuentes municipales a este diario."
PAGE = (f'<html><head><title>T</title><script>var x = "no";</script></head><body><nav><a href="/">Inicio</a><a href="/d">Deportes</a>'
        f'<a href="/e">Economía</a></nav><main><article><h1>Plan de obras en el sur</h1><p class="lead">Un resumen del plan.</p>'
        f'<p>{P1}</p><figure><img src="x.jpg"><figcaption>Obras en el sur. Foto: EFE</figcaption></figure><p>{P2}</p>'
        f'<div class="ad">Publicidad</div><p>{P3} Por Ana Pérez</p><noscript>Activa JavaScript</noscript>'
        f'<p hidden>Texto oculto del teaser</p><select><option>Autor 1</option><option>Autor 2</option></select></article></main>'
        f'<footer><p>© Diario</p><p>Contacto</p><p>Aviso legal</p></footer></body></html>')


def texts(segs):
    return [s["text"] for s in segs]


# --- docview/1 ------------------------------------------------------------------------------------------------------------------


def test_the_text_view_is_every_body_text_split_at_block_boundaries_only():
    segs = docview.segments(PAGE)
    t = texts(segs)
    # inline links with no white space between them run together -- as the markup and a browser have them; the view adds nothing
    assert t[:3] == ["InicioDeportesEconomía", "Plan de obras en el sur", "Un resumen del plan."]
    assert P1 in t and P2 in t and f"{P3} Por Ana Pérez" in t                       # a credit inside a paragraph stays inside it
    assert "Obras en el sur. Foto: EFE" in t and "Publicidad" in t and "Autor 1 | Autor 2" in t
    assert not any("var x" in s or s == "T" or "JavaScript" in s for s in t)        # script, head and noscript left out
    by = {s["text"]: s for s in segs}
    assert "nav" in by["InicioDeportesEconomía"]["flags"] and by["InicioDeportesEconomía"]["link_share"] == 1.0
    assert "figure" in by["Obras en el sur. Foto: EFE"]["flags"] and "hidden" in by["Texto oculto del teaser"]["flags"]
    assert by["Plan de obras en el sur"]["tag"] == "h1" and "footer" in by["Contacto"]["flags"]
    assert docview.view_sha256(segs) == docview.view_sha256(docview.segments(PAGE))
    assert texts(docview.segments("<html><head><title>x</title><body><p>Uno<br>dos</p></body>")) == ["Uno", "dos"]  # head never closed
    assert texts(docview.segments("<p>a &amp; b&nbsp;c</p>")) == ["a & b c"]


# --- the package ----------------------------------------------------------------------------------------------------------


def build(tmp_path, n=3, kind="HOLDOUT", name="pkg"):
    materials, cases = {}, []
    for i in range(n):
        html = PAGE.replace("Plan de obras en el sur", f"Plan de obras en el sur {i}")
        data = html.encode("utf-8")
        page = {"fetch_id": f"fet_{i:02d}", "outlet_id": f"o{i % 2}", "url": f"https://x.test/{i}", "fetched_at": "2026-11-20T10:00:00Z",
                "body_sha256": hashlib.sha256(data).hexdigest()}
        materials[page["fetch_id"]] = G.case_material("", page, html, country_id="uy")
        cases.append({"fetch_id": page["fetch_id"], "outlet_id": page["outlet_id"], "case_id": f"H{i + 1:03d}", "component": "probability",
                      "stratum": page["outlet_id"], "replicate": 1 + i // 2, "frame_size": 4, "inclusion_probability": 0.5,
                      "weight_documents": 2.0, "weight_outlets": 0.5})
    G.write_package(tmp_path / name, kind=kind, cases=cases, materials=materials, design={"design": "test"}, meta={}, repository=REPOSITORY)
    return G.Package(tmp_path / name)


def test_a_gold_package_holds_no_machine_output_and_is_verified(tmp_path):
    package = build(tmp_path)
    assert package.manifest["predictions"].startswith("none") and package.manifest["codebook"] == G.CODEBOOK
    text = json.dumps(package.cases["H001"], ensure_ascii=False)
    for word in ('"role"', '"selection"', '"core"', "ACCEPT", "REJECT", "body_text", "stratum", "inclusion_probability", "extractor"):
        assert word not in text, word
    assert package.cases["H001"]["stated"]["headline"] is None
    with pytest.raises(G.GoldError, match="outside the repository"):
        G.write_package(REPOSITORY / "tmp_gold_never_written", kind="HOLDOUT", cases=[], materials={}, design={}, meta={}, repository=REPOSITORY)
    with pytest.raises(G.GoldError, match="kind"):
        G.write_package(tmp_path / "other", kind="GOLDISH", cases=[], materials={}, design={}, meta={})
    (tmp_path / "pkg" / "sealed" / "design.json").write_text("{}", encoding="utf-8")
    with pytest.raises(G.GoldError, match="does not match"):
        G.Package(tmp_path / "pkg")


def digest(package, cid, a, b):
    return G._range_digest(package.cases[cid], a, b)


def index_of(package, cid, text):
    return next(s["i"] for s in package.cases[cid]["view"]["segments"] if s["text"] == text)


def annotate(journal, package, cid, *, core="yes", reasons=()):
    """Label the article as body, the headline title, the lead standfirst, the caption caption, the credit a foreign span."""
    a, b = index_of(package, cid, P1), index_of(package, cid, f"{P3} Por Ana Pérez")
    journal.append({"kind": "label_range", "case_id": cid, "payload": {"from": a, "to": b, "digest": digest(package, cid, a, b), "label": "body"}})
    for seg in package.cases[cid]["view"]["segments"]:
        if seg["text"].startswith("Obras en el sur"):
            journal.append({"kind": "label_range", "case_id": cid, "payload": {"from": seg["i"], "to": seg["i"],
                                                                               "digest": digest(package, cid, seg["i"], seg["i"]), "label": "caption"}})
        if seg["text"] == "Publicidad":
            journal.append({"kind": "label_range", "case_id": cid, "payload": {"from": seg["i"], "to": seg["i"],
                                                                               "digest": digest(package, cid, seg["i"], seg["i"]), "label": "foreign"}})
    credit = f"{P3} Por Ana Pérez"
    i = index_of(package, cid, credit)
    journal.append({"kind": "span_add", "case_id": cid, "payload": {"segment": i, "sha256": package.cases[cid]["view"]["segments"][i]["sha256"],
                                                                     "start": len(P3) + 1, "end": len(credit), "label": "foreign"}})
    journal.append({"kind": "source_state", "case_id": cid, "payload": {"value": "complete"}})
    journal.append({"kind": "core", "case_id": cid, "payload": {"value": core, "reasons": list(reasons), "note": ""}})


def test_events_are_checked_against_the_view(tmp_path):
    package = build(tmp_path)
    journal = G.Journal(package)
    bad = [({"kind": "label_range", "case_id": "H001", "payload": {"from": 0, "to": 999, "digest": "x", "label": "body"}}, "range"),
           ({"kind": "label_range", "case_id": "H001", "payload": {"from": 0, "to": 1, "digest": "0" * 64, "label": "body"}}, "digest"),
           ({"kind": "label_range", "case_id": "H001", "payload": {"from": 0, "to": 0, "digest": digest(package, "H001", 0, 0), "label": "maybe"}}, "label"),
           ({"kind": "span_add", "case_id": "H001", "payload": {"segment": 0, "sha256": "x", "start": 0, "end": 1, "label": "body"}}, "digest"),
           ({"kind": "core", "case_id": "H001", "payload": {"value": "no", "reasons": ["boring"]}}, "CORE"),
           ({"kind": "finalize", "case_id": "H001", "payload": {}}, "confirms"),
           ({"kind": "finalize", "case_id": "H001", "payload": {"rest_confirmed": True}}, "not complete"),
           ({"kind": "label_range", "case_id": "H009", "payload": {}}, "not a case")]
    for event, message in bad:
        with pytest.raises(G.GoldError, match=message):
            journal.append(event)
    journal.append({"kind": "core", "case_id": "H001", "payload": {"value": "no", "reasons": [], "note": ""}})
    journal.append({"kind": "source_state", "case_id": "H001", "payload": {"value": "complete"}})
    with pytest.raises(G.GoldError, match="core_reason"):
        journal.append({"kind": "finalize", "case_id": "H001", "payload": {"rest_confirmed": True}})


def test_resolution_spans_and_replay_after_a_restart(tmp_path):
    package = build(tmp_path)
    journal = G.Journal(package)
    annotate(journal, package, "H001")
    journal.append({"kind": "finalize", "case_id": "H001", "payload": {"rest_confirmed": True}})
    with pytest.raises(G.GoldError, match="closed"):
        journal.append({"kind": "comment", "case_id": "H001", "payload": {"text": "x"}})
    with journal.path.open("ab") as handle:
        handle.write(b'{"schema": "gold-body-ev')
    again = G.Journal(G.Package(package.directory))
    assert again.torn == 1 and again.state["H001"]["finalized"] and again.state["H001"]["labels"] == journal.state["H001"]["labels"]
    case = package.cases["H001"]
    resolved = G.resolve(case, again.state["H001"])
    labels = G.char_labels(case, resolved)
    i = index_of(package, "H001", f"{P3} Por Ana Pérez")
    assert labels[i][0] == "body" and labels[i][-1] == "foreign" and labels[0][0] == G.IMPLICIT     # nav unlabelled: implicit
    assert all(e["view_sha256"] == case["view"]["sha256"] and e["body_sha256"] == case["body_sha256"] for e in again.events)


def test_the_freeze_writes_gold_without_text_and_closes_the_package(tmp_path):
    package = build(tmp_path, n=2)
    journal = G.Journal(package)
    annotate(journal, package, "H001")
    journal.append({"kind": "finalize", "case_id": "H001", "payload": {"rest_confirmed": True}})
    with pytest.raises(G.GoldError, match="not closed"):
        G.freeze(package, journal, tmp_path / "gold.json", by="test")
    annotate(journal, package, "H002", core="no", reasons=["too_short"])
    journal.append({"kind": "finalize", "case_id": "H002", "payload": {"rest_confirmed": True}})
    marker = G.freeze(package, journal, tmp_path / "gold.json", by="test")
    data = (tmp_path / "gold.json").read_text(encoding="utf-8")
    for fragment in (P1[:40], P2[:40], "Publicidad", "Inicio"):
        assert fragment not in data                                         # no publisher text in the gold
    gold = G.load_gold(package, tmp_path / "gold.json")
    assert gold["schema"] == G.GOLD_SCHEMA and marker["gold_sha256"] == hashlib.sha256((tmp_path / "gold.json").read_bytes()).hexdigest()
    with pytest.raises(G.GoldError, match="frozen"):
        G.Journal(package).append({"kind": "comment", "case_id": "H001", "payload": {"text": "late"}})
    (tmp_path / "other.json").write_text(data.replace("test", "tset"), encoding="utf-8")
    with pytest.raises(G.GoldError, match="not the gold"):
        G.load_gold(package, tmp_path / "other.json")
    practice = build(tmp_path, n=1, kind="PRACTICE", name="practice")
    with pytest.raises(G.GoldError, match="practice"):
        G.freeze(practice, G.Journal(practice), tmp_path / "p.json", by="test")


# --- alignment and scoring --------------------------------------------------------------------------------------------


def test_the_machine_body_is_aligned_word_by_word_to_the_gold(tmp_path):
    package = build(tmp_path, n=2)
    journal = G.Journal(package)
    annotate(journal, package, "H001")
    gold_case = {"resolved": G.resolve(package.cases["H001"], journal.state["H001"])}
    case = package.cases["H001"]
    words = lambda s: len(GS._TOKEN.findall(s))  # noqa: E731
    perfect = GS.case_metrics(case, gold_case, [P1, P2, P3])
    assert perfect["gold_body_words"] == perfect["included_body_words"] == words(P1) + words(P2) + words(P3)
    assert perfect["missed_spans"] == 0 and perfect["contamination_words"] == 0 and perfect["unaligned_machine_words"] == 0
    noisy = GS.case_metrics(case, gold_case, ["Un resumen del plan.", P1, "Publicidad", f"{P3} Por Ana Pérez", "texto que no está en la página"])
    assert noisy["missed_spans"] == 1 and noisy["missed_body_words"] == noisy["missed_span_words"] == words(P2)
    # "Publicidad" (1) and the credit span "Por Ana Pérez" (3) are foreign; the lead (4) was left unlabelled: implicit foreign
    assert noisy["included_by_label"] == {"foreign": 4, G.IMPLICIT: 4} and noisy["contamination_words"] == 8
    assert noisy["unaligned_machine_words"] == words("texto que no está en la página") == 7


def test_scores_need_the_frozen_gold_and_give_design_estimates(tmp_path):
    package = build(tmp_path, n=4)
    journal = G.Journal(package)
    for cid in package.case_ids:
        annotate(journal, package, cid, core="yes")
        journal.append({"kind": "finalize", "case_id": cid, "payload": {"rest_confirmed": True}})
    G.freeze(package, journal, tmp_path / "gold.json", by="test")
    gold = G.load_gold(package, tmp_path / "gold.json")
    base = {"core": "ACCEPT", "core_reasons": []}
    cases = {}
    for k, cid in enumerate(package.case_ids):
        cases[cid] = {"candidate": {**base, "body_blocks": [P1, P2, P3]},
                      "baseline": {**base, "body_blocks": [P1, "Publicidad", P3] if k % 2 else [P1, P2, P3, "Publicidad"]},
                      "predecessor": {**base, "body_blocks": [P1, P2, P3]}}
    with pytest.raises(G.GoldError, match="not made against"):
        GS.score(package, gold, {"gold_sha256": "0" * 64, "cases": cases})
    result = GS.score(package, gold, {"gold_sha256": package.frozen["gold_sha256"], "cases": cases})
    est = result["estimates"]["documents"]
    assert est["candidate"]["word_recall"]["estimate"] == 1.0 and est["candidate"]["cases_with_contamination"]["estimate"] == 0.0
    assert est["baseline"]["cases_with_contamination"]["estimate"] == 1.0
    assert est["candidate_minus_baseline"]["word_recall"]["estimate"] > 0
    assert set(result["estimates"]) == {"documents", "outlets"} and result["counts"]["probability"]["cases"] == 4
    assert est["variance_design"] == "outlet strata / documents" and est["candidate"]["word_recall"]["n"] == 4


def test_a_freeze_of_replicate_one_is_weighted_as_one_document_per_outlet(tmp_path):
    package = build(tmp_path, n=4)                       # outlets o0, o1; replicate 1 = H001, H002
    journal = G.Journal(package)
    for cid in ("H001", "H002"):
        annotate(journal, package, cid)
        journal.append({"kind": "finalize", "case_id": cid, "payload": {"rest_confirmed": True}})
    with pytest.raises(G.GoldError, match="not closed"):
        G.freeze(package, journal, tmp_path / "all.json", by="test")
    G.freeze(package, journal, tmp_path / "r1.json", by="test", case_ids=["H001", "H002"], scope="replicates 1..1")
    gold = G.load_gold(package, tmp_path / "r1.json")
    assert gold["scope"] == {"label": "replicates 1..1", "cases": 2, "of": 4} and len(gold["cases"]) == 2
    with pytest.raises(G.GoldError, match="frozen"):
        G.Journal(package).append({"kind": "comment", "case_id": "H003", "payload": {"text": "after"}})
    blocks = {"core": "ACCEPT", "core_reasons": [], "body_blocks": [P1, P2, P3]}
    result = GS.score(package, gold, {"gold_sha256": package.frozen["gold_sha256"],
                                      "cases": {c: {n: blocks for n in GS.SYSTEMS} for c in ("H001", "H002")}})
    est = result["estimates"]["documents"]
    assert est["variance_design"].startswith("collapsed") and est["variance_units"] == 2
    assert result["per_case"][0]["component"] == "probability"


# --- the estimators -------------------------------------------------------------------------------------------------------


def test_the_ratio_estimator_and_its_variance():
    # equal weights, one stratum, units as clusters: the variance is the classical with-replacement variance of a mean
    y = [1.0, 0.0, 1.0, 1.0]
    out = SS.proportion(y, weights=[1.0] * 4)
    p = 0.75
    assert out["estimate"] == p and math.isclose(out["se"], math.sqrt(sum((v - p) ** 2 for v in y) / (4 * 3)), rel_tol=1e-4)
    assert out["k"] == 3 and out["interval"][0] < p < out["interval"][1]
    zero = SS.proportion([0.0] * 50, weights=[2.0] * 50)
    assert zero["estimate"] == 0 and zero["n_eff"] == 50 and "design effect" in zero["note"] and zero["interval"][1] < 0.08
    weighted = SS.proportion([1.0, 0.0], weights=[3.0, 1.0], strata=["a", "b"])
    assert weighted["estimate"] == 0.75 and weighted["singleton_strata"] == ["a", "b"]
    words = SS.ratio([90, 10], [100, 100], weights=[1.0, 1.0])
    assert words["estimate"] == 0.5 and words["df"] == 1 and words["interval"] is not None
    # paired: the shared noise cancels -- a constant difference of 0.1 over very different units has no variance
    diff = SS.ratio_difference([9, 4, 10, 2], [10] * 4, [8, 3, 9, 1], [10] * 4, weights=[1.0] * 4)
    assert math.isclose(diff["estimate"], 0.1) and diff["se"] == 0 and diff["interval"] == [0.1, 0.1]
    unpaired_se = SS.ratio([9, 4, 10, 2], [10] * 4, weights=[1.0] * 4)["se"]
    assert unpaired_se > 0.1
    with pytest.raises(ValueError):
        SS.design_from_cases([{"case_id": "x"}])


def test_the_holdout_draw_is_per_outlet_seeded_and_carries_both_weights():
    frame = [{"fetch_id": f"f{i:03d}", "outlet_id": "a" if i < 10 else ("b" if i < 13 else "c")} for i in range(14)]
    cases = G.draw_per_outlet(frame, per_outlet=2, seed=3)
    assert cases == G.draw_per_outlet(frame, per_outlet=2, seed=3) and len(cases) == 5
    a = [c for c in cases if c["outlet_id"] == "a"]
    assert len(a) == 2 and a[0]["inclusion_probability"] == 0.2 and a[0]["weight_documents"] == 5.0 and a[0]["weight_outlets"] == 0.5
    c = [x for x in cases if x["outlet_id"] == "c"]
    assert len(c) == 1 and c[0]["inclusion_probability"] == 1.0 and c[0]["weight_outlets"] == 1.0
    assert [x["case_id"] for x in cases] == ["H001", "H002", "H003", "H004", "H005"]
    assert [x["replicate"] for x in cases] == [1, 1, 1, 2, 2]                          # one per outlet first, a sample on its own
    assert {x["outlet_id"] for x in cases[:3]} == {"a", "b", "c"}


# --- the holdout's separation from development ------------------------------------------------------------------------------


def test_development_never_reads_a_holdout_run(tmp_path, monkeypatch):
    import sys

    import coprepan.validation_holdout as V
    monkeypatch.syspath_prepend(str(REPOSITORY / "scripts"))
    import study_phase3_metadata as S3
    assert str(REPOSITORY / "scripts") in sys.path

    assert V.holdout_runs() == frozenset() or isinstance(V.holdout_runs(), frozenset)
    cache = tmp_path / "pages.jsonl.gz"
    with gzip.open(cache, "wt", encoding="utf-8") as h:
        h.write(json.dumps({"fetch_id": "f1", "run_id": "dev-run", "body_b64": ""}) + "\n")
        h.write(json.dumps({"fetch_id": "f2", "run_id": "val-run", "body_b64": ""}) + "\n")
    monkeypatch.setattr(V, "holdout_runs", lambda root=None: frozenset({"val-run"}))
    with pytest.raises(SystemExit, match="holdout"):
        list(S3.stored_pages(SimpleNamespace(page_cache=cache)))
    assert [p["fetch_id"] for p, _ in S3.stored_pages(SimpleNamespace(page_cache=cache, include_holdout=True))] == ["f1", "f2"]
    (tmp_path / "config" / "validation").mkdir(parents=True)
    (tmp_path / "config" / "validation" / "holdout_runs.json").write_text('{"schema": "other", "runs": []}', encoding="utf-8")
    monkeypatch.undo()
    with pytest.raises(V.HoldoutError):
        V.holdout_runs(tmp_path)
    with pytest.raises(V.HoldoutError):
        V.holdout_runs(tmp_path / "nowhere")


# --- the server ------------------------------------------------------------------------------------------------------------


def request(port, method, path, body=None, host=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if data:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=data, headers=headers)
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, dict(response.getheaders()), payload


def test_the_server_serves_the_view_and_has_no_machine_or_design_endpoint(tmp_path):
    package = build(tmp_path, n=1)
    server = G.make_server(package, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        assert request(port, "GET", "/")[0] == 200
        info = json.loads(request(port, "GET", "/api/package")[2])
        assert info["kind"] == "HOLDOUT" and info["vocabulary"]["labels"] == list(G.LABELS) and not info["frozen"]
        case = json.loads(request(port, "GET", "/api/case/H001")[2])
        assert case["view"]["version"] == docview.VERSION
        for path in ("/api/case/H001/machine", "/sealed/design.json", "/api/design", "/api/case/H001/../../sealed/design.json"):
            assert request(port, "GET", path)[0] == 404
        status, headers, body = request(port, "GET", "/api/case/H001/source")
        assert headers["Content-Security-Policy"].startswith("default-src 'none'") and b"<script" not in body
        ok = request(port, "POST", "/api/event", {"kind": "source_state", "case_id": "H001", "payload": {"value": "complete"}})
        assert ok[0] == 200
        assert request(port, "POST", "/api/event", {"kind": "core", "case_id": "H001", "payload": {"value": "perhaps"}})[0] == 409
        assert request(port, "GET", "/api/state", host="evil.test")[0] == 403
    finally:
        server.shutdown()
        server.server_close()
    with pytest.raises(G.GoldError, match="loopback"):
        G.make_server(package, host="0.0.0.0", port=0)
