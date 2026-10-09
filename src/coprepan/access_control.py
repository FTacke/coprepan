"""Technical access controls as observed evidence (decision CPD-0017 §4).

A robots file is a request of the publisher; an access control is a fact of the server. This module
names what an answer shows — an authentication demand, a refusal, an enforced rate limit, a CAPTCHA,
a bot challenge, a redirect to a login or a paywall — and nothing else. It never suggests a way
past any of them: what is observed here ends the path (or, for the classes in
:data:`ORIGIN_HOLD`, every further request to that origin in the run), and the fetcher records it.

The markers are deliberately few and conservative. A false positive stops a path that could have
been read; a false negative stores a challenge page, which the extraction and the review then show.
Neither leads to a request that should not have been made.
"""

from __future__ import annotations

import zlib
from typing import Iterable
from urllib.parse import urlsplit

# /2 (canary finding F2, CPD-0019): the Sucuri JavaScript challenge is known, and a small body is
# inspected whatever its status — the challenge of 2026-10-08 came as a 307 without a `Location`.
# /3 (qualification run of 2026-10-09): Cloudflare's detection script on an ordinary page is not a challenge
# (`mx_la_jornada`: a 410 Gone of a retired feed held the origin; `py_adn_digital`: a plain 403 was named a challenge).
# /4 (CPD-0027): a block page of a content-delivery firewall is named for what it is (`blocked`), because a plain 403
# for a robots address no longer holds anything and such a page must (`mx_milenio`: CloudFront, "Request blocked").
CLASSIFIER_VERSION = "access-control/4"

NONE_OBSERVED = "none_observed"
UNKNOWN = "unknown"                       # no answer was classified (a transport failure, a replay)
AUTH_REQUIRED = "auth_required"           # 401, 407
FORBIDDEN = "forbidden"                   # 403 without a recognised challenge
LEGAL_BLOCK = "unavailable_for_legal_reasons"  # 451
RATE_LIMITED = "rate_limited"             # 429
CAPTCHA = "captcha"
BOT_CHALLENGE = "bot_challenge"
BLOCKED = "blocked"                       # a protection service's own block page: the request was refused by a firewall rule
LOGIN_REDIRECT = "login_redirect"
PAYWALL_REDIRECT = "paywall_redirect"

ACCESS_CONTROLS = (AUTH_REQUIRED, FORBIDDEN, LEGAL_BLOCK, RATE_LIMITED, CAPTCHA, BOT_CHALLENGE, BLOCKED, LOGIN_REDIRECT, PAYWALL_REDIRECT)
# The classes that hold something. *What* they hold depends on what was asked: `hold_scope`.
ORIGIN_HOLD = (AUTH_REQUIRED, FORBIDDEN, LEGAL_BLOCK, RATE_LIMITED, CAPTCHA, BOT_CHALLENGE, BLOCKED)

# How far an observed access control reaches (CPD-0027). Until 2026-10-09 every class of `ORIGIN_HOLD` held the whole
# origin whatever had been asked: a 403 for a robots address, a retired feed or a challenged sitemap each ended an outlet.
HOLD_SCOPE_VERSION = "access-hold-scope/1"
SCOPE_ORIGIN, SCOPE_URL = "origin", "url"
_ACTIVE_CONTROLS = (CAPTCHA, BOT_CHALLENGE, BLOCKED, LEGAL_BLOCK)    # the server acts against this client or this use: not a status alone
KIND_ROBOTS, KIND_CHANNEL, KIND_ITEM = "robots_txt", "channel_document", "item"


def hold_scope(fetch_kind: str, access_class: str) -> str | None:
    """What an access control observed on one answer holds: the origin, that one URL, or nothing.

    - a **rate limit** (429) holds the origin whatever was asked: the server says "slower", and it means all of it;
    - on a **robots address**: a challenge, a CAPTCHA or a legal block holds the origin — a server that challenges
      even that address challenges this client. A plain 401 or 403 holds **nothing**: it is a robots file that is not
      available (RFC 9309 §2.3.1.3), which is the robots layer's to weigh, and the resource that is then asked for
      answers for itself;
    - on a **channel document** (a feed, a sitemap, a listing): any control holds **that URL**. One discovery route
      that is refused or challenged is not the outlet; the route is not asked again;
    - on an **item page** — the thing itself — any control holds the origin: nothing more is asked of it.

    Never a way past anything: what is held is not requested, by this run or a later one.
    """
    if access_class not in ORIGIN_HOLD:
        return None
    if access_class == RATE_LIMITED:
        return SCOPE_ORIGIN
    if fetch_kind == KIND_ROBOTS:
        return SCOPE_ORIGIN if access_class in _ACTIVE_CONTROLS else None
    if fetch_kind == KIND_CHANNEL:
        return SCOPE_URL
    return SCOPE_ORIGIN

_INSPECTED_BYTES = 64 * 1024
_SMALL_BODY_BYTES = 32 * 1024             # a challenge page is small; an article that embeds a form widget is not
_CAPTCHA_MARKERS = (b"g-recaptcha", b"h-captcha", b"hcaptcha.com/1/api.js", b"cf-turnstile", b"captcha-delivery.com", b"px-captcha")
# Cloudflare: the challenge itself (`…/challenge-platform/h/…/orchestrate/…`, `_cf_chl_opt`) — not the path
# `cdn-cgi/challenge-platform` alone, which also carries the detection script Cloudflare adds to ordinary pages
# (`…/scripts/jsd/main.js`): a plain 410 with that script was read as a challenge and held an origin whose feed worked.
_CHALLENGE_MARKERS = (b"cdn-cgi/challenge-platform/h/", b"_cf_chl_opt", b"cf-chl-", b"just a moment...", b"checking your browser",
                      b"attention required! | cloudflare", b"_incapsula_resource", b"ddos-guard",
                      # Sucuri CloudProxy: a script that computes a cookie and reloads the page.
                      b"sucuri_cloudproxy_js", b"sucuri_cloudproxy_uuid")
# A firewall's block page: two marks of the same page, so that an article about a blocked request is not one.
_BLOCK_PAGES = ((b"request blocked", b"generated by cloudfront"), (b"access denied", b"errors.edgesuite.net"))
_LOGIN_SEGMENTS = frozenset(("login", "log-in", "signin", "sign-in", "iniciar-sesion", "inicio-sesion", "ingresar", "acceder",
                             "auth", "sso", "account", "accounts", "cuenta", "mi-cuenta", "registro", "register"))
_PAYWALL_SEGMENTS = frozenset(("paywall", "suscripcion", "suscripciones", "suscribete", "suscribirse", "subscribe",
                               "subscription", "subscriptions", "premium", "checkout"))


def _decoded_prefix(body: bytes, headers: Iterable[tuple[str, str]]) -> bytes:
    """The first bytes of a body with its content coding undone, lower-cased. Unreadable: as sent."""
    coding = next((value.strip().lower() for name, value in headers if name.lower() == "content-encoding"), "identity")
    data = body
    if coding in ("gzip", "x-gzip", "deflate"):
        try:
            data = zlib.decompressobj(47 if coding != "deflate" else 15).decompress(body, _INSPECTED_BYTES)
        except zlib.error:
            data = body
    return data[:_INSPECTED_BYTES].lower()


def classify_response(status: int, headers: Iterable[tuple[str, str]], body: bytes) -> str:
    """What an answer shows about access. One class per answer; a challenge outranks its status."""
    headers = list(headers)
    lowered = {name.lower(): value.strip().lower() for name, value in headers}
    if lowered.get("cf-mitigated") == "challenge":
        return BOT_CHALLENGE
    # A challenge page is small and comes with whatever status the protection likes: 200, 403, 503,
    # or a redirect status that names no target. The status therefore does not select what is read;
    # the size does, except for the three statuses a protection typically answers with.
    if status in (403, 429, 503) or len(body) <= _SMALL_BODY_BYTES:
        text = _decoded_prefix(body, headers)
        if any(marker in text for marker in _CAPTCHA_MARKERS):
            return CAPTCHA
        if any(marker in text for marker in _CHALLENGE_MARKERS):
            return BOT_CHALLENGE
        if status in (403, 429, 503) and any(all(mark in text for mark in page) for page in _BLOCK_PAGES):
            return BLOCKED
    if status in (401, 407):
        return AUTH_REQUIRED
    if status == 403:
        return FORBIDDEN
    if status == 451:
        return LEGAL_BLOCK
    if status == 429:
        return RATE_LIMITED
    return NONE_OBSERVED


def classify_redirect(target: str) -> str | None:
    """A redirect that leads to a login or a paywall, judged by whole path segments and host labels
    of its target. Such a target is never requested: the redirect answer is the evidence.
    """
    try:
        parts = urlsplit(target)
    except ValueError:
        return None
    names = {segment.lower() for segment in parts.path.split("/") if segment}
    names |= set((parts.hostname or "").lower().split(".")[:-2])
    if names & _LOGIN_SEGMENTS:
        return LOGIN_REDIRECT
    if names & _PAYWALL_SEGMENTS:
        return PAYWALL_REDIRECT
    return None


def tdm_reservation(headers: Iterable[tuple[str, str]]) -> str | None:
    """A machine-readable text-and-data-mining reservation in the response headers (the
    ``tdm-reservation`` field of the TDM Reservation Protocol), as written. Recorded as evidence
    of a general reservation; what it means for research is the policy's to say (CPD-0017 §5).
    """
    return next((value.strip() for name, value in headers if name.lower() == "tdm-reservation"), None)
