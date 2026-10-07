# COPREPAN 3.0 — Pre-canary completion, legacy freeze manifest and Phase-3 readiness

```text
run_started_at:      2026-10-07T22:54:35+02:00   (first clock reading)
run_ended_at:        2026-10-07T23:30:31+02:00   (last clock reading before this report was closed; the commits and the push followed)
timezone:            Europe/Berlin
wall_clock_seconds:  2156   (between the two readings above)
status:              PASS   — for the scope of §0
kind of run:         decision + implementation, with reproducibility and robustness checks, and
                     one read-only operation on real data (the legacy freeze manifest).
                     No scientific validation. No production activation.
EXTERNAL_API_USAGE = NONE   (no model API, no external service, no request to any outlet or other website)
NETWORK USE:         `git push` to `origin` only. HTTP requests of the tests went to a server on a
                     literal loopback address started by the test itself. Nothing was installed.
```

## 0. What `PASS` covers, and what it does not

**Covers:** every piece of technical work that could sensibly be done before the operator's
answers to O-11, O-1, O-2 and O-3 is built and tested offline; the legacy freeze manifest (O-10)
exists and is verified against the live legacy tree; the instruments Phase 3 needs exist before
its data does.

**Does not cover, and must not be read into it:** not one external request was made; no outlet is
registered; no policy value was decided; no preservation target was chosen; **no gold label was
created and no extractor was compared, measured or adopted**; nothing about any real outlet or any
real page is known; the legacy corpus has **no backup** as a result of this run — a manifest is
not a copy. No production gate of `docs/STATUS.md` §5 is passed; O-10 is a go-ahead and a
manifest.

## 1. Brief and state at the start

Operator brief: "Pre-Canary Completion, Legacy Freeze & Phase-3 Readiness", with the explicit
go-ahead for O-10 and the instruction that after this run only the known human and operator gates
should stand between the repository and the first real canary.

| | State at the start (measured) |
|---|---|
| this repository | `main` at `9e0a1c0539ffac46f565f6547b5a715cdb20c701`, equal to `origin/main`; working tree clean; 597 tests passing |
| legacy repository (`legacy\\coprepan`, read-only) | `3e6bdd3350913d55c07efe500036bf752de65cc2`, `git status` clean |
| other reference repositories | not touched |

Present from the operator during the run, untracked: `docs/plans/COPREPAN3_PHASE3_CROSS_CORPUS_ANALYSIS_CONTRACT_RUN.md`
— the brief of the **next** run. It was committed unchanged with this run and not acted on.

## 2. O-10 — legacy freeze manifest

Tool: `src/coprepan/legacy_freeze.py` (`legacy-freeze/1`). It opens files for reading and nothing
else; the legacy git commands were run with `--no-optional-locks` so that not even git's index was
refreshed.

| | Value (measured) |
|---|---|
| freeze id | `coprepan-legacy-2026-06` |
| files / bytes, whole tree without `.git/` | 32,235 / 18,782,593,808 |
| files / bytes, release scope of legacy index §5 | 3,256 / 17,370,148,925 |
| largest area | `json_annotated/`: 926 files, 16,997,911,087 bytes |
| listing | `files.jsonl`, 32,235 rows, 7,352,041 bytes, SHA-256 `e7029dd7063fffd7f271375930f032dcb3bfb53cc3d98fcca87ecdf715c93cc4` |
| legacy commit / status | `3e6bdd3350913d55c07efe500036bf752de65cc2` / clean |
| build time | 143 s |
| state | `MANIFEST_ONLY` |

Verification, both after the build, both over all bytes of the tree:

1. `python -m coprepan.legacy_freeze verify` → `VERIFIED`: 32,235 unchanged, 0 added, 0 removed,
   0 changed; git head as recorded.
2. An independent script (standard library only, sharing no code with the module; kept in the
   session scratch directory, not in the repository) recomputed every hash and compared it with
   the listing → identical, 18,782,593,808 bytes.

Legacy tree after the run: same commit, `git status` clean (measured again before the commit).

Design choices, in CPD-0007 §1: bytes only (a timestamp-only change is not a difference — tested);
`.git/` bound by commit and status hash; symbolic links refused; the whole tree listed, including
the legacy `.venv` (28,557 files), so that nothing is outside the record, with the release scope
counted separately.

**Limits.** The SQLite files were hashed as files, not as checkpointed copies (no database was
opened). The manifest was built once; "reproducible" here means: the same tree gives the same
listing (tested on a synthetic tree) and the real tree re-verified twice — not that an independent
party rebuilt it. Phase 0 stays open: preserved copy, restore check and study-loader check need O-3.

## 3. Candidate qualification

`src/coprepan/candidate_filter.py`, CPD-0007 §2. Decisions `QUALIFIED` / `REJECTED` / `DEFERRED`,
appended per candidate and rule set, with reasons and evidence. Generic rules only reject what is
no page by its URL. `config/candidate_rules.json` holds no outlet rule: none can be written
without having seen an outlet. A rejected candidate and its discovery events stay.

## 4. Re-fetch semantics and fetch plan

`src/coprepan/schedule.py`, CPD-0007 §3. History (append-only), lifecycle (derived), versions
(identity) and schedule (a pure function) are separate. Eleven states; table in the acquisition
index §11. `config/schedule_policy.json` is `NOT_DECIDED` and refused by the loader: a fourth,
independent refusal of external acquisition, and a visible part of O-1.

Cases covered by tests: never fetched; success; unchanged (interval grows, capped); changed (interval
resets); revisit window closed; transport failure; 429 and 5xx with `Retry-After` (never asked
earlier than the server said); repeated failures → suspended → due again after the cooldown;
404 / 410 → rechecks → retired; other 4xx; redirect not followed; policy deny (due at once under
a new policy version); policy defer / suppression; robots deny; permanent redirect; the clock
boundary (`due_at == now` is due); determinism of the plan; the
log is never rewritten.

## 5. Conditional requests and redirects

`fetcher.py`, `acquisition.py`, `document_identity.py`, `core_pipeline.py`; CPD-0007 §4–§5.

- A 304 is a fetch with an empty body and `revalidates: {fetch_id, body_sha256}`; identity adds an
  observation to the existing version; no extraction, no new version, **no body invented**.
- Validators go out on the first hop only.
- Permanent redirect (301 / 308) to another URL key of the outlet: new candidate, attributed
  `FINISHED` row, old candidate `MOVED`. The fetch record gains `response.redirect_statuses`.

## 6. Robots sitemaps and crawl-delay; channel health

- `use_robots_sitemaps` (off by default) reads the sitemaps named by a robots file under the
  reserved source `<outlet>:ch:robots_sitemaps`. `Crawl-delay` is recorded in the gate's evidence
  and in the request log and **applied by nothing** (O-1).
- `src/coprepan/channel_health.py`: six states derived from the discovery tables with their
  evidence; nothing stored; nothing switched. One defect of the previous run surfaced and was
  fixed on the way: two refusals of the same channel document in two runs had the same synthetic
  input id and were collapsed into one observation; the id now includes the run.

## 7. Admission labels and extractor lifecycle

`src/coprepan/admission.py` (new component index `docs/admission/INDEX.md`), CPD-0007 §8–§9.
Technical status with a closed reason list, each reason `blocks` or `informs` with evidence;
append-only; removes nothing. It is deliberately silent on article / not article, genre, register,
section, opinion, access class and language. `baseline_html/0.1.0` is `EXPERIMENTAL`; labels made
with it say `extractor_not_active`.

## 8. Phase-3 instruments

| Deliverable | Where | State |
|---|---|---|
| evaluation harness: sample manifest, arms (extractor or precomputed), double run per arm, disagreements, scores against a reference, summary | `src/coprepan/extraction_eval.py` | built; exercised on synthetic pages |
| metrics: text retention, boilerplate inclusion, title, body boundary, metadata, catastrophic | same | built as **diagnostics**; the catastrophic threshold has no default |
| review package generator: blinded candidates, empty decision form, key apart | same | built |
| gold-sample design | `docs/extraction/GOLD_SAMPLE_DESIGN.md` | methodology only; every size a parameter |
| extractor candidates | `docs/extraction/EXTRACTOR_CANDIDATES.md` | a list from general knowledge, **unverified**; nothing installed or run |

No gold exists. The numbers the harness printed in its tests come from invented pages and an
invented "reference" inside the test and are not reported here: they would read like a result.

The legacy extractor cannot be an arm on legacy pages (no raw HTML was kept, archaeology F-1); it
can enter as a precomputed arm on pages preserved by 3.0, which needs an operator-ordered run of
legacy code in its own environment.

## 9. Canary planner and preflight

`src/coprepan/canary.py`, CPD-0007 §11. On the repository as committed (measured):

- `plan --outlets 5`: **0 selected**, `sufficient: false`; all 82 outlets ineligible (not
  registered; URL rules still the import's placeholder; no time zone; some without a channel).
- `preflight`: `NOT_READY`; failed checks by gate: O-11 1, O-1 2, O-2 1, O-3 2, engineering 1 (no
  test result supplied), canary approval 1 (no approved baseline supplied).

The planner optimises registry metadata for diversity and says so; it cannot judge whether an
outlet is a good first target. The preflight starts nothing.

## 10. Failure injection

| Area | Injected | Outcome |
|---|---|---|
| schedule | clock at the boundary; repeated and permanent failures; new content after success; a rewritten policy version | due exactly at the boundary; suspended, then due after the cooldown; interval resets; denied candidate due at once |
| conditional GET | stale ETag; a 304 to an unconditional request; revalidated fetch unknown; changed body under an unchanged ETag | new body and new version; counted as failure and labelled; nothing assigned; new version (hash decides) |
| qualification | allow and reject rule on one URL; outlet without rules; changed rule version | `DEFERRED` with both reasons; generic rules only; a second decision beside the first |
| channel health | partial success; unreadable channel document; nothing new; disabled channel | `DEGRADED`; `DEGRADED` then `FAILING`; `STALE`; `DISABLED` |
| harness | arm without output; evaluation on another sample; body with another hash; arm with two answers | `NO_OUTPUT` recorded; refused; refused; `NonDeterministicArm` |
| legacy freeze (synthetic tree) | modified, removed, added file; timestamp-only change; tampered listing | `DIFFERS` with the path named; `VERIFIED`; refused |
| preflight | each precondition missing in turn; configuration drift after approval | `NOT_READY` naming the gate |

## 11. Files

New code: `src/coprepan/legacy_freeze.py` (214 lines), `candidate_filter.py` (145), `schedule.py`
(279), `channel_health.py` (117), `admission.py` (197), `extraction_eval.py` (459), `canary.py`
(261). Changed: `acquisition.py`, `fetcher.py`, `policy.py`, `discovery.py`, `registry.py`,
`http_acquisition.py`, `extraction.py`, `document_identity.py`, `core_pipeline.py`, `freeze.py`.

New configuration: `config/schedule_policy.json` (`NOT_DECIDED`), `config/candidate_rules.json`
(no outlet rule).

New data: `docs/legacy/freeze/coprepan-legacy-2026-06/manifest.json`, `files.jsonl`.

New tests: `tests/test_legacy_freeze.py` (10), `test_schedule.py` (27), `test_admission_eval.py`
(22), `test_refetch_e2e.py` (14), `test_canary.py` (9). Changed: `test_offline_e2e.py`,
`test_core_pipeline.py`, `test_readiness.py`, `test_preservation.py`, `support_http.py`, the suite
manifest.

New documents: CPD-0007; `docs/admission/INDEX.md`; `docs/extraction/GOLD_SAMPLE_DESIGN.md`;
`docs/extraction/EXTRACTOR_CANDIDATES.md`; this report. Updated: `docs/STATUS.md`, the master
plan, the decision registry, the architecture index, the terminology, the acquisition,
extraction, legacy, corpus-supply, identity and storage indexes.

Nothing was moved, deleted or overwritten outside this repository. Inside it, no tracked file was
deleted. The legacy tree was read only.

## 12. Tests

`python -m pytest -p no:cacheprovider -q` (Python 3.12.10, pytest 9.1.1):

| | Result |
|---|---|
| at the start | 597 passed |
| at the end | **705 passed, 1 skipped** |
| the skip | `test_legacy_freeze.py`: creating a symbolic link is not permitted for this account on this machine; the refusal of symbolic links is therefore **not exercised here** |

Behaviour of existing tests that changed, and why: the offline canary now rejects its PDF
candidate at qualification instead of fetching it, and its permanently redirected URL produces a
second candidate (8 instead of 7 candidates; 6 instead of 7 item requests). The baseline manifest
has one more blocker (schedule policy).

Mistakes made and corrected during the run, kept on record: a bulk text replacement in
`tests/test_offline_e2e.py` damaged two multi-line statements (repaired by hand); a default
argument bound at definition made the label table ignore a new rule set (fixed, tested); an
expectation of mine about sort order in two new tests was wrong (the code was right); one shell
command used a heredoc against the repository rule — it failed before doing anything and was
replaced by a script file.

## 13. Gate assessment

| Gate | Before | After | Evidence |
|---|---|---|---|
| O-10 legacy freeze manifest | `OPEN` | **`PASS`** | §2 |
| O-1 acquisition policy | `OPEN` | `OPEN` — now explicitly including the schedule policy and whether `Crawl-delay` binds | §4, §6 |
| O-2 crawler identity | `READY_FOR_HUMAN_REVIEW` | unchanged | — |
| O-3 preservation target | `OPEN` | unchanged | — |
| O-4 capacity | `OPEN` | unchanged; not a precondition of the canary | §9 |
| O-11 registry review | `READY_FOR_HUMAN_REVIEW` | unchanged; the planner shows what "complete enough" means per outlet | §9 |
| O-12 baseline freeze | `OPEN` (`PRE_FREEZE`) | unchanged; six blockers | — |
| Phase 0 | open | **still open** (copy and restore need O-3) | §2 |
| Phase-1 core gate, Phase-2 canary gate | `OPEN` | unchanged | — |

Stage 7 (admission labels): `NOT_STARTED` → `PARTIAL`. No other stage state changed. Nothing is
validated or activated.

## 14. Validation classification

| Kind | What this run supports |
|---|---|
| reproducibility | same history, policy and instant → same plan; same sample and arms → same evaluation; same candidate and rules → same decision; the legacy tree re-read twice equals its manifest |
| robustness | the failure injections of §10 |
| replicability | **nothing.** No second implementation, no second team, no second data set. The independent freeze check is a second *reading* of the same files, not a replication |
| generalisability | **nothing.** Synthetic documents on a loopback server say nothing about real outlets; the harness has no real page |

## 15. Known limitations and real risks

1. **The legacy corpus still has no backup.** The manifest can prove a loss; it cannot undo one.
   This is the most consequential open item and it waits on O-3 (and on the unanswered O-9).
2. Re-fetching has met only a scripted server. Real servers send weak validators, ignore
   conditional headers, answer 200 with a soft "not found", redirect permanently by mistake. The
   lifecycle is derived, so a wrong rule is corrected by a new planner version without touching
   history — but it will need correcting.
3. The generic candidate rules are by extension and path only. On real listings they will pass
   section fronts and tag pages; that is what outlet rules and, later, content-level labels are for.
4. A permanent redirect by a misconfigured server moves a candidate for good under this rule. The
   old URL and both log rows stay, so it is reversible by a planner version — not automatically.
5. The token-overlap metrics are insensitive to order and blind to editorial boundaries.
6. `TECHNICALLY_USABLE` will be read as "is an article" by someone. The label and its index say
   otherwise in every place I could put it.
7. The symbolic-link refusal of the freeze tool is untested on this machine.
8. Qualification, label and identity tables live in the runtime workspace; their durable home is
   open (storage §11).
9. The extractor-candidate list is from general knowledge and may be out of date.

## 16. Next step, and the question the brief asked

**Is there any technical work left that should sensibly be done before O-11 / O-1 / O-2 / O-3?**
No work of the acquisition path. What remains is either the operator's or needs real material:

- operator: registry review for the canary outlets (O-11) — including, per outlet, time zone, URL
  rules and web origins, without which the planner does not consider it; the acquisition policy
  **with the schedule policy** (O-1); the four identity values (O-2); the preservation target (O-3);
- then engineering, in this order: Phase-1 gate on the chosen target → legacy preserved copy and
  restore check → `canary plan` reviewed → baseline manifest approved → `canary preflight` `READY`
  → the canary → O-4 measurement → Phase 3 on what the canary preserved.

Work that is independent of those answers and was **not** in this run's scope: the cross-corpus
analysis contract (master plan Phase 7; "can start in parallel with Phase 3"). The operator has
already filed its brief (`docs/plans/COPREPAN3_PHASE3_CROSS_CORPUS_ANALYSIS_CONTRACT_RUN.md`); it
is the next run and is reported separately.

Two smaller things an operator may want before the canary and that need a decision rather than
code: whether process-kill crash tests are wanted before or on the real target; whether the
legacy extractor is to be run on canary pages as a comparison arm.
