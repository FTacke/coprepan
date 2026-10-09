"""Delegated operator authorisation (decision CPD-0023).

Two ways exist to arm and freeze a canary. In the **interactive** mode a person types the two
confirmations at a terminal (CPD-0016 §4, CPD-0021). In the **delegated** mode an agent the operator
has commissioned does both, under a versioned *authorisation record* that states what the commission
covers: the waves, their outlets, the request limits, the policy, the validity, what is not covered.

This module reads such a record and answers one question — *does this record cover exactly this
canary?* — and nothing else. It arms nothing and confirms nothing. Nothing here is a human
confirmation and nothing is recorded as one: evidence produced under a record carries the mode
``DELEGATED_OPERATOR_AUTHORIZATION`` and the record's id and digest.

A record is **written once**. The checks that need the repository's history (one commit, unmodified,
pushed) are the caller's (``scripts/canary_operator.py``), because this module does not run git.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import naming
from .canonical import sha256_bytes

AUTHORIZATION_SCHEMA = naming.schema_id("operator-authorization", 1)
MODE_DELEGATED = "DELEGATED_OPERATOR_AUTHORIZATION"
MODE_INTERACTIVE = "INTERACTIVE_OPERATOR"
RECORDS = "config/operator_authorizations"
_KEYS = {"schema", "authorization_id", "kind", "issued_on", "issued_by", "issued_to", "source", "valid_until", "policy_versions",
         "actions_authorized", "not_authorized", "holds_in_force", "technical_gates", "stop_conditions", "disarming", "decisions", "waves"}
_WAVE_KEYS = {"label", "outlets", "registration", "limits", "canaries", "note"}
_LIMIT_KEYS = ("item_requests_total", "item_requests_per_outlet", "other_requests_per_outlet", "total_requests_ceiling")


class AuthorizationError(ValueError):
    """The record is not an authorisation this project can act on, or does not cover what is asked."""


def load(path: Path) -> dict[str, Any]:
    try:
        raw = Path(path).read_bytes()
        record = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as error:
        raise AuthorizationError(f"the authorisation record is not readable: {error}") from error
    validate(record)
    return {**record, "_sha256": sha256_bytes(raw)}


def validate(record: Any) -> None:
    if not isinstance(record, dict) or set(record) != _KEYS:
        raise AuthorizationError(f"an authorisation record has exactly the keys {sorted(_KEYS)}")
    if record["schema"] != AUTHORIZATION_SCHEMA or record["kind"] != MODE_DELEGATED:
        raise AuthorizationError(f"schema {AUTHORIZATION_SCHEMA} and kind {MODE_DELEGATED} are required")
    for key in ("authorization_id", "issued_by", "issued_to"):
        if not isinstance(record[key], str) or not record[key].strip():
            raise AuthorizationError(f"{key} is a non-empty string")
    for key in ("issued_on", "valid_until"):
        try:
            date.fromisoformat(record[key])
        except (TypeError, ValueError) as error:
            raise AuthorizationError(f"{key} is an ISO date") from error
    source = record["source"]
    if not isinstance(source, dict) or not source.get("form") or not source.get("authorising_clauses"):
        raise AuthorizationError("source names the form of the commission and quotes the clauses that authorise")
    for key in ("policy_versions", "actions_authorized", "not_authorized", "technical_gates", "stop_conditions"):
        if not isinstance(record[key], list) or not record[key] or not all(isinstance(item, str) and item for item in record[key]):
            raise AuthorizationError(f"{key} is a non-empty list of strings")
    for key in ("decisions", "holds_in_force"):
        if not isinstance(record[key], list) or not all(isinstance(item, str) and item for item in record[key]):
            raise AuthorizationError(f"{key} is a list of strings")
    if not isinstance(record["disarming"], str) or not record["disarming"].strip():
        raise AuthorizationError("disarming states the duty to disarm")
    waves = record["waves"]
    if not isinstance(waves, list) or not waves:
        raise AuthorizationError("an authorisation names at least one wave")
    labels = set()
    for wave in waves:
        if not isinstance(wave, dict) or set(wave) != _WAVE_KEYS:
            raise AuthorizationError(f"a wave has exactly the keys {sorted(_WAVE_KEYS)}")
        if not isinstance(wave["label"], str) or wave["label"] in labels:
            raise AuthorizationError("wave labels are distinct strings")
        labels.add(wave["label"])
        outlets = wave["outlets"]
        if not isinstance(outlets, list) or not outlets or len(set(outlets)) != len(outlets) or not all(naming.is_outlet_id(o) for o in outlets):
            raise AuthorizationError(f"{wave['label']}: outlets is a non-empty list of distinct outlet ids")
        limits = wave["limits"]
        if not isinstance(limits, dict) or set(limits) != set(_LIMIT_KEYS) or any(
                isinstance(limits[k], bool) or not isinstance(limits[k], int) or limits[k] < 0 for k in _LIMIT_KEYS):
            raise AuthorizationError(f"{wave['label']}: limits states exactly {_LIMIT_KEYS} as non-negative integers")
        if wave["canaries"] != 1:
            raise AuthorizationError(f"{wave['label']}: a wave is one canary; a second needs its own wave in a commission that grants it")
        if wave["registration"] is not None and (not isinstance(wave["registration"], dict) or set(wave["registration"]) != {"proposal", "proposal_sha256", "only"}):
            raise AuthorizationError(f"{wave['label']}: registration names the proposal, its digest and the outlets it registers")


def wave_of(record: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    for wave in record["waves"]:
        if wave["label"] == label:
            return wave
    raise AuthorizationError(f"the authorisation {record['authorization_id']} names no wave {label!r}")


def check(record: Mapping[str, Any], label: str, *, outlets: Sequence[str], budget: Mapping[str, int], total_requests_ceiling: int,
          policy_version: str, today: date, waves_used: Sequence[str] = ()) -> dict[str, Any]:
    """Whether the record covers exactly this canary. Raises with the first reason it does not;
    returns the block that the baseline pins and every later artefact carries.

    Exactly, in both directions: the outlets are the wave's outlets, no more and no fewer; no limit
    of the canary exceeds the wave's; the policy is one the record names; the record is in date;
    the wave has not been used.
    """
    wave = wave_of(record, label)
    if today > date.fromisoformat(record["valid_until"]) or today < date.fromisoformat(record["issued_on"]):
        raise AuthorizationError(f"the authorisation is valid from {record['issued_on']} to {record['valid_until']}")
    if sorted(outlets) != sorted(wave["outlets"]):
        extra, missing = sorted(set(outlets) - set(wave["outlets"])), sorted(set(wave["outlets"]) - set(outlets))
        raise AuthorizationError(f"{label}: the canary is not the authorised set (not authorised: {extra}; missing: {missing})")
    if label in waves_used:
        raise AuthorizationError(f"{label}: this wave of {record['authorization_id']} has a frozen baseline already; a wave is one canary")
    if policy_version not in record["policy_versions"]:
        raise AuthorizationError(f"policy {policy_version} is not one the authorisation names ({record['policy_versions']})")
    asked = {**{key: budget[key] for key in _LIMIT_KEYS[:3]}, "total_requests_ceiling": total_requests_ceiling}
    over = {key: (asked[key], wave["limits"][key]) for key in _LIMIT_KEYS if asked[key] > wave["limits"][key]}
    if over:
        raise AuthorizationError(f"{label}: the canary's budget exceeds the authorised limits (asked, authorised): {over}")
    return {"mode": MODE_DELEGATED, "authorization_id": record["authorization_id"], "authorization_sha256": record["_sha256"],
            "wave": label, "issued_by": record["issued_by"], "issued_to": record["issued_to"]}


def waves_used(baselines: Sequence[Mapping[str, Any]], authorization_id: str, *, except_manifest: str | None = None) -> list[str]:
    """The waves of an authorisation that already have a frozen baseline, from the baseline files.
    ``except_manifest`` is the digest of the baseline a run is started under: its own wave is not *used* by itself.
    """
    return sorted({(b.get("canary") or {}).get("authorization", {}).get("wave") for b in baselines
                   if (b.get("canary") or {}).get("authorization", {}).get("authorization_id") == authorization_id
                   and b.get("manifest_sha256") != except_manifest} - {None})


def frozen_baselines(directory: Path) -> list[dict[str, Any]]:
    """Every frozen baseline of record in a checkout (``docs/canary/BASELINE_FROZEN_*.json``). A file that
    cannot be read is an error, not an absent baseline: a used wave must not disappear behind a damaged file.
    """
    found = []
    for path in sorted(Path(directory).glob("BASELINE_FROZEN_*.json")):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            raise AuthorizationError(f"{path.name} is not readable, so the waves already used cannot be told: {error}") from error
    return found


def block_for(path: Path, label: str, *, repository: Path, outlets: Sequence[str], budget: Mapping[str, int], total_requests_ceiling: int,
              policy_version: str, today: date, except_manifest: str | None = None) -> dict[str, Any]:
    """The ``authorization`` block a baseline pins: :func:`check` against the record at ``path`` and the
    frozen baselines of ``repository``, plus the record's place in the checkout. The path must lie under
    ``config/operator_authorizations/`` of that checkout — a record from anywhere else is not one.
    """
    resolved, home = Path(path).resolve(), (Path(repository) / RECORDS).resolve()
    if resolved.parent != home:
        raise AuthorizationError(f"an authorisation record lies in {RECORDS}/ of the checkout")
    record = load(resolved)
    used = waves_used(frozen_baselines(Path(repository) / "docs" / "canary"), record["authorization_id"], except_manifest=except_manifest)
    return {**check(record, label, outlets=outlets, budget=budget, total_requests_ceiling=total_requests_ceiling,
                    policy_version=policy_version, today=today, waves_used=used), "record": f"{RECORDS}/{resolved.name}"}
