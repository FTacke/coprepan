"""Acquisition run, fetch record and the sealed WARC pack."""

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from coprepan import acquisition as A
from coprepan import pack as P
from coprepan.acquisition import AcquisitionRun, RecordedExchange

T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
OUTLET = "uy_diario_ejemplo"
URL = "https://www.diario-ejemplo.test/Economia/Nota-1.html?utm_source=rss"
HTML = "<html><body><p>Texto con ñ y «comillas».</p></body></html>".encode("utf-8")
HEADERS = (("Content-Type", "text/html; charset=UTF-8"), ("Set-Cookie", "a=1"), ("Set-Cookie", "b=2"))


def run(**overrides):
    arguments = dict(kind="recorded_replay", started_at=T0, outlet_ids=(OUTLET,), discovery_method="recorded_exchanges",
                     software_version="0.2.0", component_versions={"pack_writer": "pack-writer/1"},
                     configuration={"fixture_set": "canary"})
    return AcquisitionRun(**{**arguments, **overrides})


def exchange(url=URL, body=HTML, minutes=0, **overrides):
    arguments = dict(requested_url=url, fetch_started_at=T0 + timedelta(minutes=minutes),
                     fetch_finished_at=T0 + timedelta(minutes=minutes, seconds=1), status=200,
                     response_headers=HEADERS, body=body, channel_id=f"{OUTLET}:ch:rss_001")
    return RecordedExchange(**{**arguments, **overrides})


def failed(url=URL + "&x=1", minutes=5):
    return exchange(url=url, body=None, minutes=minutes, status=None, response_headers=(), failure_reason="timeout")


def fetch(*args, **kwargs):
    item = exchange(*args, **kwargs)
    return A.build_fetch_record(run(), OUTLET, item), item.body


def pack_id():
    return P.pack_id(OUTLET, "20261007")


def filled(tmp_path, items):
    opened = P.OpenPack(tmp_path, pack_id(), opened_at=T0)
    for record, body in items:
        opened.append(record, body)
    return opened


# --- run ------------------------------------------------------------------------------------------


def test_run_id_is_stable_sortable_and_covers_what_was_asked():
    first = run()
    assert first.run_id == run().run_id and A.is_run_id(first.run_id)
    assert first.run_id.startswith("acq1-20261007T120000000000Z-")
    variants = {first.run_id, run(started_at=T0 + timedelta(seconds=1)).run_id,
                run(software_version="0.2.1").run_id, run(configuration={"fixture_set": "other"}).run_id,
                run(discovery_method="other").run_id, run(component_versions={"pack_writer": "pack-writer/2"}).run_id,
                run(outlet_ids=(OUTLET, "uy_otro")).run_id}
    assert len(variants) == 7
    assert run(started_at=T0 + timedelta(hours=1)).run_id > first.run_id


def test_run_record_carries_time_source_method_software_and_configuration():
    record = run().as_record()
    assert record["schema"] == "coprepan-acquisition-run/v1"
    assert record["started_at"] == "2026-10-07T12:00:00.000000Z" and record["outlet_ids"] == [OUTLET]
    assert record["configuration_sha256"] == hashlib.sha256(b'{"fixture_set":"canary"}').hexdigest()
    assert {"kind", "discovery_method", "software_version", "component_versions", "configuration"} <= set(record)


@pytest.mark.parametrize(
    "overrides",
    [{"kind": "live"}, {"outlet_ids": ()}, {"outlet_ids": ("El_Pais",)}, {"outlet_ids": ("uy_b", "uy_a")},
     {"software_version": ""}, {"started_at": datetime(2026, 10, 7)}, {"configuration": {"x": object()}}],
)
def test_a_malformed_run_is_refused(overrides):
    with pytest.raises((A.AcquisitionError, ValueError)):
        run(**overrides)


def test_run_lifecycle_is_written_once_and_an_interrupted_run_is_visible(tmp_path):
    assert A.open_run(tmp_path, run()) is True
    assert A.open_run(tmp_path, run()) is False  # resume
    assert A.unfinished_runs(tmp_path) == [run().run_id]
    result = A.close_run(tmp_path, run(), finished_at=T0 + timedelta(minutes=9), status="COMPLETED",
                         counts={"fetched": 2, "fetch_failed": 1}, pack_ids=[pack_id()])
    assert A.read_run_result(tmp_path, run().run_id) == result and A.unfinished_runs(tmp_path) == []
    assert result["status"] == "COMPLETED" and result["errors"] == []
    with pytest.raises(A.RunStateError):
        A.close_run(tmp_path, run(), finished_at=T0, status="FAILED", counts={}, pack_ids=[])
    with pytest.raises(A.RunStateError):
        A.open_run(tmp_path, run())
    with pytest.raises(A.RunStateError):
        A.close_run(tmp_path, run(started_at=T0 + timedelta(days=1)), finished_at=T0, status="FAILED", counts={}, pack_ids=[])
    with pytest.raises(A.AcquisitionError):
        A.close_run(tmp_path, run(), finished_at=T0, status="DONE", counts={}, pack_ids=[])


# --- fetch record ---------------------------------------------------------------------------------


def test_fetch_record_holds_everything_about_the_retrieval_but_not_the_body():
    record, body = fetch(final_url="https://www.diario-ejemplo.test/Economia/Nota-1.html",
                         redirect_chain=("https://diario-ejemplo.test/Economia/Nota-1.html",),
                         request_headers=(("User-Agent", "fixture"),))
    assert record["schema"] == "coprepan-fetch-record/v1" and record["outcome"] == "FETCHED"
    assert record["body_sha256"] == hashlib.sha256(body).hexdigest() and record["body_size_bytes"] == len(body)
    assert record["request"] == {"method": "GET", "requested_url": URL, "headers": [["User-Agent", "fixture"]]}
    assert record["response"]["status"] == 200 and record["response"]["content_type"] == "text/html"
    assert record["response"]["headers"] == [list(pair) for pair in HEADERS]  # order and repetition kept
    assert record["response"]["final_url"].endswith("Nota-1.html") and len(record["response"]["redirect_chain"]) == 1
    assert record["fetch_started_at"] == "2026-10-07T12:00:00.000000Z"
    assert record["run_id"] == run().run_id and record["outlet_id"] == OUTLET
    assert record["discovery"] == {"channel_id": f"{OUTLET}:ch:rss_001"}
    assert set(record["policy"].values()) == {"not_applicable"}  # a replay consulted no robots.txt
    assert HTML.decode("utf-8") not in json.dumps(record, ensure_ascii=False)
    assert A.validate_fetch_record(record) is record


def test_missing_metadata_is_stated_not_invented():
    record, _ = fetch(response_headers=(), channel_id=None)
    assert record["response"]["content_type"] == "unknown" and record["discovery"] == {"channel_id": "unknown"}
    assert record["response"]["final_url"] == URL  # no redirect recorded: the response came from the requested URL


def test_a_failed_fetch_is_a_record_with_a_reason_and_no_body():
    record = A.build_fetch_record(run(), OUTLET, failed())
    assert (record["outcome"], record["failure_reason"]) == ("FETCH_FAILED", "timeout")
    assert record["body_sha256"] == record["response"]["status"] == "not_applicable"
    assert A.validate_fetch_record(record) is record


def test_the_fetch_id_separates_two_fetches_of_the_same_bytes():
    first, second = fetch()[0], fetch(minutes=30)[0]
    assert first["body_sha256"] == second["body_sha256"] and first["fetch_id"] != second["fetch_id"]
    assert fetch()[0] == first  # the same event described twice is the same record


@pytest.mark.parametrize(
    "overrides",
    [{"status": None}, {"status": 99}, {"status": True}, {"body": "text"}, {"failure_reason": "timeout"},
     {"method": "get"}, {"requested_url": "https://e.test/a b"}, {"final_url": "https://e.test/\n"},
     {"response_headers": (("Bad Name", "x"),)}, {"response_headers": (("X", "a\r\nInjected: 1"),)},
     {"channel_id": "rss"}, {"fetch_finished_at": T0 - timedelta(seconds=1)},
     {"policy": {"robots": "allowed"}}, {"body": None}, {"body": None, "status": None, "response_headers": (), "failure_reason": "tired"}],
)
def test_an_inconsistent_exchange_is_refused(overrides):
    with pytest.raises(A.AcquisitionError):
        A.build_fetch_record(run(), OUTLET, exchange(**overrides))


def test_a_fetch_for_an_outlet_outside_the_run_is_refused():
    with pytest.raises(A.AcquisitionError):
        A.build_fetch_record(run(), "uy_otro", exchange())


def test_a_tampered_fetch_record_no_longer_validates():
    record, _ = fetch()
    for key, value in (("body_sha256", "0" * 64), ("fetch_started_at", "2026-10-07T12:00:01.000000Z")):
        with pytest.raises(A.AcquisitionError):
            A.validate_fetch_record({**record, key: value})
    with pytest.raises(A.AcquisitionError):
        A.validate_fetch_record({**record, "request": {**record["request"], "requested_url": URL + "x"}})


# --- pack -----------------------------------------------------------------------------------------


def test_pack_id_form():
    assert pack_id() == "pk1-uy_diario_ejemplo-20261007-000" and P.is_pack_id(pack_id())
    assert P.pack_outlet(pack_id()) == OUTLET and P.pack_id(OUTLET, "20261007", 12).endswith("-012")
    for bad in (("El_Pais", "20261007"), (OUTLET, "2026-10-07"), (OUTLET, "20261007", 1000)):
        with pytest.raises(P.PackError):
            P.pack_id(*bad)


def test_raw_bytes_survive_the_pack_exactly(tmp_path):
    bodies = [HTML, b"", b"\x00\xff\r\n\r\nWARC/1.1\r\n binary \x1f\x8b", HTML * 3000]
    items = [fetch(url=f"{URL}&n={n}", body=body, minutes=n) for n, body in enumerate(bodies)]
    filled(tmp_path, items)
    manifest = P.seal(tmp_path, pack_id(), sealed_at=T0 + timedelta(hours=1))
    entries = P.read_index(tmp_path, pack_id())
    sealed = tmp_path / f"{pack_id()}.warc.gz"
    assert [P.read_body(sealed, entry) for entry in entries] == bodies
    assert [P.read_fetch_record(sealed, entry) for entry in entries] == [record for record, _ in items]
    assert manifest["fetch_count"] == manifest["fetched_count"] == 4
    assert manifest["pack_sha256"] == hashlib.sha256(sealed.read_bytes()).hexdigest()


def test_a_pack_is_a_readable_warc_file(tmp_path):
    filled(tmp_path, [fetch(), (A.build_fetch_record(run(), OUTLET, failed()), None)])
    P.seal(tmp_path, pack_id(), sealed_at=T0)
    text = gzip.decompress((tmp_path / f"{pack_id()}.warc.gz").read_bytes())  # concatenated members
    assert text.count(b"WARC/1.1\r\n") == 4  # warcinfo, response, metadata, metadata
    assert text.startswith(b"WARC/1.1\r\nWARC-Type: warcinfo\r\n")
    assert b"WARC-Type: response\r\n" in text and b"Content-Type: application/http;msgtype=response\r\n" in text
    assert f"WARC-Payload-Digest: sha256:{hashlib.sha256(HTML).hexdigest()}".encode() in text
    assert b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=UTF-8\r\nSet-Cookie: a=1\r\nSet-Cookie: b=2\r\n\r\n" + HTML in text
    assert f"WARC-Target-URI: {URL}".encode() in text


def test_index_and_manifest_are_pinned(tmp_path):
    record, body = fetch()
    filled(tmp_path, [(record, body), (A.build_fetch_record(run(), OUTLET, failed()), None)])
    manifest = P.seal(tmp_path, pack_id(), sealed_at=T0)
    rows = [json.loads(line) for line in (tmp_path / f"{pack_id()}.index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["outcome"] for row in rows] == ["FETCHED", "FETCH_FAILED"]
    assert rows[0]["fetch_id"] == record["fetch_id"] and rows[0]["body_sha256"] == record["body_sha256"]
    assert rows[1]["body_sha256"] is None and rows[1]["response_offset"] is None
    assert set(manifest) == {"schema", "pack_id", "outlet_id", "utc_day", "container", "writer", "pack_sha256",
                             "pack_size_bytes", "index_sha256", "fetch_count", "fetched_count", "sealed_at"}
    assert manifest["index_sha256"] == hashlib.sha256((tmp_path / f"{pack_id()}.index.jsonl").read_bytes()).hexdigest()
    assert (manifest["fetch_count"], manifest["fetched_count"]) == (2, 1)


def test_the_same_fetches_give_the_same_pack_bytes(tmp_path):
    for name in ("a", "b"):
        filled(tmp_path / name, [fetch(), fetch(minutes=10)])
        P.seal(tmp_path / name, pack_id(), sealed_at=T0)
    assert (tmp_path / "a" / f"{pack_id()}.warc.gz").read_bytes() == (tmp_path / "b" / f"{pack_id()}.warc.gz").read_bytes()


def test_a_sealed_pack_is_never_appended_to_and_sealing_is_idempotent(tmp_path):
    filled(tmp_path, [fetch()])
    manifest = P.seal(tmp_path, pack_id(), sealed_at=T0)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert P.seal(tmp_path, pack_id(), sealed_at=T0 + timedelta(days=1)) == manifest
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    with pytest.raises(P.PackError):
        P.OpenPack(tmp_path, pack_id(), opened_at=T0)
    assert P.verify_sealed(tmp_path, pack_id()) == manifest


def test_a_pack_refuses_what_does_not_belong_in_it(tmp_path):
    opened = filled(tmp_path, [fetch()])
    with pytest.raises(P.DuplicateFetch):
        opened.append(*fetch())
    other_run = run(outlet_ids=(OUTLET, "uy_otro"))
    with pytest.raises(P.PackError):
        opened.append(A.build_fetch_record(other_run, "uy_otro", exchange(minutes=1)), HTML)
    with pytest.raises(P.PackError):
        opened.append(*fetch(minutes=24 * 60))  # next UTC day
    record, _ = fetch(minutes=2)
    with pytest.raises(P.PackError):
        opened.append(record, HTML + b"x")  # not the body the record identifies
    with pytest.raises(P.PackError):
        opened.append(record, None)
    assert len(P.scan(opened.path, pack_id())) == 1


def test_reopening_an_open_pack_continues_it(tmp_path):
    first = filled(tmp_path, [fetch()])
    reopened = P.OpenPack(tmp_path, pack_id(), opened_at=T0 + timedelta(hours=2))
    assert fetch()[0]["fetch_id"] in reopened
    reopened.append(*fetch(minutes=3))
    assert len(P.scan(first.path, pack_id())) == 2


# --- fixity and interruption (robustness) ---------------------------------------------------------


def test_a_changed_sealed_pack_fails_its_fixity_check(tmp_path):
    filled(tmp_path, [fetch(), fetch(minutes=1)])
    P.seal(tmp_path, pack_id(), sealed_at=T0)
    sealed = tmp_path / f"{pack_id()}.warc.gz"
    data = bytearray(sealed.read_bytes())
    data[len(data) // 2] ^= 0xFF
    sealed.write_bytes(bytes(data))
    with pytest.raises(P.PackError):
        P.verify_sealed(tmp_path, pack_id())


def test_an_index_that_does_not_fit_the_stream_is_refused(tmp_path):
    filled(tmp_path, [fetch(), fetch(minutes=1)])
    P.seal(tmp_path, pack_id(), sealed_at=T0)
    sealed = tmp_path / f"{pack_id()}.warc.gz"
    first, second = P.read_index(tmp_path, pack_id())
    crossed = P.PackEntry(**{**first.__dict__, "response_offset": second.response_offset, "response_length": second.response_length})
    with pytest.raises(P.PackError):
        P.read_body(sealed, crossed)  # lands on another fetch's response
    with pytest.raises(P.PackError):
        P.read_body(sealed, P.PackEntry(**{**first.__dict__, "response_offset": first.response_offset + 3}))
    with pytest.raises(P.PackError):
        P.read_fetch_record(sealed, P.PackEntry(**{**first.__dict__, "metadata_offset": second.metadata_offset,
                                                   "metadata_length": second.metadata_length}))
    index = tmp_path / f"{pack_id()}.index.jsonl"
    index.write_bytes(index.read_bytes().replace(first.fetch_id.encode(), second.fetch_id.encode(), 1))
    with pytest.raises(P.PackError):
        P.read_index(tmp_path, pack_id())  # no longer the index the manifest names


@pytest.mark.parametrize("cut", ["inside_response", "between_response_and_fetch_record", "inside_fetch_record"])
def test_an_interrupted_append_is_detected_and_quarantined_not_dropped(tmp_path, cut):
    opened = filled(tmp_path, [fetch()])
    intact = opened.path.read_bytes()
    record, body = fetch(minutes=1)
    members = P.render_fetch(record, body)
    response_length = len(P._record("response", P._record_id(record["fetch_id"], "response"), record["fetch_started_at"],
                                    P._response_block(record, body), "application/http;msgtype=response",
                                    {"WARC-Target-URI": URL, "WARC-Payload-Digest": f"sha256:{record['body_sha256']}"}))
    assert members[:response_length] != members and members[:2] == b"\x1f\x8b"
    torn = {"inside_response": members[: response_length // 2], "between_response_and_fetch_record": members[:response_length],
            "inside_fetch_record": members[: response_length + 20]}[cut]
    opened.path.write_bytes(intact + torn)

    with pytest.raises(P.PackTornTail):
        P.OpenPack(tmp_path, pack_id(), opened_at=T0)
    with pytest.raises(P.PackTornTail):
        P.seal(tmp_path, pack_id(), sealed_at=T0)
    sidecar = P.quarantine_torn_tail(tmp_path, pack_id())
    assert sidecar.read_bytes() == torn and opened.path.read_bytes() == intact
    assert P.quarantine_torn_tail(tmp_path, pack_id()) is None

    resumed = P.OpenPack(tmp_path, pack_id(), opened_at=T0)
    resumed.append(record, body)  # the interrupted fetch is written again, whole
    P.seal(tmp_path, pack_id(), sealed_at=T0)
    assert [entry.fetch_id for entry in P.read_index(tmp_path, pack_id())] == [fetch()[0]["fetch_id"], record["fetch_id"]]


def test_sealing_completes_after_a_crash_between_rename_and_manifest(tmp_path, monkeypatch):
    filled(tmp_path, [fetch()])

    def crash(*args, **kwargs):
        raise OSError("power lost")

    with monkeypatch.context() as patched:
        patched.setattr(P, "write_bytes_atomic", crash)
        with pytest.raises(OSError):
            P.seal(tmp_path, pack_id(), sealed_at=T0)
    assert (tmp_path / f"{pack_id()}.warc.gz").exists() and not (tmp_path / f"{pack_id()}.pack.json").exists()
    assert P.seal(tmp_path, pack_id(), sealed_at=T0)["fetch_count"] == 1


def test_a_file_that_is_not_this_pack_is_refused(tmp_path):
    filled(tmp_path, [fetch()])
    other = P.pack_id(OUTLET, "20261008")
    (tmp_path / f"{pack_id()}.warc.gz.open").rename(tmp_path / f"{other}.warc.gz.open")
    with pytest.raises(P.PackError):
        P.seal(tmp_path, other, sealed_at=T0)
    with pytest.raises(P.PackError):
        P.seal(tmp_path, pack_id(), sealed_at=T0)  # nothing to seal
