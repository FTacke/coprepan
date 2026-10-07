"""``robots.txt`` as evidence (RFC 9309).

This module parses a robots file and answers a narrow question: *does this file, read as RFC 9309
says, allow this product token to request this path?* It does not fetch, it does not decide
whether a disallowed path may be requested, and it makes no legal statement. What a robots answer
means for acquisition is the acquisition policy's to say (``policy.py``); a robots file is one
source of evidence among several and does not settle text-and-data-mining questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

from .canonical import sha256_bytes

PARSER_VERSION = "robots-parser/1"
ALLOWED, DISALLOWED = "allowed", "disallowed"

EVIDENCE_FETCHED = "fetched"            # a robots file was retrieved and parsed
EVIDENCE_ABSENT = "absent"              # the server answered 4xx: no robots file
EVIDENCE_UNREACHABLE = "unreachable"    # 5xx, network failure or an unusable answer
EVIDENCE_NOT_CONSULTED = "not_consulted"
EVIDENCE_STATES = (EVIDENCE_FETCHED, EVIDENCE_ABSENT, EVIDENCE_UNREACHABLE, EVIDENCE_NOT_CONSULTED)

MAX_ROBOTS_BYTES = 500 * 1024  # RFC 9309 §2.5: at least 500 kibibytes must be parsed


@dataclass(frozen=True)
class RobotsRules:
    """Groups of ``(allow?, pattern)`` rules by lower-cased product token, plus what else was seen."""

    groups: Mapping[str, tuple[tuple[bool, str], ...]]
    sitemaps: tuple[str, ...] = ()
    crawl_delays: Mapping[str, str] = field(default_factory=dict)  # not part of RFC 9309; recorded, not interpreted

    def evaluate(self, product_token: str, path: str) -> tuple[str, str | None]:
        """``(allowed | disallowed, the rule that decided)`` for a path with its query.

        The group of the product token, else the ``*`` group, else everything is allowed. Within
        the group the longest matching pattern decides; on a tie, allow.
        """
        rules = self.groups.get(product_token.lower(), self.groups.get("*", ()))
        best: tuple[int, bool, str] | None = None
        for allow, pattern in rules:
            if pattern and _matches(pattern, path or "/"):
                candidate = (len(pattern), allow, pattern)
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
        if best is None:
            return ALLOWED, None
        return (ALLOWED if best[1] else DISALLOWED), f"{'allow' if best[1] else 'disallow'}: {best[2]}"


@dataclass(frozen=True)
class RobotsEvidence:
    """What is known about one origin's robots file at the time of a policy decision."""

    state: str
    sha256: str = "not_applicable"
    rules: RobotsRules | None = None
    detail: str = "not_applicable"

    def __post_init__(self) -> None:
        if self.state not in EVIDENCE_STATES or (self.state == EVIDENCE_FETCHED) != (self.rules is not None):
            raise ValueError(f"inconsistent robots evidence: {self.state}")


def _matches(pattern: str, path: str) -> bool:
    anchored = pattern.endswith("$")
    expression = "".join(".*" if char == "*" else re.escape(char) for char in (pattern[:-1] if anchored else pattern))
    return re.match(expression + ("$" if anchored else ""), path) is not None


def parse_robots(body: bytes) -> RobotsRules:
    """Parse a robots file. Lines that are not understood are ignored, as the RFC requires; only
    the first 500 KiB are read.
    """
    groups: dict[str, list[tuple[bool, str]]] = {}
    sitemaps: list[str] = []
    delays: dict[str, str] = {}
    current: list[str] = []
    in_rules = False
    for raw in body[:MAX_ROBOTS_BYTES].decode("utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        key, colon, value = line.partition(":")
        if not colon:
            continue
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if in_rules:
                current, in_rules = [], False
            token = value.lower()
            current.append(token)
            groups.setdefault(token, [])
        elif key in ("allow", "disallow"):
            in_rules = True
            for token in current:
                groups[token].append((key == "allow", value))
        elif key == "sitemap":
            if value:
                sitemaps.append(value)
        elif key == "crawl-delay":
            in_rules = True
            for token in current:
                delays[token] = value
    return RobotsRules({token: tuple(rules) for token, rules in groups.items()}, tuple(sitemaps), delays)


def evidence_from_response(status: int | None, body: bytes | None) -> RobotsEvidence:
    """Turn the answer to a ``/robots.txt`` request into evidence. No interpretation beyond the
    three states: a 2xx file is parsed, a 4xx is "absent", anything else is "unreachable".
    """
    if status is not None and 200 <= status < 300 and body is not None:
        return RobotsEvidence(EVIDENCE_FETCHED, sha256_bytes(body), parse_robots(body), f"http_{status}")
    if status is not None and 400 <= status < 500:
        return RobotsEvidence(EVIDENCE_ABSENT, detail=f"http_{status}")
    return RobotsEvidence(EVIDENCE_UNREACHABLE, detail=f"http_{status}" if status is not None else "no_response")
