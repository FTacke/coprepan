"""Evaluation harness for extractor candidates (Phase 3 instrument; CPD-0007 §8).

This is the *measuring instrument*, built before there is anything real to measure. It runs
several extractor arms over the same preserved bodies, records what each produced, compares them
with each other and — once it exists — with a human reference, and writes a review package for the
people who will make that reference.

What it must never be mistaken for:

* **It contains no gold.** A reference is produced by human reviewers on real preserved pages;
  none exists, and nothing here simulates one.
* **Its automatic numbers are diagnostics.** Token overlap says how much of a reference text an
  arm reproduced and how much else it added. It cannot say whether a page is an article, whether
  the body boundary is editorially right, or whether a text is fit for linguistic analysis. Where
  the numbers and a reviewer disagree, the reviewer is the measurement.
* **It adopts nothing.** An arm that scores well is a candidate until a decision adopts it.

Arms: any :class:`~coprepan.extraction.Extractor`, or precomputed outputs supplied from outside
(:class:`PrecomputedArm`) — the form in which an extractor that cannot run here, such as the
legacy one on re-fetched pages, can enter a comparison.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import extraction, naming
from .canonical import canonical_json, record_json, require_sha256, sha256_bytes

SAMPLE_SCHEMA = naming.schema_id("extraction-sample", 1)
EVALUATION_SCHEMA = naming.schema_id("extraction-evaluation", 1)
REFERENCE_SCHEMA = naming.schema_id("extraction-reference", 1)
REVIEW_CASE_SCHEMA = naming.schema_id("extraction-review-case", 1)
HARNESS_VERSION = "extraction-eval/1"

ARM_OK, ARM_ERROR, ARM_MISSING = "OK", "EXTRACTOR_ERROR", "NO_OUTPUT"
# States a reviewer may give a case instead of a reference (docs/extraction/GOLD_SAMPLE_DESIGN.md).
REFERENCE_STATES = ("JUDGED", "NOT_AN_ARTICLE", "DAMAGED_SOURCE", "UNJUDGEABLE")
BOUNDARY_TOKENS = 12
_TOKEN = re.compile(r"\S+")


class EvaluationError(RuntimeError):
    """The evaluation cannot be run or trusted as asked."""


class NonDeterministicArm(EvaluationError):
    """An arm gave two different answers for the same input."""


# --- sample -----------------------------------------------------------------------------------------


def draw_sample(frame: Sequence[Mapping[str, Any]], *, strata: Sequence[str], per_stratum: int, seed: str) -> list[dict[str, Any]]:
    """A stratified sample from a frame of cases, reproducible from ``seed``.

    Within each stratum the cases are ordered by the SHA-256 of ``seed`` and their ``case_id`` and
    the first ``per_stratum`` are taken — no random-number generator, no dependence on input
    order. A stratum with fewer cases contributes all it has; the caller sees that in the result.
    """
    if per_stratum < 1 or not seed:
        raise EvaluationError("a sample needs a positive size per stratum and a seed")
    groups: dict[tuple, list[Mapping[str, Any]]] = {}
    for case in frame:
        try:
            key = tuple(case["strata"][name] for name in strata)
        except KeyError as error:
            raise EvaluationError(f"case {case.get('case_id')!r} lacks the stratum {error}") from error
        groups.setdefault(key, []).append(case)
    chosen = []
    for key in sorted(groups):
        ordered = sorted(groups[key], key=lambda case: sha256_bytes(f"{seed}|{case['case_id']}".encode("utf-8")))
        chosen += [dict(case) for case in ordered[:per_stratum]]
    return chosen


def sample_manifest(cases: Sequence[Mapping[str, Any]], *, sample_id: str, strata: Sequence[str], seed: str,
                    per_stratum: int, frame_description: str) -> dict[str, Any]:
    """A frozen description of a sample: which cases, drawn how. Its hash pins the sample."""
    rows = []
    for case in cases:
        rows.append({"case_id": case["case_id"], "fetch_id": case["fetch_id"],
                     "body_sha256": require_sha256(case["body_sha256"], "body_sha256"),
                     "pack_id": case.get("pack_id"), "outlet_id": case["outlet_id"], "strata": dict(case["strata"]),
                     "declared_content_type": case["declared_content_type"],
                     "declared_charset": case.get("declared_charset", extraction.UNKNOWN),
                     "content_encoding": case.get("content_encoding", extraction.IDENTITY)})
    if len({row["case_id"] for row in rows}) != len(rows):
        raise EvaluationError("a case id occurs twice in the sample")
    manifest = {"schema": SAMPLE_SCHEMA, "sample_id": sample_id, "strata": list(strata), "seed": seed,
                "per_stratum": per_stratum, "frame_description": frame_description,
                "cases": sorted(rows, key=lambda row: row["case_id"])}
    manifest["sample_sha256"] = sha256_bytes(canonical_json(manifest))
    return manifest


def verify_sample(manifest: Mapping[str, Any]) -> None:
    body = {key: value for key, value in manifest.items() if key != "sample_sha256"}
    if manifest.get("schema") != SAMPLE_SCHEMA or manifest.get("sample_sha256") != sha256_bytes(canonical_json(body)):
        raise EvaluationError("the sample manifest does not match its own digest")


# --- arms -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PrecomputedArm:
    """Outputs produced elsewhere, keyed by case id: extraction records, or just a block list."""

    name: str
    version: str
    outputs: Mapping[str, Mapping[str, Any]]
    lifecycle: str = extraction.LIFECYCLE_EXPERIMENTAL

    @property
    def stage_version(self) -> str:
        return f"{self.name}/{self.version}"


def _run_arm(arm: Any, case: Mapping[str, Any], body: bytes) -> dict[str, Any]:
    """One arm on one case: its record, or how it failed. Never drops a case."""
    if isinstance(arm, PrecomputedArm):
        if case["case_id"] not in arm.outputs:
            return {"state": ARM_MISSING, "detail": "no precomputed output for this case", "record": None}
        return {"state": ARM_OK, "detail": None, "record": dict(arm.outputs[case["case_id"]])}
    arguments = dict(body_sha256=case["body_sha256"], content_type=case["declared_content_type"],
                     declared_charset=case["declared_charset"], content_encoding=case["content_encoding"])
    try:
        first = arm.run(body, **arguments)
        second = arm.run(body, **arguments)
    except Exception as error:  # noqa: BLE001 - a crashing arm is a result of the evaluation, not the end of it
        return {"state": ARM_ERROR, "detail": f"{type(error).__name__}: {error}", "record": None}
    if first.payload != second.payload:
        raise NonDeterministicArm(f"{arm.stage_version} gave two different answers for case {case['case_id']}")
    return {"state": ARM_OK, "detail": None, "record": dict(first.record)}


# --- metrics ----------------------------------------------------------------------------------------


def tokens(text: str) -> list[str]:
    """Whitespace tokens. A deliberately crude unit: it is what both sides can agree on without
    an annotator, and it is not the corpus's token definition.
    """
    return _TOKEN.findall(text or "")


def overlap(candidate: str, reference: str) -> dict[str, Any]:
    """Bag-of-tokens overlap of a candidate text with a reference text.

    ``retention`` — share of the reference's tokens the candidate contains (what was kept);
    ``excess`` — share of the candidate's tokens that are not in the reference (what was added:
    boilerplate, if the reference is the article). Order is ignored, so this says nothing about
    where the text begins and ends; :func:`boundary` does.
    """
    cand, ref = Counter(tokens(candidate)), Counter(tokens(reference))
    shared = sum((cand & ref).values())
    cand_total, ref_total = sum(cand.values()), sum(ref.values())
    return {
        "reference_tokens": ref_total, "candidate_tokens": cand_total, "shared_tokens": shared,
        "retention": shared / ref_total if ref_total else None,
        "excess": (cand_total - shared) / cand_total if cand_total else None,
    }


def boundary(candidate: str, reference: str, width: int = BOUNDARY_TOKENS) -> dict[str, Any]:
    """Whether the candidate starts and ends where the reference does (first and last ``width`` tokens)."""
    cand, ref = tokens(candidate), tokens(reference)
    if not ref:
        return {"start_matches": None, "end_matches": None}
    return {"start_matches": cand[:width] == ref[:width], "end_matches": cand[-width:] == ref[-width:]}


def _texts(record: Mapping[str, Any] | None) -> dict[str, str]:
    blocks = (record or {}).get("blocks") or []
    return {"title": " ".join(b["text"] for b in blocks if b["role"] == extraction.ROLE_TITLE),
            "body": extraction.body_text(blocks),
            "non_body": "\n\n".join(b["text"] for b in blocks if b["role"] == extraction.ROLE_NON_BODY)}


def _normal(text: Any) -> str:
    return " ".join(str(text or "").split())


def score_against_reference(record: Mapping[str, Any] | None, reference: Mapping[str, Any], *,
                            catastrophic_retention_below: float) -> dict[str, Any]:
    """Diagnostics of one arm's record against one human reference.

    ``catastrophic_retention_below`` has no default: what counts as a catastrophic loss is a
    parameter of the evaluation plan, stated before the reference is looked at.
    """
    if reference.get("state") != "JUDGED":
        return {"scored": False, "reference_state": reference.get("state")}
    texts = _texts(record)
    body = overlap(texts["body"], reference["body"])
    metadata = {}
    for field, expected in (reference.get("metadata") or {}).items():
        found = ((record or {}).get("metadata") or {}).get(field, {}).get("value", extraction.UNKNOWN)
        metadata[field] = {"expected": expected, "found": found, "correct": _normal(found) == _normal(expected)}
    catastrophic = []
    if record is None:
        catastrophic.append("no_output")
    elif record.get("outcome") != extraction.OUTCOME_EXTRACTED:
        catastrophic.append("not_extracted")
    elif body["reference_tokens"] and not body["candidate_tokens"]:
        catastrophic.append("empty_body")
    elif body["retention"] is not None and body["retention"] < catastrophic_retention_below:
        catastrophic.append("body_mostly_lost")
    return {
        "scored": True, "reference_state": "JUDGED",
        "text_retention": body["retention"], "boilerplate_inclusion": body["excess"],
        "title_correct": _normal(texts["title"]) == _normal(reference.get("title")),
        "body_boundary": boundary(texts["body"], reference["body"]),
        "metadata": metadata, "catastrophic": catastrophic,
        "tokens": {key: body[key] for key in ("reference_tokens", "candidate_tokens", "shared_tokens")},
    }


def disagreement(first: Mapping[str, Any] | None, second: Mapping[str, Any] | None) -> dict[str, Any]:
    """How two arms differ on one case, without a reference: where a reviewer should look."""
    a, b = _texts(first), _texts(second)
    body = overlap(a["body"], b["body"])
    return {
        "same_outcome": (first or {}).get("outcome") == (second or {}).get("outcome"),
        "same_title": _normal(a["title"]) == _normal(b["title"]),
        "same_body": _normal(a["body"]) == _normal(b["body"]),
        "body_tokens": [body["candidate_tokens"], body["reference_tokens"]],
        "body_shared_share_of_first": 1 - body["excess"] if body["excess"] is not None else None,
        "body_shared_share_of_second": body["retention"],
        "metadata_differs": sorted(field for field in extraction.METADATA_FIELDS
                                   if ((first or {}).get("metadata") or {}).get(field, {}).get("value")
                                   != ((second or {}).get("metadata") or {}).get(field, {}).get("value")),
    }


# --- run --------------------------------------------------------------------------------------------


def evaluate(
    manifest: Mapping[str, Any],
    arms: Sequence[Any],
    body_of: Callable[[Mapping[str, Any]], bytes],
    *,
    references: Mapping[str, Mapping[str, Any]] | None = None,
    catastrophic_retention_below: float | None = None,
) -> dict[str, Any]:
    """Run every arm on every case of a sample. Deterministic: no clock, no order dependence.

    ``body_of(case)`` supplies the preserved bytes of a case; they must hash to the digest the
    sample names, or the evaluation stops — a comparison on other bytes than the sample's is not
    this sample's comparison.
    """
    verify_sample(manifest)
    names = [arm.stage_version for arm in arms]
    if len(set(names)) != len(names) or not names:
        raise EvaluationError("arms are distinct and at least one")
    if references is not None and catastrophic_retention_below is None:
        raise EvaluationError("scoring against a reference needs catastrophic_retention_below, stated in advance")
    cases_out = []
    for case in manifest["cases"]:
        body = body_of(case)
        if sha256_bytes(body) != case["body_sha256"]:
            raise EvaluationError(f"case {case['case_id']}: the bytes supplied are not the bytes the sample names")
        outputs = {arm.stage_version: _run_arm(arm, case, body) for arm in arms}
        entry: dict[str, Any] = {
            "case_id": case["case_id"], "fetch_id": case["fetch_id"], "body_sha256": case["body_sha256"],
            "outlet_id": case["outlet_id"], "strata": case["strata"],
            "arms": {name: {"state": out["state"], "detail": out["detail"],
                            "outcome": (out["record"] or {}).get("outcome"),
                            "record_sha256": sha256_bytes(canonical_json(out["record"])) if out["record"] is not None else None,
                            "body_tokens": len(tokens(_texts(out["record"])["body"])),
                            "blocks": len((out["record"] or {}).get("blocks") or [])}
                     for name, out in outputs.items()},
            "disagreements": {f"{a} | {b}": disagreement(outputs[a]["record"], outputs[b]["record"])
                              for index, a in enumerate(names) for b in names[index + 1:]},
        }
        if references is not None:
            reference = references.get(case["case_id"])
            entry["reference"] = None if reference is None else {
                name: score_against_reference(out["record"], reference, catastrophic_retention_below=catastrophic_retention_below)
                for name, out in outputs.items()}
        cases_out.append((entry, outputs))
    result = {
        "schema": EVALUATION_SCHEMA, "harness": HARNESS_VERSION, "sample_id": manifest["sample_id"],
        "sample_sha256": manifest["sample_sha256"],
        "arms": [{"arm": arm.stage_version, "lifecycle": getattr(arm, "lifecycle", extraction.UNKNOWN),
                  "kind": "precomputed" if isinstance(arm, PrecomputedArm) else "extractor"} for arm in arms],
        "parameters": {"catastrophic_retention_below": catastrophic_retention_below, "boundary_tokens": BOUNDARY_TOKENS,
                       "token_unit": "whitespace"},
        "has_reference": references is not None,
        "cases": [entry for entry, _ in cases_out],
        "summary": _summary([entry for entry, _ in cases_out], names),
        "reading": "Diagnostics only. No arm is adopted by this record; without a human reference nothing here measures quality.",
    }
    result["evaluation_sha256"] = sha256_bytes(canonical_json(result))
    result["_outputs"] = {entry["case_id"]: {name: out["record"] for name, out in outputs.items()} for entry, outputs in cases_out}
    return result


def _summary(cases: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {"cases": len(cases), "arms": {}}
    for name in names:
        states = Counter(case["arms"][name]["state"] for case in cases)
        scored = [case["reference"][name] for case in cases if case.get("reference") and case["reference"][name]["scored"]]
        entry: dict[str, Any] = {"states": dict(sorted(states.items())), "scored_cases": len(scored)}
        if scored:
            mean = lambda values: sum(values) / len(values) if values else None  # noqa: E731
            entry.update(
                mean_text_retention=mean([s["text_retention"] for s in scored if s["text_retention"] is not None]),
                mean_boilerplate_inclusion=mean([s["boilerplate_inclusion"] for s in scored if s["boilerplate_inclusion"] is not None]),
                title_correct=sum(1 for s in scored if s["title_correct"]),
                body_start_matches=sum(1 for s in scored if s["body_boundary"]["start_matches"]),
                body_end_matches=sum(1 for s in scored if s["body_boundary"]["end_matches"]),
                catastrophic_cases=sum(1 for s in scored if s["catastrophic"]),
            )
        summary["arms"][name] = entry
    return summary


def public_record(result: Mapping[str, Any]) -> dict[str, Any]:
    """The evaluation without the arms' full outputs — the part that is stored and hashed."""
    return {key: value for key, value in result.items() if key != "_outputs"}


# --- review package ---------------------------------------------------------------------------------


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style", "noscript", "template"):
            self.skip += 1
        elif tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "blockquote"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "template") and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def visible_text(body: bytes, content_encoding: str = extraction.IDENTITY) -> str:
    """Every text node of the page in document order, scripts and styles left out.

    The neutral side of a review case: not an extraction, no body decision, nothing removed for
    being navigation. A reviewer compares the arms against *this*, not against each other.
    """
    try:
        data = extraction.decode_content(body, content_encoding)
    except extraction.ContentDecodingError as error:
        return f"[source could not be decoded: {error.reason}]"
    parser = _VisibleText()
    parser.feed(data.decode("utf-8", errors="replace"))
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.parts).split("\n")]
    return "\n".join(line for line in lines if line)


def review_package(
    manifest: Mapping[str, Any],
    result: Mapping[str, Any],
    body_of: Callable[[Mapping[str, Any]], bytes],
    out_dir: Path,
    *,
    blind_seed: str,
) -> dict[str, Any]:
    """Write one review case per sampled case, with the arms under blinded labels.

    ``cases/<case_id>.json`` holds the source reference, the neutral visible text, each arm's
    title, body, other blocks and metadata under a label (``A``, ``B`` …) assigned per case from
    ``blind_seed``, and an **empty** decision form. ``blinding_key.json`` maps labels back to arms
    and is kept away from reviewers. Nothing is pre-filled: this package asks, it does not answer.
    """
    if result["sample_sha256"] != manifest["sample_sha256"]:
        raise EvaluationError("the evaluation was not made on this sample")
    out_dir = Path(out_dir)
    (out_dir / "cases").mkdir(parents=True, exist_ok=False)
    key: dict[str, dict[str, str]] = {}
    arm_names = [arm["arm"] for arm in result["arms"]]
    for case in manifest["cases"]:
        order = sorted(arm_names, key=lambda name: sha256_bytes(f"{blind_seed}|{case['case_id']}|{name}".encode("utf-8")))
        labels = {name: chr(ord("A") + index) for index, name in enumerate(order)}
        key[case["case_id"]] = {label: name for name, label in labels.items()}
        candidates = {}
        for name in order:
            record = result["_outputs"][case["case_id"]][name]
            texts = _texts(record)
            candidates[labels[name]] = {
                "produced_output": record is not None, "outcome": (record or {}).get("outcome"),
                "title": texts["title"], "body": texts["body"],
                "other_blocks": [{"kind": b["kind"], "text": b["text"]} for b in (record or {}).get("blocks") or []
                                 if b["role"] == extraction.ROLE_NON_BODY],
                "metadata": {field: {"value": value["value"], "basis": value["basis"]}
                             for field, value in ((record or {}).get("metadata") or {}).items()},
            }
        review_case = {
            "schema": REVIEW_CASE_SCHEMA, "case_id": case["case_id"], "sample_id": manifest["sample_id"],
            "sample_sha256": manifest["sample_sha256"],
            "source": {"fetch_id": case["fetch_id"], "body_sha256": case["body_sha256"], "pack_id": case["pack_id"],
                       "outlet_id": case["outlet_id"]},
            "visible_text": visible_text(body_of(case), case["content_encoding"]),
            "candidates": candidates,
            "decision": {"state": None, "allowed_states": list(REFERENCE_STATES), "title": None, "body": None,
                         "metadata": {field: None for field in extraction.METADATA_FIELDS},
                         "per_candidate": {label: {"title_correct": None, "body_start_correct": None, "body_end_correct": None,
                                                   "text_missing": None, "boilerplate_included": None}
                                           for label in sorted(candidates)},
                         "reviewer": None, "reviewed_at": None, "notes": None},
        }
        (out_dir / "cases" / f"{case['case_id']}.json").write_bytes(record_json(review_case))
    index = {"schema": REVIEW_CASE_SCHEMA, "sample_id": manifest["sample_id"], "sample_sha256": manifest["sample_sha256"],
             "evaluation_sha256": result["evaluation_sha256"], "cases": sorted(key), "blinded": True,
             "instructions": "Fill 'decision' in each case file. Do not open blinding_key.json before every case is decided."}
    (out_dir / "index.json").write_bytes(record_json(index))
    (out_dir / "blinding_key.json").write_bytes(record_json({"sample_sha256": manifest["sample_sha256"], "blind_seed": blind_seed,
                                                             "labels": key}))
    (out_dir / "index.html").write_bytes(_html_index(manifest, sorted(key)).encode("utf-8"))
    return index


def _html_index(manifest: Mapping[str, Any], case_ids: list[str]) -> str:
    rows = "\n".join(f'<li><a href="cases/{html.escape(case)}.json">{html.escape(case)}</a></li>' for case in case_ids)
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Extraction review</title></head><body>\n"
            f"<h1>Extraction review — sample {html.escape(manifest['sample_id'])}</h1>\n"
            "<p>One file per case. Candidates are blinded. Nothing is pre-filled.</p>\n"
            f"<ul>\n{rows}\n</ul>\n</body></html>\n")


def reference_from_decisions(review_dir: Path) -> dict[str, dict[str, Any]]:
    """Read the decided cases of a review package as a reference. A case without a decided state
    is not in the reference; an invalid state is refused.
    """
    reference = {}
    for path in sorted((Path(review_dir) / "cases").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        decision = case["decision"]
        if decision["state"] is None:
            continue
        if decision["state"] not in REFERENCE_STATES:
            raise EvaluationError(f"{case['case_id']}: {decision['state']!r} is not a reference state")
        reference[case["case_id"]] = {"schema": REFERENCE_SCHEMA, "state": decision["state"], "title": decision["title"],
                                      "body": decision["body"] or "",
                                      "metadata": {k: v for k, v in decision["metadata"].items() if v is not None},
                                      "reviewer": decision["reviewer"]}
    return reference
