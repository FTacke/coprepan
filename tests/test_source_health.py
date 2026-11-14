"""The source-health matrix (scripts/build_source_health.py): built from tracked evidence only, deterministic, every documented
outlet in it, and each recommendation traceable to its evidence. No workspace and no request are needed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLASSES = {"READY", "READY_WITH_LIMITATIONS", "REPAIR_REQUIRED", "REQUALIFICATION_REQUIRED", "HELD", "NOT_REGISTERED"}


def builder():
    spec = importlib.util.spec_from_file_location("build_source_health", REPO / "scripts" / "build_source_health.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_documented_outlet_is_in_the_matrix_with_a_traceable_recommendation():
    doc = builder().build(None, "test")
    registry = {o["outlet_id"] for o in json.loads((REPO / "config" / "outlet_registry.json").read_text(encoding="utf-8"))["outlets"]}
    inventory = {o["outlet_id"] for o in json.loads((REPO / "config" / "source_discovery" / "source_inventory_2026-10-10.1.json").read_text(encoding="utf-8"))["outlets"]}
    ids = {r["outlet_id"] for r in doc["outlets"]}
    assert ids == registry | inventory
    assert all(r["recommendation"] in CLASSES for r in doc["outlets"])
    assert all(r["because"] for r in doc["outlets"] if r["recommendation"] != "READY")       # every non-READY class names its evidence
    assert sum(doc["totals"]["recommendations"].values()) == len(ids) and doc["totals"]["operationally_stable"] == 0
    readiness = json.loads((REPO / "config" / "intake" / "intake_readiness_2026-10-10.1.json").read_text(encoding="utf-8"))
    assert doc["totals"]["qualified_for_intake"] == len(readiness["outlets"])


def test_the_known_cases_of_the_24_hour_intake_are_classified_as_the_evidence_says():
    rows = {r["outlet_id"]: r for r in builder().build(None, "test")["outlets"]}
    assert rows["ve_efecto_cocuyo"]["recommendation"] == "HELD"                      # its only channel held since the 24-hour intake
    assert rows["pe_elperuano"]["recommendation"] == "REQUALIFICATION_REQUIRED"       # no item page (robots unreachable)
    heraldo = rows["hn_el_heraldo"]
    assert heraldo["recommendation"] == "REQUALIFICATION_REQUIRED"                   # a section sitemap, not a news stream
    assert any(c["status"] == "HISTORICAL_ENTRIES_ONLY" for c in heraldo["channels"])
    assert rows["pa_diaadia"]["recommendation"] == "REPAIR_REQUIRED" and rows["pa_diaadia"]["review_cases"]
    clarin = rows["ar_clarin"]
    assert clarin["novelty_coverage"]["new_dated_left_unfetched"] == 389 and clarin["recommendation"] == "READY_WITH_LIMITATIONS"


def test_the_matrix_is_deterministic():
    module = builder()
    assert json.dumps(module.build(None, "x"), sort_keys=True) == json.dumps(module.build(None, "x"), sort_keys=True)
