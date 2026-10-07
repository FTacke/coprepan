"""The policy gate between a fetch intent and a request (master plan O-1; decision CPD-0006 §5).

```text
fetch intent → evaluate → ALLOW | DENY | DEFER, with reasons and evidence
```

**Nothing is allowed by default.** The tracked policy ships ``NOT_DECIDED``; under it every
external request is denied. The gate does not contain the policy — which robots signals bind,
what an opt-out is, how fast an origin may be asked are institutional decisions recorded in
``config/acquisition_policy.json``. The gate enforces whatever is recorded there, refuses when a
needed value is missing, and records what it applied with every fetch.

A *loopback test policy* exists for tests of the real transport against a server the test started.
It can only ever allow a literal loopback address.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from . import acquisition, naming, robots
from .crawler_identity import SCOPE_EXTERNAL, SCOPE_LOOPBACK_TEST, CrawlerIdentity
from .identity import IdentityError, format_instant, normalise_origin
from .registry import Registry, UnregisteredOutlet
from .storage_roots import CHECKOUT

POLICY_SCHEMA = naming.schema_id("acquisition-policy", 1)
DEFAULT_POLICY_FILE = CHECKOUT / "config" / "acquisition_policy.json"
NOT_DECIDED = "not_decided"

ALLOW, DENY, DEFER = "ALLOW", "DENY", "DEFER"
DECISIONS = (ALLOW, DENY, DEFER)
STATUS_DECIDED, STATUS_NOT_DECIDED = "DECIDED", "NOT_DECIDED"

ROBOTS_MODES = ("enforce", "record_only")
ON_ABSENT = ("allow", "deny")
ON_UNREACHABLE = ("allow", "deny", "defer")

_KEYS = {"schema", "note", "policy_version", "status", "scope", "external_acquisition", "robots", "rate_limit",
         "disabled_outlets", "disabled_channels", "opt_outs", "suppressions"}


class PolicyError(ValueError):
    """The policy document is not a policy this gate can enforce."""


@dataclass(frozen=True)
class FetchIntent:
    """What is about to be requested, for whom, and where the connection would actually go."""

    url: str
    outlet_id: str
    fetch_kind: str
    at: datetime
    transport_host: str
    channel_id: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reasons: tuple[str, ...]
    policy_version: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    retry_at: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == ALLOW


def load_policy(path: Path | None = None) -> dict[str, Any]:
    """Read the tracked policy. A loopback test policy is built in a test, never loaded."""
    try:
        document = json.loads(Path(path or DEFAULT_POLICY_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PolicyError(f"acquisition policy is not readable: {error}") from error
    validate_policy(document)
    if document["scope"] != SCOPE_EXTERNAL:
        raise PolicyError("a policy loaded from configuration has scope 'external'")
    return document


def validate_policy(document: Any) -> None:
    if not isinstance(document, dict) or set(document) - _KEYS or not (_KEYS - {"note"}) <= set(document):
        raise PolicyError(f"a policy has exactly the keys {sorted(_KEYS)}")
    if document["schema"] != POLICY_SCHEMA:
        raise PolicyError(f"schema is {document['schema']!r}, expected {POLICY_SCHEMA!r}")
    if document["status"] not in (STATUS_DECIDED, STATUS_NOT_DECIDED):
        raise PolicyError("status is DECIDED or NOT_DECIDED")
    if document["scope"] not in (SCOPE_EXTERNAL, SCOPE_LOOPBACK_TEST):
        raise PolicyError("scope is 'external' or 'loopback_test'")
    if document["external_acquisition"] not in ("enabled", "disabled"):
        raise PolicyError("external_acquisition is 'enabled' or 'disabled'")
    if not isinstance(document["policy_version"], str) or not document["policy_version"]:
        raise PolicyError("policy_version is a non-empty string")
    robots_block, rate = document["robots"], document["rate_limit"]
    if not isinstance(robots_block, dict) or set(robots_block) != {"mode", "on_absent", "on_unreachable"}:
        raise PolicyError("robots has exactly mode, on_absent, on_unreachable")
    if not isinstance(rate, dict) or set(rate) != {"min_interval_seconds_per_origin"}:
        raise PolicyError("rate_limit has exactly min_interval_seconds_per_origin")
    for name in ("disabled_outlets", "disabled_channels", "opt_outs", "suppressions"):
        if not isinstance(document[name], list):
            raise PolicyError(f"{name} is a list")
    for entry in document["opt_outs"]:
        if not isinstance(entry, dict) or not ({"reason", "recorded_at"} <= set(entry)) or not (set(entry) & {"outlet_id", "origin"}):
            raise PolicyError("an opt-out names an outlet_id or an origin, a reason and recorded_at")
    for entry in document["suppressions"]:
        if not isinstance(entry, dict) or not ({"reason", "until"} <= set(entry)) or not (set(entry) & {"outlet_id", "origin"}):
            raise PolicyError("a suppression names an outlet_id or an origin, a reason and until")
        try:
            datetime.strptime(entry["until"], "%Y-%m-%dT%H:%M:%S.%f%z")
        except (TypeError, ValueError) as error:
            raise PolicyError(f"suppression 'until' is a UTC instant: {error}") from error
    if document["status"] == STATUS_DECIDED:
        # A decided policy has decided everything it will be asked.
        problems = []
        if robots_block["mode"] not in ROBOTS_MODES:
            problems.append(f"robots.mode is one of {ROBOTS_MODES}")
        if robots_block["on_absent"] not in ON_ABSENT:
            problems.append(f"robots.on_absent is one of {ON_ABSENT}")
        if robots_block["on_unreachable"] not in ON_UNREACHABLE:
            problems.append(f"robots.on_unreachable is one of {ON_UNREACHABLE}")
        interval = rate["min_interval_seconds_per_origin"]
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval < 0:
            problems.append("rate_limit.min_interval_seconds_per_origin is a non-negative number")
        if document["policy_version"] in ("undecided", NOT_DECIDED):
            problems.append("a decided policy has a version")
        if problems:
            raise PolicyError("a DECIDED policy leaves nothing undecided: " + "; ".join(problems))


def loopback_test_policy(**overrides: Any) -> dict[str, Any]:
    """A decided policy of scope ``loopback_test``. The gate lets it allow loopback targets only."""
    policy = {
        "schema": POLICY_SCHEMA, "policy_version": "loopback-test/1", "status": STATUS_DECIDED,
        "scope": SCOPE_LOOPBACK_TEST, "external_acquisition": "disabled",
        "robots": {"mode": "enforce", "on_absent": "allow", "on_unreachable": "deny"},
        "rate_limit": {"min_interval_seconds_per_origin": 0},
        "disabled_outlets": [], "disabled_channels": [], "opt_outs": [], "suppressions": [],
    }
    policy.update(overrides)
    validate_policy(policy)
    return policy


def is_loopback_host(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _origin(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        return normalise_origin(f"{parts.scheme}://{parts.netloc}")
    except (IdentityError, ValueError):
        return None


class PolicyGate:
    """Evaluates fetch intents under one policy, one registry and one crawler identity."""

    def __init__(self, policy: Mapping[str, Any], registry: Registry, identity: CrawlerIdentity) -> None:
        validate_policy(dict(policy))
        self.policy, self.registry, self.identity = policy, registry, identity

    @property
    def min_interval_seconds(self) -> float | None:
        value = self.policy["rate_limit"]["min_interval_seconds_per_origin"]
        return None if isinstance(value, (str, bool)) else float(value)

    def evaluate(self, intent: FetchIntent, robots_evidence: robots.RobotsEvidence | None = None) -> PolicyDecision:
        """Decide one intent. The first refusal ends the evaluation; nothing is weighed against it."""
        policy = self.policy
        evidence: dict[str, Any] = {"policy_scope": policy["scope"], "identity_scope": self.identity.scope,
                                    "robots_decision": "not_evaluated", "robots_txt_sha256": "not_applicable"}

        def decide(decision: str, reason: str, retry_at: str | None = None) -> PolicyDecision:
            return PolicyDecision(decision, (reason,), policy["policy_version"], evidence, retry_at)

        if intent.fetch_kind not in acquisition.FETCH_KINDS:
            return decide(DENY, "unknown_fetch_kind")
        # 1. May anything be requested at all, and from here?
        if policy["status"] != STATUS_DECIDED:
            return decide(DENY, "policy_not_decided")
        if policy["scope"] != self.identity.scope:
            return decide(DENY, "identity_scope_does_not_match_policy_scope")
        if policy["scope"] == SCOPE_LOOPBACK_TEST:
            if not is_loopback_host(intent.transport_host):
                return decide(DENY, "loopback_test_policy_cannot_reach_a_non_loopback_address")
        elif policy["external_acquisition"] != "enabled":
            return decide(DENY, "external_acquisition_disabled")
        elif is_loopback_host(intent.transport_host):
            return decide(DENY, "external_policy_does_not_cover_loopback_targets")

        # 2. Is this a source the registry stands behind?
        try:
            outlet = self.registry.resolve(intent.outlet_id)
        except UnregisteredOutlet:
            return decide(DENY, "outlet_not_registered")
        origin = _origin(intent.url)
        if origin is None:
            return decide(DENY, "unusable_url")
        channel_origins = {_origin(channel["url_history"][-1]["url"]) for channel in outlet["channels"]}
        allowed_origins = set(outlet["web_origins"])
        if intent.fetch_kind != acquisition.FETCH_KIND_ITEM:
            allowed_origins |= channel_origins - {None}  # a feed may live on a host that publishes no article
        if origin not in allowed_origins:
            return decide(DENY, "off_origin")
        if intent.channel_id is not None and intent.channel_id not in {c["channel_id"] for c in outlet["channels"]}:
            return decide(DENY, "channel_not_registered")

        # 3. Operator switches, opt-outs, suppressions.
        if intent.outlet_id in policy["disabled_outlets"]:
            return decide(DENY, "outlet_disabled")
        if intent.channel_id is not None and intent.channel_id in policy["disabled_channels"]:
            return decide(DENY, "channel_disabled")
        for entry in policy["opt_outs"]:
            if entry.get("outlet_id") == intent.outlet_id or entry.get("origin") == origin:
                evidence["opt_out"] = dict(entry)
                return decide(DENY, "explicit_opt_out")
        now = format_instant(intent.at)
        for entry in policy["suppressions"]:
            if (entry.get("outlet_id") == intent.outlet_id or entry.get("origin") == origin) and now < entry["until"]:
                evidence["suppression"] = dict(entry)
                return decide(DEFER, "temporarily_suppressed", entry["until"])

        # 4. Rate limit: a request without a configured pace is not made.
        if self.min_interval_seconds is None:
            return decide(DENY, "rate_limit_not_configured")

        # 5. robots.txt — evidence, weighed as the policy says. The robots file itself is always
        #    requestable: it is how the evidence is obtained.
        if intent.fetch_kind != acquisition.FETCH_KIND_ROBOTS:
            mode = policy["robots"]["mode"]
            if robots_evidence is None or robots_evidence.state == robots.EVIDENCE_NOT_CONSULTED:
                return decide(DEFER, "robots_not_consulted")
            evidence["robots_state"] = robots_evidence.state
            evidence["robots_txt_sha256"] = robots_evidence.sha256
            if robots_evidence.rules is not None:
                # Recorded as written and handed on to scheduling. Whether it binds is the
                # policy's to say (O-1); nothing here applies it.
                delays = robots_evidence.rules.crawl_delays
                evidence["robots_crawl_delay"] = delays.get(self.identity.robots_product_token, delays.get("*"))
                evidence["robots_sitemaps"] = list(robots_evidence.rules.sitemaps)
            if robots_evidence.state == robots.EVIDENCE_ABSENT:
                evidence["robots_decision"] = "absent"
                if policy["robots"]["on_absent"] == "deny":
                    return decide(DENY, "robots_absent")
            elif robots_evidence.state == robots.EVIDENCE_UNREACHABLE:
                evidence["robots_decision"] = "unreachable"
                action = policy["robots"]["on_unreachable"]
                if action != "allow":
                    return decide(DENY if action == "deny" else DEFER, "robots_unreachable")
            else:
                parts = urlsplit(intent.url)
                path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
                verdict, rule = robots_evidence.rules.evaluate(self.identity.robots_product_token, path)
                evidence["robots_decision"], evidence["robots_rule"] = verdict, rule
                if verdict == robots.DISALLOWED and mode == "enforce":
                    return decide(DENY, "robots_disallow")
        return decide(ALLOW, "allowed_by_policy")
