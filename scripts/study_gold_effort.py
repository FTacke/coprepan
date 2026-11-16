"""The structure a gold reviewer works through, measured on development pages (CPD-0044) -- the basis of the effort estimate.

Usage:
  python scripts/study_gold_effort.py (--runtime <ws> | --page-cache <cache>) --n 200 --seed 44 --out <effort.json>

On a random sample of the **development** population (never a holdout): per page the ``docview/1`` segments and words, and --
using the preferred extractor's BODY as a stand-in for where the article is, which is admissible on development pages only -- the
contiguous runs of article segments, the segments inside a run that are not article text (each one an override), the longer
segments outside the runs (each one an ``N`` check), and the article words a reviewer reads. The numbers of actions follow from
these counts; the seconds per action and the reading speed are **scenario assumptions**, stated as such.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

from coprepan import docview, extraction as E, extraction_body as B  # noqa: E402
import gold_review as CLI  # noqa: E402
import study_phase3_metadata as S3  # noqa: E402

SCENARIOS = {"fast": {"seconds_per_action": 2.0, "words_per_minute": 400, "fixed_seconds": 45},
             "slow": {"seconds_per_action": 4.0, "words_per_minute": 220, "fixed_seconds": 90}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--runtime", type=Path)
    src.add_argument("--page-cache", type=Path)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=44)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    rng = random.Random(arguments.seed)
    sample, seen = [], 0
    for page, body in S3.stored_pages(arguments):
        seen += 1
        if len(sample) < arguments.n:
            sample.append((page, body))
        elif (k := rng.randrange(seen)) < arguments.n:
            sample[k] = (page, body)
    rows = []
    for page, body in sample:
        html = CLI._decoded(page, body)
        segs = docview.segments(html)
        x = B.ARTICLE_4_2.run(body, body_sha256=page["body_sha256"], **page["args"])
        body_texts = {b["text"].strip() for b in x.record["blocks"] if b["role"] == E.ROLE_BODY} if x.outcome == E.OUTCOME_EXTRACTED else set()
        is_body = [s["text"] in body_texts for s in segs]
        idx = [i for i, v in enumerate(is_body) if v]
        runs, gaps = 0, 0
        if idx:
            runs = 1 + sum(1 for a, b in zip(idx, idx[1:]) if b != a + 1)
            gaps = sum(1 for i in range(idx[0], idx[-1] + 1) if not is_body[i])
        outside_long = sum(1 for i, s in enumerate(segs) if not is_body[i] and len(s["text"].split()) >= 8
                           and not ({"nav", "footer"} & set(s["flags"])))
        words = sum(len(s["text"].split()) for i, s in enumerate(segs) if is_body[i])
        rows.append({"segments": len(segs), "view_words": sum(len(s["text"].split()) for s in segs), "article_words": words,
                     "runs": runs, "overrides_inside": gaps, "long_outside": outside_long})

    def summary(key):
        v = sorted(r[key] for r in rows)
        return {"median": statistics.median(v), "p25": v[len(v) // 4], "p75": v[3 * len(v) // 4], "p90": v[9 * len(v) // 10], "mean": round(statistics.mean(v), 1)}

    # actions: jump (1) + per run: two clicks and a key (3) + per override inside: click and key (2) + title and standfirst (4)
    # + per long outside segment an N check (1) + the case questions (6: source, CORE, a reason or two, confirm, close)
    def actions(r):
        return 1 + 3 * r["runs"] + 2 * r["overrides_inside"] + 4 + r["long_outside"] + 6

    per_case = {}
    for name, s in SCENARIOS.items():
        minutes = [(actions(r) * s["seconds_per_action"] + r["article_words"] / s["words_per_minute"] * 60 + s["fixed_seconds"]) / 60 for r in rows]
        per_case[name] = {"assumptions": s, "minutes_median": round(statistics.median(minutes), 1),
                          "minutes_mean": round(statistics.mean(minutes), 1)}
    out = {"schema": "coprepan-gold-effort/v1", "decision": "CPD-0044", "population": "development pages (random sample)",
           "n": len(rows), "seed": arguments.seed, "measured": {k: summary(k) for k in rows[0]},
           "actions_per_case": summary_from([actions(r) for r in rows]),
           "minutes_per_case_scenarios": per_case,
           "note": "segments, words, runs, overrides and outside checks are measured on development pages with the extractor's BODY "
                   "as a stand-in for the article; the minutes are scenario assumptions, not a measurement of a human reviewer"}
    arguments.out.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps(out, ensure_ascii=False)[:2500])
    return 0


def summary_from(values):
    v = sorted(values)
    return {"median": statistics.median(v), "p25": v[len(v) // 4], "p75": v[3 * len(v) // 4], "p90": v[9 * len(v) // 10],
            "mean": round(statistics.mean(v), 1)}


if __name__ == "__main__":
    sys.exit(main())
