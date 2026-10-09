"""The policy gate between a fetch intent and a request (master plan O-1; decision CPD-0006 §5).

```text
fetch intent → evaluate → ALLOW | DENY | DEFER, with reasons and evidence
```

**Three layers, never one** (decision CPD-0017). What a robots file says is *evidence*
(``robots_evidence``); whether the project's research text-and-data-mining policy covers the request
is a second, separate statement (``research_tdm``); the *acquisition decision* is the third
(``ALLOW`` · ``ALLOW_RESEARCH_OVERRIDE`` · ``REFUSE`` · ``HOLD``). A ``Disallow`` is recorded as
observed. Under the mode ``research_tdm_override`` it is overridden only when every condition of the
research policy holds, and then openly: the decision says so, names its basis and the rule. A
technical access control is never weighed against anything — it is observed by the fetcher and ends
the path.

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
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from . import acquisition, naming, robots
from .crawler_identity import SCOPE_EXTERNAL, SCOPE_LOOPBACK_TEST, CrawlerIdentity
from .canonical import canonical_json, sha256_bytes
from .identity import IdentityError, format_instant, normalise_origin
from .registry import Registry, UnregisteredOutlet
from .storage_roots import CHECKOUT

# v2: Crawl-delay may bind (CPD-0013). v3: the research-TDM layer and `on_parse_error` (CPD-0017).
# No request was ever made under v1 or v2.
POLICY_SCHEMA = naming.schema_id("acquisition-policy", 3)
DEFAULT_POLICY_FILE = CHECKOUT / "config" / "acquisition_policy.json"
NOT_DECIDED = "not_decided"

ALLOW, DENY, DEFER = "ALLOW", "DENY", "DEFER"
DECISIONS = (ALLOW, DENY, DEFER)
STATUS_DECIDED, STATUS_NOT_DECIDED = "DECIDED", "NOT_DECIDED"

# `enforce`: an applicable Disallow refuses. `research_tdm_override`: it refuses unless the research
# layer is eligible, and then the override is on record. `record_only` exists for tests on loopback
# only: a policy loaded from configuration may not use it — an override is never silent.
ROBOTS_MODES = ("enforce", "research_tdm_override", "record_only")
ON_ABSENT = ("allow", "deny")
ON_UNREACHABLE = ("allow", "deny", "defer")
ON_PARSE_ERROR = ("allow", "deny", "defer")

# Layer 1 — what the robots protocol evidence is.
ROBOTS_ALLOW, ROBOTS_DISALLOW_OBSERVED = "ROBOTS_ALLOW", "ROBOTS_DISALLOW_OBSERVED"
ROBOTS_UNAVAILABLE, ROBOTS_UNREACHABLE = "ROBOTS_UNAVAILABLE", "ROBOTS_UNREACHABLE"   # RFC 9309 §2.3.1.3 and §2.3.1.4
ROBOTS_PARSE_ERROR, ROBOTS_NOT_EVALUATED = "ROBOTS_PARSE_ERROR", "ROBOTS_NOT_EVALUATED"
# Layer 2 — whether the research-TDM policy covers the request.
RESEARCH_TDM_ELIGIBLE, RESEARCH_TDM_NOT_APPLICABLE, RESEARCH_TDM_REVIEW = (
    "RESEARCH_TDM_ELIGIBLE", "RESEARCH_TDM_NOT_APPLICABLE", "RESEARCH_TDM_REVIEW")
# Layer 3 — the acquisition decision. `decision` (ALLOW · DENY · DEFER) stays what the transport and
# the schedule act on; this says what kind of allowance or refusal it is.
ALLOW_RESEARCH_OVERRIDE, REFUSE, HOLD = "ALLOW_RESEARCH_OVERRIDE", "REFUSE", "HOLD"
ACQUISITION_DECISIONS = ("ALLOW", ALLOW_RESEARCH_OVERRIDE, REFUSE, HOLD)
# Evidence classes of what stops a request for a person to look at, not for good.
ACCESS_CONTROL_OBSERVED, DIRECT_OPT_OUT, LEGAL_REVIEW_HOLD = "ACCESS_CONTROL_OBSERVED", "DIRECT_OPT_OUT", "LEGAL_REVIEW_HOLD"
_HOLD_REASONS = {"access_control_observed": ACCESS_CONTROL_OBSERVED, "explicit_opt_out": DIRECT_OPT_OUT,
                 "legal_review_hold": LEGAL_REVIEW_HOLD}

# /1: Disallow denies. /2: the three layers of CPD-0017. /3 (CPD-0027): a 401 or 403 for the robots address is a robots
# file that is not available and holds nothing by itself; a 429 for it is unreachable; holds have a scope.
ROBOTS_DECISION_SEMANTICS = "robots-decision/3"
TDM_BASIS_NONE = "not_applicable"
TDM_BASES = ("SCIENTIFIC_TDM_POLICY_V1",)
# Every one must be stated `true` by the decided policy for a research override to exist. They are
# the operator's statements about the project (CPD-0017 §3), not things the gate can observe; what
# the gate and the fetcher can observe — the scheme, an access control — is checked where it occurs.
TDM_CONDITIONS = ("scientific_research_purpose", "research_organisation_operator", "non_commercial",
                  "public_unauthenticated_http_only", "no_access_control_circumvention", "conservative_rate_limits",
                  "protected_research_storage", "no_public_redistribution_of_raw_material")
_TDM_KEYS = {"basis", "decision", "conditions", "legal_review_holds"}
# What a `Crawl-delay` line of robots.txt does. It is not part of RFC 9309; whether it binds is the policy's to say.
CRAWL_DELAY_MODES = ("binding_minimum", "record_only")
_RATE_KEYS = {"min_interval_seconds_per_origin", "crawl_delay", "crawl_delay_max_seconds"}
_DELAY = re.compile(r"\d{1,6}(?:\.\d{1,3})?")

_KEYS = {"schema", "note", "policy_version", "status", "scope", "external_acquisition", "robots", "research_tdm", "rate_limit",
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

    @property
    def acquisition_decision(self) -> str:
        """Layer 3: ``ALLOW``, ``ALLOW_RESEARCH_OVERRIDE``, ``REFUSE`` or ``HOLD``."""
        return self.evidence.get("acquisition_decision") or {ALLOW: ALLOW, DENY: REFUSE, DEFER: HOLD}[self.decision]


def load_policy(path: Path | None = None) -> dict[str, Any]:
    """Read the tracked policy. A loopback test policy is built in a test, never loaded."""
    try:
        document = json.loads(Path(path or DEFAULT_POLICY_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PolicyError(f"acquisition policy is not readable: {error}") from error
    validate_policy(document)
    if document["scope"] != SCOPE_EXTERNAL:
        raise PolicyError("a policy loaded from configuration has scope 'external'")
    if document["robots"]["mode"] == "record_only":
        raise PolicyError("a policy loaded from configuration does not ignore robots.txt silently: "
                          "robots.mode is 'enforce' or 'research_tdm_override'")
    return document


def research_tdm_pin(document: Mapping[str, Any]) -> dict[str, Any]:
    """What a baseline pins about the research-TDM layer: its basis, the decision semantics and one
    digest over everything that decides how robots evidence, the research layer and the pace act.
    """
    block = document["research_tdm"]
    decisive = {"semantics": ROBOTS_DECISION_SEMANTICS, "robots": document["robots"], "rate_limit": document["rate_limit"],
                "basis": block["basis"], "decision": block["decision"], "conditions": block["conditions"]}
    return {"research_tdm_policy_version": block["basis"], "decided_in": block["decision"],
            "robots_decision_semantics": ROBOTS_DECISION_SEMANTICS, "robots_mode": document["robots"]["mode"],
            "research_tdm_policy_sha256": sha256_bytes(canonical_json(decisive))}


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
    if not isinstance(robots_block, dict) or set(robots_block) != {"mode", "on_absent", "on_unreachable", "on_parse_error"}:
        raise PolicyError("robots has exactly mode, on_absent, on_unreachable, on_parse_error")
    tdm = document["research_tdm"]
    if not isinstance(tdm, dict) or set(tdm) != _TDM_KEYS or not isinstance(tdm["conditions"], dict) \
            or not isinstance(tdm["legal_review_holds"], list) or not isinstance(tdm["decision"], str):
        raise PolicyError(f"research_tdm has exactly {sorted(_TDM_KEYS)}")
    if tdm["basis"] not in (TDM_BASIS_NONE, *TDM_BASES):
        raise PolicyError(f"research_tdm.basis is one of {(TDM_BASIS_NONE, *TDM_BASES)}")
    if tdm["basis"] != TDM_BASIS_NONE and (set(tdm["conditions"]) != set(TDM_CONDITIONS)
                                           or any(not isinstance(v, bool) for v in tdm["conditions"].values())):
        raise PolicyError(f"research_tdm.conditions states each of {TDM_CONDITIONS} as true or false")
    for entry in tdm["legal_review_holds"]:
        if not isinstance(entry, dict) or not ({"reason", "recorded_at"} <= set(entry)) or not (set(entry) & {"outlet_id", "origin"}):
            raise PolicyError("a legal review hold names an outlet_id or an origin, a reason and recorded_at")
    if not isinstance(rate, dict) or set(rate) != _RATE_KEYS:
        raise PolicyError(f"rate_limit has exactly {sorted(_RATE_KEYS)}")
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
        if robots_block["on_parse_error"] not in ON_PARSE_ERROR:
            problems.append(f"robots.on_parse_error is one of {ON_PARSE_ERROR}")
        if robots_block["mode"] == "research_tdm_override" and tdm["basis"] == TDM_BASIS_NONE:
            problems.append("robots.mode 'research_tdm_override' needs a research_tdm.basis")
        interval = rate["min_interval_seconds_per_origin"]
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval < 0:
            problems.append("rate_limit.min_interval_seconds_per_origin is a non-negative number")
        if rate["crawl_delay"] not in CRAWL_DELAY_MODES:
            problems.append(f"rate_limit.crawl_delay is one of {CRAWL_DELAY_MODES}")
        limit = rate["crawl_delay_max_seconds"]
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit < 0:
            problems.append("rate_limit.crawl_delay_max_seconds is a non-negative number")
        if document["policy_version"] in ("undecided", NOT_DECIDED):
            problems.append("a decided policy has a version")
        if problems:
            raise PolicyError("a DECIDED policy leaves nothing undecided: " + "; ".join(problems))


def loopback_test_policy(**overrides: Any) -> dict[str, Any]:
    """A decided policy of scope ``loopback_test``. The gate lets it allow loopback targets only."""
    policy = {
        "schema": POLICY_SCHEMA, "policy_version": "loopback-test/1", "status": STATUS_DECIDED,
        "scope": SCOPE_LOOPBACK_TEST, "external_acquisition": "disabled",
        "robots": {"mode": "enforce", "on_absent": "allow", "on_unreachable": "deny", "on_parse_error": "defer"},
        "research_tdm": {"basis": TDM_BASIS_NONE, "decision": TDM_BASIS_NONE, "conditions": {}, "legal_review_holds": []},
        "rate_limit": {"min_interval_seconds_per_origin": 0, "crawl_delay": "record_only", "crawl_delay_max_seconds": 0},
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

    def crawl_delay_seconds(self, robots_evidence: robots.RobotsEvidence | None) -> float | None:
        """The pause an origin's robots file asks of this crawler, in seconds — when the policy
        makes `Crawl-delay` binding and the value is an unambiguous non-negative decimal number.
        The line for the crawler's own product token wins over the one for ``*``. Anything else
        (no line, another syntax, a policy that only records) is ``None``: recorded, not applied.
        """
        if self.policy["rate_limit"]["crawl_delay"] != "binding_minimum" or robots_evidence is None or robots_evidence.rules is None:
            return None
        delays = robots_evidence.rules.crawl_delays
        written = delays.get(self.identity.robots_product_token, delays.get("*"))
        if not isinstance(written, str) or _DELAY.fullmatch(written.strip()) is None:
            return None
        return float(written.strip())

    def interval_seconds(self, robots_evidence: robots.RobotsEvidence | None) -> float:
        """The pause between two requests to one origin: the policy's minimum, or the origin's
        binding `Crawl-delay` when that is longer. Never shorter than the policy's minimum.
        """
        return max(self.min_interval_seconds or 0.0, self.crawl_delay_seconds(robots_evidence) or 0.0)

    def research_tdm(self, intent: FetchIntent) -> tuple[str, list[str]]:
        """Layer 2 for one intent: the status and, when it is not eligible, what is missing.

        Eligible means: the policy names a basis, states every condition as true, and the request is
        a plain ``http``/``https`` one. A legal review hold or an opt-out for the source never
        reaches this point — it has ended the evaluation before.
        """
        block = self.policy["research_tdm"]
        if block["basis"] == TDM_BASIS_NONE:
            return RESEARCH_TDM_NOT_APPLICABLE, []
        unmet = [name for name in TDM_CONDITIONS if block["conditions"].get(name) is not True]
        if urlsplit(intent.url).scheme not in ("http", "https") or urlsplit(intent.url).username is not None:
            unmet.append("plain_http_request_without_credentials")
        return (RESEARCH_TDM_REVIEW, unmet) if unmet else (RESEARCH_TDM_ELIGIBLE, [])

    def evaluate(self, intent: FetchIntent, robots_evidence: robots.RobotsEvidence | None = None, *,
                 access_observed: str | None = None) -> PolicyDecision:
        """Decide one intent. The first refusal ends the evaluation; nothing is weighed against it.

        ``access_observed`` is the technical access control the fetcher has seen at this origin in
        this run, if any: it refuses whatever a robots file or the research layer would say.
        """
        policy = self.policy
        evidence: dict[str, Any] = {"policy_scope": policy["scope"], "identity_scope": self.identity.scope,
                                    "robots_decision": "not_evaluated", "robots_txt_sha256": "not_applicable",
                                    "robots_evidence": ROBOTS_NOT_EVALUATED, "robots_decision_semantics": ROBOTS_DECISION_SEMANTICS}

        def decide(decision: str, reason: str, retry_at: str | None = None) -> PolicyDecision:
            evidence.setdefault("acquisition_decision", ALLOW if decision == ALLOW else
                                HOLD if decision == DEFER or reason in _HOLD_REASONS else REFUSE)
            if reason in _HOLD_REASONS:
                evidence["hold_class"] = _HOLD_REASONS[reason]
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
                # A publisher's direct request: nothing more is asked, and a person decides what
                # follows. Nothing already preserved is deleted by this.
                evidence["opt_out"] = dict(entry)
                return decide(DENY, "explicit_opt_out")
        for entry in policy["research_tdm"]["legal_review_holds"]:
            if entry.get("outlet_id") == intent.outlet_id or entry.get("origin") == origin:
                evidence["legal_review_hold"] = dict(entry)
                return decide(DENY, "legal_review_hold")
        if access_observed is not None:
            # A fact of the server, seen in this run. Not a robots matter and never overridden.
            evidence["access_class_observed"] = access_observed
            return decide(DENY, "access_control_observed")
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
                # Recorded as written. Whether it binds is the policy's to say (O-1,
                # `rate_limit.crawl_delay`); the fetcher's pace applies it when it does.
                delays = robots_evidence.rules.crawl_delays
                evidence["robots_crawl_delay"] = delays.get(self.identity.robots_product_token, delays.get("*"))
                evidence["robots_sitemaps"] = list(robots_evidence.rules.sitemaps)
                binding = self.crawl_delay_seconds(robots_evidence)
                evidence["robots_crawl_delay_binding_seconds"] = binding
                if binding is not None and binding > float(policy["rate_limit"]["crawl_delay_max_seconds"]):
                    # The origin asks for a slower pace than this policy is willing to keep. It is
                    # not fetched faster than asked: it is not fetched.
                    return decide(DENY, "robots_crawl_delay_exceeds_limit")
            if robots_evidence.state == robots.EVIDENCE_ABSENT:
                evidence["robots_decision"], evidence["robots_evidence"] = "absent", ROBOTS_UNAVAILABLE
                if policy["robots"]["on_absent"] == "deny":
                    return decide(DENY, "robots_absent")
            elif robots_evidence.state == robots.EVIDENCE_UNREACHABLE:
                evidence["robots_decision"], evidence["robots_evidence"] = "unreachable", ROBOTS_UNREACHABLE
                action = policy["robots"]["on_unreachable"]
                if action != "allow":
                    return decide(DENY if action == "deny" else DEFER, "robots_unreachable")
            elif robots_evidence.rules.parse_error:
                # Something answered at /robots.txt and none of it is a robots line. It is neither
                # read as a permission nor as a prohibition: the policy says what happens.
                evidence["robots_decision"], evidence["robots_evidence"] = "parse_error", ROBOTS_PARSE_ERROR
                action = policy["robots"]["on_parse_error"]
                if action != "allow":
                    return decide(DENY if action == "deny" else DEFER, "robots_parse_error")
            else:
                parts = urlsplit(intent.url)
                path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
                verdict, rule = robots_evidence.rules.evaluate(self.identity.robots_product_token, path)
                evidence["robots_decision"], evidence["robots_rule"] = verdict, rule
                evidence["robots_evidence"] = ROBOTS_DISALLOW_OBSERVED if verdict == robots.DISALLOWED else ROBOTS_ALLOW
                if verdict == robots.DISALLOWED and mode != "record_only":
                    # Layer 1 says Disallow. Layer 2 is asked only now, and only under the mode that
                    # names it; layer 3 is the answer. There is no path from here to ALLOW that is
                    # not written into the decision.
                    status, unmet = self.research_tdm(intent)
                    evidence["research_tdm"] = status
                    if mode != "research_tdm_override" or status != RESEARCH_TDM_ELIGIBLE:
                        if unmet:
                            evidence["research_tdm_unmet"] = unmet
                        return decide(DENY, "robots_disallow")
                    evidence["acquisition_decision"] = ALLOW_RESEARCH_OVERRIDE
                    evidence["override"] = {
                        "basis": policy["research_tdm"]["basis"], "decided_in": policy["research_tdm"]["decision"],
                        "robots_rule": rule, "robots_txt_sha256": robots_evidence.sha256,
                        "product_token": self.identity.robots_product_token, "conditions": list(TDM_CONDITIONS),
                        "url": intent.url, "at": format_instant(intent.at)}
                    return decide(ALLOW, "research_tdm_override")
        evidence["research_tdm"] = self.research_tdm(intent)[0]
        return decide(ALLOW, "allowed_by_policy")
