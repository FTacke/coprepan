"""Crawler identity (master plan O-2; decision CPD-0006 §4).

Four things that are not the same thing:

* **software identity** — which code made the request: package version and fetcher version;
* **operator identity** — who is responsible: organisation, a public page, a contact address;
* **the HTTP ``User-Agent``** — one *representation* of both, derived, never typed by hand;
* **the acquisition run** — which execution a request belonged to (``run_id``), recorded in the
  fetch record, never sent to a server.

There is **no built-in operator identity**. The tracked configuration ships with every field
``not_configured``; an identity for external requests exists only when all of them hold real
values. A placeholder address (the legacy system sent one for half a year) is refused.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import __version__, naming
from .canonical import canonical_json, sha256_bytes
from .storage_roots import CHECKOUT

IDENTITY_SCHEMA = naming.schema_id("crawler-identity", 1)
FETCHER_VERSION = "http-fetcher/1"
DEFAULT_IDENTITY_FILE = CHECKOUT / "config" / "crawler_identity.json"
NOT_CONFIGURED = "not_configured"

SCOPE_EXTERNAL = "external"
SCOPE_LOOPBACK_TEST = "loopback_test"

_OPERATOR_FIELDS = ("crawler_name", "organisation", "contact_url", "contact_email")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,63}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
# Domains that never name a responsible party: reserved names, and the legacy placeholder.
_PLACEHOLDER_DOMAINS = ("example.com", "example.org", "example.net", "university.edu", "localhost")
_PLACEHOLDER_SUFFIXES = (".test", ".invalid", ".example", ".localhost", ".local")


class CrawlerIdentityNotConfigured(RuntimeError):
    """No usable operator identity is configured. External acquisition is refused."""


@dataclass(frozen=True)
class SoftwareIdentity:
    name: str = "coprepan"
    version: str = __version__
    fetcher: str = FETCHER_VERSION


@dataclass(frozen=True)
class OperatorIdentity:
    crawler_name: str
    organisation: str
    contact_url: str
    contact_email: str


@dataclass(frozen=True)
class CrawlerIdentity:
    operator: OperatorIdentity
    scope: str
    software: SoftwareIdentity = SoftwareIdentity()

    @property
    def user_agent(self) -> str:
        """``<crawler_name>/<package version> (+<contact_url>; <contact_email>)``."""
        return (f"{self.operator.crawler_name}/{self.software.version} "
                f"(+{self.operator.contact_url}; {self.operator.contact_email})")

    @property
    def robots_product_token(self) -> str:
        """The token a ``robots.txt`` group is matched against (RFC 9309 §2.2.1)."""
        return self.operator.crawler_name.lower()

    @property
    def crawler_version(self) -> str:
        return f"{self.software.name}/{self.software.version} {self.software.fetcher}"

    def as_record(self) -> dict[str, Any]:
        return {
            "schema": IDENTITY_SCHEMA, "scope": self.scope, "user_agent": self.user_agent,
            "operator": {name: getattr(self.operator, name) for name in _OPERATOR_FIELDS},
            "software": {"name": self.software.name, "version": self.software.version, "fetcher": self.software.fetcher},
        }

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json(self.as_record()))


def _is_placeholder(host: str) -> bool:
    host = host.lower().rstrip(".")
    return host in _PLACEHOLDER_DOMAINS or host.endswith(_PLACEHOLDER_SUFFIXES) or any(
        host.endswith("." + domain) for domain in _PLACEHOLDER_DOMAINS
    )


def validate_operator(operator: OperatorIdentity) -> list[str]:
    """Why this operator identity may not be sent to a real server; empty when it may."""
    problems = []
    for name in _OPERATOR_FIELDS:
        value = getattr(operator, name)
        if not isinstance(value, str) or not value.strip() or value == NOT_CONFIGURED:
            problems.append(f"{name} is not configured")
    if problems:
        return problems
    if _NAME.fullmatch(operator.crawler_name) is None:
        problems.append("crawler_name is one product token: a letter, then letters, digits, '-' or '_'")
    parts = urlsplit(operator.contact_url)
    if parts.scheme != "https" or not parts.hostname:
        problems.append("contact_url is an https URL of a page a publisher can read")
    elif _is_placeholder(parts.hostname):
        problems.append("contact_url names a placeholder domain")
    email = _EMAIL.fullmatch(operator.contact_email)
    if email is None:
        problems.append("contact_email is not an e-mail address")
    elif _is_placeholder(email.group(1)):
        problems.append("contact_email names a placeholder domain")
    return problems


def load_identity(path: Path | None = None) -> CrawlerIdentity:
    """The crawler identity for external requests, or a refusal that says what is missing."""
    path = Path(path) if path is not None else DEFAULT_IDENTITY_FILE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document["schema"] != IDENTITY_SCHEMA:
            raise ValueError(f"schema {document['schema']!r}")
        operator = OperatorIdentity(**{name: document[name] for name in _OPERATOR_FIELDS})
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CrawlerIdentityNotConfigured(f"crawler identity is not readable: {error}") from error
    problems = validate_operator(operator)
    if problems:
        raise CrawlerIdentityNotConfigured("crawler identity is not configured for external requests: " + "; ".join(problems))
    return CrawlerIdentity(operator, SCOPE_EXTERNAL)


def loopback_test_identity() -> CrawlerIdentity:
    """An identity that says what it is, for requests that never leave the machine.

    The policy gate lets an identity of this scope reach literal loopback addresses only.
    """
    return CrawlerIdentity(
        OperatorIdentity("coprepan-loopback-test", "none (local test)", "https://loopback.invalid/", "nobody@loopback.invalid"),
        SCOPE_LOOPBACK_TEST,
    )
