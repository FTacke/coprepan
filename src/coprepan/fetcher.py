"""HTTP transport (decision CPD-0006 §3).

One job: turn an allowed fetch intent into :class:`~coprepan.acquisition.RecordedExchange` objects
— one per attempt — that say exactly what was asked and what came back. It decides nothing about
content and extracts nothing.

* **Policy first.** Every request, including every redirect hop and the robots file, is put to the
  policy gate before a connection is opened. A denied intent makes no transport call.
* **The body is the HTTP payload as sent**: content coding intact, transfer coding removed. It is
  hashed and stored as received; a body cut short or longer than the limit is a failed fetch,
  never a shorter body.
* **Retries are explicit.** Which outcomes are retried, how often and after how long is stated
  here and recorded per attempt. Time and waiting are injected, so tests run without sleeping.
* **Standard library only** (``http.client``): no hidden retry, redirect or decoding behaviour.
* **One request at a time.** The pace per origin is the policy's minimum interval.
* **An access control ends the path** (CPD-0017 §4). What an answer shows — an authentication
  demand, a 403, a 429, a CAPTCHA, a bot challenge — is recorded with the exchange and is not
  retried; for the rest of this fetcher's life nothing more is asked of that origin. A redirect to
  a login or a paywall is not followed. Nothing here changes what the client says about itself.

``connect_override`` maps an origin to another address to connect to (as ``curl --connect-to``
does). Tests use it to serve an outlet's URLs from a loopback server; the policy gate is told the
address that is really dialled.
"""

from __future__ import annotations

import http.client
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

from . import access_control, acquisition, robots
from .acquisition import RecordedExchange
from .canonical import canonical_json, sha256_bytes
from .crawler_identity import CrawlerIdentity
from .identity import format_instant
from .policy import ALLOW, DEFER, DENY, FetchIntent, PolicyDecision, PolicyGate, _origin

REQUEST_ID_PREFIX = "rq1"
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)
RETRYABLE_FAILURES = ("timeout", "connection_error", "incomplete_response")
REDIRECT_STATUSES = (301, 302, 303, 307, 308)

FINAL_FETCHED, FINAL_FAILED, FINAL_DENIED, FINAL_DEFERRED = "FETCHED", "FETCH_FAILED", "DENIED", "DEFERRED"
RETRY_NONE, RETRY_SCHEDULED, RETRY_GAVE_UP = "none", "retry", "gave_up"

_READ_CHUNK = 64 * 1024


@dataclass(frozen=True)
class FetchLimits:
    """Every limit of the transport. All are required: none has a built-in value."""

    timeout_seconds: float
    max_redirects: int
    max_body_bytes: int
    max_attempts: int
    backoff_base_seconds: float
    backoff_max_seconds: float

    def __post_init__(self) -> None:
        for name in ("timeout_seconds", "max_redirects", "max_body_bytes", "max_attempts",
                     "backoff_base_seconds", "backoff_max_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"{name} must be a non-negative number: {value!r}")
        if self.max_attempts < 1 or self.timeout_seconds <= 0:
            raise ValueError("max_attempts is at least 1 and timeout_seconds is positive")

    def backoff(self, attempt: int) -> float:
        """Seconds to wait after attempt ``n`` failed: base · 2^(n-1), capped. No jitter: one
        client, one request at a time, and a run must be reproducible.
        """
        return min(self.backoff_base_seconds * (2 ** (attempt - 1)), self.backoff_max_seconds)


@dataclass(frozen=True)
class FetchRequest:
    url: str
    outlet_id: str
    fetch_kind: str = acquisition.FETCH_KIND_ITEM
    channel_id: str | None = None
    candidate_id: str | None = None
    # A conditional request (CPD-0007 §4): the validators of an earlier answer and which fetch
    # they came from. All four together or none.
    if_none_match: str | None = None
    if_modified_since: str | None = None
    revalidates_fetch_id: str | None = None
    revalidates_body_sha256: str | None = None
    # For a channel document: how far below the registered channel document it is (0: the channel
    # document itself; 1: a sitemap an index names, a next page). Budgets may tell the two apart.
    expansion_depth: int = 0

    def __post_init__(self) -> None:
        conditional = self.if_none_match is not None or self.if_modified_since is not None
        named = self.revalidates_fetch_id is not None and self.revalidates_body_sha256 is not None
        if conditional != named or (self.revalidates_fetch_id is None) != (self.revalidates_body_sha256 is None):
            raise ValueError("a conditional request names the fetch and the body it revalidates, and only it does")

    @property
    def conditional_headers(self) -> list[tuple[str, str]]:
        return [(name, value) for name, value in (("If-None-Match", self.if_none_match),
                                                  ("If-Modified-Since", self.if_modified_since)) if value]


@dataclass(frozen=True)
class Attempt:
    number: int
    exchange: RecordedExchange
    retry: str
    delay_seconds: float | None = None
    retry_after: str | None = None


@dataclass
class FetchOutcome:
    request: FetchRequest
    request_id: str
    final: str
    decision: PolicyDecision
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def exchanges(self) -> list[RecordedExchange]:
        return [attempt.exchange for attempt in self.attempts]

    @property
    def last(self) -> RecordedExchange | None:
        return self.attempts[-1].exchange if self.attempts else None


def request_id(request: FetchRequest, planned_at: datetime) -> str:
    """``rq1:`` + 32 hex over what is about to be asked and when it was planned."""
    preimage = canonical_json({"url": request.url, "outlet_id": request.outlet_id, "fetch_kind": request.fetch_kind,
                               "channel_id": request.channel_id, "planned_at": format_instant(planned_at)})
    return f"{REQUEST_ID_PREFIX}:{sha256_bytes(preimage)[:32]}"


def parse_retry_after(value: str | None, now: datetime) -> float | None:
    """Seconds asked for by ``Retry-After`` (delta-seconds or an HTTP date); ``None`` if unusable."""
    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0.0, (moment - now).total_seconds())


class HttpFetcher:
    def __init__(
        self,
        *,
        identity: CrawlerIdentity,
        gate: PolicyGate,
        limits: FetchLimits,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], None] = time.sleep,
        connect_override: Mapping[str, tuple[str, int]] | None = None,
        access_holds: Mapping[str, str] | None = None,
    ) -> None:
        self.identity, self.gate, self.limits = identity, gate, limits
        self.clock, self.sleep = clock, sleep
        self.connect_override = dict(connect_override or {})
        self._robots: dict[tuple[str, str], robots.RobotsEvidence] = {}
        self._last_request: dict[str, datetime] = {}
        self.robots_exchanges: list[tuple[str, RecordedExchange]] = []  # (outlet_id, exchange): evidence to preserve
        self.transport_calls = 0
        # origin -> the access control seen there. Given at construction when a run is resumed.
        self.access_holds: dict[str, str] = dict(access_holds or {})

    # -- public ----------------------------------------------------------------------------------

    def fetch(self, request: FetchRequest, *, planned_at: datetime | None = None) -> FetchOutcome:
        """Fetch one URL under the policy: zero or more attempts, each a recorded exchange."""
        planned_at = planned_at or self.clock()
        identifier = request_id(request, planned_at)
        decision = self._decide(request, request.url)
        if not decision.allowed:
            return FetchOutcome(request, identifier, FINAL_DENIED if decision.decision == DENY else FINAL_DEFERRED, decision)
        outcome = FetchOutcome(request, identifier, FINAL_FAILED, decision)
        for number in range(1, self.limits.max_attempts + 1):
            exchange = self._attempt(request, identifier, number, decision)
            retryable = (exchange.body is None and exchange.failure_reason in RETRYABLE_FAILURES) or (
                exchange.body is not None and exchange.status in RETRYABLE_STATUSES)
            refused = exchange.policy["access_class_observed"] in access_control.ACCESS_CONTROLS
            if refused and retryable:
                # A rate limit or a challenge is the server's refusal of this client. It is not asked
                # again in this call; when it named a time, that time is on record for the schedule.
                asked = parse_retry_after(dict((k.lower(), v) for k, v in exchange.response_headers).get("retry-after"),
                                          exchange.fetch_finished_at)
                retry_after = format_instant(exchange.fetch_finished_at + timedelta(seconds=asked)) if asked is not None else None
                outcome.attempts.append(Attempt(number, exchange, RETRY_GAVE_UP, asked, retry_after))
                break
            if not retryable:
                outcome.attempts.append(Attempt(number, exchange, RETRY_NONE))
                break
            asked = parse_retry_after(dict((k.lower(), v) for k, v in exchange.response_headers).get("retry-after"),
                                      exchange.fetch_finished_at)
            delay = max(self.limits.backoff(number), asked or 0.0)
            retry_after = format_instant(exchange.fetch_finished_at + timedelta(seconds=delay))
            if number == self.limits.max_attempts or (asked is not None and asked > self.limits.backoff_max_seconds):
                # Out of attempts, or the server asks for more patience than a run has: stop and
                # say when a later run may try again. Not a retry inside this call.
                outcome.attempts.append(Attempt(number, exchange, RETRY_GAVE_UP, delay, retry_after))
                break
            outcome.attempts.append(Attempt(number, exchange, RETRY_SCHEDULED, delay, retry_after))
            self.sleep(delay)
        outcome.final = FINAL_FETCHED if outcome.last is not None and outcome.last.body is not None else FINAL_FAILED
        return outcome

    def robots_evidence(self, outlet_id: str, origin: str) -> robots.RobotsEvidence:
        """The robots evidence of an origin, fetched once per fetcher through the same gate."""
        key = (outlet_id, origin)
        if key not in self._robots:
            request = FetchRequest(f"{origin}/robots.txt", outlet_id, acquisition.FETCH_KIND_ROBOTS)
            decision = self._decide(request, request.url)
            if not decision.allowed:
                self._robots[key] = robots.RobotsEvidence(robots.EVIDENCE_NOT_CONSULTED, detail=decision.reasons[0])
            else:
                exchange = self._attempt(request, request_id(request, self.clock()), 1, decision)
                self.robots_exchanges.append((outlet_id, exchange))
                # The exchange is preserved as received; the content coding is undone for parsing only.
                self._robots[key] = robots.evidence_from_response(
                    exchange.status, exchange.body, acquisition.content_encoding_of(exchange.response_headers))
        return self._robots[key]

    def robots_seen(self, outlet_id: str) -> list[robots.RobotsEvidence]:
        """The robots files this fetcher has read for an outlet's origins, in origin order."""
        return [evidence for (outlet, _), evidence in sorted(self._robots.items())
                if outlet == outlet_id and evidence.rules is not None]

    # -- policy ----------------------------------------------------------------------------------

    def _transport_target(self, url: str) -> tuple[str, str, int]:
        parts = urlsplit(url)
        origin = _origin(url)
        if origin in self.connect_override:
            host, port = self.connect_override[origin]
            return "http", host, port
        return parts.scheme, parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80)

    def _decide(self, request: FetchRequest, url: str) -> PolicyDecision:
        _, host, _ = self._transport_target(url)
        intent = FetchIntent(url, request.outlet_id, request.fetch_kind, self.clock(), host, request.channel_id)
        origin = _origin(url)
        if request.fetch_kind == acquisition.FETCH_KIND_ROBOTS:
            return self.gate.evaluate(intent, access_observed=self.access_holds.get(origin))
        # Ask the gate first without robots evidence: a request that is refused for another
        # reason must not cause a robots request either.
        first = self.gate.evaluate(intent, access_observed=self.access_holds.get(origin))
        if first.decision != DEFER or first.reasons != ("robots_not_consulted",):
            return first
        evidence = self.robots_evidence(request.outlet_id, origin)  # may itself meet an access control
        return self.gate.evaluate(intent, evidence, access_observed=self.access_holds.get(origin))

    # -- transport -------------------------------------------------------------------------------

    def _attempt(self, request: FetchRequest, identifier: str, number: int, decision: PolicyDecision) -> RecordedExchange:
        started = self.clock()
        url, chain, statuses, not_followed = request.url, [], [], None
        extra = request.conditional_headers
        policy = {
            "policy_decision": decision.acquisition_decision, "policy_version": decision.policy_version,
            "robots_decision": str(decision.evidence.get("robots_decision", "not_evaluated")),
            "robots_txt_sha256": str(decision.evidence.get("robots_txt_sha256", "not_applicable")),
            "access_class_observed": "unknown", "crawler_version": self.identity.crawler_version,
            "user_agent": self.identity.user_agent,
        }
        common = dict(requested_url=request.url, fetch_started_at=started, channel_id=request.channel_id,
                      fetch_kind=request.fetch_kind, request_id=identifier, attempt_number=number, policy=policy,
                      request_headers=tuple(self._request_headers(extra)))
        while True:
            try:
                status, headers, body = self._request(url, extra)
            except _TransportFailure as failure:
                return RecordedExchange(fetch_finished_at=self.clock(), failure_reason=failure.reason,
                                        failure_detail=failure.detail, redirect_chain=tuple(chain),
                                        redirect_statuses=tuple(statuses), **common)
            location = dict((k.lower(), v) for k, v in headers).get("location")
            if status in REDIRECT_STATUSES and location:
                target = urljoin(url, location.strip())
                if len(chain) >= self.limits.max_redirects:
                    return RecordedExchange(fetch_finished_at=self.clock(), failure_reason="redirect_limit_exceeded",
                                            failure_detail=f"more than {self.limits.max_redirects} redirects",
                                            redirect_chain=tuple(chain), redirect_statuses=tuple(statuses), **common)
                hop = self._decide(request, target)
                leads_to = access_control.classify_redirect(target) if hop.allowed else None
                if leads_to:
                    # A login or a paywall is where this path ends. The target is not requested.
                    policy["access_class_observed"] = leads_to
                    not_followed = f"ACCESS_CONTROL_OBSERVED: {leads_to}"
                elif hop.allowed:
                    if hop.acquisition_decision != ALLOW:  # a hop allowed by the research override: the record says so
                        policy["policy_decision"] = hop.acquisition_decision
                        policy["robots_decision"] = str(hop.evidence.get("robots_decision", policy["robots_decision"]))
                    chain.append(url)
                    statuses.append(status)
                    url = target
                    extra = []  # validators belong to the URL they came from, not to where it redirects
                    continue
                else:
                    not_followed = f"{hop.decision}: {hop.reasons[0]}"  # the redirect answer itself is the response
            revalidates = None
            if status == 304 and extra and body == b"":
                # The server says the body it sent before is still current. No body is stored for
                # this fetch; it points at the fetch that holds one.
                revalidates = {"fetch_id": request.revalidates_fetch_id, "body_sha256": request.revalidates_body_sha256}
            if policy["access_class_observed"] == access_control.UNKNOWN:
                policy["access_class_observed"] = access_control.classify_response(status, headers, body)
            if policy["access_class_observed"] in access_control.ORIGIN_HOLD:
                self.access_holds.setdefault(_origin(url) or url, policy["access_class_observed"])
            return RecordedExchange(fetch_finished_at=self.clock(), status=status, response_headers=tuple(headers),
                                    body=body, final_url=url, redirect_chain=tuple(chain),
                                    redirect_statuses=tuple(statuses), redirect_not_followed=not_followed,
                                    revalidates=revalidates, **common)

    def _request_headers(self, extra: Sequence[tuple[str, str]] = ()) -> list[tuple[str, str]]:
        return [("User-Agent", self.identity.user_agent), ("Accept", "*/*"), ("Accept-Encoding", "gzip"), *extra]

    def _pace(self, origin: str) -> None:
        # The policy's minimum, or the origin's own Crawl-delay where the policy makes it binding.
        seen = [evidence for (_, known), evidence in self._robots.items() if known == origin]
        interval = max([self.gate.interval_seconds(evidence) for evidence in seen] or [self.gate.min_interval_seconds or 0.0])
        last = self._last_request.get(origin)
        if last is not None:
            wait = interval - (self.clock() - last).total_seconds()
            if wait > 0:
                self.sleep(wait)
        self._last_request[origin] = self.clock()

    def _request(self, url: str, extra: Sequence[tuple[str, str]] = ()) -> tuple[int, list[tuple[str, str]], bytes]:
        parts = urlsplit(url)
        scheme, host, port = self._transport_target(url)
        self._pace(_origin(url) or url)
        self.transport_calls += 1
        connection_class = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        connection = connection_class(host, port, timeout=self.limits.timeout_seconds)
        try:
            path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            connection.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
            connection.putheader("Host", parts.netloc)
            for name, value in self._request_headers(extra):
                connection.putheader(name, value)
            connection.putheader("Connection", "close")
            connection.endheaders()
            response = connection.getresponse()
            headers = [(name, value) for name, value in response.getheaders()]
            chunks, size = [], 0
            while True:
                chunk = response.read(_READ_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.limits.max_body_bytes:
                    raise _TransportFailure("body_limit_exceeded", f"body exceeds {self.limits.max_body_bytes} bytes")
                chunks.append(chunk)
            if response.length:
                # http.client does not raise on a short read with an explicit amount: a body that
                # ends before its declared Content-Length is detected here.
                raise _TransportFailure("incomplete_response", f"{response.length} declared bytes never arrived")
            return response.status, headers, b"".join(chunks)
        except _TransportFailure:
            raise
        except http.client.IncompleteRead as error:
            raise _TransportFailure("incomplete_response", f"{len(error.partial)} bytes before the connection ended") from error
        except (socket.timeout, TimeoutError) as error:
            raise _TransportFailure("timeout", type(error).__name__) from error
        except http.client.HTTPException as error:
            raise _TransportFailure("malformed_response", type(error).__name__) from error
        except OSError as error:
            raise _TransportFailure("connection_error", type(error).__name__) from error
        finally:
            connection.close()


class _TransportFailure(Exception):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(reason)
        self.reason, self.detail = reason, detail
