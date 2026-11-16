# The independent BODY/CORE validation (CPD-0044) — operator guide

| Document | What it is |
|---|---|
| [Plan v1](BODY_CORE_VALIDATION_PLAN_2026-11-16.md) | the pre-registration: population, design, sample size, measures, independence (`PROPOSED`) |
| [Codebook `gold-body-codebook/1`](GOLD_CODEBOOK_1.md) | what to mark and how (`PROPOSED`) |
| [Acquisition preparation](holdout_acquisition_PREPARATION_2026-11-16.md) | the holdout to acquire and the commission to issue (`BLOCKED`) |
| [Development population](development_population_2026-11-16.json) | every page development has read (ids and address digests) — excluded from any holdout |
| [Effort](gold_effort_2026-11-16.json) | the structure a reviewer works through, measured on 200 development pages |

**Local packages** (publisher text; never in the repository), in the runtime workspace
`C:\dev\panhispanic_media_corpora\coprepan_workspace\review\`:

| Package | Kind | Use |
|---|---|---|
| `practice_2026-11-16` (`d206afc1789208b0a32def29`, 5 cases) | `PRACTICE` | to learn the tool; never gold |
| `body_final_review_2026-11-16_a24462c3c84a7691b2ab12d7` (120 cases) | v1 package, `DEVELOPMENT_DIAGNOSTIC` | optional error diagnosis with the old reviewer (`scripts/body_review.py`); not independent |
| the holdout package | `HOLDOUT` | built after the acquisition |

## 1. Try the tool (practice, 10–20 minutes)

```
python scripts/gold_review.py serve --package "C:\dev\panhispanic_media_corpora\coprepan_workspace\review\practice_2026-11-16"
```

The browser opens `http://127.0.0.1:8766/` (loopback only; no network). Press `?` for the codebook and the keys. A practice package
is never frozen and never scored; play freely.

## 2. Annotate a case

1. **G** jumps to the main heading. Click the first article paragraph, **Shift+click** the last one, press **B** (article text).
2. Inside that range, overwrite what is not article text: click (or Shift+click a run) and press **F** (foreign), **C** (caption)
   or **E** (embed). Mark the headline **T** and a standfirst **V**.
3. A segment that mixes article text and something else: select the deviating part with the mouse, press its key (a span). To
   remove a span, select inside it and press **X**.
4. **N** walks every longer segment you have not labelled — no article text is overlooked. Folded navigation and footer lines open
   on a double click.
5. To locate something you see in the original: select it on the left and press **S**.
6. **Q** goes to the case questions: the source, text missing from the view, **CORE** (yes / no / unsure; a reason or note for no and
   unsure), page types, a comment. Tick "Alle nicht markierten Segmente sind kein Artikeltext" and close with **Ctrl+Enter**.

Every answer is saved at once (`judgments/events.jsonl` in the package). Stop with Ctrl+C in the terminal whenever you like; the
next start opens where you were. A closed case is locked; "Wieder öffnen" records the correction.

## 3. Along the way

```
python scripts/gold_review.py status   --package <package>
python scripts/gold_review.py snapshot --package <package> --out docs/intake/validation/<package_id>/events_snapshot.jsonl
```

A snapshot copies the event log (labels, offsets and digests — no publisher text) into the repository; committing it keeps a
backup of the work in progress. It holds no prediction and leaks nothing.

## 4. Freeze the gold, then — and only then — the machine

```
python scripts/gold_review.py freeze  --package <package> --out docs/intake/validation/<package_id>/gold.json --by "<name>" [--replicate 1]
git add -- docs/intake/validation/<package_id>/gold.json ; git commit -F <message file> ; git push
python scripts/gold_review.py predict --package <package> --gold docs/intake/validation/<package_id>/gold.json --runtime <workspace>
python scripts/gold_review.py score   --package <package> --gold <gold> --predictions <package>\predictions\predictions_<…>.json --out <result.json>
```

`freeze` accepts no open case of its scope (all, or replicates 1..N); afterwards the package takes no answer. `predict` refuses
unless the gold is the frozen one, tracked and unchanged against `HEAD`. Nothing here decides acceptance; the result is weighed
by the operator (plan §7).
