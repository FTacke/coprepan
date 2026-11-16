"""The local BODY review (CPD-0043): a frozen package of stored pages, a browser reviewer on a loopback server, the operator's
judgments as an append-only event log, a validated export and a scoring against the sealed machine labels.

**What a package is.** ``prepare`` draws cases from the stored pages (a stratified random component and a targeted one), runs the
preferred extractor and gates, and writes, outside the repository:

* ``manifest.json`` -- the package identity (``package_id``: the digest of the case list), the versions, the sampling plan, its
  seed and the population counts, and the SHA-256 of every file in the package. The server verifies every file before it
  serves a case; a changed file is a refusal, never a repair.
* ``cases/<case_id>/case.json`` -- what the reviewer sees: the outlet, country, address and dates, the title surface, the
  candidate blocks in page order **without** their machine roles (the BODY, the blocks the selection decided, and the text blocks
  around them), and every text block of the page for the full source text view.
* ``cases/<case_id>/source.html`` -- the stored publisher page made inert (:func:`sanitize`): no script, frame, object, form
  control, link target, image source or any other address; served with a Content-Security-Policy that allows no request at all
  and shown in a sandboxed frame that runs no script.
* ``sealed/key.json`` -- the machine labels (role and reason of every shown block, the CORE decision and its reasons, the
  BODY status) and why each case was drawn. The reviewer sees a case's machine labels only after closing that case (or in an
  explicitly separate diagnostic mode, whose judgments are marked and never scored as gold).

**Judgments.** Every answer is an event in ``judgments/events.jsonl`` (appended and synced), each bound to the package, the case,
the fetch, the raw body digest, the extractor version and -- for a block -- the block index and the SHA-256 of its text; the
current state is folded from the log (``judgments/latest.json`` is a convenience copy, written atomically). A correction is a
new event. A case answered again after its machine labels were shown is marked ``revised_after_reveal`` and is not blind.
Nothing recomputes or rewrites a judgment; :func:`score` reads the frozen key.

No network: the server binds a loopback address only and checks the Host header. Publisher text stays in the package, outside
the repository.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import math
import os
import random
import re
import threading
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import extraction as E

PACKAGE_SCHEMA = "coprepan-body-review-package/v1"
CASE_SCHEMA = "coprepan-body-review-case/v1"
KEY_SCHEMA = "coprepan-body-review-key/v1"
EVENT_SCHEMA = "coprepan-body-review-event/v1"
EXPORT_SCHEMA = "coprepan-body-review-judgments/v1"
RESULT_SCHEMA = "coprepan-body-review-result/v1"

BLOCK_LABELS = ("article", "foreign", "unsure")
TITLE_LABELS = ("correct", "wrong", "unsure")
COMPLETENESS = ("complete", "beginning_missing", "middle_missing", "end_missing", "not_assessable")
MISSING_PARTS = ("beginning_missing", "middle_missing", "end_missing")
CORE_LABELS = ("yes", "no", "unsure")
PAGE_TYPES = ("news_report", "opinion", "interview", "feature", "live_ticker", "preview_or_service", "recipe_or_howto",
              "sports_with_tables", "list_or_ranking", "gallery_or_video", "agency_wire", "sponsored_or_press_release",
              "paywall_or_teaser", "section_or_index_page", "not_an_article")
EVENT_KINDS = ("label_block", "title", "completeness", "missing_add", "missing_remove", "core", "page_types", "comment",
               "finalize", "reopen", "position", "reveal")
JUDGMENT_KINDS = ("label_block", "title", "completeness", "missing_add", "missing_remove", "core", "page_types", "comment")
MAX_QUOTE_CHARACTERS = 4000
MAX_TEXT_CHARACTERS = 2000
CONTEXT_BLOCKS = 3                 # text blocks shown before the first and after the last machine candidate
SOURCE_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri 'none'"
APP_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
           "frame-src 'self'; base-uri 'none'; form-action 'none'")
APP_DIRECTORY = Path(__file__).resolve().parent / "body_review_app"
_ALNUM = re.compile(r"[^\W_]", re.UNICODE)


class ReviewError(ValueError):
    """A refusal: a package that does not verify, an event that does not fit the package, an export that does not validate."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_sha256(text: str) -> str:
    return _sha(text.encode("utf-8"))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def fold_text(text: str) -> str:
    """The comparison form of a quote or a block: NFC, white space folded, lower case. For scoring only."""
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text.replace("\xa0", " "))).strip().lower()


# --- making a publisher page inert ----------------------------------------------------------------------------------------------

_DROP_WITH_CONTENT = frozenset({"script", "noscript", "iframe", "frame", "frameset", "object", "embed", "applet", "template",
                                "svg", "math", "video", "audio", "canvas", "select", "textarea", "button", "xmp", "plaintext",
                                "title", "dialog", "portal"})
_DROP_VOID = frozenset({"link", "meta", "base", "input", "source", "track", "param", "keygen", "img", "image", "picture", "area",
                        "map", "wbr"})
_UNWRAP = frozenset({"html", "head", "body", "form", "picture"})
_VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
_KEEP_ATTRIBUTES = frozenset({"class", "id", "style", "lang", "dir", "colspan", "rowspan", "hidden", "datetime", "headers", "scope"})
_STYLE_URL = re.compile(r"url\s*\(|expression\s*\(|@import|behavior\s*:|-moz-binding", re.I)
_BASE_STYLE = ("body{font:16px/1.5 Georgia,serif;margin:16px;color:#111;background:#fff;max-width:60rem}"
               "a{color:#1a4fa0;text-decoration:underline}.cpp-img{display:inline-block;border:1px dashed #999;color:#666;"
               "font:12px sans-serif;padding:2px 6px;margin:2px}")


class _Inert(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip: list[str] = []
        self.styles: list[str] = []
        self.in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip:
            if tag == self.skip[-1] and tag not in _VOID:
                self.skip.append(tag)
            return
        if tag in _DROP_WITH_CONTENT:
            if tag not in _VOID:
                self.skip.append(tag)
            return
        if tag == "style":
            self.in_style = True
            return
        if tag in ("img", "image"):
            alt = next((v for k, v in attrs if k.lower() == "alt" and v), "")
            self.out.append(f'<span class="cpp-img">[{_html.escape("Bild: " + alt if alt else "Bild")}]</span>')
            return
        if tag in _DROP_VOID or tag in _UNWRAP or not re.fullmatch(r"[a-z][a-z0-9-]*", tag):
            return
        kept = []
        for name, value in attrs:
            name = name.lower()
            if name not in _KEEP_ATTRIBUTES:
                continue
            value = value or ""
            if name == "style" and _STYLE_URL.search(value):
                continue
            kept.append(f' {name}="{_html.escape(value, quote=True)}"')
        self.out.append(f"<{tag}{''.join(kept)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in _DROP_WITH_CONTENT or name == "style":       # "<iframe/>", "<style/>": nothing opens, nothing to skip
            return
        self.handle_starttag(tag, attrs)
        if name not in _VOID and not self.skip and name not in _DROP_VOID | _UNWRAP | {"image"} \
                and re.fullmatch(r"[a-z][a-z0-9-]*", name):
            self.out.append(f"</{name}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag == "style":
            self.in_style = False
            return
        if tag in _DROP_WITH_CONTENT or tag in _DROP_VOID or tag in _UNWRAP or tag in _VOID \
                or not re.fullmatch(r"[a-z][a-z0-9-]*", tag):
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.in_style:
            if not _STYLE_URL.search(data):
                self.styles.append(data.replace("</", "<\\/"))
            return
        self.out.append(_html.escape(data, quote=False))


def sanitize(html: str) -> str:
    """The page made inert, for display only: every script, frame, object, embed, form control and media element dropped with
    its content; every attribute dropped but class, id, style (without ``url()``), lang, dir and table spans -- so no link
    target, image source, event handler or any other address survives; images shown as their alt text. Inline styles are kept
    for the page's look. The result carries its own Content-Security-Policy that allows no request."""
    parser = _Inert()
    parser.feed(html or "")
    parser.close()
    style = "".join(parser.styles)
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{SOURCE_CSP}">'
            f"<style>{_BASE_STYLE}</style><style>{style}</style></head><body>{''.join(parser.out)}</body></html>")


# --- the cases ---------------------------------------------------------------------------------------------------------------


def shown_blocks(record: Mapping[str, Any]) -> list[int]:
    """The candidate blocks a reviewer labels, in page order: every BODY block, every block the selection decided, and every
    block with text between the first and the last of them, with ``CONTEXT_BLOCKS`` text blocks before and after. Title
    surface blocks are judged apart. The machine role of a block is never part of the case."""
    blocks = record["blocks"]
    texty = [b["index"] for b in blocks if _ALNUM.search(b["text"]) and b["role"] != E.ROLE_TITLE]
    anchors = [b["index"] for b in blocks if b["role"] == E.ROLE_BODY or b.get("selection")]
    if not anchors:
        return []
    first, last = min(anchors), max(anchors)
    inside = [i for i in texty if first <= i <= last]
    before = [i for i in texty if i < first][-CONTEXT_BLOCKS:]
    after = [i for i in texty if i > last][:CONTEXT_BLOCKS]
    return sorted(set(before + inside + after + anchors))


def case_material(case_id: str, page: Mapping[str, Any], record: Mapping[str, Any], *, country_id: str,
                  extractor: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """The blind case (what the reviewer sees) and the machine side of the key for one drawn page."""
    blocks = record["blocks"]
    by_index = {b["index"]: b for b in blocks}
    shown = shown_blocks(record)
    metadata = record.get("metadata") or {}
    published = (metadata.get("publication_date") or {}).get("value")
    case = {
        "schema": CASE_SCHEMA, "case_id": case_id, "fetch_id": page["fetch_id"], "body_sha256": page["body_sha256"],
        "extractor": extractor, "outlet_id": page["outlet_id"], "country_id": country_id, "url": page["url"],
        "fetched_at": page.get("fetched_at"), "published": published if published not in (None, E.UNKNOWN) else None,
        "title_blocks": [{"index": b["index"], "kind": b["kind"], "text": b["text"], "text_sha256": text_sha256(b["text"])}
                         for b in blocks if b["role"] == E.ROLE_TITLE],
        "blocks": [{"n": n, "index": i, "kind": by_index[i]["kind"], "text": by_index[i]["text"],
                    "text_sha256": text_sha256(by_index[i]["text"])} for n, i in enumerate(shown, 1)],
        "page_text": [{"index": b["index"], "kind": b["kind"], "text": b["text"]} for b in blocks if _ALNUM.search(b["text"])],
    }
    machine = {"blocks": {str(i): {"role": by_index[i]["role"], "reason": (by_index[i].get("selection") or {}).get("reason"),
                                   "decision": (by_index[i].get("selection") or {}).get("decision")} for i in shown},
               "title_blocks": [b["index"] for b in blocks if b["role"] == E.ROLE_TITLE],
               "body_text_sha256": record.get("body_text_sha256"),
               "body_text": E.body_text(blocks)}
    return case, machine


def _largest_remainder(sizes: Mapping[str, int], n: int) -> dict[str, int]:
    total = sum(sizes.values())
    if total == 0 or n <= 0:
        return {k: 0 for k in sizes}
    exact = {k: n * v / total for k, v in sizes.items()}
    out = {k: min(sizes[k], math.floor(x)) for k, x in exact.items()}
    for k in sorted(sizes, key=lambda k: (-(exact[k] - math.floor(exact[k])), k)):
        if sum(out.values()) >= n:
            break
        if out[k] < sizes[k]:
            out[k] += 1
    return out


def draw(rows: list[Mapping[str, Any]], *, random_n: int, targeted: Mapping[str, int], strata: Mapping[str, Any],
         seed: int) -> list[dict[str, Any]]:
    """The cases of a package. ``rows``: one per eligible page, ``{"fetch_id", "country_id", ...}``. The random component is a
    stratified simple random sample by country, proportional allocation (largest remainder); each case carries its exact
    inclusion probability ``n_h / N_h``. The targeted component draws ``targeted[name]`` pages at random from each named stratum
    (``strata[name]``: a predicate on a row; a page counts in the first stratum it meets, in the plan's order) among the pages
    the random component did not take; its cases carry no population weight. The order of the cases is shuffled, so a case's
    number says nothing about why it was drawn."""
    rng = random.Random(seed)
    by_country: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["fetch_id"]):
        by_country[r["country_id"]].append(r)
    allocation = _largest_remainder({k: len(v) for k, v in by_country.items()}, random_n)
    picked: list[dict[str, Any]] = []
    taken: set[str] = set()
    for country in sorted(by_country):
        members = by_country[country]
        for r in rng.sample(members, allocation[country]):
            picked.append({"fetch_id": r["fetch_id"], "component": "random", "stratum": f"country:{country}",
                           "inclusion_probability": round(allocation[country] / len(members), 6)})
            taken.add(r["fetch_id"])
    first: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["fetch_id"]):
        if r["fetch_id"] in taken:
            continue
        name = next((s for s in targeted if strata[s](r)), None)
        if name is not None:
            first[name].append(r)
    for name, quota in targeted.items():
        for r in rng.sample(first[name], min(quota, len(first[name]))):
            picked.append({"fetch_id": r["fetch_id"], "component": "targeted", "stratum": name, "inclusion_probability": None,
                           "stratum_size": len(first[name])})
    rng.shuffle(picked)
    for n, case in enumerate(picked, 1):
        case["case_id"] = f"P{n:03d}"
    return picked


def write_package(out_dir: Path, *, cases: list[dict[str, Any]], materials: Mapping[str, tuple[dict, dict, str]],
                  meta: Mapping[str, Any], repository: Path | None = None) -> dict[str, Any]:
    """Write a package and freeze it. ``materials[fetch_id] = (case, machine, inert source html)``. Refuses a directory inside
    the repository (publisher text never enters it) and a directory that is not empty (a package is written once)."""
    out_dir = out_dir.resolve()
    if repository is not None:
        repo = repository.resolve()
        if out_dir == repo or repo in out_dir.parents:
            raise ReviewError(f"{out_dir}: a review package holds publisher text and is written outside the repository")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ReviewError(f"{out_dir}: not empty -- a package is written once")
    files: dict[str, str] = {}

    def put(relative: str, data: bytes) -> None:
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[relative] = _sha(data)

    key_cases = []
    listing = []
    for c in sorted(cases, key=lambda c: c["case_id"]):
        case, machine, source = materials[c["fetch_id"]]
        case = {**case, "case_id": c["case_id"]}
        put(f"cases/{c['case_id']}/case.json", (json.dumps(case, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        put(f"cases/{c['case_id']}/source.html", source.encode("utf-8"))
        key_cases.append({"case_id": c["case_id"], "fetch_id": c["fetch_id"], "component": c["component"], "stratum": c["stratum"],
                          "inclusion_probability": c["inclusion_probability"], "stratum_size": c.get("stratum_size"),
                          "machine": machine})
        listing.append({"case_id": c["case_id"], "fetch_id": c["fetch_id"], "body_sha256": case["body_sha256"],
                        "blocks": [[b["index"], b["text_sha256"]] for b in case["blocks"]],
                        "title_blocks": [[b["index"], b["text_sha256"]] for b in case["title_blocks"]]})
    package_id = _sha(_canonical({"cases": listing, "extractor": meta.get("versions", {}).get("extractor")}))[:24]
    put("sealed/key.json", (json.dumps({"schema": KEY_SCHEMA, "package_id": package_id, "cases": key_cases}, ensure_ascii=False,
                                       indent=1) + "\n").encode("utf-8"))
    manifest = {"schema": PACKAGE_SCHEMA, "package_id": package_id, "created_at": _now(), **meta,
                "cases": [{"case_id": x["case_id"], "fetch_id": x["fetch_id"], "body_sha256": x["body_sha256"],
                           "shown_blocks": len(x["blocks"])} for x in listing],
                "case_listing_sha256": _sha(_canonical(listing)), "files": dict(sorted(files.items()))}
    (out_dir / "manifest.json").write_bytes((json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    (out_dir / "judgments").mkdir()
    return manifest


# --- the package, verified -----------------------------------------------------------------------------------------------


class Package:
    """A frozen package, verified file by file when opened."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        path = self.directory / "manifest.json"
        if not path.is_file():
            raise ReviewError(f"{self.directory}: no manifest.json")
        self.manifest = json.loads(path.read_text(encoding="utf-8"))
        if self.manifest.get("schema") != PACKAGE_SCHEMA:
            raise ReviewError(f"{path}: not a {PACKAGE_SCHEMA} manifest")
        for relative, digest in self.manifest["files"].items():
            file = self.directory / relative
            if not file.is_file() or _sha(file.read_bytes()) != digest:
                raise ReviewError(f"{relative}: does not match the frozen package (changed or missing) -- nothing is served")
        self.package_id = self.manifest["package_id"]
        self.case_ids = [c["case_id"] for c in self.manifest["cases"]]
        self.cases = {cid: json.loads((self.directory / "cases" / cid / "case.json").read_text(encoding="utf-8"))
                      for cid in self.case_ids}
        self._key: dict[str, Any] | None = None

    def key(self) -> dict[str, Any]:
        if self._key is None:
            data = json.loads((self.directory / "sealed" / "key.json").read_text(encoding="utf-8"))
            if data.get("schema") != KEY_SCHEMA or data.get("package_id") != self.package_id:
                raise ReviewError("sealed/key.json: not this package's key")
            self._key = {c["case_id"]: c for c in data["cases"]}
        return self._key

    def source(self, case_id: str) -> bytes:
        return (self.directory / "cases" / case_id / "source.html").read_bytes()


# --- events -------------------------------------------------------------------------------------------------------------


def check_event(package: Package, event: Mapping[str, Any]) -> dict[str, Any]:
    """An incoming answer made into a stored event, or a refusal: the case must be the package's, the block one the case shows
    (with the text digest the case gives), every value in its closed vocabulary."""
    kind, case_id = event.get("kind"), event.get("case_id")
    if kind not in EVENT_KINDS or kind == "reveal":
        raise ReviewError(f"not an event kind: {kind!r}")
    if case_id not in package.cases:
        raise ReviewError(f"not a case of this package: {case_id!r}")
    case = package.cases[case_id]
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        raise ReviewError("payload must be an object")
    clean: dict[str, Any] = {}
    if kind == "label_block":
        block = next((b for b in case["blocks"] if b["index"] == payload.get("index")), None)
        if block is None:
            raise ReviewError(f"{case_id}: block {payload.get('index')!r} is not one the case shows")
        if payload.get("text_sha256") != block["text_sha256"]:
            raise ReviewError(f"{case_id}: block {block['index']}: the text digest does not match the case")
        if payload.get("label") not in BLOCK_LABELS + (None,):
            raise ReviewError(f"not a block label: {payload.get('label')!r}")
        clean = {"index": block["index"], "text_sha256": block["text_sha256"], "label": payload.get("label")}
    elif kind == "title":
        if payload.get("label") not in TITLE_LABELS + (None,):
            raise ReviewError(f"not a title label: {payload.get('label')!r}")
        clean = {"label": payload.get("label")}
    elif kind == "completeness":
        values = payload.get("values")
        if not isinstance(values, list) or not set(values) <= set(COMPLETENESS) or len(set(values)) != len(values):
            raise ReviewError(f"not a completeness answer: {values!r}")
        if len(values) > 1 and set(values) - set(MISSING_PARTS):
            raise ReviewError("'complete' and 'not_assessable' stand alone; only missing parts combine")
        clean = {"values": sorted(values, key=COMPLETENESS.index)}
    elif kind == "missing_add":
        quote = payload.get("quote")
        if not isinstance(quote, str) or not quote.strip() or len(quote) > MAX_QUOTE_CHARACTERS:
            raise ReviewError("a missing-text mark needs the marked text (at most 4,000 characters)")
        if payload.get("view") not in ("original", "page_text"):
            raise ReviewError("a missing-text mark names the view it was made in")
        clean = {"mark_id": str(uuid.uuid4()), "quote": quote.strip(), "quote_sha256": text_sha256(fold_text(quote)),
                 "view": payload["view"], "part": payload.get("part") if payload.get("part") in MISSING_PARTS else None}
    elif kind == "missing_remove":
        clean = {"mark_id": str(payload.get("mark_id") or "")}
    elif kind == "core":
        if payload.get("value") not in CORE_LABELS + (None,):
            raise ReviewError(f"not a CORE answer: {payload.get('value')!r}")
        reason = payload.get("reason") or ""
        if not isinstance(reason, str) or len(reason) > MAX_TEXT_CHARACTERS:
            raise ReviewError("a CORE reason is text of at most 2,000 characters")
        clean = {"value": payload.get("value"), "reason": reason.strip()}
    elif kind == "page_types":
        values, other = payload.get("values") or [], payload.get("other") or ""
        if not isinstance(values, list) or not set(values) <= set(PAGE_TYPES) or not isinstance(other, str) \
                or len(other) > MAX_TEXT_CHARACTERS:
            raise ReviewError(f"not a page-type answer: {values!r}")
        clean = {"values": sorted(set(values), key=PAGE_TYPES.index), "other": other.strip()}
    elif kind == "comment":
        text = payload.get("text") or ""
        if not isinstance(text, str) or len(text) > MAX_TEXT_CHARACTERS:
            raise ReviewError("a comment is text of at most 2,000 characters")
        clean = {"text": text.strip()}
    return {"kind": kind, "case_id": case_id, "payload": clean}


def fold(package: Package, events: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """The current answers per case, replayed from the events in order."""
    state: dict[str, dict[str, Any]] = {cid: {"blocks": {}, "title": None, "completeness": None, "missing": {}, "core": None,
                                              "page_types": {"values": [], "other": ""}, "comment": "", "finalized": False,
                                              "revealed": False, "revised_after_reveal": False, "events": 0,
                                              "first_at": None, "finalized_at": None}
                                        for cid in package.case_ids}
    position = None
    for e in events:
        cid, kind, p = e["case_id"], e["kind"], e["payload"]
        s = state[cid]
        if kind == "position":
            position = cid
            continue
        if kind == "reveal":
            s["revealed"] = True
            continue
        s["events"] += 1
        s["first_at"] = s["first_at"] or e["at"]
        if kind in JUDGMENT_KINDS and s["revealed"]:
            s["revised_after_reveal"] = True
        if kind == "label_block":
            if p["label"] is None:
                s["blocks"].pop(str(p["index"]), None)
            else:
                s["blocks"][str(p["index"])] = p["label"]
        elif kind == "title":
            s["title"] = p["label"]
        elif kind == "completeness":
            s["completeness"] = p["values"] or None
        elif kind == "missing_add":
            s["missing"][p["mark_id"]] = {k: p[k] for k in ("quote", "quote_sha256", "view", "part")}
        elif kind == "missing_remove":
            s["missing"].pop(p["mark_id"], None)
        elif kind == "core":
            s["core"] = {"value": p["value"], "reason": p["reason"]} if p["value"] else None
        elif kind == "page_types":
            s["page_types"] = {"values": p["values"], "other": p["other"]}
        elif kind == "comment":
            s["comment"] = p["text"]
        elif kind == "finalize":
            s["finalized"], s["finalized_at"] = True, e["at"]
        elif kind == "reopen":
            s["finalized"] = False
    for cid, s in state.items():
        s["open_items"] = open_items(package.cases[cid], s)
    state["_position"] = {"case_id": position}
    return state


def open_items(case: Mapping[str, Any], s: Mapping[str, Any]) -> list[str]:
    """What a case still needs before it can be closed."""
    out = []
    unlabelled = [b["n"] for b in case["blocks"] if str(b["index"]) not in s["blocks"]]
    if unlabelled:
        out.append(f"blocks_unlabelled:{len(unlabelled)}")
    if case["title_blocks"] and s["title"] is None:
        out.append("title")
    if not s["completeness"]:
        out.append("completeness")
    if not s["core"]:
        out.append("core")
    elif s["core"]["value"] in ("no", "unsure") and not s["core"]["reason"]:
        out.append("core_reason")
    return out


class Journal:
    """The append-only event log of a package and its folded state. One writer (the server holds the lock)."""

    def __init__(self, package: Package, *, diagnostic: bool = False) -> None:
        self.package = package
        self.diagnostic = diagnostic
        self.path = package.directory / "judgments" / "events.jsonl"
        self.path.parent.mkdir(exist_ok=True)
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
                if n >= len(lines) - 2:          # a torn last line (an interrupted write): left out, reported, kept on disk
                    torn += 1
                    continue
                raise ReviewError(f"{self.path}: line {n + 1} is not an event -- the log is not this tool's")
            if e.get("schema") != EVENT_SCHEMA or e.get("package_id") != self.package.package_id:
                raise ReviewError(f"{self.path}: line {n + 1} belongs to another package")
            events.append(e)
        return events, torn

    def append(self, incoming: Mapping[str, Any]) -> dict[str, Any]:
        with self.lock:
            if incoming.get("kind") == "reveal":
                checked = {"kind": "reveal", "case_id": incoming["case_id"], "payload": {}}
            else:
                checked = check_event(self.package, incoming)
            s = self.state[checked["case_id"]]
            if checked["kind"] in JUDGMENT_KINDS and s["finalized"]:
                raise ReviewError(f"{checked['case_id']}: closed -- reopen it to change an answer")
            if checked["kind"] == "finalize" and s["open_items"]:
                raise ReviewError(f"{checked['case_id']}: not complete: {', '.join(s['open_items'])}")
            case = self.package.cases[checked["case_id"]]
            event = {"schema": EVENT_SCHEMA, "event_id": str(uuid.uuid4()), "seq": len(self.events) + 1, "at": _now(),
                     "package_id": self.package.package_id, "case_id": checked["case_id"], "fetch_id": case["fetch_id"],
                     "body_sha256": case["body_sha256"], "extractor": case["extractor"],
                     "mode": "diagnostic" if self.diagnostic else "blind", "revealed": s["revealed"],
                     "kind": checked["kind"], "payload": checked["payload"]}
            line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            with self.path.open("ab") as handle:
                handle.write(line.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            self.events.append(event)
            self.state = fold(self.package, self.events)
            _atomic_write(self.package.directory / "judgments" / "latest.json",
                          json.dumps({"package_id": self.package.package_id, "events": len(self.events), "state": self.state},
                                     ensure_ascii=False, indent=1) + "\n")
            return event


def _atomic_write(path: Path, text: str) -> None:
    part = path.with_name(path.name + ".part")
    with part.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(part, path)


# --- export, validation, scoring ---------------------------------------------------------------------------------------


def export(package: Package, journal: Journal) -> dict[str, Any]:
    """The operator's judgments as one validated document: every closed case with its answers bound to the case's identities,
    whether it was answered blind, and the digest of the event log it was folded from."""
    log = journal.path.read_bytes() if journal.path.exists() else b""
    cases = []
    for cid in package.case_ids:
        s, case = journal.state[cid], package.cases[cid]
        if not s["finalized"]:
            continue
        modes = {e["mode"] for e in journal.events if e["case_id"] == cid and e["kind"] in JUDGMENT_KINDS}
        cases.append({"case_id": cid, "fetch_id": case["fetch_id"], "body_sha256": case["body_sha256"], "extractor": case["extractor"],
                      "blocks": [{"index": b["index"], "text_sha256": b["text_sha256"], "label": s["blocks"][str(b["index"])]}
                                 for b in case["blocks"]],
                      "title": s["title"], "completeness": s["completeness"], "missing": list(s["missing"].values()),
                      "core": s["core"], "page_types": s["page_types"], "comment": s["comment"],
                      "blind": modes <= {"blind"} and not s["revised_after_reveal"], "mode": "diagnostic" if "diagnostic" in modes else "blind",
                      "revised_after_reveal": s["revised_after_reveal"], "first_at": s["first_at"], "finalized_at": s["finalized_at"]})
    out = {"schema": EXPORT_SCHEMA, "package_id": package.package_id, "case_listing_sha256": package.manifest["case_listing_sha256"],
           "exported_at": _now(), "events": len(journal.events), "events_sha256": _sha(log), "torn_lines_left_out": journal.torn,
           "cases_total": len(package.case_ids), "cases_closed": len(cases), "cases": cases}
    validate_export(package, out)
    return out


def validate_export(package: Package, data: Mapping[str, Any]) -> None:
    """Refuse an export that is not this package's or whose answers do not fit its cases."""
    if data.get("schema") != EXPORT_SCHEMA:
        raise ReviewError(f"not a {EXPORT_SCHEMA} document")
    if data.get("package_id") != package.package_id or data.get("case_listing_sha256") != package.manifest["case_listing_sha256"]:
        raise ReviewError("the judgments belong to another package")
    seen = set()
    for c in data["cases"]:
        case = package.cases.get(c["case_id"])
        if case is None or c["case_id"] in seen:
            raise ReviewError(f"{c['case_id']}: unknown or repeated case")
        seen.add(c["case_id"])
        if (c["fetch_id"], c["body_sha256"], c["extractor"]) != (case["fetch_id"], case["body_sha256"], case["extractor"]):
            raise ReviewError(f"{c['case_id']}: the identities do not match the case")
        if [(b["index"], b["text_sha256"]) for b in c["blocks"]] != [(b["index"], b["text_sha256"]) for b in case["blocks"]]:
            raise ReviewError(f"{c['case_id']}: the blocks do not match the case")
        if any(b["label"] not in BLOCK_LABELS for b in c["blocks"]):
            raise ReviewError(f"{c['case_id']}: a block without a valid label")
        if not c["completeness"] or not set(c["completeness"]) <= set(COMPLETENESS):
            raise ReviewError(f"{c['case_id']}: no valid completeness answer")
        if not c["core"] or c["core"]["value"] not in CORE_LABELS:
            raise ReviewError(f"{c['case_id']}: no valid CORE answer")
        if case["title_blocks"] and c["title"] not in TITLE_LABELS:
            raise ReviewError(f"{c['case_id']}: no valid title answer")


def _wilson(k: int, n: int, z: float = 1.959964) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def score(package: Package, data: Mapping[str, Any], *, include_not_blind: bool = False) -> dict[str, Any]:
    """The machine labels of the sealed key against the operator's judgments, the random and the targeted component apart.
    The five classes: article text removed (false deletion), foreign material kept (residue), article text missing (the
    completeness answer and the marked quotes not in the machine BODY), CORE wrong, and doubt (``unsure``). Only blind cases
    count unless ``include_not_blind``; diagnostic judgments never count. Rates with Wilson 95 % intervals are given for the
    random component, at the case level (blocks are clustered in cases); the targeted component gives counts only -- it is not a
    sample of the population."""
    validate_export(package, data)
    key = package.key()
    comp: dict[str, Counter] = {"random": Counter(), "targeted": Counter()}
    words: dict[str, Counter] = {"random": Counter(), "targeted": Counter()}
    per_case = []
    left_out = []
    for c in data["cases"]:
        if c["mode"] == "diagnostic" or (not c["blind"] and not include_not_blind):
            left_out.append(c["case_id"])
            continue
        k = key[c["case_id"]]
        m = k["machine"]
        part = k["component"]
        n = comp[part]
        n["cases"] += 1
        case = package.cases[c["case_id"]]
        text = {b["index"]: b["text"] for b in case["blocks"]}
        found = Counter()
        for b in c["blocks"]:
            role = m["blocks"][str(b["index"])]["role"]
            w = len(text[b["index"]].split())
            machine_body = role == E.ROLE_BODY
            if b["label"] == "unsure":
                cls = "doubt"
            elif b["label"] == "article":
                cls = "kept_article" if machine_body else "false_deletion"
            else:
                cls = "residue" if machine_body else "removed_foreign"
            found[cls] += 1
            n[f"blocks_{cls}"] += 1
            words[part][f"words_{cls}"] += w
        body = fold_text(m["body_text"])
        page = fold_text(" ".join(b["text"] for b in case["page_text"]))
        marks = Counter()
        for q in c["missing"]:
            quote = fold_text(q["quote"])
            marks["in_machine_body" if quote in body else ("in_page_text" if quote in page else "outside_the_page_text")] += 1
        for k2, v in marks.items():
            n[f"missing_marks_{k2}"] += v
        incomplete = c["completeness"] != ["complete"] and c["completeness"] != ["not_assessable"]
        machine_core = "yes" if k["machine"].get("core", {}).get("decision") == "ACCEPT" else "no"
        human_core = c["core"]["value"]
        core_cls = "core_doubt" if human_core == "unsure" else ("core_agree" if human_core == machine_core else
                                                               ("core_false_accept" if machine_core == "yes" else "core_false_reject"))
        n[core_cls] += 1
        for flag, cond in (("cases_with_false_deletion", found["false_deletion"] > 0), ("cases_with_residue", found["residue"] > 0),
                           ("cases_incomplete", incomplete), ("cases_with_doubt", found["doubt"] > 0 or human_core == "unsure"),
                           ("cases_not_assessable", c["completeness"] == ["not_assessable"])):
            n[flag] += int(cond)
        per_case.append({"case_id": c["case_id"], "component": part, "stratum": k["stratum"], **dict(found),
                         "completeness": c["completeness"], "missing_marks": dict(marks), "core": [human_core, machine_core],
                         "page_types": c["page_types"]["values"]})
    out = {"schema": RESULT_SCHEMA, "package_id": package.package_id, "events_sha256": data.get("events_sha256"),
           "include_not_blind": include_not_blind, "cases_left_out": left_out, "components": {}}
    for part, n in comp.items():
        entry = {"cases": n["cases"], **dict(sorted(n.items())), **dict(sorted(words[part].items()))}
        if part == "random":
            entry["rates_case_level_wilson95"] = {
                name: {"k": n[name], "n": n["cases"], "share": round(n[name] / n["cases"], 4) if n["cases"] else None,
                       "interval": _wilson(n[name], n["cases"])}
                for name in ("cases_with_false_deletion", "cases_with_residue", "cases_incomplete", "core_false_accept",
                             "core_false_reject", "core_doubt")}
            removed = n["blocks_removed_foreign"] + n["blocks_false_deletion"]
            entry["note"] = (f"stratified random sample by country, proportional allocation; {removed} blocks the machine kept out "
                             "were judged")
        else:
            entry["note"] = "targeted: counts only, no population rate"
        out["components"][part] = entry
    out["cases"] = per_case
    return out


# --- the server -----------------------------------------------------------------------------------------------------------


_LOOPBACK = ("127.0.0.1", "::1")


def make_server(package: Package, *, host: str = "127.0.0.1", port: int = 0, diagnostic: bool = False) -> ThreadingHTTPServer:
    """The reviewer's local server: a loopback address only, the Host header checked (a page elsewhere cannot reach it through a
    rebound name), the package verified, answers appended to the journal."""
    if host not in _LOOPBACK:
        raise ReviewError(f"the reviewer binds a loopback address only, not {host!r}")
    journal = Journal(package, diagnostic=diagnostic)
    assets = {name: (APP_DIRECTORY / name).read_bytes() for name in ("index.html", "app.js", "app.css")}
    types = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "app.css": "text/css; charset=utf-8"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "coprepan-body-review/1"

        def log_message(self, *args: Any) -> None:       # no request log on the console; the journal is the record
            return

        def _host_ok(self) -> bool:
            port_ = self.server.server_address[1]
            allowed = {f"127.0.0.1:{port_}", f"[::1]:{port_}", f"localhost:{port_}"}
            return self.headers.get("Host") in allowed

        def _send(self, status: int, body: bytes, content_type: str, csp: str = APP_CSP) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", csp)
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
                m = package.manifest
                return self._json(200, {"package_id": package.package_id, "cases": package.case_ids, "versions": m.get("versions"),
                                        "created_at": m.get("created_at"), "diagnostic": diagnostic,
                                        "vocabulary": {"block": BLOCK_LABELS, "title": TITLE_LABELS, "completeness": COMPLETENESS,
                                                       "core": CORE_LABELS, "page_types": PAGE_TYPES},
                                        "torn_lines_left_out": journal.torn})
            if path == "/api/state":
                return self._json(200, journal.state)
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "api" and parts[1] == "case" and parts[2] in package.cases:
                cid = parts[2]
                if len(parts) == 3:
                    return self._json(200, package.cases[cid])
                if parts[3:] == ["machine"]:
                    if not (journal.state[cid]["finalized"] or journal.state[cid]["revealed"] or diagnostic):
                        return self._json(HTTPStatus.FORBIDDEN, {"error": "the machine labels are shown after the case is closed"})
                    if not journal.state[cid]["revealed"]:
                        journal.append({"kind": "reveal", "case_id": cid})
                    k = package.key()[cid]
                    return self._json(200, {"machine": {x: y for x, y in k["machine"].items() if x != "body_text"},
                                            "component": k["component"], "stratum": k["stratum"]})
                if parts[3:] == ["source"]:
                    return self._send(200, package.source(cid), "text/html; charset=utf-8", csp=SOURCE_CSP)
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
            path = self.path.split("?")[0]
            try:
                if path == "/api/event":
                    event = journal.append(body)
                    return self._json(200, {"event": event, "case": journal.state[event["case_id"]]})
                if path == "/api/export":
                    data = export(package, journal)
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    target = package.directory / "judgments" / f"export_{stamp}.json"
                    _atomic_write(target, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
                    return self._json(200, {"file": target.name, "cases_closed": data["cases_closed"],
                                            "cases_total": data["cases_total"]})
            except ReviewError as error:
                return self._json(HTTPStatus.CONFLICT, {"error": str(error)})
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    server = ThreadingHTTPServer((host, port), Handler)
    server.journal = journal          # type: ignore[attr-defined]
    return server


__all__ = ["Package", "Journal", "ReviewError", "sanitize", "shown_blocks", "case_material", "draw", "write_package",
           "check_event", "fold", "open_items", "export", "validate_export", "score", "make_server", "fold_text", "text_sha256",
           "PACKAGE_SCHEMA", "CASE_SCHEMA", "KEY_SCHEMA", "EVENT_SCHEMA", "EXPORT_SCHEMA", "RESULT_SCHEMA", "BLOCK_LABELS",
           "TITLE_LABELS", "COMPLETENESS", "CORE_LABELS", "PAGE_TYPES", "SOURCE_CSP"]
