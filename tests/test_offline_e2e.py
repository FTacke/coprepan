"""The complete offline canary, on the production code path:

```text
registered channel → policy gate → HTTP fetch (loopback) → discovery → candidate → policy gate
   → HTTP fetch (loopback) → fetch record → WARC pack → seal → promotion → RAW_PRESERVED
   → document identity → extraction → document version → replay
```

A real HTTP server on a loopback address plays an invented outlet; its pages are the synthetic
fixtures. The outlet exists only in this file's in-memory registry. **This validates the pipeline
against itself and against scripted failures — reproducibility and robustness. It shows nothing
about any real outlet, real page or real network condition, and it does not exercise TLS.**
"""

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from warcio.archiveiterator import ArchiveIterator

from coprepan import acquisition, core_pipeline as C, discovery, fetcher as F, http_acquisition as H
from coprepan import layer_store, pack, policy as P, preservation
from coprepan.crawler_identity import loopback_test_identity
from coprepan.document_identity import IdentityTables
from support_http import FakeClock, LocalSite, Response
from test_fetcher import FEEDS, MOBILE, OUTLET, WWW

FIXTURES = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
HTML = [("Content-Type", "text/html; charset=utf-8")]
XML = [("Content-Type", "application/xml")]
ARTICLE = f"{WWW}/Economia/Puerto-crecimiento-2026.html"
LIMITS = F.FetchLimits(timeout_seconds=2, max_redirects=3, max_body_bytes=500_000, max_attempts=3,
                       backoff_base_seconds=2, backoff_max_seconds=60)
BUDGET = discovery.DiscoveryBudget(max_depth=3, max_documents=20, max_candidates=100, max_bytes=1_000_000)
RSS, SITEMAP = f"{OUTLET}:ch:rss_001", f"{OUTLET}:ch:sitemap_001"
ROBOTS = b"User-agent: *\nDisallow: /privado/\nSitemap: https://www.diario-ejemplo.test/sitemap_index.xml\n"
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"


def fx(name):
    return (FIXTURES / name).read_bytes()


def make_registry():
    from coprepan import registry as R

    return R.validate_registry({"schema": "coprepan-outlet-registry/v1", "outlets": [{
        "outlet_id": OUTLET, "country_id": "uy", "registration_status": "registered",
        "display_names": [{"name": "Diario Ejemplo", "valid_from": "unknown", "valid_to": "not_applicable"}],
        "outlet_type": "unknown", "outlet_group": "unknown", "city": "unknown", "region": "unknown",
        "scope": "unknown", "access_model": "unknown", "medium": "unknown", "editions": [],
        "web_origins": [WWW, MOBILE], "timezone": "America/Montevideo", "same_outlet_basis": "not_applicable",
        "url_rules": {"version": f"{OUTLET}-url-rules/v1", "significant_query_params": ["id"],
                      "strip_path_prefixes": ["/amp"], "strip_path_suffixes": []},
        "channels": [
            {"channel_id": RSS, "kind": "rss", "url_history": [{"url": f"{WWW}/rss.xml", "valid_from": "unknown"}], "legacy_observed": {}},
            {"channel_id": SITEMAP, "kind": "sitemap_index",
             "url_history": [{"url": f"{WWW}/sitemap_index.xml", "valid_from": "unknown"}], "legacy_observed": {}},
        ],
        "legacy_aliases": [], "legacy_observed": {}, "review_notes": [],
    }]})


def script(site):
    """What the invented outlet serves."""
    site.routes.update({
        "/robots.txt": Response(200, [("Content-Type", "text/plain")], ROBOTS),
        "/rss.xml": Response(200, [("Content-Type", "application/rss+xml")], fx("discovery/rss.xml")),
        "/rss.xml?page=2": Response(200, HTML, fx("discovery/rss_page2.xml")),  # a feed served as text/html
        "/sitemap_index.xml": Response(200, XML, fx("discovery/sitemap_index.xml")),
        "/sitemaps/2026-10.xml": Response(200, XML + [("Content-Encoding", "gzip")], gzip.compress(fx("discovery/sitemap_urlset.xml"), mtime=0)),
        "/sitemaps/anidado.xml": Response(200, XML, fx("discovery/sitemap_nested_index.xml")),
        "/sitemaps/profundo.xml": Response(200, XML, b"<urlset><url><loc>https://www.diario-ejemplo.test/profundo/1</loc></url></urlset>"),
        # /profundo/1 itself is not served: the item answers 404
        "/Economia/Puerto-crecimiento-2026.html?utm_source=rss&utm_medium=feed": Response(200, HTML, fx("canary/nota_v1.html")),
        "/Regionales/puerto-separan-cargas": [Response(503, HTML + [("Retry-After", "5")], b"<html><body>mantenimiento</body></html>"),
                                              Response(200, HTML, fx("canary/nota_republicada.html"), chunked=True)],
        "/breves/123": Response(301, [("Location", "/breves/123/")]),
        "/breves/123/": Response(200, [], fx("canary/sin_metadatos.html")),      # no Content-Type at all
        "/docs/informe.pdf": Response(200, [("Content-Type", "application/pdf")], PDF),
        "/Deportes/Final": Response(200, HTML + [("Content-Encoding", "gzip")],
                                    gzip.compress(b"<html><body><article><h1>Final</h1><p>La final se juega el domingo.</p></article></body></html>", mtime=0)),
        "/deportes/final": Response(200, HTML, b"<html><body><article><h1>final</h1><p>Glosario: el ultimo partido.</p></article></body></html>"),
    })


class Pass:
    """One complete acquisition pass against a scripted site, in its own workspace and root."""

    def __init__(self, base, site, *, policy=None, start=T0, run_configuration=None):
        self.workspace = C.Workspace(base / "workspace")
        self.root = base / "preservation_root"
        for directory in (self.workspace.root, self.root):
            directory.mkdir(parents=True, exist_ok=True)
        self.site, self.registry, self.clock = site, make_registry(), FakeClock(start)
        self.identity = loopback_test_identity()
        gate = P.PolicyGate(policy or P.loopback_test_policy(), self.registry, self.identity)
        override = {origin: ("127.0.0.1", site.port) for origin in (WWW, MOBILE, FEEDS)}
        self.fetcher = F.HttpFetcher(identity=self.identity, gate=gate, limits=LIMITS, clock=self.clock,
                                     sleep=self.clock.sleep, connect_override=override)
        self.run = H.http_fetch_run(start, [OUTLET], run_configuration or {"limits": LIMITS.__dict__, "budget": BUDGET.__dict__}, self.identity)
        self.pack_id = pack.pack_id(OUTLET, start.strftime("%Y%m%d"))

    def acquire(self, channels=(RSS, SITEMAP), max_item_fetches=50):
        self.summary = H.run_http_acquisition(self.workspace, self.registry, self.run, OUTLET, fetcher=self.fetcher,
                                              channel_ids=channels, budget=BUDGET, max_item_fetches=max_item_fetches,
                                              clock=self.clock)
        return self.summary

    def preserve(self):
        self.promotion = C.seal_and_preserve(self.workspace, self.pack_id, preservation_root=self.root, now=self.clock())
        return self.promotion

    def derive(self, **kwargs):
        self.results = C.identify_and_extract(self.workspace, self.registry, preservation_root=self.root,
                                              identifier=self.pack_id, now=self.clock(), **kwargs)
        return self.results

    def all(self):
        self.acquire(), self.preserve(), self.derive()
        acquisition.close_run(self.workspace.root, self.run, finished_at=self.clock(), status="COMPLETED",
                              counts=self.summary["recorded"], pack_ids=[self.pack_id])
        return self

    def records(self):
        preserved = C.open_preserved_pack(self.root, self.pack_id)
        return [preserved.fetch_record(fetch_id) for fetch_id in preserved.entries]

    def states(self):
        return self.workspace.ledger().states()


@pytest.fixture
def site():
    with LocalSite() as server:
        script(server)
        yield server


@pytest.fixture
def done(tmp_path, site):
    return Pass(tmp_path / "first", site).all()


def files(base):
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}


# --- the happy path, end to end ----------------------------------------------------------------------


def test_offline_canary_end_to_end(done):
    summary = done.summary
    assert [(d["channel_id"], d["documents_read"], d["candidates_new"], d["stopped_by"]) for d in summary["discovery"]] == [
        (RSS, 2, 4, []), (SITEMAP, 4, 3, [])]
    assert summary["requests"] == {"channel_document:FETCHED": 6, "item:FETCHED": 7}
    assert summary["candidates_known"] == summary["candidates_requested"] == 7 and summary["candidates_left"] == 0

    records = done.records()
    kinds = [r["fetch_kind"] for r in records]
    assert (kinds.count("channel_document"), kinds.count("item"), kinds.count("robots_txt")) == (6, 8, 1)
    assert set(done.states().values()) == {"RAW_PRESERVED"}  # every response is preserved, also 404 and 503
    statuses = sorted(r["response"]["status"] for r in records)
    assert statuses.count(404) == 1 and statuses.count(503) == 1  # the unserved page; the first attempt of a retried one

    # only items become documents; a feed or a robots file never does
    assert len(done.results) == 8 and {r["identity"] for r in done.results} == {"assigned"}
    tables = IdentityTables(done.workspace.identity)
    assert sorted(d["url_key"] for d in tables.documents.values()) == sorted([
        ARTICLE, f"{WWW}/Regionales/puerto-separan-cargas", f"{WWW}/breves/123/", f"{WWW}/docs/informe.pdf",
        f"{WWW}/Deportes/Final", f"{WWW}/deportes/final", f"{WWW}/profundo/1"])
    by_key = {tables.documents[r["document_id"]]["url_key"]: r for r in done.results}
    assert by_key[ARTICLE]["url_key_basis"] == "rel_canonical"
    assert by_key[f"{WWW}/breves/123/"]["url_key_basis"] == "final_url"          # followed the redirect, no canonical
    assert by_key[f"{WWW}/Deportes/Final"]["extraction_outcome"] == "EXTRACTED"  # gzip decoded for reading
    assert by_key[f"{WWW}/docs/informe.pdf"]["document_version_id"] is None
    assert by_key[f"{WWW}/profundo/1"]["extraction_outcome"] == "EXTRACTED"      # an error page extracts; whether it is an article is a later label
    # the 503 attempt and the 200 attempt of one request are two fetches of one document
    regional = [r for r in done.results if tables.documents[r["document_id"]]["url_key"].endswith("puerto-separan-cargas")]
    assert len(regional) == 2 and len({r["document_id"] for r in regional}) == 1 and len({r["document_version_id"] for r in regional}) == 2
    assert acquisition.unfinished_runs(done.workspace.root) == [] and H.unfinished_requests(done.workspace) == []


def test_every_request_went_through_the_gate_and_carries_its_policy_context(done):
    assert done.site.paths()[0] == "/robots.txt" and done.site.paths().count("/robots.txt") == 1
    agent = loopback_test_identity().user_agent
    assert {headers["user-agent"] for _, headers in done.site.requests} == {agent}
    robots_sha = hashlib.sha256(ROBOTS).hexdigest()
    for record in done.records():
        assert record["policy"]["policy_decision"] == "ALLOW" and record["policy"]["policy_version"] == "loopback-test/1"
        assert record["policy"]["user_agent"] == agent and record["run_id"] == done.run.run_id
        if record["fetch_kind"] != "robots_txt":
            assert (record["policy"]["robots_decision"], record["policy"]["robots_txt_sha256"]) == ("allowed", robots_sha)
    log = [json.loads(line) for line in H.request_log_path(done.workspace).read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in log].count("PLANNED") == [row["event"] for row in log].count("FINISHED") == 13
    retried = next(row for row in log if row["event"] == "FINISHED" and len(row["attempts"]) == 2)
    assert [a["retry"] for a in retried["attempts"]] == ["retry", "none"] and retried["attempts"][0]["delay_seconds"] == 5.0
    assert 5.0 in done.clock.slept  # Retry-After honoured by the injected clock


def test_raw_bytes_on_the_preservation_root_are_what_the_server_sent(done):
    preserved = C.open_preserved_pack(done.root, done.pack_id)
    bodies = {}
    for fetch_id in preserved.entries:
        record = preserved.fetch_record(fetch_id)
        bodies[(record["request"]["requested_url"], record["response"]["status"])] = (preserved.body(fetch_id), record)
    assert bodies[(f"{WWW}/rss.xml", 200)][0] == fx("discovery/rss.xml")
    assert bodies[(f"{ARTICLE}?utm_source=rss&utm_medium=feed", 200)][0] == fx("canary/nota_v1.html")
    packed, record = bodies[(f"{WWW}/sitemaps/2026-10.xml", 200)]
    assert packed == gzip.compress(fx("discovery/sitemap_urlset.xml"), mtime=0) and record["response"]["content_encoding"] == "gzip"
    chunked, record = bodies[(f"{WWW}/Regionales/puerto-separan-cargas", 200)]
    assert chunked == fx("canary/nota_republicada.html")  # transfer coding removed, bytes exact
    assert ["Transfer-Encoding", "chunked"] in record["response"]["headers"]  # the header is kept as received
    redirected, record = bodies[(f"{WWW}/breves/123", 200)]
    assert redirected == fx("canary/sin_metadatos.html") and record["response"]["redirect_chain"] == [f"{WWW}/breves/123"]
    assert record["response"]["final_url"] == f"{WWW}/breves/123/" and record["response"]["content_type"] == "unknown"
    for body, record in bodies.values():
        assert hashlib.sha256(body).hexdigest() == record["body_sha256"]


def test_two_independent_passes_are_identical(tmp_path, site, done):
    site._served.clear()
    second = Pass(tmp_path / "second", site).all()
    assert second.run.run_id == done.run.run_id and second.summary == done.summary and second.results == done.results
    assert second.promotion.sha256 == done.promotion.sha256  # the sealed pack, byte for byte
    first_files, second_files = files(done.workspace.root), files(second.workspace.root)
    assert first_files.keys() == second_files.keys()
    differing = sorted(name for name in first_files if first_files[name] != second_files[name])
    assert differing == []  # ledger, request log, discovery and identity tables, layer store: all the same bytes


def test_a_later_run_in_the_same_workspace_adds_and_never_rewrites(done, site):
    preserved_before = files(done.root)
    day_one_identity = files(done.workspace.identity)
    site._served.clear()
    later = Pass(done.workspace.root.parent, site, start=T0 + timedelta(days=1))
    later.acquire()
    assert later.run.run_id != done.run.run_id
    assert later.summary["candidates_requested"] == 0            # everything known was already fetched
    assert later.summary["requests"] == {"channel_document:FETCHED": 6}
    assert all(d["candidates_new"] == 0 for d in later.summary["discovery"])
    later.preserve()
    now = files(done.root)
    assert {name: now[name] for name in preserved_before} == preserved_before  # day one untouched
    assert len(now) == len(preserved_before) + 4                               # a new pack, index and two manifests
    assert later.derive() == [] and files(done.workspace.identity) == day_one_identity
    # discovery saw the same listings again: new events (a listing observed twice), no new candidate
    tables = H.discovery_tables(done.workspace)
    assert len(tables.candidates) == 7 and len({e["run_id"] for e in tables.events.values()}) == 2


def test_no_record_depends_on_the_machine_or_the_port(done, tmp_path):
    needles = [str(tmp_path), tmp_path.as_posix(), str(tmp_path).replace("\\", "\\\\"), "127.0.0.1", str(done.site.port)]
    checked = 0
    for name, data in {**files(done.workspace.root), **files(done.root)}.items():
        if name.endswith((".json", ".jsonl")):
            text = data.decode("utf-8")
            assert not any(needle in text for needle in needles[:4]), name
            assert f":{done.site.port}" not in text, name
            checked += 1
    assert checked > 20
    raw = gzip.decompress((done.root / done.promotion.relative_path).read_bytes())
    assert b"127.0.0.1" not in raw and f":{done.site.port}".encode() not in raw


# --- an independent reader ---------------------------------------------------------------------------


def test_the_preserved_pack_is_read_by_an_independent_warc_reader(done):
    """warcio 1.7.5 (not this repository's parser) reads the sealed, promoted pack: every record,
    its type, target URI, HTTP status and exact payload, with digests checked.
    """
    expected = {}
    preserved = C.open_preserved_pack(done.root, done.pack_id)
    for fetch_id in preserved.entries:
        record = preserved.fetch_record(fetch_id)
        expected[fetch_id] = (record, preserved.body(fetch_id))
    types, seen = [], {}
    with open(done.root / done.promotion.relative_path, "rb") as stream:
        for item in ArchiveIterator(stream, check_digests=True):
            types.append(item.rec_type)
            payload = item.raw_stream.read() if item.rec_type != "response" else None
            if item.rec_type == "response":
                fetch_id = item.rec_headers.get_header("WARC-Record-ID").split(":response>")[0].split("urn:coprepan:")[1]
                record, body = expected[fetch_id]
                assert item.rec_headers.get_header("WARC-Target-URI") == record["request"]["requested_url"]
                assert item.rec_headers.get_header("WARC-Date") == record["fetch_started_at"]
                assert item.rec_headers.get_header("WARC-Payload-Digest") == f"sha256:{record['body_sha256']}"
                assert int(item.http_headers.get_statuscode()) == record["response"]["status"]
                assert item.http_headers.get_header("Transfer-Encoding") is None  # never tells a reader to de-chunk
                seen[fetch_id] = item.raw_stream.read()                            # the payload exactly as stored
            elif item.rec_type == "metadata":
                assert json.loads(payload)["schema"] == "coprepan-fetch-record/v1"
            assert item.digest_checker.passed is True and item.digest_checker.problems == []
    assert types[0] == "warcinfo" and types.count("response") == types.count("metadata") == len(expected) == 15
    assert seen == {fetch_id: body for fetch_id, (_, body) in expected.items()}


# --- replay ------------------------------------------------------------------------------------------


def test_replay_needs_no_network_and_reproduces_every_extraction(done, monkeypatch):
    import socket

    def no_socket(*args, **kwargs):
        raise AssertionError("replay opened a socket")

    monkeypatch.setattr(socket, "socket", no_socket)
    replayed = 0
    for result in done.results:
        replay = C.replay_extraction(done.workspace, preservation_root=done.root, identifier=done.pack_id,
                                     fetch_id=result["fetch_id"])
        assert (replay["status"], replay["artifact_id"]) == ("ALREADY_STORED", result["extraction_artifact_id"])
        replayed += 1
    assert replayed == 8


# --- failure injection -------------------------------------------------------------------------------


def test_discovery_parse_failure_stops_that_channel_only(tmp_path, site):
    site.routes["/rss.xml"] = Response(200, XML, fx("discovery/malformed.xml"))
    run = Pass(tmp_path, site).all()
    rss, sitemap = run.summary["discovery"]
    assert rss["candidates_new"] == 0 and any(note.startswith("unparseable") for note in rss["notes"])
    assert sitemap["candidates_new"] == 5 and run.summary["requests"]["item:FETCHED"] == 5
    inputs = H.discovery_tables(run.workspace).inputs
    assert inputs[0]["outcome"] == "UNPARSEABLE" and inputs[0]["input_fetch_id"] in C.open_preserved_pack(run.root, run.pack_id).entries
    # the unparseable feed is itself preserved: the evidence of the failure survives
    assert C.open_preserved_pack(run.root, run.pack_id).body(inputs[0]["input_fetch_id"]) == fx("discovery/malformed.xml")


def test_policy_deny_makes_no_request_and_leaves_a_record_of_the_refusal(tmp_path, site):
    policy = P.loopback_test_policy(disabled_channels=[RSS])
    run = Pass(tmp_path, site, policy=policy)
    run.acquire()
    assert "/rss.xml" not in site.paths()
    assert run.summary["requests"]["channel_document:DENIED"] == 1 and run.summary["discovery"][0]["candidates_new"] == 0
    log = [json.loads(line) for line in H.request_log_path(run.workspace).read_text(encoding="utf-8").splitlines()]
    denied = next(row for row in log if row["event"] == "FINISHED" and row["final"] == "DENIED")
    assert denied["policy_reasons"] == ["channel_disabled"] and denied["fetch_ids"] == []
    assert not any(state == "REFUSED_BY_POLICY" for state in run.states().values())  # no fetch id exists for a request never made


def test_robots_disallow_is_enforced_inside_the_run(tmp_path, site):
    site.routes["/robots.txt"] = Response(200, [("Content-Type", "text/plain")], b"User-agent: *\nDisallow: /Deportes/\n")
    run = Pass(tmp_path, site).all()
    assert "/Deportes/Final" not in site.paths() and "/deportes/final" in site.paths()  # robots paths are case-sensitive
    assert run.summary["requests"]["item:DENIED"] == 1 and run.summary["candidates_left"] == 0
    assert H.fetched_candidates(run.workspace) == {c for c in H.discovery_tables(run.workspace).candidates} - {
        discovery.candidate_id(OUTLET, f"{WWW}/Deportes/Final")}


def test_transport_failure_and_retry_exhaustion_never_look_like_success(tmp_path, site):
    site.routes["/deportes/final"] = Response(200, HTML, b"<html>cortado", declared_length=5000)   # truncated every time
    site.routes["/Deportes/Final"] = Response(503, HTML, b"<html>caido</html>")                    # down every time
    run = Pass(tmp_path, site).all()
    assert run.summary["requests"] == {"channel_document:FETCHED": 6, "item:FETCHED": 6, "item:FETCH_FAILED": 1}
    states = run.states()
    truncated = [r for r in run.records() if r["request"]["requested_url"].endswith("/deportes/final")]
    assert [r["outcome"] for r in truncated] == ["FETCH_FAILED"] * 3 and {r["failure_reason"] for r in truncated} == {"incomplete_response"}
    assert all(states[r["fetch_id"]] == "FETCH_FAILED" for r in truncated)  # never RAW_PRESERVED
    assert [r["attempt_number"] for r in truncated] == [1, 2, 3]
    down = [r for r in run.records() if r["request"]["requested_url"].endswith("/Deportes/Final")]
    assert [r["response"]["status"] for r in down] == [503, 503, 503]  # responses: preserved as what they are
    documents = {d["url_key"] for d in IdentityTables(run.workspace.identity).documents.values()}
    assert f"{WWW}/deportes/final" not in documents                     # nothing came back: no document
    # the candidate whose fetch failed stays open for a later run; the 503 one is "fetched" (a response exists)
    assert discovery.candidate_id(OUTLET, f"{WWW}/deportes/final") not in H.fetched_candidates(run.workspace)


def test_an_interrupted_run_resumes_and_its_interrupted_request_stays_on_record(tmp_path, site):
    run = Pass(tmp_path, site)
    real_fetch, calls = run.fetcher.fetch, []

    def dying(request, **kwargs):
        calls.append(request.url)
        if len(calls) == 9:
            raise KeyboardInterrupt("process killed")
        return real_fetch(request, **kwargs)

    run.fetcher.fetch = dying
    with pytest.raises(KeyboardInterrupt):
        run.acquire()
    assert acquisition.unfinished_runs(run.workspace.root) == [run.run.run_id]
    interrupted = H.unfinished_requests(run.workspace)
    assert [row["url"] for row in interrupted] == [calls[-1]]
    with pytest.raises(C.NotPreserved):
        run.derive()  # nothing was promoted: nothing may be derived

    run.fetcher.fetch = real_fetch
    site._served.clear()
    run.all()
    assert H.unfinished_requests(run.workspace) == interrupted          # evidence of the interruption is not erased
    assert H.fetched_candidates(run.workspace) == set(H.discovery_tables(run.workspace).candidates)
    assert set(run.states().values()) == {"RAW_PRESERVED"} and len(IdentityTables(run.workspace.identity).documents) == 7


def test_pack_and_promotion_failures_leave_no_false_success(tmp_path, site, monkeypatch):
    run = Pass(tmp_path, site)
    run.acquire()

    def lost(*args, **kwargs):
        raise OSError("share went away")

    with monkeypatch.context() as patched:
        patched.setattr(preservation, "_land", lost)
        with pytest.raises(preservation.PreservationError):
            run.preserve()
    assert set(run.states().values()) == {"PRESERVATION_PENDING"} and files(run.root) == {}
    with pytest.raises(C.NotPreserved):
        run.derive()
    opened = run.workspace.packs / f"{run.pack_id}.warc.gz"
    assert opened.exists()  # sealed in the workspace, still not preserved
    assert run.preserve().action == "promoted" and set(run.states().values()) == {"RAW_PRESERVED"}
    assert len(run.derive()) == 8


def test_a_torn_pack_is_not_sealed_until_the_tail_is_quarantined(tmp_path, site):
    run = Pass(tmp_path, site)
    run.acquire()
    opened = run.workspace.packs / f"{run.pack_id}.warc.gz.open"
    intact = opened.read_bytes()
    opened.write_bytes(intact + b"\x1f\x8b\x08\x00half a record")
    with pytest.raises(pack.PackTornTail):
        run.preserve()
    assert files(run.root) == {} and "RAW_VERIFIED" not in run.states().values()
    sidecar = pack.quarantine_torn_tail(run.workspace.packs, run.pack_id)
    assert sidecar.read_bytes() == b"\x1f\x8b\x08\x00half a record" and opened.read_bytes() == intact
    assert run.preserve().action == "promoted"


def test_a_corrupted_index_or_pack_on_the_preservation_root_is_never_read(done):
    index = done.root / "preservation" / "raw_index" / "uy" / OUTLET / f"{done.pack_id}.index.jsonl"
    original = index.read_bytes()
    index.write_bytes(original.replace(b'"response_offset": ', b'"response_offset": 1', 1))
    with pytest.raises(preservation.PreservationError):
        done.derive()
    with pytest.raises(preservation.PreservationError):
        C.replay_extraction(done.workspace, preservation_root=done.root, identifier=done.pack_id, fetch_id=done.results[0]["fetch_id"])
    index.write_bytes(original)
    master = done.root / done.promotion.relative_path
    data = bytearray(master.read_bytes())
    data[len(data) // 3] ^= 0xFF
    master.write_bytes(bytes(data))
    with pytest.raises(preservation.PreservationError):
        done.derive()
    assert not preservation.verify_master(done.root, "raw", done.pack_id)
    # promotion does not call a damaged master "already preserved": it re-lands the verified
    # workspace copy and reports the repair
    assert done.preserve().action == "repaired" and preservation.verify_master(done.root, "raw", done.pack_id)
    assert done.derive() != []


def test_an_identity_conflict_and_an_extraction_failure_stop_loudly(tmp_path, site, monkeypatch):
    run = Pass(tmp_path, site)
    run.acquire(), run.preserve()

    def broken_extractor(body, **kwargs):
        raise RuntimeError("extractor crashed")

    from coprepan import extraction

    with pytest.raises(RuntimeError):
        run.derive(extractor=extraction.Extractor("baseline_html", "0.1.0", broken_extractor))
    tables = IdentityTables(run.workspace.identity)
    assert len(tables.versions) == 0 and len(tables.documents) == 1  # the document was assigned; no version was invented
    results = run.derive()                                           # the working extractor completes it
    assert len(results) == 8 and len(IdentityTables(run.workspace.identity).versions) == 7

    # a stored extraction that no longer matches its marker is refused, not re-used
    store = run.workspace.layer_store()
    artifact = store.get("extraction", results[0]["extraction_fingerprint"])
    (artifact.directory / "payload").write_bytes(b"{}")
    with pytest.raises(layer_store.LayerStoreError):
        run.derive()
    with pytest.raises(layer_store.LayerStoreError):
        C.replay_extraction(run.workspace, preservation_root=run.root, identifier=run.pack_id, fetch_id=results[0]["fetch_id"])


def test_under_the_tracked_policy_and_identity_nothing_can_be_requested(tmp_path, site):
    """The configuration as committed: undecided policy, unconfigured identity. Fail closed."""
    from coprepan import crawler_identity as CI

    with pytest.raises(CI.CrawlerIdentityNotConfigured):
        CI.load_identity()
    run = Pass(tmp_path, site, policy={**P.load_policy()})
    run.acquire()
    assert site.requests == [] and run.fetcher.transport_calls == 0
    assert run.summary["requests"] == {"channel_document:DENIED": 2} and run.summary["candidates_known"] == 0
    assert not run.workspace.packs.exists() and not run.workspace.ledger_path.exists()
