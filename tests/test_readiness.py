"""Acquisition readiness: preservation-target check, capacity model, baseline manifest, registry
review package. Each of these prepares an operator decision; none of them takes it.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coprepan import capacity as CAP
from coprepan import freeze as FZ
from coprepan import preservation
from coprepan import preservation_target as PT
from coprepan import registry as R
from coprepan import registry_review as RR
from coprepan.canonical import canonical_json, record_json

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 7, 21, 0, 0, tzinfo=timezone.utc)
COMMIT = "a54ce05a58af8f0c2d77ab4d9020882bf8be2399"


# --- preservation target ----------------------------------------------------------------------------


def checks(report):
    return {check["check"]: check["status"] for check in report["checks"]}


def test_a_target_without_an_identity_is_not_ready(tmp_path):
    report = PT.check_readiness(tmp_path, required_free_bytes=1, now=NOW)
    assert report["status"] == "NOT_READY" and checks(report)["target_identity"] == "FAIL"
    assert checks(report)["atomic_promotion"] == "PASS"  # everything else is still checked and reported
    assert list(tmp_path.iterdir()) == []                # the probe removed exactly what it wrote


def test_an_initialised_target_passes_and_the_report_says_what_was_checked(tmp_path):
    marker = PT.initialise_target(tmp_path, "coprepan-preservation-01", operator="operator", now=NOW)
    assert marker == PT.read_target(tmp_path) and marker["target_id"] == "coprepan-preservation-01"
    report = PT.check_readiness(tmp_path, required_free_bytes=1024, now=NOW)
    assert report["status"] == "READY" and report["target_id"] == "coprepan-preservation-01"
    assert checks(report) == {"usable_root": "PASS", "reachable": "PASS", "target_identity": "PASS", "free_space": "PASS",
                              "writable": "PASS", "atomic_promotion": "PASS", "no_silent_overwrite": "PASS",
                              "case_sensitivity": "INFO", "long_names": "PASS", "fixity": "INFO"}
    assert report["free_bytes"] > 0 and report["schema"] == "coprepan-preservation-readiness/v1"
    assert sorted(p.name for p in tmp_path.iterdir()) == [PT.MARKER_NAME]
    json.dumps(report)  # a report is a plain record


def test_a_target_keeps_its_identity(tmp_path):
    PT.initialise_target(tmp_path, "target-a", operator="operator", now=NOW)
    with pytest.raises(PT.TargetError):
        PT.initialise_target(tmp_path, "target-b", operator="operator", now=NOW)
    assert PT.read_target(tmp_path)["target_id"] == "target-a"
    for bad in ("", "has space", "../x"):
        with pytest.raises(PT.TargetError):
            PT.initialise_target(tmp_path / "other", bad, operator="operator", now=NOW)
    (tmp_path / PT.MARKER_NAME).write_text("{broken", encoding="utf-8")
    assert checks(PT.check_readiness(tmp_path, required_free_bytes=1, now=NOW))["target_identity"] == "FAIL"


@pytest.mark.parametrize("root", ["relative/dir", REPO, REPO / "data"])
def test_an_unusable_root_is_not_probed(root):
    report = PT.check_readiness(root, required_free_bytes=1, now=NOW)
    assert report["status"] == "NOT_READY" and checks(report) == {"usable_root": "FAIL"}


def test_an_unreachable_target_reports_unknown_not_empty(tmp_path):
    report = PT.check_readiness(tmp_path / "not-mounted", required_free_bytes=1, now=NOW)
    assert report["status"] == "NOT_READY" and checks(report)["reachable"] == "FAIL"
    assert report["free_bytes"] == "unknown" and not (tmp_path / "not-mounted").exists()


def test_too_little_free_space_and_failed_fixity_make_a_target_not_ready(tmp_path):
    PT.initialise_target(tmp_path, "target-a", operator="operator", now=NOW)
    assert checks(PT.check_readiness(tmp_path, required_free_bytes=10**18, now=NOW))["free_space"] == "FAIL"
    source = tmp_path.parent / "sealed.bin"
    source.write_bytes(b"sealed pack")
    import hashlib
    result = preservation.promote(source, root=tmp_path, area="raw", object_id="pack-a", relative_path="uy/pack-a.warc.gz",
                                  declared_sha256=hashlib.sha256(b"sealed pack").hexdigest(), now=NOW)
    good = PT.check_readiness(tmp_path, required_free_bytes=1, now=NOW)
    assert (good["status"], checks(good)["fixity"]) == ("READY", "PASS")
    before = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    (tmp_path / result.relative_path).write_bytes(b"bit rot")
    bad = PT.check_readiness(tmp_path, required_free_bytes=1, now=NOW)
    assert (bad["status"], checks(bad)["fixity"]) == ("NOT_READY", "FAIL")
    assert {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()} == before  # nothing touched or tidied


def test_no_storage_target_is_configured_in_this_repository():
    """O-3 is open: there is nothing to probe, and the check does not invent a target."""
    from coprepan import storage_roots

    with pytest.raises(storage_roots.StorageRootNotConfigured):
        storage_roots.resolve_root("PRESERVATION")


# --- capacity model ---------------------------------------------------------------------------------


def scenario(**overrides):
    q = CAP.Quantity
    inputs = {
        "fetches_per_day": q(3112, "measured", "legacy database copy, 2026-10-07: median rows per active crawl day"),
        "stored_body_bytes_per_fetch": q(50_000, "assumed", "audit scenario: 50 KB compressed per fetch"),
        "pack_overhead_bytes_per_fetch": q(1300, "measured", "synthetic exchange, 2026-10-07"),
        "index_bytes_per_fetch": q(400, "estimated", "index row format"),
        "workspace_bytes_per_fetch": q(3000, "estimated", "ledger and request-log row formats"),
        "item_share": q(0.9, "assumed", "scenario"),
        "extraction_bytes_per_item": q(100_000, "assumed", "scenario"),
        "retention_days": q(365, "assumed", "one year"),
        "copies": q(2, "assumed", "preservation plus one backup"),
    }
    inputs.update(overrides)
    return inputs


def test_the_model_computes_layers_and_labels_every_result_by_its_weakest_input():
    report = CAP.storage_model(scenario())
    fetches = 3112 * 365
    assert report["fetches_in_horizon"] == fetches
    assert report["layers"]["raw_packs"] == {"bytes": fetches * 51_300, "label": "assumed"}
    assert report["layers"]["pack_indexes"]["bytes"] == fetches * 400
    assert report["layers"]["preservation_all_copies"]["bytes"] == 2 * fetches * 51_700
    assert report["total"]["label"] == "assumed" and report["total"]["gib"] > 0
    assert report["inputs"]["fetches_per_day"]["label"] == "measured"


def test_a_result_is_only_measured_when_everything_under_it_is():
    q = CAP.Quantity
    measured = {name: q(value.value, "measured", "x") for name, value in scenario().items()}
    assert CAP.storage_model(measured)["total"]["label"] == "measured"
    one_estimate = {**measured, "index_bytes_per_fetch": q(400, "estimated", "x")}
    report = CAP.storage_model(one_estimate)
    assert report["layers"]["pack_indexes"]["label"] == "estimated" and report["layers"]["raw_packs"]["label"] == "measured"
    assert report["total"]["label"] == "estimated"
    assert CAP.weakest(q(1, "measured", "x"), q(1, "assumed", "x"), q(1, "estimated", "x")) == "assumed"


def test_the_model_has_no_built_in_value_and_refuses_a_guess():
    inputs = scenario()
    del inputs["stored_body_bytes_per_fetch"]
    with pytest.raises(ValueError):
        CAP.storage_model(inputs)
    with pytest.raises(ValueError):
        CAP.storage_model({**scenario(), "growth": CAP.Quantity(1, "assumed", "x")})
    for bad in ((1, "guessed", "x"), (-1, "assumed", "x"), (1, "assumed", ""), (True, "assumed", "x")):
        with pytest.raises(ValueError):
            CAP.Quantity(*bad)


def test_the_calculator_runs_from_the_command_line(capsys):
    arguments = [f"--{name.replace('_', '-')}={q.value}:{q.label}:{q.source}" for name, q in scenario().items()]
    assert CAP.main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["total"]["label"] == "assumed"


def test_the_model_is_deterministic():
    assert CAP.storage_model(scenario()) == CAP.storage_model(scenario())


# --- baseline manifest ------------------------------------------------------------------------------


def manifest(**kwargs):
    arguments = dict(code_commit=COMMIT, created_at=NOW, operator="operator", test_baseline={"suite": "python -m pytest", "passed": 1})
    return FZ.build_manifest(**{**arguments, **kwargs})


def test_the_repository_as_committed_is_pre_freeze_and_says_why():
    m = manifest()
    assert m["state"] == "PRE_FREEZE" and m["schema"] == "coprepan-acquisition-baseline/v1"
    assert [reason.split(":")[0] for reason in m["blocking"]] == (["O-1"] if m["policy"]["external_acquisition"] == "disabled" else []) + ["O-3", "O-4"]
    assert m["schedule_policy"]["version"].startswith("canary/") and m["components"]["extractor_lifecycle"] == "EXPERIMENTAL"
    assert (m["registry"]["outlets"], m["registry"]["registered"], m["registry"]["proposed"], m["registry"]["channels"]) == (91, 22, 69, 373)
    assert m["policy"]["status"] == "DECIDED" and m["policy"]["external_acquisition"] in ("enabled", "disabled")   # decided; armed only for the canary
    assert m["crawler_identity"]["state"] == "configured" and m["crawler_identity"]["identity"]["operator"]["crawler_name"] == "PanhispanicMediaResearchBot"
    assert m["storage_target"] == {"status": "not_configured"} and m["code"]["commit"] == COMMIT
    assert FZ.verify_manifest(m)


def test_the_manifest_references_everything_an_acquisition_start_rests_on():
    m = manifest()
    assert set(m["decisions"]) >= {"CPD-0001", "CPD-0002", "CPD-0003", "CPD-0004", "CPD-0005"}
    assert all(len(value) == 64 for value in m["decisions"].values())
    for schema in ("coprepan-fetch-record/v1", "coprepan-pack/v1", "coprepan-extraction/v1", "coprepan-outlet-registry/v1",
                   "coprepan-acquisition-policy/v3", "coprepan-discovery-event/v2", "coprepan-url-key/v1", "coprepan-fetch-id/v1"):
        assert schema in m["schemas"], schema
    assert m["components"]["extractor"] == "baseline_html/0.1.0" and m["components"]["pack_writer"] == "pack-writer/1"
    assert {entry["path"] for entry in m["test_baseline"]["fixtures"]} == {
        "tests/fixtures/canary/MANIFEST.json", "tests/fixtures/discovery/MANIFEST.json", "tests/fixtures/qualification/MANIFEST.json"}
    assert m["registry"]["path"] == "config/outlet_registry.json" and len(m["registry"]["sha256"]) == 64
    assert not any(str(REPO) in json.dumps(m) for _ in (0,))  # relative paths only


def test_the_manifest_is_deterministic_and_changes_with_what_it_covers():
    first = manifest()
    assert first == manifest() and first["manifest_sha256"] == manifest()["manifest_sha256"]
    assert manifest(operator="someone else")["manifest_sha256"] != first["manifest_sha256"]
    assert manifest(code_commit="b" * 40)["manifest_sha256"] != first["manifest_sha256"]
    tampered = {**first, "blocking": []}
    assert not FZ.verify_manifest(tampered)
    for bad in ("", "abc", COMMIT[:7], COMMIT.upper()):
        with pytest.raises(ValueError):
            manifest(code_commit=bad)


def test_a_freeze_is_refused_while_anything_blocks():
    m = manifest()
    with pytest.raises(FZ.FreezeRefused):
        FZ.freeze(m, operator="operator", confirmed_at=NOW, confirmation=m["manifest_sha256"])
    forged = {**m, "state": "READY_TO_FREEZE", "blocking": []}
    with pytest.raises(FZ.FreezeRefused):  # editing the state away does not survive the digest
        FZ.freeze(forged, operator="operator", confirmed_at=NOW, confirmation=m["manifest_sha256"])


def test_a_ready_target_and_measured_capacity_remove_only_their_own_blockers(tmp_path):
    PT.initialise_target(tmp_path, "target-a", operator="operator", now=NOW)
    report = PT.check_readiness(tmp_path, required_free_bytes=1, now=NOW)
    m = manifest(storage_target=report, capacity_measured=True)
    switch_off = m["policy"]["external_acquisition"] == "disabled"
    assert [reason.split(":")[0] for reason in m["blocking"]] == (["O-1"] if switch_off else [])
    assert m["state"] == ("PRE_FREEZE" if switch_off else "READY_TO_FREEZE")
    assert m["storage_target"]["target_id"] == "target-a"


def test_the_manifest_command_writes_once_and_never_freezes(tmp_path, capsys):
    out = tmp_path / "baseline.json"
    assert FZ.main(["--commit", COMMIT, "--operator", "operator", "--tests-passed", "1", "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["state"] == "PRE_FREEZE" and FZ.verify_manifest(written) and "freeze" not in written
    assert json.loads(capsys.readouterr().out)["state"] == "PRE_FREEZE"
    with pytest.raises(FileExistsError):
        FZ.main(["--commit", COMMIT, "--operator", "operator", "--tests-passed", "1", "--out", str(out)])


# --- a frozen manifest verifies its own digest (defect of 2026-10-08: it never did) -------------------


def ready_manifest(tmp_path):
    """A manifest with nothing blocking, in either state of the tracked acquisition switch. With the switch off
    the O-1 blocker is taken out by hand and the digest recomputed here, independently of the module."""
    (tmp_path / "target").mkdir()
    PT.initialise_target(tmp_path / "target", "target-a", operator="operator", now=NOW)
    built =manifest(storage_target=PT.check_readiness(tmp_path / "target", required_free_bytes=1, now=NOW), capacity_measured=True)
    body = {key: value for key, value in built.items() if key != "manifest_sha256"} | {"state": "READY_TO_FREEZE", "blocking": []}
    return {**body, "manifest_sha256": hashlib.sha256(canonical_json(body)).hexdigest()}


def test_build_freeze_write_read_verify_keeps_one_digest(tmp_path):
    from coprepan import canary_driver

    ready = ready_manifest(tmp_path)
    digest = ready["manifest_sha256"]
    assert ready["state"] == "READY_TO_FREEZE" and FZ.verify_manifest(ready) and FZ.manifest_digest(ready) == digest
    built, out = tmp_path / "baseline.json", tmp_path / "frozen.json"
    built.write_bytes(record_json(ready))
    assert canary_driver.main(["freeze", "--manifest", str(built), "--operator", "operator", "--confirm", digest, "--out", str(out)]) == 0
    frozen = json.loads(out.read_text(encoding="utf-8"))
    assert frozen["state"] == "FROZEN" and frozen["manifest_sha256"] == digest and frozen["freeze"]["confirms"] == digest
    assert FZ.verify_manifest(frozen) and FZ.manifest_digest(frozen) == digest
    with pytest.raises(FZ.FreezeRefused):  # a frozen manifest is not frozen a second time
        FZ.freeze(frozen, operator="operator", confirmed_at=NOW, confirmation=digest)
    with pytest.raises(FZ.FreezeRefused):
        FZ.freeze(ready, operator="operator", confirmed_at=NOW, confirmation="0" * 64)


def test_a_change_of_protected_content_of_a_frozen_manifest_is_noticed(tmp_path):
    ready = ready_manifest(tmp_path)
    frozen = FZ.freeze(ready, operator="operator", confirmed_at=NOW, confirmation=ready["manifest_sha256"])
    assert FZ.verify_manifest(frozen)
    for change in ({"operator": "someone else"}, {"scope": "canary"}, {"created_at": "2026-10-07T21:00:01Z"}, {"blocking": ["O-1: x"]},
                   {"code": {**frozen["code"], "commit": "b" * 40}}, {"policy": {**frozen["policy"], "sha256": "0" * 64}},
                   {"components": {**frozen["components"], "fetcher": "other/9"}}, {"manifest_sha256": "0" * 64}, {"added": 1}):
        assert not FZ.verify_manifest({**frozen, **change}), change
    assert not FZ.verify_manifest({key: value for key, value in frozen.items() if key != "schemas"})
    # the state is covered too: frozen and built are the only two states a verifying manifest of this content has
    assert not FZ.verify_manifest({**frozen, "state": "PRE_FREEZE"}) and not FZ.verify_manifest({**frozen, "state": "READY_TO_FREEZE"})


def test_the_freeze_record_must_confirm_the_digest_and_its_attestation_is_not_the_baselines_identity(tmp_path):
    ready = ready_manifest(tmp_path)
    digest = ready["manifest_sha256"]
    frozen = FZ.freeze(ready, operator="operator", confirmed_at=NOW, confirmation=digest)
    record = frozen["freeze"]
    for bad in (None, {}, {**record, "confirms": "0" * 64}, {**record, "operator": ""}, {**record, "confirmed_at": ""}):
        assert not FZ.verify_manifest({**frozen, "freeze": bad}), bad
    assert not FZ.verify_manifest({key: value for key, value in frozen.items() if key != "freeze"})   # FROZEN with no record
    assert not FZ.verify_manifest({**ready, "freeze": record})                                      # a record on a manifest that is not frozen
    # who froze it and when is an attestation beside the baseline: the digest stays the baseline's, and verifies
    later = {**frozen, "freeze": {**record, "operator": "another person", "confirmed_at": "2026-10-09T00:00:00Z"}}
    assert FZ.verify_manifest(later) and FZ.manifest_digest(later) == digest


def test_the_digest_is_of_the_parsed_content_not_of_the_files_line_endings(tmp_path):
    ready = ready_manifest(tmp_path)
    frozen = FZ.freeze(ready, operator="operator", confirmed_at=NOW, confirmation=ready["manifest_sha256"])
    lf = json.dumps(frozen, indent=2, ensure_ascii=False).encode("utf-8")
    crlf = lf.replace(b"\n", b"\r\n")
    assert lf != crlf
    for raw in (lf, crlf, record_json(frozen)):
        read = json.loads(raw.decode("utf-8"))
        assert FZ.verify_manifest(read) and FZ.manifest_digest(read) == ready["manifest_sha256"]


def test_the_first_frozen_canary_baseline_was_a_correct_artefact_that_the_old_check_refused():
    """Historical evidence, kept: its digest was right; the verification hashed the state the freeze had changed."""
    first = json.loads((REPO / "docs" / "canary" / "BASELINE_FROZEN_2026-10-08.json").read_text(encoding="utf-8"))
    digest = "f7ae73c3e9f0e7eeac31bbcf07f35e4ae186736327a5a05078994b5d1d75eaaf"
    assert first["state"] == "FROZEN" and first["manifest_sha256"] == digest == first["freeze"]["confirms"]
    as_the_old_check_hashed_it = {key: value for key, value in first.items() if key not in ("manifest_sha256", "freeze")}
    assert hashlib.sha256(canonical_json(as_the_old_check_hashed_it)).hexdigest() != digest
    assert FZ.verify_manifest(first) and FZ.manifest_digest(first) == digest


# --- registry review package ------------------------------------------------------------------------

REGISTRY = REPO / "config" / "outlet_registry.json"
PACKAGE = REPO / "config" / "registry_review" / "outlet_review_package.json"
PAGE = REPO / "docs" / "corpus_supply" / "REGISTRY_REVIEW_PACKAGE.md"


def test_the_tracked_package_is_what_the_generator_produces_from_the_tracked_registry(tmp_path):
    RR.write_package(REGISTRY, tmp_path / "package.json", tmp_path / "page.md")
    assert (tmp_path / "package.json").read_bytes() == PACKAGE.read_bytes()
    assert (tmp_path / "page.md").read_bytes() == PAGE.read_bytes()


def test_the_package_recommends_and_registers_nothing():
    before = REGISTRY.read_bytes()
    review = RR.build_review(json.loads(before.decode("utf-8")))
    assert REGISTRY.read_bytes() == before and review["status"].startswith("RECOMMENDATION_ONLY")
    registry = R.load_registry(REGISTRY)
    assert sum(o["registration_status"] == "registered" for o in registry.outlets.values()) == 22   # by a registration record, not by the package
    assert (review["summary"]["outlets"], review["summary"]["channels"]) == (91, 373)


NEW_TO_THE_REGISTRY = {"ar_el_tribuno", "bo_opinion", "cu_14ymedio", "cu_cubanet", "hn_criterio", "ni_articulo66", "ni_nicaragua_investiga",
                       "pr_noticel", "uy_montevideo_portal"}


def test_every_outlet_has_the_fields_a_reviewer_needs():
    review = json.loads(PACKAGE.read_text(encoding="utf-8"))
    statuses = {o["outlet_id"]: o["registration_status"] for o in R.load_registry(REGISTRY).outlets.values()}
    needed = {"outlet_id", "recommended_outlet_id", "display_name", "country_id", "legacy", "web_origins", "publisher",
              "channel_count", "channel_kinds", "channels", "unknown_fields", "warnings", "recommended_action"}
    for entry in review["outlets"]:
        assert needed <= set(entry), entry["outlet_id"]
        assert entry["publisher"] == "unknown"                       # not evidenced by the legacy database: not invented
        if statuses[entry["outlet_id"]] == "proposed":
            assert set(entry["unknown_fields"]) == set(RR.UNKNOWN_FIELDS)  # nothing was filled in
        else:
            assert set(entry["unknown_fields"]) < set(RR.UNKNOWN_FIELDS) and "timezone" not in entry["unknown_fields"]
        # An outlet of the legacy import names its legacy record; an outlet new to the registry (wave C, 2026-10-09) has none,
        # and none is made up for it.
        assert all(alias["newspaper_code"] for alias in entry["legacy"])
        assert entry["legacy"] or entry["outlet_id"] in NEW_TO_THE_REGISTRY, entry["outlet_id"]
        assert len(entry["channels"]) == entry["channel_count"]
    assert {entry["outlet_id"] for entry in review["outlets"] if not entry["legacy"]} == NEW_TO_THE_REGISTRY


def test_the_id_convention_is_uniform_and_collision_free_on_the_real_proposal():
    review = json.loads(PACKAGE.read_text(encoding="utf-8"))
    recommended = [entry["recommended_outlet_id"] for entry in review["outlets"]]
    assert len(set(recommended)) == len(recommended) == 91 and None not in recommended
    from coprepan import naming
    assert all(naming.is_outlet_id(value) for value in recommended)
    changed = {e["outlet_id"]: e["recommended_outlet_id"] for e in review["outlets"] if e["recommended_outlet_id"] != e["outlet_id"]}
    assert len(changed) == review["summary"]["ids_changed_by_the_convention"] == 23   # 21 of the legacy import; hn_criterio and ni_articulo66 of wave C (registered under the ids of their proposal)
    assert changed["co_elpais"] == "co_el_pais" and changed["pa_laestrelladepanama"] == "pa_la_estrella_de_panama"
    assert changed["bo_lostiempos"] == "bo_los_tiempos" and "uy_el_pais" not in changed
    # the legacy code stays provenance: every alias maps to exactly one recommended id
    mapping = review["legacy_to_recommended_id"]
    assert len(mapping) == 82 and {row["mapping_status"] for row in mapping} == {"hypothesis"}
    assert {(row["country_code"], row["legacy_slug"]): row["recommended_outlet_id"] for row in mapping}[("COL", "elpaís")] == "co_el_pais"


def test_channel_ids_are_unique_and_well_formed():
    from coprepan.identity import is_channel_id

    review = json.loads(PACKAGE.read_text(encoding="utf-8"))
    ids = [channel["recommended_channel_id"] for entry in review["outlets"] for channel in entry["channels"]]
    assert len(ids) == len(set(ids)) == 373 and all(is_channel_id(value) for value in ids)
    assert all(len(value.split(":ch:")[1]) <= 60 for value in ids)


def test_review_cases_are_flagged_and_never_merged():
    review = json.loads(PACKAGE.read_text(encoding="utf-8"))
    assert [(case["case"], case["outlets"]) for case in review["review_cases"]] == [
        ("channels_on_the_origin_of_another_outlet", ["pr_el_nuevo_dia", "pr_primera_hora"])]
    by_id = {entry["outlet_id"]: entry for entry in review["outlets"]}
    assert by_id["pr_primera_hora"]["recommended_action"] == "CHECK_CHANNEL_ATTRIBUTION"
    assert by_id["pr_primera_hora"]["publisher_evidence"] == ["shares a host with pr_el_nuevo_dia"]
    assert by_id["cl_biobiochile"]["hosts_not_of_the_outlet"] == ["feeds.feedburner.com"]
    assert by_id["cr_crhoy"]["additional_origin_candidates"] == ["https://crhoy.com"]
    assert by_id["co_el_tiempo"]["recommended_action"] == "FIND_CHANNELS_OR_LEAVE_UNREGISTERED"
    assert review["summary"]["by_recommended_action"] == {
        "CHECK_CHANNEL_ATTRIBUTION": 6, "CONFIRM_ID_AND_COMPLETE_ATTRIBUTES": 65, "FIND_CHANNELS_OR_LEAVE_UNREGISTERED": 20}


def test_same_outlet_candidates_are_a_review_case_not_a_merge():
    def entry(outlet_id, name, origin):
        return {"outlet_id": outlet_id, "country_id": outlet_id[:2], "registration_status": "proposed",
                "display_names": [{"name": name, "valid_from": "unknown", "valid_to": "unknown"}],
                "outlet_type": "unknown", "outlet_group": "unknown", "city": "unknown", "region": "unknown", "scope": "unknown",
                "access_model": "unknown", "medium": "unknown", "editions": [], "web_origins": [origin], "timezone": "unknown",
                "same_outlet_basis": "unknown",
                "url_rules": {"version": "proposed", "significant_query_params": [], "strip_path_prefixes": [], "strip_path_suffixes": []},
                "channels": [], "legacy_aliases": [], "legacy_observed": {"sources": []}, "review_notes": []}

    review = RR.build_review({"schema": "coprepan-outlet-registry/v1", "outlets": [
        entry("mx_el_universal", "El Universal", "https://www.eluniversal.test"),
        entry("mx_universal", "El Universal", "https://eluniversal.test")]})
    assert len(review["outlets"]) == 2                                   # both entries are still there
    assert {e["recommended_action"] for e in review["outlets"]} == {"DECIDE_ONE_OUTLET_OR_TWO"}
    assert sorted(case["case"] for case in review["review_cases"]) == ["recommended_id_collision", "same_display_name_in_one_country"]


def test_the_package_generator_is_a_pure_function_of_the_registry(tmp_path):
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert RR.build_review(document) == RR.build_review(document)
    first = RR.write_package(REGISTRY, tmp_path / "a.json", tmp_path / "a.md")
    RR.write_package(REGISTRY, tmp_path / "b.json", tmp_path / "b.md")
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    assert len(first["registry_sha256"]) == 64 and first["registry_sha256"] in (tmp_path / "a.md").read_text(encoding="utf-8")
