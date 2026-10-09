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
CLASSIFIER_VERSION = "access-control/2"

NONE_OBSERVED = "none_observed"
UNKNOWN = "unknown"                       # no answer was classified (a transport failure, a replay)
AUTH_REQUIRED = "auth_required"           # 401, 407
FORBIDDEN = "forbidden"                   # 403 without a recognised challenge
LEGAL_BLOCK = "unavailable_for_legal_reasons"  # 451
RATE_LIMITED = "rate_limited"             # 429
CAPTCHA = "captcha"
BOT_CHALLENGE = "bot_challenge"
LOGIN_REDIRECT = "login_redirect"
PAYWALL_REDIRECT = "paywall_redirect"

ACCESS_CONTROLS = (AUTH_REQUIRED, FORBIDDEN, LEGAL_BLOCK, RATE_LIMITED, CAPTCHA, BOT_CHALLENGE, LOGIN_REDIRECT, PAYWALL_REDIRECT)
# The server refuses this client, not this page: nothing more is asked of the origin in the run.
ORIGIN_HOLD = (AUTH_REQUIRED, FORBIDDEN, LEGAL_BLOCK, RATE_LIMITED, CAPTCHA, BOT_CHALLENGE)

_INSPECTED_BYTES = 64 * 1024
_SMALL_BODY_BYTES = 32 * 1024             # a challenge page is small; an article that embeds a form widget is not
_CAPTCHA_MARKERS = (b"g-recaptcha", b"h-captcha", b"hcaptcha.com/1/api.js", b"cf-turnstile", b"captcha-delivery.com", b"px-captcha")
_CHALLENGE_MARKERS = (b"cdn-cgi/challenge-platform", b"cf-chl-", b"just a moment...", b"checking your browser",
                      b"attention required! | cloudflare", b"_incapsula_resource", b"ddos-guard",
                      # Sucuri CloudProxy: a script that computes a cookie and reloads the page.
                      b"sucuri_cloudproxy_js", b"sucuri_cloudproxy_uuid")
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
