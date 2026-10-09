"""The consolidated qualification overview, the third canary wave and the operator's workflow (CPD-0020 §5–§7).

What is tested: that the overview is the join it says it is and registers nothing; that outlets
which were never in the legacy system enter a registry only through an applied proposal, with a
record, never by collision; and that the operator's tool cannot be confirmed by anything but a
person at a terminal. No test arms, fetches or touches the tracked configuration.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import shutil
from pathlib import Path

import pytest

from coprepan import canary_driver as D, candidate_filter, policy as P, registry as R, registry_review as RR

REPO = Path(__file__).resolve().parents[1]
DISCOVERY = REPO / "config" / "source_discovery"
REVIEW_DIR = REPO / "config" / "registry_review"
OVERVIEW = DISCOVERY / "source_qualification_overview_2026-10-09.2.json"
SUPPLEMENT = DISCOVERY / "coprepan_prediscovery_ergaenzung_2026-10-09.json"
WAVE_C = REVIEW_DIR / "wave_c_proposal_2026-10-09.json"
WAVE_B = REVIEW_DIR / "extended_canary_proposal_2026-10-09.json"
WAVE_B_REVIEW = REVIEW_DIR / "extended_canary_review_2026-10-09.json"
STAGES = ("RESEARCHED", "CANDIDATE", "TECHNICALLY_QUALIFIED", "REGISTERED", "ACQUISITION_VERIFIED", "OPERATIONALLY_STABLE")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checkout_copy(tmp_path: Path) -> Path:
    copy = tmp_path / "checkout"
    (copy / "config" / "registry_review").mkdir(parents=True)
    (copy / "docs" / "corpus_supply").mkdir(parents=True)
    for name in ("outlet_registry.json", "candidate_rules.json", "acquisition_policy.json"):
        shutil.copyfile(REPO / "config" / name, copy / "config" / name)
    return copy


def untouched() -> bool:
    registry = R.load_registry(REPO / "config" / "outlet_registry.json")
    return not any(o in registry.outlets for o in (e["outlet_id"] for e in load(WAVE_C)["new_outlets"]))


@pytest.fixture(scope="module")
def overview():
    return load(OVERVIEW)


# --- the overview -------------------------------------------------------------------------------------


def test_the_overview_names_its_inputs_by_digest_and_is_what_the_script_builds(overview, tmp_path):
    inputs = overview["inputs"]
    assert hashlib.sha256((DISCOVERY / inputs["inventory"]["file"]).read_bytes()).hexdigest() == inputs["inventory"]["sha256"]
    assert hashlib.sha256(SUPPLEMENT.read_bytes()).hexdigest() == inputs["supplement"]["sha256"]
    for entry in [*inputs["proposals"], *inputs["reviews"]]:
        assert hashlib.sha256((REVIEW_DIR / entry["file"]).read_bytes()).hexdigest() == entry["sha256"], entry["file"]
    builder = script("consolidate_source_discovery")
    arguments = ["--inventory", str(DISCOVERY / inputs["inventory"]["file"]), "--supplement", str(SUPPLEMENT), "--proposal", str(WAVE_B),
                 "--proposal", str(WAVE_C), "--review", str(WAVE_B_REVIEW), "--version", "2026-10-09.2",
                 "--out-json", str(tmp_path / "o.json"), "--out-md", str(tmp_path / "o.md")]
    assert builder.main(arguments) == 0
    assert (tmp_path / "o.json").read_bytes() == OVERVIEW.read_bytes()            # deterministic
    assert (tmp_path / "o.md").read_bytes() == (REPO / "docs" / "corpus_supply" / "SOURCE_COVERAGE_REPORT.md").read_bytes()
    with pytest.raises(SystemExit):
        builder.main(arguments)                                                  # a version is written once


def test_the_supplement_is_kept_as_delivered_and_every_entry_is_classified_once(overview):
    supplement = load(SUPPLEMENT)
    assert supplement["kind"] == "EVIDENCE_ONLY_NOT_REGISTRY_NOT_LIVE_QUALIFICATION" and len(supplement["candidates"]) == 19
    entries = overview["supplement"]
    assert [e["outlet_id_candidate"] for e in entries] == [c["outlet_id_candidate"] for c in supplement["candidates"]]
    assert all(e["classification"] in overview["classification_rules"] and e["disposition"] in overview["disposition_meaning"] for e in entries)
    assert all(e["status"] == "RESEARCH_ONLY / NOT_REGISTERED / NOT_LIVE_VALIDATED" for e in entries)
    by_id = {e["outlet_id_candidate"]: e for e in entries}
    registry = load(REPO / "config" / "outlet_registry.json")
    legacy_ids = {o["outlet_id"] for o in registry["outlets"] if o["legacy_observed"]}
    assert {i for i, e in by_id.items() if e["in_registry"]} == set(by_id) & legacy_ids
    # the deduplication against the earlier files: one exact registry channel, three outlets no earlier file names
    assert by_id["ec_el_comercio"]["classification"] == "KNOWN_IDENTICAL"
    assert {i for i, e in by_id.items() if e["classification"] == "NEW_OUTLET_CANDIDATE"} == {"cu_diario_de_cuba", "ar_el_tribuno", "mx_expansion"}
    assert sum(1 for e in entries if e["classification"] == "OUTLET_ALREADY_PROPOSED") == 10
    assert by_id["py_abc_color"]["matches"][0]["match"] == "registry_channel_variant"        # the same route without its query: a variant, no new channel
    assert by_id["co_el_tiempo"]["disposition"] == "HOLD_LEGAL_REVIEW" and by_id["co_el_tiempo"]["requires_specific_legal_review"]
    assert by_id["mx_el_siglo_de_torreon"]["conflicting_evidence"] and by_id["mx_el_siglo_de_torreon"]["disposition"] == "NEEDS_CURRENT_EVIDENCE"
    assert by_id["ec_el_universo"]["disposition"] == "EVIDENCE_FOR_REVIEWED_WAVE"            # the reviewed wave is not changed by it


def test_stages_follow_from_evidence_and_nothing_outside_the_registry_is_more_than_a_candidate(overview):
    sources = {s["outlet_id"]: s for s in overview["sources"]}
    assert len(sources) == 82 and all(set(s["stages"]) <= set(STAGES) for s in sources.values())
    # A dated snapshot: the stages are those of the registry the overview was built from, before the waves were registered.
    assert {i for i, s in sources.items() if "REGISTERED" in s["stages"]} == {"bo_el_deber", "do_diario_libre", "hn_proceso_digital", "py_la_nacion", "ve_efecto_cocuyo"}
    assert {i for i, s in sources.items() if "ACQUISITION_VERIFIED" in s["stages"]} == {"do_diario_libre"}
    assert not any("OPERATIONALLY_STABLE" in s["stages"] for s in sources.values())
    outside = overview["outlet_candidates"]
    assert len(outside) == 63 and all(set(c["stages"]) <= {"RESEARCHED", "CANDIDATE"} and not c["in_registry"] for c in outside)
    assert len({(c["country_id"], c["name"]) for c in outside}) == 63                         # the 60 earlier proposals and three new, no outlet twice
    assert not any(c["host_is_a_registry_origin_of"] for c in outside)                        # no candidate sits on a registry outlet's host
    coverage = overview["coverage_by_country"]
    assert sum(row["registry_outlets"] for row in coverage.values()) == 82 and sum(row["acquisition_verified"] for row in coverage.values()) == 1
    assert [c for c, row in coverage.items() if row["legacy_outlets_with_accepted_articles"] == 0] == ["ec", "ni"]
    assert coverage["ni"]["in_a_proposed_wave"] == ["ni_confidencial", "ni_articulo66", "ni_nicaragua_investiga"]


def test_the_identity_cases_state_facts_and_decide_nothing(overview):
    cases = {case["case"]: case for case in overview["identity_cases"]}
    assert {"pr_primera_hora", "cl_el_mercurio", "ni_confidencial", "bo_la_razon", "ni_la_prensa", "closed outlets"} <= set(cases)
    primera = cases["pr_primera_hora"]["facts"]
    assert primera["channel_hosts"] == ["elnuevodia.com"] and primera["web_origins"] == ["https://www.primerahora.com"]
    assert cases["cl_el_mercurio"]["facts"]["web_origins"] == ["https://www.emol.com"]
    assert all(case["decision"].startswith(("OPEN", "no action")) for case in cases.values())
    registry = R.load_registry(REPO / "config" / "outlet_registry.json")                     # and nothing was acted on
    assert registry.outlets["pr_primera_hora"]["registration_status"] == "proposed" and len(registry.outlets["pr_primera_hora"]["channels"]) == 3
    assert registry.outlets["bo_la_razon"]["web_origins"] == ["https://www.la-razon.com"]


# --- the third wave: outlets that were never in the legacy system ------------------------------------------


def test_the_wave_registers_nothing_and_names_outlets_the_registry_does_not_hold():
    proposal = load(WAVE_C)
    assert proposal["status"].startswith("PROPOSAL") and proposal["proposed"] == [] and len(proposal["new_outlets"]) == 9
    assert len({e["country_id"] for e in proposal["new_outlets"]}) == 7
    for entry in proposal["new_outlets"]:
        assert entry["evidence"] and all(item["source"] and item["how"] for item in entry["evidence"])
        assert entry["outlet_id"][:2] == entry["country_id"] and entry["attributes_set"]["timezone"] != "unknown"
    if untouched():
        assert candidate_filter.load_rules() == {}                               # no allow rule is proposed: none is evidenced
    assert sum(1 for e in proposal["new_outlets"] for c in e["new_channels"] if c["kind"] in ("archive", "section_page")) == 5


def test_applied_to_a_copy_the_wave_gives_new_registered_outlets_a_record_and_a_canary(tmp_path):
    if not untouched():
        pytest.skip("the wave has been applied: its registration record is what the registry tests hold the registry against")
    applier, proposal = script("apply_registration_proposal"), load(WAVE_C)
    copy = checkout_copy(tmp_path)
    before = (REPO / "config" / "outlet_registry.json").read_bytes()
    assert applier.main(["--proposal", str(WAVE_C), "--approved-by", "a test", "--repository", str(copy), "--write"]) == 0
    assert (REPO / "config" / "outlet_registry.json").read_bytes() == before
    registry = R.load_registry(copy / "config" / "outlet_registry.json")
    new = [e["outlet_id"] for e in proposal["new_outlets"]]
    record = load(next((copy / "config" / "registry_review").glob("wave_c_registration_*.json")))
    assert [e["outlet_id"] for e in record["registered"]] == new and all(e["new_outlet"] for e in record["registered"])
    for outlet_id in new:
        outlet = registry.resolve(outlet_id)
        assert outlet["legacy_observed"] == {} and outlet["legacy_aliases"] == [] and all(c["legacy_observed"] == {} for c in outlet["channels"])
    assert len(registry.outlets) == 82 + 9 and list(registry.outlets) == sorted(registry.outlets)
    old = {o["outlet_id"]: o for o in load(REPO / "config" / "outlet_registry.json")["outlets"]}
    assert all(registry.outlets[i] == o for i, o in old.items())                 # no existing row was changed
    assert (copy / "config" / "acquisition_policy.json").read_bytes() == (REPO / "config" / "acquisition_policy.json").read_bytes()
    RR.write_package(copy / "config" / "outlet_registry.json", tmp_path / "package.json", tmp_path / "page.md")
    assert (tmp_path / "package.json").read_bytes() == (copy / "config" / "registry_review" / "outlet_review_package.json").read_bytes()

    budget = D.canary_budget(len(new))
    pin = D.driver_pin(budget, registry, new, P.load_policy(copy / "config" / "acquisition_policy.json")["disabled_channels"], {})
    assert (budget.item_requests_per_outlet, budget.item_requests_total) == (10, 90)
    assert pin["outlets"]["ni_articulo66"] == ["ni_articulo66:ch:rss_r001", "ni_articulo66:ch:archive_r001"]      # a feed and a numbered archive
    assert pin["outlets"]["pr_noticel"] == ["pr_noticel:ch:section_page_r001"]                                    # a listing and nothing else
    assert pin["outlets"]["uy_montevideo_portal"] == ["uy_montevideo_portal:ch:rss_r001", "uy_montevideo_portal:ch:rss_r002"]
    assert pin["driver"] == D.DRIVER_VERSION and pin["candidate_budget_order"] == "candidate-budget-order/1"


def test_the_wave_can_follow_the_first_wave_and_an_id_or_a_host_the_registry_holds_is_refused(tmp_path):
    if not untouched() or load(WAVE_B)["inputs"]["registry_sha256_before"] != hashlib.sha256((REPO / "config" / "outlet_registry.json").read_bytes()).hexdigest():
        pytest.skip("a proposal has been applied")
    applier = script("apply_registration_proposal")
    copy = checkout_copy(tmp_path)
    first = ["--proposal", str(WAVE_B), "--approved-by", "a test", "--repository", str(copy), "--write"]
    for outlet in load(WAVE_B_REVIEW)["recommended_first_wave"]:
        first += ["--only", outlet]
    assert applier.main(first) == 0                                              # the first wave changes the registry …
    assert applier.main(["--proposal", str(WAVE_C), "--approved-by", "a test", "--repository", str(copy), "--write",
                         "--only", "ni_articulo66", "--only", "uy_montevideo_portal"]) == 0     # … and the new outlets can still be added, in part
    registry = R.load_registry(copy / "config" / "outlet_registry.json")
    assert sum(1 for o in registry.outlets.values() if o["registration_status"] == "registered") == 5 + 8 + 2 and "cu_cubanet" not in registry.outlets
    documents = [load(copy / "config" / name) for name in ("outlet_registry.json", "candidate_rules.json", "acquisition_policy.json")]
    proposal = load(WAVE_C)
    with pytest.raises(applier.ProposalError, match="holds this id already"):
        applier.apply(proposal, *documents, approved_by="x", approved_on="2026-10-09", only=["ni_articulo66"])
    clash = json.loads(json.dumps(proposal))
    clash["new_outlets"][0].update(outlet_id="ar_otro_tribuno", web_origins=["https://clarin.com"])
    clash["new_outlets"][0]["new_channels"] = [{"channel_id": "ar_otro_tribuno:ch:rss_r001", "kind": "rss", "url": "https://clarin.com/rss", "valid_from": "unknown"}]
    clash["new_outlets"][0]["channel_order"] = ["ar_otro_tribuno:ch:rss_r001"]
    with pytest.raises(applier.ProposalError, match="is an origin of ar_clarin"):
        applier.apply(clash, *documents, approved_by="x", approved_on="2026-10-09", only=["ar_otro_tribuno"])
    wrong = json.loads(json.dumps(proposal))
    wrong["new_outlets"][0]["outlet_id"] = "uy_el_tribuno"                          # an id of another country than the entry's
    with pytest.raises(applier.ProposalError):
        applier.apply(wrong, *documents, approved_by="x", approved_on="2026-10-09", only=["uy_el_tribuno"])


# --- the operator's workflow -------------------------------------------------------------------------------


class Terminal(io.StringIO):
    def isatty(self):
        return True


MANIFEST = {"state": "READY_TO_FREEZE", "blocking": [], "manifest_sha256": "d" * 64, "code": {"commit": "c" * 40},
            "policy": {"sha256": "p" * 64}, "registry": {"sha256": "r" * 64},
            "canary": {"driver": {"driver": "canary-driver/4", "budget": {}, "outlets": {}}, "storage_target": {"target_id": "t"}}}


def test_a_confirmation_is_accepted_only_from_a_person_at_a_terminal_and_only_the_digest(capsys):
    tool = script("canary_operator")
    for not_a_person in (io.StringIO("ARM\n"), io.StringIO("d" * 64 + "\n")):   # a pipe, a file, a script
        with pytest.raises(tool.Stop, match="person at a terminal"):
            tool.typed_by_a_person("? ", not_a_person)
        with pytest.raises(tool.Stop, match="person at a terminal"):
            tool.confirm_digest(MANIFEST, not_a_person)
    for wrong in ("", "yes", "d" * 63, "D" * 64, "e" * 64):
        with pytest.raises(tool.Stop, match="nothing was frozen"):
            tool.confirm_digest(MANIFEST, Terminal(wrong + "\n"))
    tool.confirm_digest(MANIFEST, Terminal("d" * 64 + "\n"))
    assert "d" * 64 in capsys.readouterr().out                                   # the digest was shown before it was asked for
    # the command line offers no way to pass a confirmation
    with pytest.raises(SystemExit):
        tool.main(["--operator", "x", "--label", "second", "--outlet", "bo_el_deber", "--confirm", "d" * 64])
    with pytest.raises(SystemExit):
        tool.main(["--operator", "x", "--label", "second", "--outlet", "bo_el_deber", "--yes"])


def test_the_switch_is_turned_alone_and_back_to_the_same_bytes(tmp_path, monkeypatch):
    tool = script("canary_operator")
    copy = tmp_path / "acquisition_policy.json"
    original = (REPO / "config" / "acquisition_policy.json").read_bytes()
    copy.write_bytes(original)
    monkeypatch.setattr(tool, "POLICY", copy)
    start = tool.switch_state()
    tool.set_switch("enabled")
    armed = copy.read_bytes()
    assert tool.switch_state() == "enabled" and P.load_policy(copy)["external_acquisition"] == "enabled" and b"\r" not in armed
    assert {k: v for k, v in json.loads(armed).items() if k != "external_acquisition"} == {k: v for k, v in json.loads(original).items() if k != "external_acquisition"}
    tool.set_switch(start)
    assert copy.read_bytes() == original and (REPO / "config" / "acquisition_policy.json").read_bytes() == original
    copy.write_bytes(original.replace(b'"external_acquisition"', b'"external_acquisitions"'))
    with pytest.raises(tool.Stop):
        tool.switch_state()
