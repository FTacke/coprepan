"""Acquisition baseline manifest (master plan O-10 for the 3.0 side; decision CPD-0006 §9).

Before acquisition starts, *what exactly was started with* must be a named, hashed thing: which
registry, which policy, which crawler identity, which code, which decisions, which schemas and
component versions, which preservation target, which test baseline. This module builds that
manifest from the repository.

It never declares a freeze on its own. A manifest is ``PRE_FREEZE`` and lists what blocks a
freeze as long as any precondition is open; with none open it is ``READY_TO_FREEZE``; only an
explicit operator act turns that into ``FROZEN`` — and refuses while anything blocks.

(The freeze of the *legacy* corpus, ``coprepan-legacy-2026-06``, is a different manifest over a
different tree: ``docs/legacy/INDEX.md`` §5.)
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import (
    __version__, acquisition, capacity, crawler_identity, discovery, document_identity, extraction, http_acquisition,
    identity, layer_store, ledger, naming, pack, policy, preservation, preservation_target, registry, robots,
)
from .canonical import canonical_json, record_json, sha256_bytes, sha256_file
from .identity import format_instant
from .storage_roots import CHECKOUT

BASELINE_SCHEMA = naming.schema_id("acquisition-baseline", 1)
PRE_FREEZE, READY_TO_FREEZE, FROZEN = "PRE_FREEZE", "READY_TO_FREEZE", "FROZEN"

_MODULES = (acquisition, capacity, crawler_identity, discovery, document_identity, extraction, http_acquisition,
            layer_store, ledger, pack, policy, preservation, preservation_target, registry)
_CPD = re.compile(r"(CPD-\d{4})_.+\.md")


class FreezeRefused(RuntimeError):
    """A freeze was asked for while a precondition is open."""


def schema_ids() -> list[str]:
    """Every schema id the package mints, collected from its modules."""
    found = {getattr(module, name) for module in _MODULES for name in dir(module) if name.endswith("_SCHEMA")}
    found |= {identity.FETCH_ID_SCHEMA, identity.URL_KEY_RULESET}
    return sorted(value for value in found if isinstance(value, str) and naming.is_schema_id(value))


def component_versions() -> dict[str, str]:
    return {
        "package": __version__,
        "extractor": extraction.BASELINE.stage_version,
        "pack_writer": pack.PACK_WRITER_VERSION,
        "fetcher": crawler_identity.FETCHER_VERSION,
        "channel_parser": discovery.PARSER_VERSION,
        "robots_parser": robots.PARSER_VERSION,
        "head_scan": document_identity.HEAD_SCAN_VERSION,
        "preservation_policy": preservation.POLICY_VERSION,
        "url_key_ruleset": identity.URL_KEY_RULESET,
    }


def _hashed(path: Path) -> dict[str, Any]:
    digest, size = sha256_file(path)
    return {"path": path.relative_to(CHECKOUT).as_posix(), "sha256": digest, "size_bytes": size}


def build_manifest(
    *,
    code_commit: str,
    created_at: datetime,
    operator: str,
    test_baseline: Mapping[str, Any],
    storage_target: Mapping[str, Any] | None = None,
    capacity_measured: bool = False,
    repository: Path = CHECKOUT,
) -> dict[str, Any]:
    """The baseline manifest of the repository as it is on disk. Reads; changes nothing."""
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit or ""):
        raise ValueError("code_commit is a full 40-digit commit hash")
    config = repository / "config"
    registry_document = registry.load_registry(config / "outlet_registry.json")
    statuses = [outlet["registration_status"] for outlet in registry_document.outlets.values()]
    policy_document = policy.load_policy(config / "acquisition_policy.json")
    try:
        identity_record: dict[str, Any] = crawler_identity.load_identity(config / "crawler_identity.json").as_record()
        identity_state = "configured"
    except crawler_identity.CrawlerIdentityNotConfigured as refusal:
        identity_record, identity_state = {"refusal": str(refusal)}, "not_configured"

    blocking = []
    if "registered" not in statuses:
        blocking.append("O-11: no outlet is registered")
    if policy_document["status"] != policy.STATUS_DECIDED or policy_document["external_acquisition"] != "enabled":
        blocking.append("O-1: the acquisition policy is not decided or external acquisition is disabled")
    if identity_state != "configured":
        blocking.append("O-2: no crawler identity is configured")
    if storage_target is None or storage_target.get("status") != preservation_target.READY:
        blocking.append("O-3: no preservation target has passed the readiness check")
    if not capacity_measured:
        blocking.append("O-4: bytes per fetch have not been measured on real material")

    manifest: dict[str, Any] = {
        "schema": BASELINE_SCHEMA,
        "state": PRE_FREEZE if blocking else READY_TO_FREEZE,
        "blocking": blocking,
        "created_at": format_instant(created_at),
        "operator": operator,
        "code": {"commit": code_commit, "package_version": __version__},
        "registry": {**_hashed(config / "outlet_registry.json"), "schema": registry.REGISTRY_SCHEMA,
                     "outlets": len(statuses), "registered": statuses.count("registered"), "proposed": statuses.count("proposed"),
                     "channels": sum(len(outlet["channels"]) for outlet in registry_document.outlets.values())},
        "policy": {**_hashed(config / "acquisition_policy.json"), "policy_version": policy_document["policy_version"],
                   "status": policy_document["status"], "external_acquisition": policy_document["external_acquisition"]},
        "crawler_identity": {**_hashed(config / "crawler_identity.json"), "state": identity_state, "identity": identity_record},
        "configuration": [_hashed(config / name) for name in ("storage_targets.yml", "legacy_country_codes.json")],
        "decisions": {match.group(1): _hashed(path)["sha256"] for path in sorted((repository / "docs" / "decisions").glob("CPD-*.md"))
                      if (match := _CPD.fullmatch(path.name))},
        "schemas": schema_ids(),
        "components": component_versions(),
        "storage_target": dict(storage_target) if storage_target is not None else {"status": "not_configured"},
        "test_baseline": {**dict(test_baseline),
                          "fixtures": [_hashed(path) for path in sorted((repository / "tests" / "fixtures").glob("*/MANIFEST.json"))]},
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json(manifest))
    return manifest


def verify_manifest(manifest: Mapping[str, Any]) -> bool:
    """Whether a manifest's own digest covers its content."""
    body = {key: value for key, value in manifest.items() if key not in ("manifest_sha256", "freeze")}
    return manifest.get("manifest_sha256") == sha256_bytes(canonical_json(body))


def freeze(manifest: Mapping[str, Any], *, operator: str, confirmed_at: datetime, confirmation: str) -> dict[str, Any]:
    """The operator's act of freezing a baseline. Refused while anything blocks, when the
    manifest does not verify, or without the literal confirmation of its digest.
    """
    if not verify_manifest(manifest):
        raise FreezeRefused("the manifest does not match its own digest")
    if manifest["state"] != READY_TO_FREEZE or manifest["blocking"]:
        raise FreezeRefused("a baseline with open preconditions cannot be frozen: " + "; ".join(manifest["blocking"]))
    if confirmation != manifest["manifest_sha256"]:
        raise FreezeRefused("a freeze is confirmed by stating the manifest's digest")
    return {**manifest, "state": FROZEN,
            "freeze": {"operator": operator, "confirmed_at": format_instant(confirmed_at), "confirms": manifest["manifest_sha256"]}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the acquisition baseline manifest of this checkout (never a freeze).")
    parser.add_argument("--commit", required=True, help="the full hash of the commit this checkout is at")
    parser.add_argument("--operator", required=True)
    parser.add_argument("--tests-passed", type=int, required=True, help="result of the full suite on this commit")
    parser.add_argument("--out", type=Path, required=True, help="file to write (must not exist)")
    arguments = parser.parse_args(argv)
    manifest = build_manifest(code_commit=arguments.commit, created_at=datetime.now(timezone.utc), operator=arguments.operator,
                              test_baseline={"suite": "python -m pytest", "passed": arguments.tests_passed})
    with open(arguments.out, "xb") as handle:
        handle.write(record_json(manifest))
    print(json.dumps({"state": manifest["state"], "blocking": manifest["blocking"], "manifest_sha256": manifest["manifest_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
