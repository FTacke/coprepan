"""Pipeline stages and the status vocabulary of ``docs/STATUS.md``.

The order is the order of ``docs/architecture/TARGET_ARCHITECTURE.md`` §1. This module names the
stages; it implements none of them.
"""

from __future__ import annotations

PIPELINE_STAGES = (
    "outlet_registry",
    "discovery",
    "fetch",
    "raw_preservation",
    "document_identity",
    "extraction",
    "admission_labels",
    "normalisation",
    "nlp",
    "enrichment",
    "release",
    "cross_corpus_contract",
)

IMPLEMENTATION_STATES = ("NOT_STARTED", "PARTIAL", "IMPLEMENTED")
VALIDATION_STATES = ("NOT_VALIDATED", "VALIDATED")
ACTIVATION_STATES = ("INACTIVE", "ACTIVE")


def status_violations(stage: str, status: dict[str, str]) -> list[str]:
    """Why a stage status is inadmissible; empty when it is admissible.

    A stage is ACTIVE only when it is IMPLEMENTED and VALIDATED: implementation, scientific
    validation and production activation are separate acts, in that order.
    """
    problems = []
    for axis, allowed in (
        ("implementation", IMPLEMENTATION_STATES),
        ("validation", VALIDATION_STATES),
        ("activation", ACTIVATION_STATES),
    ):
        if status.get(axis) not in allowed:
            problems.append(f"{stage}: {axis}={status.get(axis)!r} is not one of {allowed}")
    if problems:
        return problems
    if status["validation"] == "VALIDATED" and status["implementation"] != "IMPLEMENTED":
        problems.append(f"{stage}: VALIDATED without IMPLEMENTED")
    if status["activation"] == "ACTIVE" and status["validation"] != "VALIDATED":
        problems.append(f"{stage}: ACTIVE without VALIDATED")
    return problems
