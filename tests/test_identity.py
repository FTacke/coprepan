"""Id serialisation and canonical URL key, as frozen by CPD-0003.

The pinned preimages below are the decision: a test that fails here means the serialisation
changed, which is a new decision and a new serialisation version, not a test to be edited.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone

import pytest

from coprepan import identity
from coprepan.identity import IdentityError, OffOriginError, OutletUrlRules, canonical_url_key

BODY = hashlib.sha256(b"<html>hola</html>").hexdigest()
TEXT = hashlib.sha256("Texto extraído.".encode("utf-8")).hexdigest()
STARTED = datetime(2026, 10, 7, 18, 42, 17, 249461, tzinfo=timezone.utc)
URL = "https://www.example-diario.test/Politica/Nota-1.html?utm_source=rss"

RULES = OutletUrlRules(
    outlet_id="uy_el_pais",
    web_origins=("https://www.example-diario.test", "https://m.example-diario.test", "http://example-diario.test"),
    version="uy_el_pais-url-rules/v1",
    significant_query_params=("id", "page"),
    strip_path_prefixes=("/amp",),
    strip_path_suffixes=("/amp", "/print"),
)


def key(url, **kwargs):
    return canonical_url_key(RULES, requested_url=url, **kwargs).key


# --- instants -------------------------------------------------------------------------------------


def test_instant_is_utc_with_microseconds():
    assert identity.format_instant(STARTED) == "2026-10-07T18:42:17.249461Z"


def test_instant_is_converted_to_utc():
    local = STARTED.astimezone(timezone(timedelta(hours=-3)))
    assert identity.format_instant(local) == identity.format_instant(STARTED)


def test_naive_instant_is_refused():
    with pytest.raises(IdentityError):
        identity.format_instant(datetime(2026, 10, 7, 18, 42, 17))


# --- fetch_id -------------------------------------------------------------------------------------


def test_fetch_id_preimage_is_pinned():
    preimage = (
        '{"body_sha256":"' + BODY + '",'
        '"fetch_started_at":"2026-10-07T18:42:17.249461Z",'
        '"requested_url":"' + URL + '",'
        '"schema":"coprepan-fetch-id/v1"}'
    ).encode("utf-8")
    expected = "ft1:" + hashlib.sha256(preimage).hexdigest()
    assert identity.fetch_id(URL, STARTED, BODY) == expected
    assert identity.is_fetch_id(expected)


def test_fetch_id_separates_events():
    base = identity.fetch_id(URL, STARTED, BODY)
    assert identity.fetch_id(URL, STARTED + timedelta(microseconds=1), BODY) != base
    assert identity.fetch_id(URL + "x", STARTED, BODY) != base
    assert identity.fetch_id(URL, STARTED, TEXT) != base


def test_fetch_id_does_not_normalise_the_requested_url():
    assert identity.fetch_id(URL, STARTED, BODY) != identity.fetch_id(URL.replace("Politica", "politica"), STARTED, BODY)


@pytest.mark.parametrize("bad_url", ["", "https://a.test/a b", "https://a.test/\n", None])
def test_fetch_id_refuses_a_bad_url(bad_url):
    with pytest.raises(IdentityError):
        identity.fetch_id(bad_url, STARTED, BODY)


@pytest.mark.parametrize("bad_hash", ["", "abc", BODY.upper(), BODY[:-1], None])
def test_fetch_id_refuses_a_bad_body_hash(bad_hash):
    with pytest.raises(ValueError):
        identity.fetch_id(URL, STARTED, bad_hash)


@pytest.mark.parametrize("value", ["ft1:abc", "ft2:" + BODY, BODY, "ft1:" + BODY.upper(), None])
def test_malformed_fetch_ids(value):
    assert not identity.is_fetch_id(value)


# --- document, version, unit, sentence, token -----------------------------------------------------


def test_document_id_is_a_16_digit_prefix_of_the_key_hash():
    url_key = "https://www.example-diario.test/Politica/Nota-1.html"
    expected = "uy_el_pais:doc:" + hashlib.sha256(url_key.encode("utf-8")).hexdigest()[:16]
    assert identity.document_id("uy_el_pais", url_key) == expected
    assert identity.is_document_id(expected)


def test_document_id_is_scoped_to_its_outlet():
    url_key = "https://www.example-diario.test/a"
    assert identity.document_id("uy_el_pais", url_key) != identity.document_id("es_el_pais", url_key)


def test_document_id_needs_a_well_formed_outlet_id():
    with pytest.raises(IdentityError):
        identity.document_id("el_país", "https://www.example-diario.test/a")


def test_version_and_child_ids_are_pinned():
    document = identity.document_id("uy_el_pais", "https://www.example-diario.test/a")
    version = identity.document_version_id(document, TEXT)
    assert version == f"{document}:v:{TEXT[:12]}"
    assert identity.is_document_version_id(version)
    assert identity.unit_id(version, 0) == f"{version}:UNIT:0"
    assert identity.sentence_id(version, 12) == f"{version}:SENT:12"
    assert identity.token_id(version, 345) == f"{version}:TOKEN:00000345"


def test_index_base_is_zero_as_reviewed_for_cpd_0003():
    """Regression for the CPD-0003 review of 2026-10-07 (KEEP): unit, sentence and token indexes
    are zero-based, like the token and sentence indexes of CO.RA.PAN 3.0 (spaCy ``token.i`` and
    ``enumerate(doc.sents)``). The first token of a version is ``…:TOKEN:00000000``; a version
    with ``n`` tokens ends at ``n - 1``.
    """
    version = identity.document_version_id(identity.document_id("uy_el_pais", "https://e.test/a"), TEXT)
    tokens = [identity.token_id(version, i) for i in range(3)]
    assert tokens[0].endswith(":TOKEN:00000000") and tokens[-1].endswith(":TOKEN:00000002")
    assert identity.sentence_id(version, 0).endswith(":SENT:0") and identity.unit_id(version, 0).endswith(":UNIT:0")
    assert [identity.parse_child_id(token).index for token in tokens] == [0, 1, 2]


def test_fetch_id_keeps_the_full_digest_as_reviewed_for_cpd_0003():
    value = identity.fetch_id(URL, STARTED, BODY)
    assert len(value) == len("ft1:") + 64 and not identity.is_fetch_id(value[:-32])


def test_child_ids_parse_back():
    version = identity.document_version_id(identity.document_id("uy_el_pais", "https://e.test/a"), TEXT)
    for builder, kind in ((identity.unit_id, "UNIT"), (identity.sentence_id, "SENT"), (identity.token_id, "TOKEN")):
        for index in (0, 7, 99_999_999):
            parsed = identity.parse_child_id(builder(version, index))
            assert (parsed.document_version_id, parsed.kind, parsed.index) == (version, kind, index)
            assert identity.parent_document_id(builder(version, index)) == version.split(":v:")[0]
    assert identity.parent_document_id(version) == version.split(":v:")[0]


def test_token_ids_sort_in_token_order():
    version = identity.document_version_id(identity.document_id("uy_el_pais", "https://e.test/a"), TEXT)
    indexes = [0, 9, 10, 99, 100, 12_345_678]
    assert sorted(identity.token_id(version, i) for i in indexes) == [identity.token_id(version, i) for i in indexes]


@pytest.mark.parametrize("index", [-1, 1.0, "1", True, None, 10**8])
def test_bad_token_index_is_refused(index):
    version = identity.document_version_id(identity.document_id("uy_el_pais", "https://e.test/a"), TEXT)
    with pytest.raises(IdentityError):
        identity.token_id(version, index)


def test_non_canonical_child_ids_are_refused():
    version = identity.document_version_id(identity.document_id("uy_el_pais", "https://e.test/a"), TEXT)
    for value in (f"{version}:TOKEN:345", f"{version}:UNIT:007", f"{version}:SEGMENT:1", version, "x"):
        with pytest.raises(IdentityError):
            identity.parse_child_id(value)


def test_version_id_needs_the_full_digest():
    document = identity.document_id("uy_el_pais", "https://e.test/a")
    with pytest.raises(ValueError):
        identity.document_version_id(document, TEXT[:12])
    with pytest.raises(IdentityError):
        identity.document_version_id("uy_el_pais", TEXT)


def test_channel_id():
    assert identity.channel_id("uy_el_pais", "rss_portada") == "uy_el_pais:ch:rss_portada"
    assert identity.is_channel_id("uy_el_pais:ch:rss_portada")
    assert not identity.is_channel_id("uy_el_pais:ch:RSS")
    assert not identity.is_channel_id("el_país:ch:rss")
    with pytest.raises(IdentityError):
        identity.channel_id("uy_el_pais", "rss portada")


# --- canonical URL key: stated cases --------------------------------------------------------------


def test_key_folds_origin_fragment_and_insignificant_query():
    assert key("HTTP://Example-Diario.test:80/Politica/Nota-1.html?utm_source=rss#comentarios") == (
        "https://www.example-diario.test/Politica/Nota-1.html"
    )


def test_key_keeps_the_case_of_the_path():
    assert key("https://www.example-diario.test/Politica/Nota") != key("https://www.example-diario.test/politica/nota")


def test_key_keeps_significant_parameters_in_a_fixed_order():
    assert key("https://www.example-diario.test/nota?page=2&utm=x&id=7") == "https://www.example-diario.test/nota?id=7&page=2"


def test_key_folds_declared_variants_at_segment_boundaries():
    plain = key("https://www.example-diario.test/politica/nota")
    assert key("https://m.example-diario.test/amp/politica/nota") == plain
    assert key("https://www.example-diario.test/politica/nota/amp") == plain
    assert key("https://www.example-diario.test/politica/nota/print") == plain
    assert key("https://www.example-diario.test/amplio/nota") == "https://www.example-diario.test/amplio/nota"
    assert key("https://www.example-diario.test/nota-amp") == "https://www.example-diario.test/nota-amp"


def test_key_normalises_escapes_and_dot_segments():
    assert key("https://www.example-diario.test/a/./b/../c%2fd/%7euser/%c3%b1") == (
        "https://www.example-diario.test/a/c%2Fd/~user/%C3%B1"
    )
    assert key("https://www.example-diario.test/ñ") == "https://www.example-diario.test/%C3%B1"
    assert key("https://www.example-diario.test") == "https://www.example-diario.test/"


def test_key_prefers_rel_canonical_then_final_then_requested():
    requested = "https://m.example-diario.test/r"
    result = canonical_url_key(
        RULES, requested_url=requested, final_url="https://www.example-diario.test/f",
        rel_canonical="https://www.example-diario.test/c",
    )
    assert (result.key, result.basis) == ("https://www.example-diario.test/c", "rel_canonical")
    result = canonical_url_key(RULES, requested_url=requested, final_url="https://www.example-diario.test/f")
    assert (result.key, result.basis) == ("https://www.example-diario.test/f", "final_url")
    assert canonical_url_key(RULES, requested_url=requested).basis == "requested_url"


def test_off_origin_canonical_and_redirect_are_skipped_not_followed():
    result = canonical_url_key(
        RULES, requested_url="https://www.example-diario.test/nota",
        final_url="https://login.other.test/wall", rel_canonical="https://agency.test/original",
    )
    assert (result.key, result.basis) == ("https://www.example-diario.test/nota", "requested_url")


def test_a_malformed_canonical_is_skipped():
    result = canonical_url_key(RULES, requested_url="https://www.example-diario.test/nota", rel_canonical="/nota")
    assert result.basis == "requested_url"


def test_a_fetch_with_no_on_origin_url_has_no_key():
    with pytest.raises(OffOriginError):
        canonical_url_key(RULES, requested_url="https://other.test/nota")


@pytest.mark.parametrize(
    "bad", ["", "nota.html", "ftp://www.example-diario.test/a", "https://u:p@www.example-diario.test/a",
            "https://www.example-diario.test/a b", "https://www.example-diario.test:notaport/a"],
)
def test_unusable_requested_urls_are_refused(bad):
    with pytest.raises(IdentityError):
        canonical_url_key(RULES, requested_url=bad)


def test_key_record_carries_everything_needed_to_recompute():
    result = canonical_url_key(RULES, requested_url=URL)
    assert result.as_record() == {
        "url_key": "https://www.example-diario.test/Politica/Nota-1.html",
        "url_key_basis": "requested_url",
        "url_key_input": URL,
        "url_key_ruleset": "coprepan-url-key/v1",
        "outlet_url_rules_version": "uy_el_pais-url-rules/v1",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"web_origins": ()},
        {"web_origins": ("https://WWW.example-diario.test",)},
        {"web_origins": ("https://www.example-diario.test/",)},
        {"web_origins": ("https://www.example-diario.test", "https://www.example-diario.test")},
        {"version": ""},
        {"strip_path_suffixes": ("amp",)},
        {"outlet_id": "El_Pais"},
    ],
)
def test_malformed_outlet_rules_are_refused(kwargs):
    arguments = {"outlet_id": "uy_el_pais", "web_origins": ("https://www.example-diario.test",), "version": "v1"}
    with pytest.raises(IdentityError):
        OutletUrlRules(**{**arguments, **kwargs})


# --- canonical URL key: properties over generated URLs --------------------------------------------
# Deterministic: a fixed seed, no external generator. Each property is checked on every case.

_SEGMENTS = ["Politica", "nota-1.html", "a%2fb", "%7Euser", "ñandú", "x.y", "2026", "amp", "print", "..", ".", ""]
_PARAMS = ["id=7", "page=2", "utm_source=rss", "fbclid=abc", "id=%c3%b1", "page", "ref=a&b", "id=3"]
_ORIGINS = ["https://www.example-diario.test", "https://m.example-diario.test", "http://example-diario.test",
            "HTTPS://WWW.EXAMPLE-DIARIO.TEST:443", "http://Example-Diario.test:80"]


def generated_urls(count=400, seed=20261007):
    rng = random.Random(seed)
    urls = []
    for _ in range(count):
        path = "/" + "/".join(rng.choice(_SEGMENTS) for _ in range(rng.randint(0, 5)))
        query = "&".join(rng.sample(_PARAMS, rng.randint(0, 4)))
        fragment = rng.choice(["", "#top", "#c=1"])
        urls.append(rng.choice(_ORIGINS) + path + ("?" + query if query else "") + fragment)
    return urls


URLS = generated_urls()


def test_generated_urls_are_reproducible():
    assert generated_urls() == URLS and len(set(URLS)) > 300


def test_property_key_is_deterministic_and_idempotent():
    for url in URLS:
        first = key(url)
        assert key(url) == first
        assert key(first) == first, url


def test_property_key_lies_on_the_canonical_origin_and_has_no_fragment():
    for url in URLS:
        result = key(url)
        assert result.startswith("https://www.example-diario.test/"), url
        assert "#" not in result and "/./" not in result and "/../" not in result, url


def test_property_fragment_and_insignificant_parameters_never_matter():
    for url in URLS:
        base = url.split("#")[0]
        joiner = "&" if "?" in base else "?"
        assert key(base + joiner + "utm_campaign=x&fbclid=y#frag") == key(url), url


def test_property_origin_alias_and_host_case_never_matter():
    for url in URLS:
        rest = url.split("//", 1)[1].split("/", 1)[1]
        assert len({key(f"{origin}/{rest}") for origin in _ORIGINS}) == 1, url


def test_property_parameter_order_never_matters():
    rng = random.Random(7)
    for url in URLS:
        base, _, fragment = url.partition("#")
        head, _, query = base.partition("?")
        if not query:
            continue
        pairs = query.split("&")
        rng.shuffle(pairs)
        assert key(head + "?" + "&".join(pairs)) == key(url), url


def test_property_path_case_is_never_folded():
    for url in URLS:
        head = url.split("?")[0].split("#")[0]
        scheme, _, rest = head.partition("//")
        host, _, path = rest.partition("/")
        origin = f"{scheme}//{host}/"
        if "Politica" in key(origin + path):  # the segment survived dot-segment removal
            assert key(origin + path.replace("Politica", "politica")) != key(origin + path), url


def test_property_document_id_follows_the_key():
    seen = {}
    for url in URLS:
        url_key = key(url)
        document = identity.document_id("uy_el_pais", url_key)
        assert seen.setdefault(document, url_key) == url_key
