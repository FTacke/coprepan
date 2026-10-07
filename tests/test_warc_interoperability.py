"""The pack writer against an independent WARC reader: warcio 1.7.5.

Scope of the claim, exactly: packs written by ``pack-writer/1`` — the record subset it writes
(``warcinfo``, ``response``, ``metadata``; one gzip member per record) — are read by warcio's
``ArchiveIterator`` with digest checking on: every record is found, typed and addressed as
written, and every payload comes back byte for byte. This is interoperability with one reader in
one version for the implemented subset. It is not a statement of WARC conformance in general, and
other tools (indexers, replay systems) have not been tried.

warcio shares no code with ``coprepan.pack``; that it really checks SHA-256 digests is shown by a
record with a wrong digest, which it flags.
"""

import gzip
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
import warcio
from warcio.archiveiterator import ArchiveIterator

from coprepan import acquisition as A
from coprepan import pack as P

T0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
OUTLET = "uy_diario_ejemplo"
URL = "https://www.diario-ejemplo.test/Economia/Nota-1.html"
RUN = A.AcquisitionRun("recorded_replay", T0, (OUTLET,), "recorded_exchanges", "0.3.0", {}, {})
BODIES = [
    "<html><body><p>Texto con ñ y «comillas».</p></body></html>".encode("utf-8"),
    b"",
    b"\x00\xff\r\n\r\nWARC/1.1\r\nWARC-Type: response\r\n\r\n\x1f\x8b\x08 binary that looks like a record",
    gzip.compress(b"<html><body><p>comprimido</p></body></html>", mtime=0),
    b"A" * 300_000,
]
HEADERS = [
    (("Content-Type", "text/html; charset=utf-8"), ("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")),
    (),
    (("Content-Type", "application/octet-stream"),),
    (("Content-Type", "text/html"), ("Content-Encoding", "gzip")),
    (("Content-Type", "text/plain"), ("Transfer-Encoding", "chunked")),
]


def fetches():
    out = []
    for n, (body, headers) in enumerate(zip(BODIES, HEADERS)):
        exchange = A.RecordedExchange(f"{URL}?n={n}&ñ=sí", T0 + timedelta(minutes=n), T0 + timedelta(minutes=n, seconds=1),
                                      status=200 if n != 1 else 404, response_headers=headers, body=body,
                                      final_url=f"{URL}?n={n}", fetch_kind="item" if n else "channel_document")
        out.append((A.build_fetch_record(RUN, OUTLET, exchange), body))
    failed = A.RecordedExchange(f"{URL}/caida", T0 + timedelta(minutes=9), T0 + timedelta(minutes=10), failure_reason="timeout")
    return out + [(A.build_fetch_record(RUN, OUTLET, failed), None)]


@pytest.fixture
def sealed(tmp_path):
    identifier = P.pack_id(OUTLET, "20261007")
    opened = P.OpenPack(tmp_path, identifier, opened_at=T0)
    for record, body in fetches():
        opened.append(record, body)
    manifest = P.seal(tmp_path, identifier, sealed_at=T0 + timedelta(hours=1))
    return tmp_path / f"{identifier}.warc.gz", manifest


def read(path_or_stream):
    stream = open(path_or_stream, "rb") if not hasattr(path_or_stream, "read") else path_or_stream
    with stream:
        out = []
        for item in ArchiveIterator(stream, check_digests=True):
            out.append({
                "type": item.rec_type, "format": item.format,
                "id": item.rec_headers.get_header("WARC-Record-ID"),
                "uri": item.rec_headers.get_header("WARC-Target-URI"),
                "date": item.rec_headers.get_header("WARC-Date"),
                "payload_digest": item.rec_headers.get_header("WARC-Payload-Digest"),
                "concurrent_to": item.rec_headers.get_header("WARC-Concurrent-To"),
                "status": item.http_headers.get_statuscode() if item.http_headers else None,
                "http_headers": list(item.http_headers.headers) if item.http_headers else None,
                "payload": item.raw_stream.read(),
                "digest_passed": item.digest_checker.passed, "digest_problems": list(item.digest_checker.problems),
            })
        return out


def test_the_reader_is_the_pinned_independent_one():
    from importlib.metadata import version

    assert version("warcio") == "1.7.5"
    assert "coprepan" not in (warcio.__file__ or "")


def test_every_record_is_found_typed_and_addressed_as_written(sealed):
    path, manifest = sealed
    records = read(path)
    assert [r["type"] for r in records] == ["warcinfo"] + ["response", "metadata"] * 5 + ["metadata"]
    assert all(r["format"] == "warc" for r in records)
    assert len([r for r in records if r["type"] == "metadata"]) == manifest["fetch_count"] == 6
    assert len([r for r in records if r["type"] == "response"]) == manifest["fetched_count"] == 5
    expected = fetches()
    responses = [r for r in records if r["type"] == "response"]
    for found, (record, _) in zip(responses, expected):
        assert found["uri"] == record["request"]["requested_url"]            # non-ASCII in the URL survives
        assert found["id"] == f"<urn:coprepan:{record['fetch_id']}:response>"
        assert found["date"] == record["fetch_started_at"]
        assert found["payload_digest"] == f"sha256:{record['body_sha256']}"
        assert int(found["status"]) == record["response"]["status"]
    metadata = [r for r in records if r["type"] == "metadata"]
    assert [json.loads(m["payload"]) for m in metadata] == [record for record, _ in expected]
    assert [m["concurrent_to"] for m in metadata[:5]] == [r["id"] for r in responses] and metadata[5]["concurrent_to"] is None


def test_payload_bytes_come_back_exactly(sealed):
    responses = [r for r in read(sealed[0]) if r["type"] == "response"]
    assert [r["payload"] for r in responses] == BODIES
    assert [hashlib.sha256(r["payload"]).hexdigest() for r in responses] == [hashlib.sha256(b).hexdigest() for b in BODIES]


def test_http_headers_are_readable_and_never_ask_the_reader_to_de_chunk(sealed):
    responses = [r for r in read(sealed[0]) if r["type"] == "response"]
    assert responses[0]["http_headers"] == [("Content-Type", "text/html; charset=utf-8"), ("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")]
    assert responses[1]["http_headers"] == [] and responses[1]["status"] == "404"
    assert responses[3]["http_headers"] == [("Content-Type", "text/html"), ("Content-Encoding", "gzip")]  # content coding as sent
    assert responses[4]["http_headers"] == [("Content-Type", "text/plain"), ("X-Coprepan-Orig-Transfer-Encoding", "chunked")]
    # the fetch record still has the header exactly as received
    assert fetches()[4][0]["response"]["headers"] == [["Content-Type", "text/plain"], ["Transfer-Encoding", "chunked"]]


def test_the_reader_decodes_a_content_coded_body_to_the_same_text(sealed):
    with open(sealed[0], "rb") as stream:
        decoded = [item.content_stream().read() for item in ArchiveIterator(stream) if item.rec_type == "response"]
    assert decoded[3] == b"<html><body><p>comprimido</p></body></html>" and decoded[4] == BODIES[4]


def test_digests_are_really_checked_by_the_reader(sealed):
    records = read(sealed[0])
    assert all(r["digest_passed"] is True and r["digest_problems"] == [] for r in records)
    record, body = fetches()[0]
    lying = P._record("response", "urn:coprepan:test:response", record["fetch_started_at"], P._response_block(record, body),
                      "application/http;msgtype=response",
                      {"WARC-Target-URI": URL, "WARC-Payload-Digest": "sha256:" + "0" * 64})
    flagged = read(io.BytesIO(lying))
    assert flagged[0]["digest_passed"] is False and flagged[0]["digest_problems"]
    assert flagged[0]["payload"] == body  # the bytes are still delivered; the reader reports, it does not hide


def test_a_pack_cut_short_is_caught_by_the_manifest_not_by_the_reader(sealed, tmp_path):
    """A finding, kept as a test: warcio reads a truncated pack without complaint and simply
    returns less. Interoperability is therefore no substitute for fixity — a pack is trusted
    because its bytes hash to its manifest, and this repository's own scan refuses a torn tail.
    """
    path, _ = sealed
    whole = read(path)
    data = path.read_bytes()
    cut = read(io.BytesIO(data[: len(data) - 40]))  # no exception from the independent reader
    assert cut != whole and len(cut) <= len(whole)
    path.write_bytes(data[: len(data) - 40])
    with pytest.raises(P.PackError):
        P.verify_sealed(tmp_path, P.pack_id(OUTLET, "20261007"))
    with pytest.raises(P.PackTornTail):
        P.scan(path, P.pack_id(OUTLET, "20261007"))


def test_both_readers_agree_on_the_sealed_pack(sealed, tmp_path):
    """The repository's own index against warcio's reading of the same file."""
    identifier = P.pack_id(OUTLET, "20261007")
    own = {entry.fetch_id: P.read_body(sealed[0], entry) for entry in P.read_index(tmp_path, identifier) if entry.body_sha256}
    theirs = {r["id"].split("urn:coprepan:")[1].rsplit(":response>", 1)[0]: r["payload"] for r in read(sealed[0]) if r["type"] == "response"}
    assert own == theirs and len(own) == 5
