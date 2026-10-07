"""Storage capacity model (master plan O-4; decision CPD-0006 §8).

A calculator, not an estimate. Every input is a :class:`Quantity` that says what kind of number
it is — ``measured`` (with where and when), ``estimated`` (derived from measurements by a stated
step) or ``assumed`` (a scenario value nobody has measured) — and every output carries the
weakest label among the inputs it was computed from. A result built on an assumption is an
assumption, however many decimals it has.

There are no built-in values: the model refuses to run on a missing input.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Mapping

from . import naming

CAPACITY_SCHEMA = naming.schema_id("capacity-model", 1)
MEASURED, ESTIMATED, ASSUMED = "measured", "estimated", "assumed"
_RANK = {ASSUMED: 0, ESTIMATED: 1, MEASURED: 2}

INPUTS = (
    "fetches_per_day",                  # all fetches: items, channel documents, robots files, retries
    "stored_body_bytes_per_fetch",      # the body as stored in the pack, i.e. after per-record gzip
    "pack_overhead_bytes_per_fetch",    # WARC headers and the fetch record, compressed
    "index_bytes_per_fetch",            # the pack index row
    "workspace_bytes_per_fetch",        # ledger, request log, discovery and identity rows
    "item_share",                       # share of fetches that are items and get an extraction
    "extraction_bytes_per_item",        # the extraction record with its layer manifest
    "retention_days",
    "copies",                           # preservation copy plus backups
)


@dataclass(frozen=True)
class Quantity:
    value: float
    label: str
    source: str

    def __post_init__(self) -> None:
        if self.label not in _RANK:
            raise ValueError(f"a quantity is measured, estimated or assumed: {self.label!r}")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or self.value < 0:
            raise ValueError(f"a quantity is a non-negative number: {self.value!r}")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("a quantity names where its value comes from")


def weakest(*quantities: Quantity) -> str:
    return min((quantity.label for quantity in quantities), key=_RANK.__getitem__)


def storage_model(inputs: Mapping[str, Quantity]) -> dict[str, Any]:
    """Bytes per layer for the given inputs. Refuses a missing or unknown input."""
    if set(inputs) != set(INPUTS):
        raise ValueError(f"the model needs exactly {INPUTS}; missing {sorted(set(INPUTS) - set(inputs))}, "
                         f"unknown {sorted(set(inputs) - set(INPUTS))}")
    q = inputs
    fetches = q["fetches_per_day"].value * q["retention_days"].value
    base = (q["fetches_per_day"], q["retention_days"])

    def layer(value: float, *used: Quantity) -> dict[str, Any]:
        return {"bytes": round(value), "label": weakest(*base, *used)}

    raw = fetches * (q["stored_body_bytes_per_fetch"].value + q["pack_overhead_bytes_per_fetch"].value)
    index = fetches * q["index_bytes_per_fetch"].value
    preservation_one = raw + index
    layers = {
        "raw_packs": layer(raw, q["stored_body_bytes_per_fetch"], q["pack_overhead_bytes_per_fetch"]),
        "pack_indexes": layer(index, q["index_bytes_per_fetch"]),
        "preservation_all_copies": layer(preservation_one * q["copies"].value, q["stored_body_bytes_per_fetch"],
                                         q["pack_overhead_bytes_per_fetch"], q["index_bytes_per_fetch"], q["copies"]),
        "workspace_records": layer(fetches * q["workspace_bytes_per_fetch"].value, q["workspace_bytes_per_fetch"]),
        "extraction_layer": layer(fetches * q["item_share"].value * q["extraction_bytes_per_item"].value,
                                  q["item_share"], q["extraction_bytes_per_item"]),
    }
    total = layers["preservation_all_copies"]["bytes"] + layers["workspace_records"]["bytes"] + layers["extraction_layer"]["bytes"]
    return {
        "schema": CAPACITY_SCHEMA,
        "inputs": {name: {"value": q[name].value, "label": q[name].label, "source": q[name].source} for name in INPUTS},
        "fetches_in_horizon": round(fetches),
        "layers": layers,
        "total": {"bytes": total, "gib": round(total / 2**30, 2), "label": weakest(*q.values())},
        "note": "A total labelled 'assumed' is a scenario, not a forecast.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Storage need for a stated scenario. Every value is 'number:label:source'.")
    for name in INPUTS:
        parser.add_argument(f"--{name.replace('_', '-')}", required=True, metavar="VALUE:LABEL:SOURCE")
    arguments = vars(parser.parse_args(argv))
    inputs = {}
    for name in INPUTS:
        value, label, source = arguments[name].split(":", 2)
        inputs[name] = Quantity(float(value), label, source)
    print(json.dumps(storage_model(inputs), indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
