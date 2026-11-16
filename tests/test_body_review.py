"""The local BODY reviewer (CPD-0043): the inert source page, the frozen package, the blind case, the event log and its
replay, the gate on the machine labels, export, validation and scoring -- and the loopback server, exercised over a literal
loopback address it started itself. Synthetic pages only; no publisher material.
"""

import hashlib
import http.client
import json
import threading
from pathlib import Path

import pytest

from coprepan import body_review as R
from coprepan import extraction as E
from coprepan import extraction_body as B
from test_body_quality import HEADLINE, TEXT
from test_phase3_metadata import ld

REPOSITORY = Path(__file__).resolve().parents[1]
NAV = "<nav><a href='/'>Inicio</a> <a href='/deportes'>Deportes</a></nav>"


def html_page(n, extra=""):
    return (f'<html lang="es"><head>{ld(headline=HEADLINE + f" {n}")}<script>alert(1)</script></head><body>{NAV}<main><article>'
            f'<h1>{HEADLINE} {n}</h1><div class="cuerpo">{TEXT}<p>Párrafo propio número {n} del artículo con texto suficiente '
            f'para ser un bloque.</p></div><div class="related"><p>Noticia relacionada con otro asunto del día número {n}</p></div>'
            f'{extra}</article></main></body></html>')


def build(tmp_path, n=3, name="pkg"):
    materials, cases = {}, []
    for i in range(n):
        html = html_page(i)
        data = html.encode("utf-8")
        page = {"fetch_id": f"fet_{i:02d}" + "0" * 20, "outlet_id": "uy_test", "url": f"https://x.test/{i}", "fetched_at":
                "2026-10-10T10:00:00+00:00", "body_sha256": hashlib.sha256(data).hexdigest()}
        x = B.ARTICLE_4_2.function(data, body_sha256=page["body_sha256"], content_type="text/html", templates=frozenset())
        case, machine = R.case_material("", page, x.record, country_id="uy", extractor="article_html/0.4.2")
        machine.update({"core": {"ruleset": "content-quality/4", "decision": "ACCEPT" if i else "REJECT", "reasons": [] if i else ["too_short"]},
                        "body_quality": "clean", "words": 300})
        materials[page["fetch_id"]] = (case, machine, R.sanitize(html))
        cases.append({"fetch_id": page["fetch_id"], "component": "random" if i < 2 else "targeted",
                      "stratum": "country:uy" if i < 2 else "near_threshold_120_180_words",
                      "inclusion_probability": 0.5 if i < 2 else None, "case_id": f"P{i + 1:03d}"})
    manifest = R.write_package(tmp_path / name, cases=cases, materials=materials, meta={"versions": {"extractor": "article_html/0.4.2"}},
                               repository=REPOSITORY)
    return R.Package(tmp_path / name), manifest


def answer_all(journal, case, *, foreign=(), core="yes", completeness=("complete",)):
    for b in case["blocks"]:
        journal.append({"kind": "label_block", "case_id": case["case_id"],
                        "payload": {"index": b["index"], "text_sha256": b["text_sha256"],
                                    "label": "foreign" if b["index"] in foreign else "article"}})
    if case["title_blocks"]:
        journal.append({"kind": "title", "case_id": case["case_id"], "payload": {"label": "correct"}})
    journal.append({"kind": "completeness", "case_id": case["case_id"], "payload": {"values": list(completeness)}})
    journal.append({"kind": "core", "case_id": case["case_id"], "payload": {"value": core, "reason": "" if core == "yes" else "breve"}})


# --- the inert page -------------------------------------------------------------------------------------------------------------


def test_the_source_page_is_inert():
    hostile = ('<html><head><meta http-equiv="refresh" content="0;url=https://evil.test"><base href="https://evil.test/">'
               '<link rel="stylesheet" href="https://cdn.test/a.css"><script src="https://evil.test/x.js"></script>'
               '<style>.a{color:red} .b{background:url(https://t.test/p.gif)}</style></head>'
               '<body onload="steal()"><iframe src="https://ads.test"></iframe><iframe/><p class="a" onclick="x()" style="color:blue">'
               'Texto <a href="https://evil.test" target="_blank" ping="https://t.test">enlace</a> &lt;b&gt;</p>'
               '<img src="https://t.test/pixel.gif" srcset="a.jpg 1x" alt="Foto del acto" onerror="x()">'
               '<svg><script>alert(1)</script><text>svg</text></svg><form action="https://evil.test"><input name="q">'
               '<button formaction="https://evil.test">Enviar</button><p>Dentro del formulario</p></form>'
               '<object data="x.swf"></object><embed src="x"><noscript><img src="https://t.test/n.gif"></noscript>'
               '<p style="background-image:url(https://t.test/bg.png)">Fondo</p><style/><p>Después</p></body></html>')
    out = R.sanitize(hostile)
    low = out.lower()
    for bad in ("<script", "onload", "onclick", "onerror", "href=", "src=", "srcset", "ping=", "<iframe", "<object", "<embed",
                "<form", "<input", "<button", "<svg", "<base", "<link", "refresh", "https://", "formaction", "target="):
        assert bad not in low, bad
    assert "Texto" in out and "enlace" in out and "&lt;b&gt;" in out and "[Bild: Foto del acto]" in out
    assert "Dentro del formulario" in out and "Después" in out and "Fondo" in out          # text survives; a self-closed tag hides nothing
    assert R.SOURCE_CSP in out and "default-src 'none'" in R.SOURCE_CSP
    assert ".a{color:red}" not in out                                # a style block that loads anything is dropped whole


# --- the package ----------------------------------------------------------------------------------------------------------------


def test_a_package_is_written_once_outside_the_repository_and_verified_file_by_file(tmp_path):
    package, manifest = build(tmp_path)
    assert manifest["schema"] == R.PACKAGE_SCHEMA and len(manifest["package_id"]) == 24 and set(package.case_ids) == {"P001", "P002", "P003"}
    with pytest.raises(R.ReviewError, match="not empty"):
        R.write_package(tmp_path / "pkg", cases=[], materials={}, meta={}, repository=REPOSITORY)
    with pytest.raises(R.ReviewError, match="outside the repository"):
        R.write_package(REPOSITORY / "tmp_review_package_never_written", cases=[], materials={}, meta={}, repository=REPOSITORY)
    case_file = tmp_path / "pkg" / "cases" / "P002" / "case.json"
    case_file.write_text(case_file.read_text(encoding="utf-8").replace("Párrafo", "Parrafo"), encoding="utf-8")
    with pytest.raises(R.ReviewError, match="does not match the frozen package"):
        R.Package(tmp_path / "pkg")


def test_the_case_shows_no_machine_role_and_the_key_holds_them(tmp_path):
    package, _ = build(tmp_path)
    case = package.cases["P001"]
    text = json.dumps(case, ensure_ascii=False)
    for word in ('"role"', '"selection"', '"reason"', "body_text", "stratum", "inclusion_probability", '"core"', "ACCEPT"):
        assert word not in text, word
    shown = {b["text"] for b in case["blocks"]}
    assert any(t.startswith("Párrafo propio") for t in shown) and any(t.startswith("Noticia relacionada") for t in shown)
    key = package.key()["P001"]
    assert set(key["machine"]["blocks"]) == {str(b["index"]) for b in case["blocks"]}
    related = next(b for b in case["blocks"] if b["text"].startswith("Noticia relacionada"))
    assert key["machine"]["blocks"][str(related["index"])]["role"] == E.ROLE_NON_BODY      # the machine kept it out: hidden from the case


def test_the_draw_is_stratified_seeded_and_says_nothing_through_the_case_numbers():
    rows = [{"fetch_id": f"f{i:03d}", "country_id": "ar" if i < 60 else "uy", "words": i} for i in range(100)]
    strata = {"short": lambda r: r["words"] < 30, "long": lambda r: r["words"] >= 90}
    a = R.draw(rows, random_n=10, targeted={"short": 2, "long": 3}, strata=strata, seed=5)
    assert a == R.draw(rows, random_n=10, targeted={"short": 2, "long": 3}, strata=strata, seed=5)
    rnd = [c for c in a if c["component"] == "random"]
    assert len(rnd) == 10 and sum(1 for c in rnd if c["stratum"] == "country:ar") == 6
    assert {c["inclusion_probability"] for c in rnd} == {0.1}
    tg = [c for c in a if c["component"] == "targeted"]
    assert len(tg) == 5 and not {c["fetch_id"] for c in tg} & {c["fetch_id"] for c in rnd}
    assert [c["case_id"] for c in a] == [f"P{n:03d}" for n in range(1, 16)]
    assert [c["component"] for c in a] != sorted(c["component"] for c in a)                 # shuffled


# --- events, replay, the gate ------------------------------------------------------------------------------------------------


def test_events_are_checked_against_the_case(tmp_path):
    package, _ = build(tmp_path)
    journal = R.Journal(package)
    b = package.cases["P001"]["blocks"][0]
    bad = [({"kind": "label_block", "case_id": "P009", "payload": {}}, "not a case"),
           ({"kind": "label_block", "case_id": "P001", "payload": {"index": 999, "text_sha256": "x", "label": "article"}}, "not one the case shows"),
           ({"kind": "label_block", "case_id": "P001", "payload": {"index": b["index"], "text_sha256": "0" * 64, "label": "article"}}, "digest"),
           ({"kind": "label_block", "case_id": "P001", "payload": {"index": b["index"], "text_sha256": b["text_sha256"], "label": "maybe"}}, "label"),
           ({"kind": "completeness", "case_id": "P001", "payload": {"values": ["complete", "end_missing"]}}, "stand alone"),
           ({"kind": "core", "case_id": "P001", "payload": {"value": "perhaps"}}, "CORE"),
           ({"kind": "reveal", "case_id": "P001", "payload": {}}, None),
           ({"kind": "finalize", "case_id": "P001", "payload": {}}, "not complete")]
    for event, message in bad:
        if message is None:
            with pytest.raises(R.ReviewError):
                R.check_event(package, event)
            continue
        with pytest.raises(R.ReviewError, match=message):
            journal.append(event)


def test_answers_replay_after_a_restart_and_a_torn_last_line_is_left_out(tmp_path):
    package, _ = build(tmp_path)
    journal = R.Journal(package)
    case = package.cases["P002"]
    answer_all(journal, case, foreign={case["blocks"][-1]["index"]})
    journal.append({"kind": "missing_add", "case_id": "P002", "payload": {"quote": "Un párrafo que falta.", "view": "original",
                                                                         "part": "end_missing"}})
    journal.append({"kind": "finalize", "case_id": "P002", "payload": {}})
    with pytest.raises(R.ReviewError, match="closed"):
        answer_all(journal, case)
    with journal.path.open("ab") as handle:
        handle.write(b'{"schema": "coprepan-body-review-ev')                 # an interrupted write
    again = R.Journal(R.Package(package.directory))
    assert again.torn == 1 and again.state["P002"]["finalized"] and again.state["P002"]["open_items"] == []
    assert again.state["P002"]["blocks"] == journal.state["P002"]["blocks"] and len(again.state["P002"]["missing"]) == 1
    assert all(e["fetch_id"] == case["fetch_id"] and e["body_sha256"] == case["body_sha256"] and e["extractor"] == "article_html/0.4.2"
               for e in again.events)


def test_a_case_changed_after_its_machine_labels_were_shown_is_not_blind(tmp_path):
    package, _ = build(tmp_path)
    journal = R.Journal(package)
    case = package.cases["P001"]
    answer_all(journal, case)
    journal.append({"kind": "finalize", "case_id": "P001", "payload": {}})
    journal.append({"kind": "reveal", "case_id": "P001"})
    assert not journal.state["P001"]["revised_after_reveal"]
    journal.append({"kind": "reopen", "case_id": "P001", "payload": {}})
    journal.append({"kind": "core", "case_id": "P001", "payload": {"value": "no", "reason": "un teaser"}})
    journal.append({"kind": "finalize", "case_id": "P001", "payload": {}})
    data = R.export(package, journal)
    assert data["cases"][0]["revised_after_reveal"] and not data["cases"][0]["blind"]
    assert R.score(package, data)["cases_left_out"] == ["P001"]
    assert R.score(package, data, include_not_blind=True)["components"]["random"]["cases"] == 1


# --- export and scoring ------------------------------------------------------------------------------------------------


def test_the_export_validates_and_the_score_separates_the_five_classes(tmp_path):
    package, _ = build(tmp_path)
    journal = R.Journal(package)
    key = package.key()
    c1 = package.cases["P001"]                                       # machine REJECT; the reviewer says yes: a false reject
    related = next(b["index"] for b in c1["blocks"] if b["text"].startswith("Noticia relacionada"))
    own = next(b["index"] for b in c1["blocks"] if b["text"].startswith("Párrafo propio"))
    assert key["P001"]["machine"]["blocks"][str(own)]["role"] == E.ROLE_BODY
    outside = {int(i) for i, m in key["P001"]["machine"]["blocks"].items() if m["role"] != E.ROLE_BODY}
    answer_all(journal, c1, foreign=outside | {own}, core="yes")    # a BODY block judged foreign: residue
    journal.append({"kind": "label_block", "case_id": "P001", "payload": {"index": related, "text_sha256":
                    next(b["text_sha256"] for b in c1["blocks"] if b["index"] == related), "label": "article"}})   # a false deletion
    journal.append({"kind": "missing_add", "case_id": "P001", "payload": {"quote": "Inicio Deportes", "view": "page_text"}})
    journal.append({"kind": "completeness", "case_id": "P001", "payload": {"values": ["beginning_missing", "end_missing"]}})
    journal.append({"kind": "finalize", "case_id": "P001", "payload": {}})
    c2 = package.cases["P002"]                                       # the reviewer agrees with every block decision
    answer_all(journal, c2, core="unsure", foreign={int(i) for i, m in key["P002"]["machine"]["blocks"].items()
                                                    if m["role"] != E.ROLE_BODY})
    journal.append({"kind": "finalize", "case_id": "P002", "payload": {}})
    data = R.export(package, journal)
    assert data["cases_closed"] == 2 and data["cases_total"] == 3 and len(data["events_sha256"]) == 64
    R.validate_export(package, json.loads(json.dumps(data)))
    tampered = json.loads(json.dumps(data))
    tampered["cases"][0]["blocks"][0]["text_sha256"] = "0" * 64
    with pytest.raises(R.ReviewError, match="blocks do not match"):
        R.validate_export(package, tampered)
    result = R.score(package, data)
    rnd = result["components"]["random"]
    assert rnd["cases"] == 2 and rnd["blocks_residue"] == 1 and rnd["blocks_false_deletion"] == 1
    assert rnd["core_false_reject"] == 1 and rnd["core_doubt"] == 1 and rnd["cases_incomplete"] == 1
    assert rnd["missing_marks_in_page_text"] == 1
    residue = rnd["estimates_design_weighted"]["cases_with_residue"]          # CPD-0044: weighted, stratified
    assert residue["estimate"] == 0.5 and residue["k"] == 1 and residue["interval"][0] < 0.5 < residue["interval"][1]
    assert result["components"]["targeted"]["cases"] == 0 and "no population rate" in result["components"]["targeted"]["note"]


# --- the server ------------------------------------------------------------------------------------------------------------


def request(port, method, path, body=None, host=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=data, headers=headers)
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, dict(response.getheaders()), payload


@pytest.fixture
def served(tmp_path):
    package, _ = build(tmp_path)
    server = R.make_server(package, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield package, server.server_address[1]
    server.shutdown()
    server.server_close()


def test_the_server_serves_blind_cases_and_shows_machine_labels_only_after_closing(served):
    package, port = served
    status, headers, body = request(port, "GET", "/")
    assert status == 200 and b"/app.js" in body and "script-src 'self'" in headers["Content-Security-Policy"]
    status, headers, body = request(port, "GET", "/api/case/P001/source")
    assert status == 200 and headers["Content-Security-Policy"] == R.SOURCE_CSP and b"<script" not in body
    assert request(port, "GET", "/api/case/P001/machine")[0] == 403
    case = json.loads(request(port, "GET", "/api/case/P001")[2])
    for b in case["blocks"]:
        status, _, _ = request(port, "POST", "/api/event", {"kind": "label_block", "case_id": "P001", "payload":
                                                             {"index": b["index"], "text_sha256": b["text_sha256"], "label": "article"}})
        assert status == 200
    for event in ({"kind": "title", "payload": {"label": "correct"}}, {"kind": "completeness", "payload": {"values": ["complete"]}},
                  {"kind": "core", "payload": {"value": "yes", "reason": ""}}, {"kind": "finalize", "payload": {}}):
        assert request(port, "POST", "/api/event", {**event, "case_id": "P001"})[0] == 200
    status, _, body = request(port, "GET", "/api/case/P001/machine")
    machine = json.loads(body)
    assert status == 200 and machine["machine"]["core"]["decision"] == "REJECT" and "body_text" not in machine["machine"]
    state = json.loads(request(port, "GET", "/api/state")[2])
    assert state["P001"]["finalized"] and state["P001"]["revealed"]
    status, _, body = request(port, "POST", "/api/export", {})
    assert status == 200 and json.loads(body)["cases_closed"] == 1
    assert request(port, "POST", "/api/event", {"kind": "core", "case_id": "P001", "payload": {"value": "no"}})[0] == 409


def test_the_server_refuses_other_hosts_and_binds_loopback_only(served, tmp_path):
    package, port = served
    assert request(port, "GET", "/api/state", host="evil.test")[0] == 403
    assert request(port, "POST", "/api/event", {"kind": "position", "case_id": "P001"}, host=f"rebind.test:{port}")[0] == 403
    assert request(port, "GET", "/api/case/P001/../../manifest.json")[0] == 404
    with pytest.raises(R.ReviewError, match="loopback"):
        R.make_server(package, host="0.0.0.0", port=0)
