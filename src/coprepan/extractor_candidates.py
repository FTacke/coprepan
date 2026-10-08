"""Wrappers of the classical extractor candidates of the Phase-3 comparison (CPD-0018).

**None of these is adopted, and none is a runtime dependency.** Each wrapper turns the output of one
third-party tool into an extraction record of this repository's shape, so that the evaluation harness
(``extraction_eval``) can show it beside the baseline. The tools are imported only when a wrapper is
called; they live in an environment made for the comparison (``pyproject.toml``, extra ``phase3``),
and a wrapper refuses to run on any version but the one pinned here.

What every wrapper does the same way, so that the candidates differ in extraction and in nothing else:

* the input is the preserved body, checked against its digest; the HTTP content coding is undone and the
  characters decoded by the baseline's own rules (``extraction.decode_content``, ``extraction._decode``),
  and the decoding is written into the record;
* the tool gets that text and no address: no wrapper passes a URL, and none of the tools is asked to fetch;
* a body the baseline would not treat as HTML is ``NOT_EXTRACTABLE`` with the same reason;
* a metadata value a tool reports is recorded with basis ``unknown``: the tools do not say where on the
  page they took it from. A field a tool does not report stays ``unknown``.

What is lost in the mapping is named per wrapper (``MAPPING``) and written into every record under
``candidate``; that loss is part of what a comparison judges.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any, Callable, Mapping

from . import extraction
from .canonical import require_sha256, sha256_bytes
from .extraction import (
    EXTRACTION_SCHEMA, METADATA_FIELDS, NOT_APPLICABLE, OUTCOME_EXTRACTED, OUTCOME_NOT_EXTRACTABLE, ROLE_BODY, ROLE_NON_BODY,
    ROLE_TITLE, UNKNOWN, Extraction, ExtractionError, Extractor,
)

WRAPPER_REVISION = "w1"
# distribution name -> the exact version a wrapper runs on. Mirrored in pyproject.toml (extra `phase3`).
PINS = {"trafilatura": "2.3.1", "readability-lxml": "0.9", "justext": "3.0.2"}
JUSTEXT_STOPLIST = "Spanish"
# The date a page may state at the latest, for the tool that validates dates against "today" by default:
# a fixed bound keeps the wrapper a function of its input and not of the day it runs on.
TRAFILATURA_MAX_DATE = "2099-12-31"

MAPPING = {
    "trafilatura": "the tool's XML output: head -> heading, p -> paragraph, item -> list_item, quote -> quote_block, any other "
                   "element with text -> unstructured_text, all with role body; the title it reports -> the title block; "
                   "author and date as it reports them (the date is the tool's normalised form, not the page's wording); "
                   "comments excluded, tables included; text the tool discards is not in the record",
    "readability-lxml": "the cleaned HTML of the container the tool selects, read block by block (p, li, blockquote, figcaption, "
                        "h1-h6; other text -> unstructured_text), all with role body; short_title() -> the title block; "
                        "no other metadata; text outside the selected container is not in the record",
    "justext": "every paragraph the tool returns, in order: not boilerplate -> role body (heading or paragraph), boilerplate -> "
               "role non_body; no title block, no metadata; inline structure inside a paragraph is not kept",
}


class CandidateUnavailable(RuntimeError):
    """The tool of a wrapper is not installed in this environment, or not in the pinned version."""


def _tool(distribution: str) -> str:
    """The installed version of a tool; refuses anything but the pin."""
    try:
        found = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as error:
        raise CandidateUnavailable(f"{distribution} is not installed (extra 'phase3')") from error
    if found != PINS[distribution]:
        raise CandidateUnavailable(f"{distribution} {found} is installed, the wrapper is pinned to {PINS[distribution]}")
    return found


def available(distribution: str) -> bool:
    try:
        _tool(distribution)
    except CandidateUnavailable:
        return False
    return True


def _clean(text: Any) -> str:
    return extraction._WHITESPACE.sub(" ", str(text or "")).strip()


def _wrap(distribution: str, name: str, parameters: Mapping[str, Any],
          run_tool: Callable[[str], tuple[list[tuple[str, str, str]], dict[str, str]]]) -> Extractor:
    """An :class:`Extractor` around one tool. ``run_tool(text)`` returns ``(blocks, metadata)``: blocks as
    ``(kind, role, text)`` in order, metadata as ``{field: value}`` for the fields the tool reports.
    """
    version = f"{PINS[distribution]}.{WRAPPER_REVISION}"

    def function(body: bytes, *, body_sha256: str, content_type: str, declared_charset: str = UNKNOWN,
                 content_encoding: str = extraction.IDENTITY) -> Extraction:
        if not isinstance(body, bytes):
            raise ExtractionError("a body is bytes")
        if sha256_bytes(body) != require_sha256(body_sha256, "body_sha256"):
            raise ExtractionError("the body offered is not the body the digest names")
        tool_version = _tool(distribution)
        record: dict[str, Any] = {
            "schema": EXTRACTION_SCHEMA,
            "extractor": {"name": name, "version": version},
            "candidate": {"tool": distribution, "tool_version": tool_version, "wrapper": WRAPPER_REVISION,
                          "parameters": dict(parameters), "mapping": MAPPING[distribution]},
            "input": {"body_sha256": body_sha256, "body_size_bytes": len(body), "declared_content_type": content_type,
                      "declared_charset": declared_charset, "content_encoding": content_encoding},
            "outcome": OUTCOME_EXTRACTED, "reason": NOT_APPLICABLE,
            "decoding": {"charset": NOT_APPLICABLE, "basis": NOT_APPLICABLE, "replaced_characters": 0},
            "metadata": {field: {"value": UNKNOWN, "basis": UNKNOWN, "candidates": []} for field in METADATA_FIELDS},
            "blocks": [],
        }
        try:
            decoded = extraction.decode_content(body, content_encoding) if body else body
            reason = extraction._refusal(decoded, content_type)
        except extraction.ContentDecodingError as error:
            reason = error.reason
        if reason is None:
            text, record["decoding"] = extraction._decode(decoded, declared_charset)
            blocks, metadata = run_tool(text)
            kept = [(kind, role, _clean(block_text)) for kind, role, block_text in blocks]
            record["blocks"] = [{"index": index, "kind": kind, "role": role, "text": block_text}
                                for index, (kind, role, block_text) in enumerate(item for item in kept if item[2])]
            for field, value in metadata.items():
                if _clean(value):
                    record["metadata"][field] = {"value": _clean(value), "basis": UNKNOWN,
                                                 "candidates": [{"value": _clean(value), "basis": UNKNOWN}]}
        else:
            record["outcome"], record["reason"] = OUTCOME_NOT_EXTRACTABLE, reason
        record["extracted_text_sha256"] = sha256_bytes(extraction.extracted_text_bytes(record["blocks"]))
        record["body_text_sha256"] = sha256_bytes(extraction.body_text(record["blocks"]).encode("utf-8"))
        return Extraction(record)

    return Extractor(name, version, function, extraction.LIFECYCLE_EXPERIMENTAL)


# --- trafilatura ------------------------------------------------------------------------------------

_TRAFILATURA_PARAMETERS = {"output_format": "xml", "include_comments": False, "include_tables": True, "include_images": False,
                           "include_links": False, "include_formatting": False, "favor_precision": False, "favor_recall": False,
                           "deduplicate": False, "with_metadata": True, "url": None, "no_fallback": False,
                           "date_extraction_params": {"extensive_search": False, "original_date": True, "max_date": TRAFILATURA_MAX_DATE}}
_TRAFILATURA_KINDS = {"head": "heading", "p": "paragraph", "item": "list_item", "quote": "quote_block"}


def _trafilatura(text: str) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    import trafilatura
    from lxml import etree

    rendered = trafilatura.extract(text, **{key: (dict(value) if isinstance(value, dict) else value)
                                            for key, value in _TRAFILATURA_PARAMETERS.items()})
    if not rendered:
        return [], {}
    document = etree.fromstring(rendered.encode("utf-8"))
    blocks: list[tuple[str, str, str]] = []
    title = document.get("title")
    if title:
        blocks.append(("title", ROLE_TITLE, title))
    main = document.find("main")
    for element in (main.iter() if main is not None else ()):
        if not isinstance(element.tag, str) or element is main:
            continue
        kind = _TRAFILATURA_KINDS.get(element.tag)
        if kind is not None:
            # a paragraph inside a quote or a list item is that block's text, not a second block
            if any(parent.tag in _TRAFILATURA_KINDS for parent in element.iterancestors() if parent is not main):
                continue
            blocks.append((kind, ROLE_BODY, "".join(element.itertext())))
        elif element.getparent() is main and not any(child.tag in _TRAFILATURA_KINDS for child in element.iter()):
            # an element of the tool's output this mapping has no kind for (a table, say): its text, kept
            blocks.append(("unstructured_text", ROLE_BODY, " ".join(element.itertext())))
    return blocks, {"title": title or "", "author": document.get("author") or "", "publication_date": document.get("date") or ""}


# --- readability-lxml -------------------------------------------------------------------------------

_READABILITY_PARAMETERS = {"html_partial": True, "url": None, "min_text_length": 25, "retry_length": 250, "handle_failures": "discard"}


def _readability(text: str) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    from readability import Document

    document = Document(text, url=None, min_text_length=_READABILITY_PARAMETERS["min_text_length"],
                        retry_length=_READABILITY_PARAMETERS["retry_length"], handle_failures=_READABILITY_PARAMETERS["handle_failures"])
    summary = document.summary(html_partial=True)
    title = document.short_title()
    parser = extraction._Parser()
    parser.stack.append("body")          # the fragment has no body element; its loose text is still text
    parser.feed(summary)
    parser.close()
    blocks = [("title", ROLE_TITLE, title)] if _clean(title) else []
    blocks += [(extraction._BLOCK_TAGS.get(item["tag"], "unstructured_text"), ROLE_BODY, item["text"]) for item in parser.raw]
    return blocks, {"title": title or ""}


# --- jusText ----------------------------------------------------------------------------------------

_JUSTEXT_PARAMETERS = {"stoplist": JUSTEXT_STOPLIST, "length_low": 70, "length_high": 200, "stopwords_low": 0.3, "stopwords_high": 0.32,
                       "max_link_density": 0.2, "max_heading_distance": 200, "no_headings": False}


def _justext(text: str) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    import justext

    parameters = {key: value for key, value in _JUSTEXT_PARAMETERS.items() if key != "stoplist"}
    paragraphs = justext.justext(text, justext.get_stoplist(JUSTEXT_STOPLIST), **parameters)
    return [("heading" if paragraph.is_heading else "paragraph", ROLE_NON_BODY if paragraph.is_boilerplate else ROLE_BODY, paragraph.text)
            for paragraph in paragraphs], {}


TRAFILATURA = _wrap("trafilatura", "trafilatura", _TRAFILATURA_PARAMETERS, _trafilatura)
READABILITY = _wrap("readability-lxml", "readability_lxml", _READABILITY_PARAMETERS, _readability)
JUSTEXT = _wrap("justext", "justext", _JUSTEXT_PARAMETERS, _justext)

# The candidates of the first comparison, in no order of preference. The baseline is the floor beside them.
CANDIDATES = {arm.stage_version: arm for arm in (TRAFILATURA, READABILITY, JUSTEXT)}
DISTRIBUTION_OF = {TRAFILATURA.stage_version: "trafilatura", READABILITY.stage_version: "readability-lxml", JUSTEXT.stage_version: "justext"}
