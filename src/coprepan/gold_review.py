"""Human gold for BODY and CORE, independent of every extractor (CPD-0044; codebook ``gold-body-codebook/1``).

A **gold package** holds stored pages as the reviewer sees them -- the inert original (``body_review.sanitize``) and the
model-independent text view (``docview/1``) -- and nothing a machine decided: no extractor, gate or status runs when a package is
built, and none of their output is in it. Its kind is ``HOLDOUT`` (the independent validation), ``DIAGNOSTIC`` (development
material, not independent) or ``PRACTICE`` (to learn the tool; never scored).

The reviewer labels **text view segments** (a range of them at once) and, where one segment mixes material, **spans** inside a
segment, with the codebook's closed labels; answers per case the state of the source, text visible in the original but absent from
the view, CORE (yes / no / unsure with reasons), page types and a comment; and closes the case, confirming that every unlabelled
segment is not article text. Every answer is an event (``gold-body-event/v1``) bound to the package, the case, the fetch, the raw
body digest and -- for a label -- the digests of the segments it covers; appended and synced; the state replayed from the log.

**Freeze.** When every case is closed, ``freeze`` writes the gold (``gold-body/v1``): the resolved labels by segment index and
character offsets with the segment digests, the case answers, the event log's digest -- **no publisher text** -- and marks the
package frozen (no event is accepted after). Predictions on the package are made only afterwards and only against a gold file that
is committed (``scripts/gold_review.py predict`` checks it). Nothing reads human gold into a pipeline stage.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import body_review as BR
from . import docview

PACKAGE_SCHEMA = "gold-body-package/v1"
CASE_SCHEMA = "gold-body-case/v1"
EVENT_SCHEMA = "gold-body-event/v1"
GOLD_SCHEMA = "gold-body/v1"
CODEBOOK = "gold-body-codebook/1"
KINDS = ("HOLDOUT", "DIAGNOSTIC", "PRACTICE")

LABELS = ("body", "title", "standfirst", "caption", "embed", "foreign", "unsure")
IMPLICIT = "foreign_implicit"                    # an unlabelled segment of a closed case: confirmed not article text
SOURCE_STATES = ("complete", "truncated", "not_visible", "not_an_article_page", "not_assessable")
OUTSIDE_PARTS = ("beginning", "middle", "end")
CORE_LABELS = ("yes", "no", "unsure")
CORE_REASONS = ("too_short", "not_an_article", "live_or_updates", "list_or_service", "mostly_structured", "paywall_or_truncated",
                "sponsored", "not_editorial", "not_spanish", "other")
PAGE_TYPES = BR.PAGE_TYPES
EVENT_KINDS = ("label_range", "span_add", "span_remove", "source_state", "outside_view", "core", "page_types", "comment",
               "finalize", "reopen", "position")
JUDGMENT_KINDS = ("label_range", "span_add", "span_remove", "source_state", "outside_view", "core", "page_types", "comment")
MAX_TEXT = 2000
APP_DIRECTORY = Path(__file__).resolve().parent / "gold_review_app"
_LD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)


class GoldError(ValueError):
    """A refusal: a package that does not verify, an event that does not fit it, a freeze that is not possible."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


# --- the case -------------------------------------------------------------------------------------------------------------


def stated(html: str) -> dict[str, Any]:
    """What the page states about itself in its JSON-LD -- headline, description, articleBody as text -- for the reviewer's
    reference only (never labelled, never a segment). Read here, with no rule of any gate."""
    import html as _h

    found: dict[str, list[str]] = {"headline": [], "description": [], "articleBody": []}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in found:
                if isinstance(node.get(key), str):
                    found[key].append(node[key])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for block in _LD.findall(html or ""):
        try:
            walk(json.loads(block.strip()))
        except ValueError:
            continue

    def text(s: str) -> str:
        s = re.sub(r"<(script|style)\b.*?</\1\s*>", " ", s, flags=re.S | re.I)
        return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]*>", " ", s))).strip()

    return {"headline": text(found["headline"][0]) if found["headline"] else None,
            "description": text(found["description"][0]) if found["description"] else None,
            "article_body": max((text(s) for s in found["articleBody"]), key=len, default=None)}


def case_material(case_id: str, page: Mapping[str, Any], html: str, *, country_id: str) -> tuple[dict[str, Any], str]:
    """The case a reviewer sees, and the inert original. Built from the stored bytes alone."""
    segs = docview.segments(html)
    case = {"schema": CASE_SCHEMA, "case_id": case_id, "fetch_id": page["fetch_id"], "body_sha256": page["body_sha256"],
            "outlet_id": page["outlet_id"], "country_id": country_id, "url": page["url"], "fetched_at": page.get("fetched_at"),
            "view": {"version": docview.VERSION, "sha256": docview.view_sha256(segs), "segments": segs},
            "stated": stated(html)}
    return case, BR.sanitize(html)


def write_package(out_dir: Path, *, kind: str, cases: list[dict[str, Any]], materials: Mapping[str, tuple[dict, str]],
                  design: Mapping[str, Any], meta: Mapping[str, Any], repository: Path | None = None) -> dict[str, Any]:
    """Write a gold package once and freeze its files. ``cases``: ``{"case_id", "fetch_id", ...design fields}``;
    ``materials[fetch_id] = (case, inert html)``; ``design``: the sampling record, kept in ``sealed/design.json`` (never
    served). Refuses a directory inside the repository and one that is not empty."""
    if kind not in KINDS:
        raise GoldError(f"not a package kind: {kind!r}")
    out_dir = out_dir.resolve()
    if repository is not None:
        repo = repository.resolve()
        if out_dir == repo or repo in out_dir.parents:
            raise GoldError(f"{out_dir}: a gold package holds publisher text and is written outside the repository")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise GoldError(f"{out_dir}: not empty -- a package is written once")
    files: dict[str, str] = {}

    def put(relative: str, data: bytes) -> None:
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[relative] = _sha(data)

    listing = []
    for c in sorted(cases, key=lambda c: c["case_id"]):
        case, source = materials[c["fetch_id"]]
        case = {**case, "case_id": c["case_id"]}
        put(f"cases/{c['case_id']}/case.json", (json.dumps(case, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        put(f"cases/{c['case_id']}/source.html", source.encode("utf-8"))
        listing.append({"case_id": c["case_id"], "fetch_id": c["fetch_id"], "body_sha256": case["body_sha256"],
                        "view_sha256": case["view"]["sha256"], "segments": len(case["view"]["segments"])})
    package_id = _sha(_canonical({"kind": kind, "cases": listing, "view": docview.VERSION, "codebook": CODEBOOK}))[:24]
    put("sealed/design.json", (json.dumps({"package_id": package_id, **design, "cases": cases}, ensure_ascii=False, indent=1)
                               + "\n").encode("utf-8"))
    manifest = {"schema": PACKAGE_SCHEMA, "package_id": package_id, "kind": kind, "codebook": CODEBOOK, "view": docview.VERSION,
                "created_at": _now(), "predictions": "none -- no extractor, gate or status ran to build this package", **meta,
                "cases": listing, "case_listing_sha256": _sha(_canonical(listing)), "files": dict(sorted(files.items()))}
    (out_dir / "manifest.json").write_bytes((json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    (out_dir / "judgments").mkdir()
    return manifest


class Package:
    """A gold package, verified file by file when opened."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        path = self.directory / "manifest.json"
        if not path.is_file():
            raise GoldError(f"{self.directory}: no manifest.json")
        self.manifest = json.loads(path.read_text(encoding="utf-8"))
        if self.manifest.get("schema") != PACKAGE_SCHEMA:
            raise GoldError(f"{path}: not a {PACKAGE_SCHEMA} manifest")
        for relative, digest in self.manifest["files"].items():
            file = self.directory / relative
            if not file.is_file() or _sha(file.read_bytes()) != digest:
                raise GoldError(f"{relative}: does not match the frozen package (changed or missing) -- nothing is served")
        self.package_id = self.manifest["package_id"]
        self.kind = self.manifest["kind"]
        self.case_ids = [c["case_id"] for c in self.manifest["cases"]]
        self.cases = {cid: json.loads((self.directory / "cases" / cid / "case.json").read_text(encoding="utf-8")) for cid in self.case_ids}

    def source(self, case_id: str) -> bytes:
        return (self.directory / "cases" / case_id / "source.html").read_bytes()

    def design(self) -> dict[str, Any]:
        return json.loads((self.directory / "sealed" / "design.json").read_text(encoding="utf-8"))

    @property
    def frozen(self) -> dict[str, Any] | None:
        marker = self.directory / "judgments" / "FROZEN.json"
        return json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else None


# --- events --------------------------------------------------------------------------------------------------------------


def _range_digest(case: Mapping[str, Any], first: int, last: int) -> str:
    segs = case["view"]["segments"][first:last + 1]
    return _sha("\n".join(s["sha256"] for s in segs).encode("ascii"))


def check_event(package: Package, event: Mapping[str, Any]) -> dict[str, Any]:
    """An incoming answer made into a stored event, or a refusal."""
    kind, case_id = event.get("kind"), event.get("case_id")
    if kind not in EVENT_KINDS:
        raise GoldError(f"not an event kind: {kind!r}")
    if case_id not in package.cases:
        raise GoldError(f"not a case of this package: {case_id!r}")
    case = package.cases[case_id]
    segs = case["view"]["segments"]
    p = event.get("payload") or {}
    if not isinstance(p, dict):
        raise GoldError("payload must be an object")
    clean: dict[str, Any] = {}
    if kind == "label_range":
        first, last = p.get("from"), p.get("to")
        if not (isinstance(first, int) and isinstance(last, int) and 0 <= first <= last < len(segs)):
            raise GoldError(f"{case_id}: not a segment range: {first!r}..{last!r}")
        if p.get("digest") != _range_digest(case, first, last):
            raise GoldError(f"{case_id}: the range digest does not match the case's segments")
        if p.get("label") not in LABELS + (None,):
            raise GoldError(f"not a label: {p.get('label')!r}")
        clean = {"from": first, "to": last, "digest": p["digest"], "label": p.get("label")}
    elif kind == "span_add":
        i, start, end = p.get("segment"), p.get("start"), p.get("end")
        if not (isinstance(i, int) and 0 <= i < len(segs)):
            raise GoldError(f"{case_id}: not a segment: {i!r}")
        if p.get("sha256") != segs[i]["sha256"]:
            raise GoldError(f"{case_id}: segment {i}: the digest does not match")
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(segs[i]["text"])):
            raise GoldError(f"{case_id}: segment {i}: not a span {start!r}..{end!r}")
        if p.get("label") not in LABELS:
            raise GoldError(f"not a label: {p.get('label')!r}")
        clean = {"span_id": str(uuid.uuid4()), "segment": i, "sha256": segs[i]["sha256"], "start": start, "end": end, "label": p["label"]}
    elif kind == "span_remove":
        clean = {"span_id": str(p.get("span_id") or "")}
    elif kind == "source_state":
        if p.get("value") not in SOURCE_STATES + (None,):
            raise GoldError(f"not a source state: {p.get('value')!r}")
        clean = {"value": p.get("value")}
    elif kind == "outside_view":
        parts, note = p.get("parts") or [], p.get("note") or ""
        if not isinstance(parts, list) or not set(parts) <= set(OUTSIDE_PARTS) or not isinstance(note, str) or len(note) > MAX_TEXT:
            raise GoldError(f"not an outside-view answer: {parts!r}")
        clean = {"parts": sorted(set(parts), key=OUTSIDE_PARTS.index), "note": note.strip()}
    elif kind == "core":
        reasons, note = p.get("reasons") or [], p.get("note") or ""
        if p.get("value") not in CORE_LABELS + (None,) or not isinstance(reasons, list) or not set(reasons) <= set(CORE_REASONS) \
                or not isinstance(note, str) or len(note) > MAX_TEXT:
            raise GoldError(f"not a CORE answer: {p.get('value')!r} {reasons!r}")
        clean = {"value": p.get("value"), "reasons": sorted(set(reasons), key=CORE_REASONS.index), "note": note.strip()}
    elif kind == "page_types":
        values, other = p.get("values") or [], p.get("other") or ""
        if not isinstance(values, list) or not set(values) <= set(PAGE_TYPES) or not isinstance(other, str) or len(other) > MAX_TEXT:
            raise GoldError(f"not a page-type answer: {values!r}")
        clean = {"values": sorted(set(values), key=PAGE_TYPES.index), "other": other.strip()}
    elif kind == "comment":
        text = p.get("text") or ""
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            raise GoldError("a comment is text of at most 2,000 characters")
        clean = {"text": text.strip()}
    elif kind == "finalize":
        if p.get("rest_confirmed") is not True:
            raise GoldError("closing a case confirms that every unlabelled segment is not article text")
        clean = {"rest_confirmed": True}
    return {"kind": kind, "case_id": case_id, "payload": clean}


def _empty() -> dict[str, Any]:
    return {"labels": {}, "spans": {}, "source_state": None, "outside_view": {"parts": [], "note": ""}, "core": None,
            "page_types": {"values": [], "other": ""}, "comment": "", "finalized": False, "reopened": 0, "events": 0,
            "first_at": None, "finalized_at": None, "modes": []}


def fold(package: Package, events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """The current answers per case, replayed from the events in order."""
    state: dict[str, Any] = {cid: _empty() for cid in package.case_ids}
    position = None
    for e in events:
        cid, kind, p = e["case_id"], e["kind"], e["payload"]
        if kind == "position":
            position = cid
            continue
        s = state[cid]
        s["events"] += 1
        s["first_at"] = s["first_at"] or e["at"]
        if e["mode"] not in s["modes"]:
            s["modes"].append(e["mode"])
        if kind == "label_range":
            for i in range(p["from"], p["to"] + 1):
                if p["label"] is None:
                    s["labels"].pop(str(i), None)
                else:
                    s["labels"][str(i)] = p["label"]
        elif kind == "span_add":
            s["spans"][p["span_id"]] = {k: p[k] for k in ("segment", "sha256", "start", "end", "label")}
        elif kind == "span_remove":
            s["spans"].pop(p["span_id"], None)
        elif kind == "source_state":
            s["source_state"] = p["value"]
        elif kind == "outside_view":
            s["outside_view"] = {"parts": p["parts"], "note": p["note"]}
        elif kind == "core":
            s["core"] = {"value": p["value"], "reasons": p["reasons"], "note": p["note"]} if p["value"] else None
        elif kind == "page_types":
            s["page_types"] = {"values": p["values"], "other": p["other"]}
        elif kind == "comment":
            s["comment"] = p["text"]
        elif kind == "finalize":
            s["finalized"], s["finalized_at"] = True, e["at"]
        elif kind == "reopen":
            s["finalized"] = False
            s["reopened"] += 1
    for cid in package.case_ids:
        state[cid]["open_items"] = open_items(state[cid])
    state["_position"] = {"case_id": position}
    return state


def open_items(s: Mapping[str, Any]) -> list[str]:
    out = []
    if not s["source_state"]:
        out.append("source_state")
    if not s["core"]:
        out.append("core")
    elif s["core"]["value"] in ("no", "unsure") and not (s["core"]["reasons"] or s["core"]["note"]):
        out.append("core_reason")
    return out


class Journal:
    """The append-only event log of a package and its folded state; refuses every event once the package is frozen."""

    def __init__(self, package: Package) -> None:
        self.package = package
        self.path = package.directory / "judgments" / "events.jsonl"
        self.lock = threading.Lock()
        self.events, self.torn = self._read()
        self.state = fold(package, self.events)

    def _read(self) -> tuple[list[dict[str, Any]], int]:
        if not self.path.exists():
            return [], 0
        lines = self.path.read_bytes().split(b"\n")
        events, torn = [], 0
        for n, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                if n >= len(lines) - 2:
                    torn += 1                     # an interrupted last write: left out, reported, kept on disk
                    continue
                raise GoldError(f"{self.path}: line {n + 1} is not an event")
            if e.get("schema") != EVENT_SCHEMA or e.get("package_id") != self.package.package_id:
                raise GoldError(f"{self.path}: line {n + 1} belongs to another package")
            events.append(e)
        return events, torn

    def append(self, incoming: Mapping[str, Any]) -> dict[str, Any]:
        with self.lock:
            if self.package.frozen:
                raise GoldError("the gold of this package is frozen -- no answer is accepted any more")
            checked = check_event(self.package, incoming)
            s = self.state[checked["case_id"]]
            if checked["kind"] in JUDGMENT_KINDS and s["finalized"]:
                raise GoldError(f"{checked['case_id']}: closed -- reopen it to change an answer")
            if checked["kind"] == "finalize" and s["open_items"]:
                raise GoldError(f"{checked['case_id']}: not complete: {', '.join(s['open_items'])}")
            case = self.package.cases[checked["case_id"]]
            event = {"schema": EVENT_SCHEMA, "event_id": str(uuid.uuid4()), "seq": len(self.events) + 1, "at": _now(),
                     "package_id": self.package.package_id, "package_kind": self.package.kind, "codebook": CODEBOOK,
                     "case_id": checked["case_id"], "fetch_id": case["fetch_id"], "body_sha256": case["body_sha256"],
                     "view_sha256": case["view"]["sha256"], "mode": "practice" if self.package.kind == "PRACTICE" else "blind",
                     "kind": checked["kind"], "payload": checked["payload"]}
            with self.path.open("ab") as handle:
                handle.write((json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            self.events.append(event)
            self.state = fold(self.package, self.events)
            BR._atomic_write(self.package.directory / "judgments" / "latest.json",
                             json.dumps({"package_id": self.package.package_id, "events": len(self.events), "state": self.state},
                                        ensure_ascii=False, indent=1) + "\n")
            return event


# --- resolution and freeze -----------------------------------------------------------------------------------------------


def resolve(case: Mapping[str, Any], s: Mapping[str, Any]) -> dict[str, Any]:
    """A closed case's labels: every segment's label (unlabelled: ``foreign_implicit``) and the spans that override it."""
    segs = case["view"]["segments"]
    labels = [s["labels"].get(str(i), IMPLICIT) for i in range(len(segs))]
    runs, start = [], 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            runs.append([start, i - 1, labels[start]])
            start = i
    return {"segments": runs, "spans": sorted(s["spans"].values(), key=lambda x: (x["segment"], x["start"]))}


def char_labels(case: Mapping[str, Any], resolved: Mapping[str, Any]) -> list[list[str]]:
    """Per segment, one label per character -- the segment's, overridden by its spans in order."""
    segs = case["view"]["segments"]
    out = []
    by_run = {}
    for first, last, label in resolved["segments"]:
        for i in range(first, last + 1):
            by_run[i] = label
    for i, seg in enumerate(segs):
        out.append([by_run[i]] * len(seg["text"]))
    for span in resolved["spans"]:
        row = out[span["segment"]]
        for k in range(span["start"], min(span["end"], len(row))):
            row[k] = span["label"]
    return out


def freeze(package: Package, journal: Journal, out: Path, *, by: str, case_ids: list[str] | None = None,
           scope: str = "all cases") -> dict[str, Any]:
    """Write the gold and mark the package frozen. Every case of the scope (all, unless ``case_ids`` -- e.g. replicate 1)
    must be closed. The gold holds no publisher text. After the freeze no answer is accepted for any case of the package."""
    if package.kind == "PRACTICE":
        raise GoldError("a practice package is never frozen as gold")
    if package.frozen:
        raise GoldError("already frozen")
    chosen = list(package.case_ids) if case_ids is None else [c for c in package.case_ids if c in set(case_ids)]
    if not chosen:
        raise GoldError("the scope holds no case")
    open_cases = [cid for cid in chosen if not journal.state[cid]["finalized"]]
    if open_cases:
        raise GoldError(f"{len(open_cases)} case(s) not closed: {', '.join(open_cases[:10])}")
    log = journal.path.read_bytes()
    cases = []
    for cid in chosen:
        s, case = journal.state[cid], package.cases[cid]
        cases.append({"case_id": cid, "fetch_id": case["fetch_id"], "body_sha256": case["body_sha256"],
                      "view_sha256": case["view"]["sha256"], "segments_total": len(case["view"]["segments"]),
                      "resolved": resolve(case, s), "source_state": s["source_state"], "outside_view": s["outside_view"],
                      "core": s["core"], "page_types": s["page_types"], "comment": s["comment"], "reopened": s["reopened"],
                      "first_at": s["first_at"], "finalized_at": s["finalized_at"], "modes": s["modes"]})
    gold = {"schema": GOLD_SCHEMA, "codebook": CODEBOOK, "view": docview.VERSION, "package_id": package.package_id,
            "package_kind": package.kind, "case_listing_sha256": package.manifest["case_listing_sha256"], "frozen_at": _now(),
            "frozen_by": by, "events": len(journal.events), "events_sha256": _sha(log), "torn_lines_left_out": journal.torn,
            "scope": {"label": scope, "cases": len(chosen), "of": len(package.case_ids)}, "cases": cases}
    data = (json.dumps(gold, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise GoldError(f"{out}: exists -- gold is written once")
    out.write_bytes(data)
    marker = {"gold_sha256": _sha(data), "gold_file": out.name, "frozen_at": gold["frozen_at"], "frozen_by": by,
              "events_sha256": gold["events_sha256"]}
    BR._atomic_write(package.directory / "judgments" / "FROZEN.json", json.dumps(marker, indent=1) + "\n")
    return marker


def load_gold(package: Package, path: Path) -> dict[str, Any]:
    """The frozen gold of a package, refused unless it is the one the package's freeze marker names, byte for byte."""
    marker = package.frozen
    if marker is None:
        raise GoldError("the package is not frozen")
    data = path.read_bytes()
    if _sha(data) != marker["gold_sha256"]:
        raise GoldError(f"{path}: not the gold this package froze")
    gold = json.loads(data)
    if gold.get("schema") != GOLD_SCHEMA or gold.get("package_id") != package.package_id:
        raise GoldError(f"{path}: not this package's gold")
    return gold


# --- drawing a holdout ----------------------------------------------------------------------------------------------------


def draw_per_outlet(frame: list[Mapping[str, Any]], *, per_outlet: int, seed: int) -> list[dict[str, Any]]:
    """The probability component of a holdout: every outlet of the frame a stratum (taken with certainty), ``per_outlet``
    documents drawn at random without replacement within it (all when it has fewer). Each case carries its exact inclusion
    probability ``n_h / N_h``, the weights of both estimands -- ``weight_documents = N_h / n_h`` (each document of the frame
    once) and ``weight_outlets = 1 / n_h`` (each outlet once) -- and its **replicate** (its place in the outlet's draw order).
    Replicate 1 (one document per outlet) comes first and is a probability sample on its own: stopping after it -- a decision on
    effort, made without any machine output -- leaves an unbiased design (the scoring recomputes the weights from the cases the
    gold holds). ``frame``: ``{"fetch_id", "outlet_id", "country_id"}`` per document; nothing of an extractor is read. Case
    numbers are shuffled within a replicate."""
    import random

    rng = random.Random(seed)
    by_outlet: dict[str, list[str]] = {}
    country = {row["outlet_id"]: row.get("country_id", "unknown") for row in frame}
    for row in sorted(frame, key=lambda r: r["fetch_id"]):
        by_outlet.setdefault(row["outlet_id"], []).append(row["fetch_id"])
    picked = []
    for outlet in sorted(by_outlet):
        ids = by_outlet[outlet]
        n = min(per_outlet, len(ids))
        for replicate, fid in enumerate(rng.sample(ids, n), 1):   # the draw order: replicate 1 is one document per outlet
            picked.append({"fetch_id": fid, "outlet_id": outlet, "country_id": country[outlet], "component": "probability",
                           "stratum": outlet, "replicate": replicate, "frame_size": len(ids), "sampled_in_stratum": n,
                           "inclusion_probability": round(n / len(ids), 6), "weight_documents": len(ids) / n, "weight_outlets": 1.0 / n})
    ordered = []
    for replicate in sorted({c["replicate"] for c in picked}):    # replicate 1 first: it is a complete probability sample alone
        block = [c for c in picked if c["replicate"] == replicate]
        rng.shuffle(block)
        ordered.extend(block)
    for k, case in enumerate(ordered, 1):
        case["case_id"] = f"H{k:03d}"
    return ordered


# --- the server ----------------------------------------------------------------------------------------------------------


def make_server(package: Package, *, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """The reviewer's local server: loopback only, Host and Origin checked, every file verified, answers appended. It has no
    endpoint for any machine output -- a gold package holds none."""
    if host not in ("127.0.0.1", "::1"):
        raise GoldError(f"the reviewer binds a loopback address only, not {host!r}")
    journal = Journal(package)
    assets = {name: (APP_DIRECTORY / name).read_bytes() for name in ("index.html", "app.js", "app.css")}
    types = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "app.css": "text/css; charset=utf-8"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "coprepan-gold-review/1"

        def log_message(self, *args: Any) -> None:
            return

        def _host_ok(self) -> bool:
            port_ = self.server.server_address[1]
            return self.headers.get("Host") in {f"127.0.0.1:{port_}", f"[::1]:{port_}", f"localhost:{port_}"}

        def _send(self, status: int, body: bytes, content_type: str, csp: str = BR.APP_CSP) -> None:
            self.send_response(status)
            for k, v in (("Content-Type", content_type), ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                         ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"), ("Content-Security-Policy", csp)):
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, value: Any) -> None:
            self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._json(HTTPStatus.FORBIDDEN, {"error": "host not allowed"})
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(200, assets["index.html"], types["index.html"])
            if path in ("/app.js", "/app.css"):
                return self._send(200, assets[path[1:]], types[path[1:]])
            if path == "/api/package":
                return self._json(200, {"package_id": package.package_id, "kind": package.kind, "cases": package.case_ids,
                                        "codebook": CODEBOOK, "view": docview.VERSION, "frozen": bool(package.frozen),
                                        "vocabulary": {"labels": LABELS, "source_states": SOURCE_STATES, "outside_parts": OUTSIDE_PARTS,
                                                       "core": CORE_LABELS, "core_reasons": CORE_REASONS, "page_types": PAGE_TYPES},
                                        "torn_lines_left_out": journal.torn})
            if path == "/api/state":
                return self._json(200, journal.state)
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "api" and parts[1] == "case" and parts[2] in package.cases:
                if len(parts) == 3:
                    return self._json(200, package.cases[parts[2]])
                if parts[3:] == ["source"]:
                    return self._send(200, package.source(parts[2]), "text/html; charset=utf-8", csp=BR.SOURCE_CSP)
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok() or self.headers.get("Origin") not in (None, f"http://{self.headers.get('Host')}"):
                return self._json(HTTPStatus.FORBIDDEN, {"error": "host or origin not allowed"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too large"})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "not JSON"})
            if self.path.split("?")[0] != "/api/event":
                return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            try:
                event = journal.append(body)
            except GoldError as error:
                return self._json(HTTPStatus.CONFLICT, {"error": str(error)})
            return self._json(200, {"event": event, "case": journal.state[event["case_id"]]})

    server = ThreadingHTTPServer((host, port), Handler)
    server.journal = journal          # type: ignore[attr-defined]
    return server


__all__ = ["Package", "Journal", "GoldError", "case_material", "write_package", "check_event", "fold", "open_items", "resolve",
           "char_labels", "freeze", "load_gold", "make_server", "stated", "draw_per_outlet", "LABELS", "IMPLICIT", "SOURCE_STATES", "OUTSIDE_PARTS",
           "CORE_LABELS", "CORE_REASONS", "PAGE_TYPES", "KINDS", "CODEBOOK", "PACKAGE_SCHEMA", "GOLD_SCHEMA", "EVENT_SCHEMA"]
