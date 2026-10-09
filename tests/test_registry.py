"""Outlet registry schema and the legacy import.

The legacy database used here is synthetic: a few invented rows in a ``tmp_path`` SQLite file with
the column names of the legacy model. No test reads the real legacy database or any reference
repository.
"""

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from coprepan import legacy_registry_import as I
from coprepan import registry as R
from coprepan.identity import canonical_url_key

REPO = Path(__file__).resolve().parents[1]


def outlet(**overrides):
    base = {
        "outlet_id": "uy_el_pais",
        "country_id": "uy",
        "registration_status": "registered",
        "display_names": [{"name": "El País", "valid_from": "unknown", "valid_to": "not_applicable"}],
        "outlet_type": "national_reference",
        "outlet_group": "unknown",
        "city": "Montevideo",
        "region": "unknown",
        "scope": "unknown",
        "access_model": "metered",
        "medium": "print_and_web",
        "editions": [],
        "web_origins": ["https://www.example-diario.test", "https://m.example-diario.test"],
        "timezone": "America/Montevideo",
        "same_outlet_basis": "not_applicable",
        "url_rules": {"version": "uy_el_pais-url-rules/v1", "significant_query_params": ["id"],
                      "strip_path_prefixes": ["/amp"], "strip_path_suffixes": []},
        "channels": [
            {"channel_id": "uy_el_pais:ch:rss_portada", "kind": "rss",
             "url_history": [{"url": "https://www.example-diario.test/rss", "valid_from": "2026-10-07"}],
             "legacy_observed": {}},
        ],
        "legacy_aliases": [
            {"country_code": "URY", "slug": "elpaís", "observed_in": "legacy_db.sources.newspaper_code",
             "mapping_status": "hypothesis"},
        ],
        "legacy_observed": {},
        "review_notes": [],
    }
    return {**copy.deepcopy(base), **overrides}


def document(*outlets):
    return {"schema": "coprepan-outlet-registry/v1", "outlets": list(outlets)}


# --- the tracked registry --------------------------------------------------------------------------


def registration_records():
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((REPO / "config" / "registry_review").glob("*_registration_*.json"))]


def test_the_tracked_registry_is_valid_and_every_registration_has_a_record():
    """Registration is a review step. An outlet is `registered` only by a dated record beside the
    registry that names the authority, the rule of selection and the evidence of every value set.
    """
    registry = R.load_registry(REPO / "config" / "outlet_registry.json")
    registered = {o["outlet_id"]: o for o in registry.outlets.values() if o["registration_status"] == "registered"}
    recorded = {}
    for record in registration_records():
        assert record["schema"] == "coprepan-registry-registration/v1" and record["gate"] == "O-11" and record["authority"]
        for entry in record["registered"]:
            assert entry["outlet_id"] not in recorded and entry["evidence"]
            assert all(item["source"] and item["how"] for item in entry["evidence"])
            recorded[entry["outlet_id"]] = entry
    assert set(registered) == set(recorded)
    for outlet_id, outlet in registered.items():
        entry = recorded[outlet_id]
        assert all(outlet[field] == value for field, value in entry["attributes_set"].items())
        assert outlet["timezone"] != "unknown" and outlet["url_rules"]["version"] == entry["url_rules"]["version"] != "proposed"
        assert {channel["channel_id"] for channel in outlet["channels"]} == set(entry["channel_ids"].values())
        assert outlet["web_origins"] == entry["web_origins"] and outlet["review_notes"] == []
        # what was not evidenced stays unknown
        assert all(outlet[field] == "unknown" for field in entry["attributes_left_unknown"])


def test_the_canary_subset_is_small_and_spread_over_countries():
    """The subset of the first canary (the registration record of 2026-10-08): five outlets, five
    countries. A later registration record is a different set with its own selection rule.
    """
    registry = R.load_registry(REPO / "config" / "outlet_registry.json")
    first = json.loads((REPO / "config" / "registry_review" / "canary_subset_registration_2026-10-08.json").read_text(encoding="utf-8"))
    registered = [registry.outlets[entry["outlet_id"]] for entry in first["registered"]]
    assert all(o["registration_status"] == "registered" for o in registered)
    assert len(registered) == 5 and len({o["country_id"] for o in registered}) == len(registered)
    kinds = {channel["kind"] for o in registered for channel in o["channels"]}
    assert {"rss", "sitemap"} <= kinds


def test_the_tracked_proposal_matches_its_review_report():
    """The registry holds the outlets the legacy import of 2026-10-07 proposed and no other; the
    review report beside it is the report of that proposal. Neither is a registration: what is
    registered is what a registration record covers, and no id changed by being registered.
    """
    registry = R.load_registry(REPO / "config" / "outlet_registry.json")
    report = json.loads((REPO / "config" / "registry_review" / "legacy_registry_import_2026-10-07.json").read_text(encoding="utf-8"))
    assert report["schema"] == "coprepan-legacy-registry-import/v1"
    proposed = {o["outlet_id"] for o in registry.outlets.values() if o["registration_status"] == "proposed"}
    assert set(registry.outlets) == {row["proposed_outlet_id"] for row in report["legacy_name_to_outlet_id"]}
    assert set(registry.outlets) - proposed == {e["outlet_id"] for record in registration_records() for e in record["registered"]}
    assert report["counts"]["proposed_outlets"] == len(registry.outlets)
    # the import's channels are the channels that carry a legacy row; a channel added by a later
    # registration has none (`legacy_observed` is empty) and is covered by its registration record
    assert report["counts"]["proposed_channels"] == sum(1 for o in registry.outlets.values() for c in o["channels"] if c["legacy_observed"])
    for row in report["legacy_name_to_outlet_id"]:
        assert registry.legacy_alias(row["country_code"], row["slug"]) == [row["proposed_outlet_id"]]
        assert row["mapping_status"] == "hypothesis"
    codes = I.load_country_codes()
    assert {o["country_id"] for o in registry.outlets.values()} <= set(codes.values())


def test_the_tracked_country_table_is_well_formed():
    codes = I.load_country_codes()
    assert codes["URY"] == "uy" and codes["PRI"] == "pr"
    assert len(set(codes.values())) == len(codes)


# --- schema ---------------------------------------------------------------------------------------


def test_a_registered_outlet_resolves_with_its_url_rules():
    registry = R.validate_registry(document(outlet()))
    assert registry.resolve("uy_el_pais")["city"] == "Montevideo"
    rules = registry.url_rules("uy_el_pais")
    key = canonical_url_key(rules, requested_url="https://m.example-diario.test/amp/Nota?id=3&utm=x")
    assert key.key == "https://www.example-diario.test/Nota?id=3"
    assert key.outlet_rules_version == "uy_el_pais-url-rules/v1"


def test_form_is_not_registration():
    registry = R.validate_registry(document(outlet(registration_status="proposed")))
    for well_formed_but_not_registered in ("uy_el_pais", "es_el_pais", "el_pais"):
        with pytest.raises(R.UnregisteredOutlet):
            registry.resolve(well_formed_but_not_registered)
    with pytest.raises(R.UnregisteredOutlet):
        registry.url_rules("uy_el_pais")


def test_legacy_names_resolve_exactly_as_observed_and_ambiguity_is_shown():
    second = outlet(outlet_id="uy_el_pais_digital", channels=[], display_names=[
        {"name": "El País Digital", "valid_from": "unknown", "valid_to": "unknown"}])
    registry = R.validate_registry(document(outlet(), second))
    assert registry.legacy_alias("URY", "elpaís") == ["uy_el_pais", "uy_el_pais_digital"]
    assert registry.legacy_alias("URY", "elpais") == []  # no normalisation of an observed name
    assert registry.legacy_alias("ESP", "elpaís") == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"outlet_id": "El_Pais"},
        {"country_id": "es"},
        {"registration_status": "active"},
        {"outlet_type": "newspaper"},
        {"outlet_type": None},
        {"access_model": "paywall"},
        {"medium": "print"},
        {"timezone": "Montevideo time"},
        {"timezone": ""},
        {"city": ""},
        {"outlet_group": None},
        {"display_names": []},
        {"display_names": [{"name": "", "valid_from": "unknown", "valid_to": "unknown"}]},
        {"display_names": [{"name": "El País", "valid_from": "07.10.2026", "valid_to": "unknown"}]},
        {"display_names": [{"name": "El País"}]},
        {"web_origins": ["https://WWW.example-diario.test"]},
        {"web_origins": ["https://www.example-diario.test/portada"]},
        {"web_origins": ["https://www.example-diario.test", "https://www.example-diario.test"]},
        {"web_origins": []},
        {"review_notes": ["still to be checked"]},
        {"url_rules": {"version": "v1"}},
        {"url_rules": {"version": "", "significant_query_params": [], "strip_path_prefixes": [], "strip_path_suffixes": []}},
        {"url_rules": {"version": "v1", "significant_query_params": [], "strip_path_prefixes": ["amp"], "strip_path_suffixes": []}},
        {"channels": [{"channel_id": "es_el_pais:ch:rss", "kind": "rss",
                       "url_history": [{"url": "https://e.test/rss", "valid_from": "unknown"}], "legacy_observed": {}}]},
        {"channels": [{"channel_id": "uy_el_pais:ch:rss", "kind": "feed",
                       "url_history": [{"url": "https://e.test/rss", "valid_from": "unknown"}], "legacy_observed": {}}]},
        {"channels": [{"channel_id": "uy_el_pais:ch:rss", "kind": "rss", "url_history": [], "legacy_observed": {}}]},
        {"channels": [{"channel_id": "uy_el_pais:ch:rss", "kind": "rss",
                       "url_history": [{"url": "https://e.test/rss", "valid_from": "unknown"}]}]},
        {"legacy_aliases": [{"country_code": "URY", "slug": "elpaís", "observed_in": "x", "mapping_status": "confirmed"}]},
        {"legacy_aliases": [{"country_code": "URY", "slug": "", "observed_in": "x", "mapping_status": "hypothesis"}]},
        {"legacy_aliases": [{"country_code": "URY", "slug": "a", "observed_in": "x", "mapping_status": "hypothesis"}] * 2},
        {"legacy_observed": None},
        {"surprise": 1},
    ],
)
def test_an_outlet_outside_the_schema_is_refused(overrides):
    with pytest.raises(R.RegistryError):
        R.validate_registry(document(outlet(**overrides)))


def test_a_missing_field_is_refused_not_defaulted():
    for field in outlet():
        incomplete = outlet()
        del incomplete[field]
        with pytest.raises(R.RegistryError):
            R.validate_registry(document(incomplete))


def test_ids_are_unique_and_the_file_is_ordered():
    with pytest.raises(R.RegistryError):
        R.validate_registry(document(outlet(), outlet()))
    first, second = outlet(outlet_id="es_el_pais", country_id="es", channels=[]), outlet()
    R.validate_registry(document(first, second))
    with pytest.raises(R.RegistryError):
        R.validate_registry(document(second, first))


@pytest.mark.parametrize("broken", [[], {"schema": "coprepan-outlet-registry/v2", "outlets": []},
                                    {"schema": "coprepan-outlet-registry/v1"},
                                    {"schema": "coprepan-outlet-registry/v1", "outlets": {}, }])
def test_a_document_that_is_not_a_registry_is_refused(broken):
    with pytest.raises(R.RegistryError):
        R.validate_registry(broken)


def test_an_unreadable_registry_file_is_refused(tmp_path):
    with pytest.raises(R.RegistryError):
        R.load_registry(tmp_path / "absent.json")


@pytest.mark.parametrize(
    "name, slug",
    [("El País", "el_pais"), ("La Estrella de Panamá", "la_estrella_de_panama"), ("elpaís", "elpais"),
     ("  20minutos.es ", "20minutos_es"), ("Ñandutí", "nanduti"), ("---", "")],
)
def test_the_slug_helper_only_proposes(name, slug):
    assert R.propose_slug(name) == slug


# --- legacy import (synthetic database) ------------------------------------------------------------

SOURCES = [
    (1, "URY", "elpais", "El País", "https://www.example-diario.test/", "es", 1, "nota"),
    (2, "URY", "elpaís", "El País (Uruguay)", "https://www.example-diario.test", "es", 0, None),
    (3, "ESP", "elpais", "El País", "https://example-es.test/portada", "es", 1, None),
    (4, "XXX", "desconocido", "Sin país", "https://example-x.test", "es", 1, None),
    (5, "ARG", "???", "Sin código", "https://example-ar.test", "es", 1, None),
    (6, "PAN", "laestrelladepanamá", "La Estrella de Panamá", "not a url", "es", 1, None),
]
FEEDS = [
    (10, 1, "https://www.example-diario.test/rss", "rss", "manual", 1, "active", 80, None),
    (11, 1, "https://www.example-diario.test/sitemap.xml", "sitemap", "robots", 0, "inactive", 0, "HTTP 404"),
    (12, 2, "https://www.example-diario.test/rss/politica", "rss", "html_head", 1, "technically_empty", 10, None),
    (13, 3, "https://example-es.test/feed", "weird_type", "heuristic", 1, "blocked", 5, "HTTP 403"),
    (14, 4, "https://example-x.test/rss", "rss", "manual", 1, "active", 50, None),
    (15, 99, "https://orphan.test/rss", "rss", "manual", 1, "active", 50, None),
    (16, 3, "  ", "rss", "manual", 1, "active", 50, None),
]


def make_legacy_db(path):
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE sources (id INTEGER PRIMARY KEY, country_code TEXT, newspaper_code TEXT, name TEXT, "
        "base_url TEXT, language TEXT, is_active INTEGER, notes TEXT)"
    )
    connection.execute(
        "CREATE TABLE feeds (id INTEGER PRIMARY KEY, source_id INTEGER, url TEXT, type TEXT, discovered_by TEXT, "
        "is_active INTEGER, status TEXT, feed_score INTEGER, last_fail_reason TEXT)"
    )
    connection.executemany("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?)", SOURCES)
    connection.executemany("INSERT INTO feeds VALUES (?,?,?,?,?,?,?,?,?)", FEEDS)
    connection.commit()
    connection.close()


@pytest.fixture
def legacy(tmp_path):
    tree = tmp_path / "legacy_tree"
    (tree / ".git").mkdir(parents=True)
    (tree / "data" / "db").mkdir(parents=True)
    database = tree / "data" / "db" / "legacy.sqlite"
    make_legacy_db(database)
    (database.with_name("legacy.sqlite-wal")).write_bytes(b"")
    work = tmp_path / "work"
    work.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    return tree, database, work, out


def snapshot(tree):
    return {p.relative_to(tree).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns, p.read_bytes())
            for p in tree.rglob("*") if p.is_file()}


def run(legacy):
    tree, database, work, out = legacy
    return I.run_import(database, work, out / "registry.json", out / "report.json")


def test_import_proposes_outlets_channels_and_aliases(legacy):
    result = run(legacy)
    registry = R.validate_registry(result.registry)
    assert sorted(registry.outlets) == ["es_elpais", "pa_laestrelladepanama", "uy_elpais"]
    assert {o["registration_status"] for o in registry.outlets.values()} == {"proposed"}

    uy = registry.outlets["uy_elpais"]
    assert [a["slug"] for a in uy["legacy_aliases"]] == ["elpais", "elpaís"]  # both observed variants, verbatim
    assert {a["mapping_status"] for a in uy["legacy_aliases"]} == {"hypothesis"}
    assert [d["name"] for d in uy["display_names"]] == ["El País", "El País (Uruguay)"]
    assert uy["web_origins"] == ["https://www.example-diario.test"]
    assert [c["channel_id"] for c in uy["channels"]] == [
        "uy_elpais:ch:rss_001", "uy_elpais:ch:sitemap_001", "uy_elpais:ch:rss_002"]
    assert any("2 legacy sources fold" in note for note in uy["review_notes"])
    assert uy["outlet_type"] == uy["timezone"] == uy["outlet_group"] == "unknown"  # nothing the database lacks is invented


def test_import_keeps_observed_legacy_values_verbatim(legacy):
    registry = R.validate_registry(run(legacy).registry)
    uy = registry.outlets["uy_elpais"]
    assert uy["legacy_observed"]["sources"][1] == {
        "id": 2, "country_code": "URY", "newspaper_code": "elpaís", "name": "El País (Uruguay)",
        "base_url": "https://www.example-diario.test", "language": "es", "is_active": 0, "notes": None}
    assert uy["channels"][1]["legacy_observed"] == {
        "id": 11, "source_id": 1, "url": "https://www.example-diario.test/sitemap.xml", "type": "sitemap",
        "discovered_by": "robots", "is_active": 0, "status": "inactive", "feed_score": 0, "last_fail_reason": "HTTP 404"}
    es = registry.outlets["es_elpais"]
    assert es["channels"][0]["kind"] == "unknown" and es["channels"][0]["legacy_observed"]["type"] == "weird_type"
    assert es["web_origins"] == ["https://example-es.test"]
    pa = registry.outlets["pa_laestrelladepanama"]
    assert pa["web_origins"] == [] and any("no usable web origin" in note for note in pa["review_notes"])


def test_import_reports_what_it_could_not_resolve_instead_of_guessing(legacy):
    report = run(legacy).report
    assert sorted((u["kind"], u["reason"], u["legacy_observed"]["id"]) for u in report["unresolved"]) == [
        ("feed", "empty_url", 16),
        ("feed", "source_not_imported", 14),
        ("feed", "source_not_imported", 15),
        ("source", "country_code_not_in_table", 4),
        ("source", "no_ascii_slug_from_newspaper_code", 5),
    ]
    assert report["counts"] == {
        "legacy_sources": 6, "legacy_feeds": 7, "proposed_outlets": 3, "proposed_channels": 4,
        "proposed_outlets_folding_several_sources": 1, "unresolved": 5}
    assert report["legacy_name_to_outlet_id"] == [
        {"country_code": "ESP", "slug": "elpais", "mapping_status": "hypothesis", "legacy_source_id": 3,
         "proposed_outlet_id": "es_elpais"},
        {"country_code": "PAN", "slug": "laestrelladepanamá", "mapping_status": "hypothesis", "legacy_source_id": 6,
         "proposed_outlet_id": "pa_laestrelladepanama"},
        {"country_code": "URY", "slug": "elpais", "mapping_status": "hypothesis", "legacy_source_id": 1,
         "proposed_outlet_id": "uy_elpais"},
        {"country_code": "URY", "slug": "elpaís", "mapping_status": "hypothesis", "legacy_source_id": 2,
         "proposed_outlet_id": "uy_elpais"},
    ]


def test_import_never_touches_the_legacy_tree(legacy):
    tree, database, work, out = legacy
    before = snapshot(tree)
    result = run(legacy)
    assert snapshot(tree) == before
    assert sorted(p.name for p in work.iterdir()) == ["legacy.sqlite", "legacy.sqlite-wal"]
    assert result.report["input"]["database_file_name"] == "legacy.sqlite"
    assert result.report["input"]["wal_sibling_present"] is True
    assert len(result.report["input"]["database_sha256"]) == 64


def test_import_is_deterministic(legacy, tmp_path):
    tree, database, work, out = legacy
    first = run(legacy)
    second_work, second_out = tmp_path / "work2", tmp_path / "out2"
    second_work.mkdir(), second_out.mkdir()
    I.run_import(database, second_work, second_out / "registry.json", second_out / "report.json")
    for name in ("registry.json", "report.json"):
        assert (out / name).read_bytes() == (second_out / name).read_bytes()
    assert json.loads((out / "registry.json").read_text(encoding="utf-8")) == first.registry


def test_import_refuses_to_work_inside_the_legacy_tree(legacy):
    tree, database, work, out = legacy
    inside = tree / "tmp_work"
    inside.mkdir()
    with pytest.raises(I.LegacyImportError):
        I.run_import(database, inside, out / "registry.json", out / "report.json")
    with pytest.raises(I.LegacyImportError):
        I.run_import(database, work, tree / "registry.json", out / "report.json")
    assert sorted(p.name for p in inside.iterdir()) == [] and not (tree / "registry.json").exists()


def test_import_refuses_a_used_work_directory_and_existing_outputs(legacy):
    tree, database, work, out = legacy
    run(legacy)
    with pytest.raises(I.LegacyImportError):  # outputs exist: never overwritten
        run(legacy)
    with pytest.raises(I.LegacyImportError):  # work directory holds the earlier copy
        I.run_import(database, work, out / "r2.json", out / "p2.json")
    assert not (out / "r2.json").exists()


def test_import_fails_closed_on_an_unexpected_database(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    database = tmp_path / "db" / "other.sqlite"
    database.parent.mkdir()
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE sources (id INTEGER PRIMARY KEY, name TEXT)")
    connection.commit()
    connection.close()
    with pytest.raises(I.LegacyImportError):
        I.run_import(database, work, tmp_path / "registry.json", tmp_path / "report.json")
    with pytest.raises(I.LegacyImportError):
        I.copy_database(tmp_path / "absent.sqlite", work)


def test_the_command_line_writes_both_outputs(legacy, capsys):
    tree, database, work, out = legacy
    assert I.main(["--database", str(database), "--work-dir", str(work),
                   "--registry-out", str(out / "registry.json"), "--report-out", str(out / "report.json")]) == 0
    assert json.loads(capsys.readouterr().out)["proposed_outlets"] == 3
    assert R.load_registry(out / "registry.json").outlets.keys() == {"es_elpais", "pa_laestrelladepanama", "uy_elpais"}
