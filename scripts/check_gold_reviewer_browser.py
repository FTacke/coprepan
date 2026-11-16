"""Browser check of the gold reviewer (CPD-0044): drives the real client in a real Chrome (Playwright, the locally installed
browser) against a **technical test package** -- never the operator's practice package, never a holdout -- and checks range
labels, text spans, keys, the search from the original, the case questions, closing, resuming after a reload, reopening, and
that a hostile page runs no script and loads nothing. Not part of the test suite: Playwright is a local tool here, not a pinned
dependency. Answers made here are test material and the package is deleted at the end (``--keep`` keeps it).

Usage:
  python scripts/check_gold_reviewer_browser.py --page-cache <cache> | --runtime <ws>  [--work <dir>] [--screenshots <dir>] [--keep]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

from coprepan import gold_review as G  # noqa: E402
import gold_review as CLI  # noqa: E402

HOSTILE = ("<html><head><meta http-equiv='refresh' content='0;url=https://evil.test'><script>window.parent.PWNED=1</script>"
           "<link rel=stylesheet href='https://cdn.test/a.css'></head><body onload='parent.PWNED=2'>"
           "<nav><ul><li><a href='/'>Portada</a></li><li><a href='/x'>Sección</a></li><li><a href='/y'>Otra</a></li></ul></nav>"
           "<article><h1>Título de prueba técnica</h1><p>Primer párrafo de la prueba técnica con texto suficiente para marcar.</p>"
           "<p>Segundo párrafo <b>con</b> <i>formato</i> en línea y una cifra de 1.250 personas. Foto: Agencia</p>"
           "<iframe src='https://ads.test/frame'></iframe><img src='https://t.test/p.gif' onerror='parent.PWNED=3' alt='Foto'>"
           "<table><tr><td>Equipo</td><td>Pts</td></tr><tr><td>Uno</td><td>10</td></tr></table>"
           "<ul><li>Primer elemento de lista</li><li>Segundo elemento</li></ul>"
           "<div style='display:none'>Texto oculto</div><p>Tercer párrafo final.<br>Línea tras salto.</p></article>"
           "<footer><p>Pie 1</p><p>Pie 2</p><p>Pie 3</p></footer><script>parent.PWNED=4</script></body></html>")


def wait(page, expression: str, timeout: float = 10.0) -> None:
    """Poll a JavaScript expression until it is true. (Playwright's wait_for_function evaluates a string with eval, which the
    reviewer's Content-Security-Policy refuses -- as it should; ``evaluate`` goes through the DevTools protocol.)"""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return
        time.sleep(0.05)
    raise TimeoutError(expression)


def build(work: Path, arguments) -> Path:
    """A technical test package: two stored development pages (a fresh random draw) and the hostile page."""
    pkg = work / "technical_test_package"
    real = []
    for page, body in CLI.S3.stored_pages(arguments):
        if hashlib.sha256(page["fetch_id"].encode()).hexdigest()[:2] in ("3a", "c7"):       # a fixed, arbitrary pick
            real.append((page, body))
        if len(real) == 2:
            break
    materials, cases = {}, []
    for k, (page, body) in enumerate(real, 1):
        cid = f"T{k:02d}"
        materials[page["fetch_id"]] = G.case_material(cid, page, CLI._decoded(page, body), country_id="test")
        cases.append({"case_id": cid, "fetch_id": page["fetch_id"], "component": "technical_test"})
    data = HOSTILE.encode("utf-8")
    hostile = {"fetch_id": "technical_test_hostile", "outlet_id": "test", "url": "https://hostile.test/a", "fetched_at": None,
               "body_sha256": hashlib.sha256(data).hexdigest()}
    materials[hostile["fetch_id"]] = G.case_material("T03", hostile, HOSTILE, country_id="test")
    cases.append({"case_id": "T03", "fetch_id": hostile["fetch_id"], "component": "technical_test"})
    G.write_package(pkg, kind="PRACTICE", cases=cases, materials=materials, design={"design": "technical browser test"},
                    meta={"label": "TECHNICAL TEST MATERIAL -- not gold, deleted after the check"}, repository=REPOSITORY)
    return pkg


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--runtime", type=Path)
    src.add_argument("--page-cache", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--keep", action="store_true")
    arguments = parser.parse_args(argv)
    work = arguments.work or Path(tempfile.mkdtemp(prefix="gold-browser-check-"))
    from playwright.sync_api import sync_playwright

    pkg = build(work, SimpleNamespace(runtime=arguments.runtime, page_cache=arguments.page_cache))
    package = G.Package(pkg)
    server = G.make_server(package, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/"
    results, requests = {}, []

    def check(name, ok, detail=""):
        results[name] = {"ok": bool(ok), "detail": detail}
        print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""), flush=True)

    def state(cid):
        return server.journal.state[cid]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = context.new_page()
            page.on("request", lambda r: requests.append(r.url))
            page.on("dialog", lambda d: d.accept())
            page.goto(base)
            page.wait_for_selector("#view .seg")
            first = page.evaluate("window.GOLD_REVIEW.kase.case_id")
            check("loads_a_case", first in package.case_ids, first)
            # go to the hostile technical page (T03) for deterministic segments
            page.select_option("#caseSelect", "T03")
            wait(page, "window.GOLD_REVIEW.kase && window.GOLD_REVIEW.kase.case_id === 'T03'")
            page.wait_for_selector("#view .seg")
            segs = package.cases["T03"]["view"]["segments"]
            idx = {s["text"]: s["i"] for s in segs}
            check("pwned_never_set", page.evaluate("window.PWNED === undefined"))
            # G: the heading
            page.keyboard.press("g")
            check("key_g_focuses_the_heading", page.evaluate("window.GOLD_REVIEW.focus") == idx["Título de prueba técnica"])
            # a range by click and shift+click, labelled with B
            a = idx["Primer párrafo de la prueba técnica con texto suficiente para marcar."]
            b = next(s["i"] for s in segs if s["text"].startswith("Segundo párrafo"))
            page.click(f'#view .seg[data-i="{a}"] .n')
            page.click(f'#view .seg[data-i="{b}"] .n', modifiers=["Shift"])
            page.keyboard.press("b")
            wait(page, f"window.GOLD_REVIEW.state.T03.labels['{b}'] === 'body'")
            check("range_label_by_click_shift_click_and_key", all(state("T03")["labels"].get(str(i)) == "body" for i in range(a, b + 1)))
            # J / Shift+J / T on the heading
            page.click(f'#view .seg[data-i="{idx["Título de prueba técnica"]}"] .n')
            page.keyboard.press("t")
            wait(page, f"window.GOLD_REVIEW.state.T03.labels['{idx['Título de prueba técnica']}'] === 'title'")
            page.keyboard.press("j")
            check("key_j_moves", page.evaluate("window.GOLD_REVIEW.focus") == idx["Título de prueba técnica"] + 1)
            page.keyboard.press("Shift+J")
            check("shift_j_extends", page.evaluate("window.GOLD_REVIEW.sel[1] - window.GOLD_REVIEW.sel[0]") == 1)
            # a span inside a segment: select "Foto: Agencia" with a real DOM range and press F
            seg_b = segs[b]["text"]
            start = seg_b.index("Foto: Agencia")
            page.evaluate("""([i, s, e]) => { const t = document.querySelector('#view .t[data-i="' + i + '"]');
                const node = t.firstChild; const r = document.createRange(); r.setStart(node, s); r.setEnd(node, e);
                const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r); }""", [b, start, len(seg_b)])
            page.keyboard.press("f")
            wait(page, "Object.keys(window.GOLD_REVIEW.state.T03.spans).length === 1")
            span = next(iter(state("T03")["spans"].values()))
            check("span_from_a_text_selection", (span["segment"], span["start"], span["end"], span["label"]) == (b, start, len(seg_b), "foreign"),
                  json.dumps(span))
            # X on a selection inside the span removes it
            page.evaluate("""([i, s, e]) => { const t = document.querySelector('#view .t[data-i="' + i + '"]');
                const sp = t.querySelector('.sp'); const r = document.createRange(); r.setStart(sp.firstChild, 0); r.setEnd(sp.firstChild, 4);
                const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r); }""", [b, start, len(seg_b)])
            page.keyboard.press("x")
            wait(page, "Object.keys(window.GOLD_REVIEW.state.T03.spans).length === 0")
            check("x_removes_a_span", not state("T03")["spans"])
            # the folded footer group: one click selects the group, F labels all of it
            foot = [s["i"] for s in segs if "footer" in s["flags"]]
            group = page.query_selector(f'#view .group[data-from="{foot[0]}"]')
            check("footer_folded_as_a_group", group is not None and len(page.query_selector_all("#view .group")) == 2)
            if group:
                group.click()
                page.keyboard.press("f")
                wait(page, f"window.GOLD_REVIEW.state.T03.labels['{foot[-1]}'] === 'foreign'")
                check("group_labelled_at_once", all(state("T03")["labels"].get(str(i)) == "foreign" for i in foot),
                      json.dumps({i: state("T03")["labels"].get(str(i)) for i in foot}))
            # S: select text in the original, find it in the view
            page.evaluate("""() => { const d = document.getElementById('source').contentDocument;
                const walker = d.createTreeWalker(d.body, NodeFilter.SHOW_TEXT); let n;
                while ((n = walker.nextNode())) { if (n.textContent.includes('Tercer párrafo')) break; }
                const r = d.createRange(); r.setStart(n, 0); r.setEnd(n, 14); const s = d.getSelection(); s.removeAllRanges(); s.addRange(r); }""")
            page.click("#findBtn")
            target = next(s["i"] for s in segs if s["text"].startswith("Tercer párrafo"))
            check("find_from_the_original", page.evaluate("window.GOLD_REVIEW.focus") == target)
            # questions and closing
            page.click('#sourceState button[data-v="complete"]')
            page.click('#coreChoice button[data-v="no"]')
            wait(page, "window.GOLD_REVIEW.state.T03.core && window.GOLD_REVIEW.state.T03.core.value === 'no'")
            page.check("#restConfirmed")
            page.keyboard.press("Control+Enter")              # refused: CORE "no" needs a reason
            time.sleep(0.5)
            check("close_refused_without_reason", page.is_disabled("#finalizeBtn") and not state("T03")["finalized"]
                  and "core_reason" in state("T03")["open_items"])
            page.check('#coreReasons input[value="too_short"]')
            wait(page, "window.GOLD_REVIEW.state.T03.core.reasons.length === 1")
            page.fill("#comment", "technical test")
            page.keyboard.press("Control+Enter")              # at once, from the text field: the comment is saved first
            wait(page, "window.GOLD_REVIEW.state.T03.finalized === true")
            check("closed_with_ctrl_enter", state("T03")["finalized"] and state("T03")["comment"] == "technical test")
            # resume after a reload: same state, same case
            page.reload()
            page.wait_for_selector("#view .seg")
            check("resumes_after_reload", page.evaluate("window.GOLD_REVIEW.kase.case_id") == "T03"
                  and page.evaluate("window.GOLD_REVIEW.state.T03.finalized") is True)
            # a closed case is locked; reopening is recorded
            check("closed_case_locked", page.is_disabled('#coreChoice button[data-v="yes"]'))
            page.click("#reopenBtn")
            wait(page, "window.GOLD_REVIEW.state.T03.finalized === false")
            check("reopen_recorded", state("T03")["reopened"] == 1)
            # a comment typed and the case left at once is saved in its own case, not in the next
            page.select_option("#caseSelect", "T02")
            wait(page, "window.GOLD_REVIEW.kase.case_id === 'T02'")
            page.fill("#comment", "only for T02")
            page.select_option("#caseSelect", "T01")
            wait(page, "window.GOLD_REVIEW.kase.case_id === 'T01'")
            time.sleep(0.3)
            check("typed_text_stays_with_its_case", state("T02")["comment"] == "only for T02" and state("T01")["comment"] == "",
                  json.dumps([state("T02")["comment"], state("T01")["comment"]]))
            # a real page renders and its view is complete
            wait(page, "window.GOLD_REVIEW.kase.case_id === 'T01'")
            page.wait_for_selector("#view .seg")
            shown = page.evaluate("document.querySelectorAll('#view .seg').length + "
                                  "[...document.querySelectorAll('#view .group')].reduce((n, g) => n + (+g.dataset.to - +g.dataset.from + 1), 0)")
            check("real_page_every_segment_reachable", shown == len(package.cases["T01"]["view"]["segments"]),
                  f"{shown} of {len(package.cases['T01']['view']['segments'])}")
            if arguments.screenshots:
                arguments.screenshots.mkdir(parents=True, exist_ok=True)
                page.click("#view .seg .n")                    # the focus out of the text field, then G
                page.keyboard.press("g")
                page.screenshot(path=str(arguments.screenshots / "gold_reviewer_real_page.png"))
            check("pwned_still_unset", page.evaluate("window.PWNED === undefined"))
            browser.close()
        foreign = [u for u in requests if not u.startswith(base)]
        check("no_request_beyond_the_local_server", not foreign, "; ".join(foreign[:5]))
    finally:
        server.shutdown()
        server.server_close()
        if not arguments.keep:
            shutil.rmtree(work, ignore_errors=True)
    failed = [k for k, v in results.items() if not v["ok"]]
    print(json.dumps({"checks": len(results), "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
