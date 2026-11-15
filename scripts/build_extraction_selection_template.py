"""The selection template of the weekend extraction comparison (CPD-0018): numbers per outlet and variant, and a drawn review
sample -- for a person to fill in. Nothing is chosen, activated or rated PASS here.

Usage: python scripts/build_extraction_selection_template.py --variants <diagnose.json> --runtime <workspace> --out <template.md>
       [--evidence <dir>] [--per-outlet 2] [--seed TEXT]

Input: the output of ``scripts/diagnose_extraction_variants.py`` (median body characters per variant and outlet) and the fetch
records of the weekend waves (both delegated records). The sample is drawn per outlet, deterministically: the pages whose
``sha256(seed + fetch_id)`` is smallest -- anyone can redraw it from the seed. Only identifiers and URLs are written, never a
text of a page.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan import canary_driver as D, core_pipeline  # noqa: E402

AUTHORIZATIONS = ("DOA-2026-11-14-2", "DOA-2026-11-15-1")
VARIANTS = ("baseline", "rule_a", "rule_b", "jsonld", "densest_p_parent", "largest_article", "first_article", "paragraphs")
AGREEMENT = 0.15  # a screening choice: two variants "agree" within 15 % of each other's median; not a quality criterion


def _n(value):
    return "–" if value is None else f"{value:,.0f}" if isinstance(value, (int, float)) else str(value)


def screening_note(row: dict) -> str:
    """Which variants agree with the publisher-stated jsonld body, where there is one -- a pointer for the reviewer, not a verdict."""
    ld = row.get("jsonld") or 0
    if not row.get("jsonld_pages"):
        return "no jsonld body: compare the variants on the sample pages"
    close = [v for v in VARIANTS if v != "jsonld" and row.get(v) and abs(row[v] - ld) <= AGREEMENT * ld]
    return ("within 15 % of jsonld: " + ", ".join(close)) if close else "no variant within 15 % of jsonld"


def draw(records, per_outlet: int, seed: str) -> dict[str, list[dict]]:
    by_outlet = defaultdict(list)
    for record in records:
        by_outlet[record["outlet_id"]].append(record)
    sample = {}
    for outlet, rows in by_outlet.items():
        rows.sort(key=lambda r: hashlib.sha256((seed + r["fetch_id"]).encode("utf-8")).hexdigest())
        sample[outlet] = rows[:per_outlet]
    return sample


def render(variants: dict, sample: dict, seed: str, per_outlet: int) -> str:
    lines = [
        "# Extraction comparison of the weekend qualification — selection template (CPD-0018)",
        "",
        "**State: TEMPLATE, nothing selected.** The experimental baseline extractor stays as it is; no variant below is activated,",
        "and no row is a PASS. A variant is chosen by the extraction evaluation of CPD-0018 after a person has compared the drawn",
        "pages against the pages themselves.",
        "",
        "Measured offline on the local bytes of the weekend waves (`scripts/diagnose_extraction_variants.py`): median body characters",
        "per page and variant. `jsonld` is the longest schema.org `articleBody` the publisher states in the page — a comparison",
        "value, not a ground truth (it can be truncated, a teaser, or absent). The agreement note uses a screening threshold of",
        f"{AGREEMENT:.0%}; it points the reviewer at a variant, it does not rate one.",
        "",
        "Variants: `baseline` (as is), `rule_a` / `rule_b` (the two measured ancestor-rule repairs of the run report of 2026-11-14),",
        "`jsonld`, `densest_p_parent` (the element whose direct `<p>` children carry the most text, outside nav/aside/footer/form),",
        "`largest_article` / `first_article` (`<article>` elements), `paragraphs` (every `<p>`: an upper bound with boilerplate).",
        "",
        "## 1. Numbers per outlet",
        "",
        "| Outlet | Pages | " + " | ".join(f"`{v}`" for v in VARIANTS) + " | jsonld pages | Screening note | Reviewer's choice |",
        "|---|---:|" + "---:|" * len(VARIANTS) + "---:|---|---|",
    ]
    for outlet, row in sorted(variants.items()):
        lines.append(f"| `{outlet}` | {row.get('pages')} | " + " | ".join(_n(row.get(v)) for v in VARIANTS)
                     + f" | {row.get('jsonld_pages', 0)} | {screening_note(row)} | |")
    lines += [
        "",
        f"## 2. Review sample ({per_outlet} pages per outlet, seed `{seed}`)",
        "",
        "Drawn by the smallest `sha256(seed + fetch_id)` among each outlet's 2xx item pages. For each page: open the URL, and note",
        "which variant holds the article body completely and nothing else (`complete` / `truncated` / `with boilerplate` / `wrong",
        "element`). The bytes are those of the fetch id (state `PRESERVATION_PENDING` until the deferred preservation).",
        "",
        "| Outlet | Fetch id | Run | URL | Best variant | Verdict per variant | Reviewer, date |",
        "|---|---|---|---|---|---|---|",
    ]
    for outlet in sorted(sample):
        for record in sample[outlet]:
            lines.append(f"| `{outlet}` | `{record['fetch_id'][:20]}…` | `{record['run_id'][:24]}…` | {record['request']['requested_url']} | | | |")
    lines += [
        "",
        "## 3. What a decision needs (open)",
        "",
        "- the filled sample (every outlet, or the outlets the decision is to cover);",
        "- the rule for an outlet whose pages disagree with each other (a per-outlet variant is a registry-level setting, a global one",
        "  a change of the baseline extractor);",
        "- the version of the extractor that would be pinned, and a re-extraction of the stored bytes under it — the bytes are kept as",
        "  received, so no page needs to be requested again for this.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--variants", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, default=REPOSITORY / "docs" / "canary" / "evidence")
    parser.add_argument("--per-outlet", type=int, default=2)
    parser.add_argument("--seed", default="weekend-qualification-2026-11-15")
    arguments = parser.parse_args(argv)
    variants = json.loads(arguments.variants.read_text(encoding="utf-8"))
    runs = set()
    for path in sorted(arguments.evidence.glob("*/canary-receipt-*.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if (receipt.get("operator_authorization") or {}).get("authorization_id") in AUTHORIZATIONS:
            runs.add(receipt["run_id"])
    records = [r for r in D.fetch_records(core_pipeline.Workspace(arguments.runtime))
               if r["run_id"] in runs and r["fetch_kind"] == "item" and r["outcome"] == "FETCHED" and 200 <= int(r["response"]["status"]) < 300
               and r["outlet_id"] in variants]
    sample = draw(records, arguments.per_outlet, arguments.seed)
    arguments.out.write_text(render(variants, sample, arguments.seed, arguments.per_outlet), encoding="utf-8")
    print(json.dumps({"outlets": len(variants), "sample_pages": sum(len(v) for v in sample.values())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
