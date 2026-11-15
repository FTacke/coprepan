# Blind control of the Phase-3 candidates (frozen 2026-11-15, CPD-0040)

**For the operator's scientific acceptance** of `article_html/0.3.0`, `content-quality/3`, `section-map/1`, `ai-disclosure/1`,
`agency-credit/2` and `text-reuse/2`. Frozen before any human verdict: the cases, the questions and the machine's answers are
fixed by digest in [`manifest.json`](manifest.json).

## Files

| File | What | Open when |
|---|---|---|
| `manifest.json` | population, exclusions, seed, the 16 strata (sizes, populations, how drawn), the case list, the questions and definitions, the digests of the three files below | any time |
| `verdicts_form.csv` | one row per case and question (253 rows, 70 cases): `case_id`, `question`, `allowed`, an empty `answer` and `note` | to answer |
| reading sheet `blind_reading_sheet_2026-11-15.html` | per case the page evidence (headline candidates, the blocks after each `h1`, the stated description, the extracted BODY, the published section, every block mentioning AI, every credit or mention of an agency; for a pair both BODY texts and their word-level differences). **Local only** — it carries publisher text; regenerate with `scripts/study_phase3_repair.py draw` (its digest must match the manifest) | to answer |
| `KEY_machine_predictions_open_only_after_the_verdicts.json` | the machine's answer to every question, its evidence, rule versions and feature values; which cases are random and which targeted | **only after every answer is entered** |

## How to answer

Read a case in the sheet, enter the answer in the form (`allowed` lists the values; several values comma-separated where the
question allows it; `unsure` is an answer). The case ids are in a neutral order: neither the id nor the position says whether a
case is random or targeted, or what the machine found. Then:

```
python scripts/study_phase3_repair.py merge --out-dir docs/intake/quality/phase3_blind_control_2026-11-15 \
    --verdicts <filled form> --out <result.json>
```

`merge` refuses a key that is not the frozen one and reports agreement per question, **the random component (24 cases) and the
targeted component (46 cases) apart**, with every disagreement listed.

## What it can and cannot say

- The random component is a systematic sample with equal inclusion probability (24 / 4,626): it speaks to the population, but
  coarsely — 24 agreements of 24 give a 95 % lower bound of about 0.86.
- The targeted strata look for errors where they are likely; their agreement is not a population precision.
- The rules were repaired on aggregate measurements of the same 4,759 pages; the control excludes every page opened one by one
  during the repair and the 109 pages of the earlier review, but it is not fresh data.
- The BODY questions judge the extracted text shown; every other question is asked without the machine's answer.
- The earlier [review sample](../phase3_review_2026-11-15.md) stays a collection of known errors and regression cases, not gold.
