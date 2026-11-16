# The final BODY/CORE validation package of 2026-11-16 (CPD-0043) — prepared, frozen, not reviewed

**Status: prepared and frozen; not reviewed.** No judgment exists. This directory holds only the package manifest (ids, digests,
the sampling plan, counts -- no publisher text and no address). The package itself, with the stored pages, lives outside the
repository on the operator's workstation.

| | |
|---|---|
| Package id | `a24462c3c84a7691b2ab12d7` |
| Manifest | [`manifest.json`](manifest.json) (SHA-256 `0fd3ac457ebe599bffb30d9123bb1a3efd9aa505390232353fb8749f8737c4fd`), the copy of the package's own |
| Built by | `python scripts/body_review.py prepare --page-cache <cache> --out-dir <package> --random 80 --per-stratum 5 --seed 20261116` |
| Candidates under test | `article_html/0.4.2` with `body-templates/1`, `content-features/2`, `content-quality/4`, `body-quality/2` |
| Local package (2026-11-16) | `%LOCALAPPDATA%\Temp\coprepan-body-final-review\package` (about 12 MB; publisher text, local only) |

## Sampling plan

- **Random component, 80 cases**: a stratified simple random sample of the 4,759 stored pages by country (20 countries,
  proportional allocation by largest remainder); every case carries its exact inclusion probability. Rates and Wilson intervals
  are computed for this component only, at the case level.
- **Targeted component, 40 cases**: 5 at random from each of eight error-class strata, among the pages the random draw did not
  take (a page counts in the first stratum it meets): BODY changed by 0.4.2 (53 pages), CORE changed since CPD-0041 (28), live or
  preview signals (81), 120–180 words (252), list or table structure (124), BODY under 80 % of the stated text (9), `residual_suspect`
  (261), rejected for another reason than length (82). These show whether known error classes are handled; they give **counts,
  never a population rate**.
- The case numbers are shuffled; nothing in a case says why it was drawn. The reasons are in the sealed key.

**What the package measures.** Article text removed (false deletion), foreign material kept (residue), article text missing
(completeness answer and marked text not in the BODY), CORE wrong (false accept, false reject), and doubt -- kept apart.

**Size.** 2,866 blocks to judge: random 1,908 (mean 23.9 per case, median 19, at most 111), targeted 958. *Measured* from the
package. The time per case is **not measured**; as a *scenario assumption* of 2–5 minutes per case (most blocks confirmed with one
key, foreign blocks marked one by one) the package takes 4–10 hours, in as many sittings as wanted. A smaller validation (the 80
random cases alone, 1,908 blocks) is possible by closing only those cases: the score separates the components.

## How to run the review

1. In the repository (any checkout of a commit with CPD-0043):
   `python scripts/body_review.py serve --package "%LOCALAPPDATA%\Temp\coprepan-body-final-review\package"`
   The browser opens `http://127.0.0.1:8765/`. The server binds the loopback address only and needs no network.
2. Per case: left, the stored page made inert (no script, image, link or request) or its full text; right, the title surface and
   the candidate blocks in page order **without** the machine's decision.
   - Each block: `1` article text, `2` foreign, `3` unsure (`J`/`K` move; `A` sets every open block to article text).
   - Missing article text: mark it on the left, choose the part, press `M`.
   - Completeness, CORE (`Y`/`N`/`U`, with a short reason for no or unsure), page types (optional, several), comment.
   - `F` closes the case; only then the machine's decision is shown. A case changed after that is marked not blind.
3. Everything is saved as you go (`judgments/events.jsonl` in the package); stop with `Ctrl+C` and start again any time.
4. When done: `python scripts/body_review.py export --package <package> --out <judgments.json>`, then
   `python scripts/body_review.py score --package <package> --judgments <judgments.json> --out <result.json>`.
   The scoring reads the frozen key; it never rewrites a judgment.

Do not start the server with `--diagnostic` for the validation: that mode shows the machine labels at once, and its answers never
count as gold.

## Rebuilding

If the operator changes a candidate before the review (e.g. a decision on structured texts), the package no longer tests the
candidate in force: build a new one with the same command and a new seed or label. This package stays as it is.
