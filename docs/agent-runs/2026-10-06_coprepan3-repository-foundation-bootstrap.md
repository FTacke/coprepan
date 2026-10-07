# COPREPAN 3.0 — Repository Foundation Bootstrap

```text
run_started_at:      2026-10-06T16:24:05+02:00   (first clock reading of the run, after the first reads)
run_ended_at:        2026-10-06T16:41:40+02:00   (last clock reading, at the final checks)
timezone:            Europe/Berlin
wall_clock_seconds:  1055                         (between the two readings; the run is slightly longer)
model:               Claude Opus 5.5
```

**Status: PASS** — the repository has a coherent foundation of governance, architecture and
documentation on which COPREPAN 3.0 can be built. This status does **not** claim that acquisition,
preservation, extraction, NLP or any production path is implemented or validated: none exists.

**Kind of run:** implementation of repository governance and documentation, plus a minimal
machine-checked contract skeleton. No diagnosis of corpus data, no scientific validation, no
production activation.

`EXTERNAL_API_USAGE = NONE`. No network access: no crawl, no feed or sitemap retrieval, no external
API, no model inference.

---

## 1. Objective

Turn an empty directory into a self-describing COPREPAN 3.0 workspace that a later agent can use
safely: agent instructions at least as mature as those of `corapan_playground`, a clear document
hierarchy, the audit's results consolidated into normative documents, naming and terminology as
foundation, hygiene files ready for a later `git init`, and exactly one defined next run.

Operator brief: "COPREPAN 3.0 – Repository Foundation Bootstrap" (2026-10-06), given in the
session.

## 2. Repository states

| Repository | HEAD | Working tree at start | At end |
|---|---|---|---|
| `coprepan_playground` (this repository) | not a git repository | empty directory | the files of §4; **still not a git repository** |
| `corapan_playground` | `be8b26256` | clean | same HEAD; nothing written by this run. At the end three untracked files of a parallel session were present (`data/human_review/profi_model_speaker_groups_v3/gold_v1_source_answers.txt`, `…/gold_v1_source_rationales.json`, `scripts/hpc/slurm/profi_model_speaker_role_calibration_v1.sbatch`); they are unrelated PROFI work and were left alone. (The audit recorded HEAD `60e70932c`; the difference is other sessions' commits.) |
| `coprepan` (legacy) | `3e6bdd3` | clean | identical; nothing written |
| `corapan_coprepan_studies` | `679e14c` | pre-existing foreign changes: `M config/label_vocabulary.yml`; untracked `docs/agent-runs/2026-07-22_alfal_ppc_country_register_overviews.md`, `docs/agent-runs/2026-09-01_sidg_pilot_implementation.md`, `studies/past_tense_study_sidg/` | identical status; nothing written |

## 3. References examined

**`corapan_playground` (read-only).** Read in full: `AGENTS.md`, `CLAUDE.md`, `.gitignore`,
`.gitattributes`, `pyproject.toml`, and the architecture audit
(`docs/agent-runs/2026-10-06_coprepan3-architecture-and-migration-audit.md`, all 1,353 lines).
Extracted by two read-only reading passes, with file-cited findings: storage targets and
preservation, storage and retention policy, pipeline evolution / backfill policy (its D67), corpus
supply index, corpus registry, the radio registry's `id_convention` and entry shape, the naming
decisions (S0/D9, D37, D38, D56), runtime-workspace decisions (D85, D87), the local-time contract,
the acquisition policy (D8); the decisions directory and its numbering history, the three
methodology registries, the architecture index, the production-stack registry and its checker, the
transformation principles and evaluation checklist, the test-suite mechanism and guards, human
review, the failed-run evidence policy, `docs/plans/`, recent run reports, the README, the hook
configuration, and the NLP index with pins, token schema and chain versions.

**`coprepan` (read-only).** Top-level layout, `config/`, package layout,
`src/coprepan/utils/slugify_ascii.py`. Its test suite was **not** run and its databases were
**not** opened (both would write). All legacy figures in the new documents are the audit's
measurements of 2026-10-06, cited as such and not re-measured.

**`corapan_coprepan_studies` (read-only).** Top-level layout, `CLAUDE.md`,
`config/corpus_paths.yml` (the absolute corpus paths the audit reports).

Two findings of the reading passes corrected the audit's wording and were carried into the new
documents:

- The audit names a shared field `production_mode` with "the D37 vocabulary". CO.RA.PAN 3.0's D37
  defines **`speech_mode`** (`unscripted`, `scripted`, `prerecorded`, `unknown`) with a separate
  `speech_mode_applicability`; there is no `production_mode` there. The naming document therefore
  treats `production_mode` as a working name of the future shared field (open item O-6).
- The audit attributes "lower-case values, upper-case status tokens" to D38. D38 is a scoping
  rule and states no such split; the split is CO.RA.PAN's practice. It is adopted here as an
  explicit rule of CPD-0002.

Also noted: the CO.RA.PAN token schema has three fields the audit's list omits (`is_punct`,
`source_token_index`, `production_event_types`); the NLP index records which are shared and which
are spoken-only.

## 4. Structure and files created

Nothing was moved, deleted or overwritten: the directory was empty.

```text
AGENTS.md                         agent and developer rules (authoritative)
CLAUDE.md                         pointer to AGENTS.md plus the most-broken rules
README.md                         human entry point
.gitignore  .gitattributes  .editorconfig  .env.example
pyproject.toml
config/storage_targets.yml        logical storage roles, ${ENV} references only
docs/
  STATUS.md                       what exists; machine-readable assertions
  architecture/INDEX.md           authority index
  architecture/TARGET_ARCHITECTURE.md
  architecture/TERMINOLOGY_AND_NAMING.md
  decisions/README.md             registry, CPD namespace, rules, template
  decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md
  decisions/CPD-0002_terminology-and-naming-model.md
  plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md
  methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md
  storage/INDEX.md
  corpus_supply/INDEX.md
  nlp/INDEX.md
  legacy/INDEX.md
  agent-runs/README.md            run-report convention
  agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md   (this file)
src/coprepan/__init__.py
src/coprepan/naming.py            lexical naming rules (CPD-0002)
src/coprepan/stages.py            stage list, status vocabulary, admissibility rule
tests/conftest.py                 suites; no-network and no-storage-root guards
tests/suites/foundation_contract.txt
tests/suites/release_gate.txt     deliberately empty
tests/fixtures/README.md
tests/test_naming.py
tests/test_repository_contract.py
tests/test_test_guards.py
```

No `scripts/` directory and no empty placeholder directories were created; a directory appears
with its first real file.

## 5. Important decisions of this run

1. **One instruction file.** `AGENTS.md` is the only set of rules; `CLAUDE.md` is a short pointer,
   as in `corapan_playground`. No further instruction files.
2. **`docs/STATUS.md` as the single statement of what exists**, with three separate axes
   (implementation / validation / activation) and a machine-readable block checked by the tests.
   It is the analogue of CO.RA.PAN's production-stack registry and self-check, sized for a
   repository with no stack.
3. **Two decision records, not more.** CPD-0001 bundles strategy C and the foundation principles
   the operator's brief and the audit had already settled; CPD-0002 fixes the naming model.
   Everything else stays a target, a plan or an open item. Both records state that their wording
   awaits the operator's review.
4. **Decision namespace `CPD-<nnnn>`**, one normalised status vocabulary, number allocated in the
   registry table first. CO.RA.PAN's sequence has collided across parallel sessions and uses
   several status spellings; both are avoided from the start.
5. **Human-facing style:** *CO.PRE.PAN* names the corpus, *COPREPAN 3.0* the pipeline generation
   and engineering project. Machine values are `coprepan` / `v3`, never the capitals. Publication
   branding is left to the operator (O-7).
6. **Target id forms are documented; their byte-level serialisation is not frozen.** Lexical rules
   that are certain (`country_id`, `outlet_id`, `release_id`, schema ids, provenance classes) are in
   code and tested; hash inputs and truncations of fetch/document/version/token ids are left to
   the Phase-1 identity run under a new CPD.
7. **Runtime separated from the checkout from day one; an unset storage root is a refusal.**
   CO.RA.PAN reached this late (D85/D87) and still carries an in-checkout fallback for unset roots.
8. **All text LF, set once in `.gitattributes`**, with fixtures byte-verbatim. CO.RA.PAN pins
   dozens of hashed paths individually because `autocrlf` broke freezes.
9. **A real network guard in the tests.** CO.RA.PAN has targeted transport brakes but no generic
   socket block; for a crawler repository the generic block is the right default.
10. **Python package `coprepan`, version `0.1.0`** — named for the corpus, not the generation; the
    package version is deliberately not "3.0". The legacy package has the same name and must never
    share an environment with it (legacy index §6).
11. **Preservation container:** sealed WARC packs kept as the target. Checked against the
    CO.RA.PAN storage contract: its promotion unit is a file with a stable identity and a manifest
    and is container-agnostic, so no technical contradiction was found. No WARC code was written.

## 6. CO.RA.PAN principles adopted (adapted to a press corpus)

| Principle | Where |
|---|---|
| Authoritative-source index; repository state before chat memory; run report ≠ specification | `AGENTS.md` §1, architecture index |
| Reference repositories read-only; foreign worktree changes untouched | `AGENTS.md` §2–§3 |
| Frozen evidence immutable; negative and historical results kept; no silent deletion | `AGENTS.md` §3, methodology §5 |
| Hashes respected; "a digest must cover what it claims to identify" | `AGENTS.md` §3, §10 |
| No heredocs on this Windows setup | `AGENTS.md` §5 |
| Working-tree classification; no blanket ignores; explicit pathspecs; runtime is not evidence | `AGENTS.md` §4 |
| Storage roles; fail-closed roots; no workstation path in domain logic | `AGENTS.md` §6, storage index §5 |
| Atomic, idempotent, conflict-refusing promotion; outage spool; no delete function; tombstones | storage index §6–§7 |
| Storage classes, retention without age, backup verification states | storage index §7–§8 |
| Forward-only versioning; backfill is a decision; bridge sample | `AGENTS.md` §11, methodology §11 |
| Diagnosis ≠ implementation ≠ validation ≠ activation; gates; benchmarking ≠ production | `AGENTS.md` §8, methodology §1, master plan §10 |
| Transformation principles; no generic hard floors; evaluation-plan checklist; dev/fresh separation | methodology §2–§6 |
| Never invent a number; label every quantity; `NOT_YET_MEASURABLE` | `AGENTS.md` §9, methodology §8 |
| Failed-run evidence policy | methodology §8, `AGENTS.md` §8 |
| Human decisions append-only on stable ids with invalidation | methodology §10 |
| Corpus cohort vs processing cohort; date with basis; provenance never a filter; preserve first, balance later; targets are not quotas | corpus-supply index |
| Registry as source of truth; ids never derived from display names; alias tables; `same_outlet_basis` | naming §5, corpus-supply index §4 |
| S0/D9 vocabulary rules; legacy values immutable; mapping status | naming §0, §6 |
| Local-time contract (IANA zone, fail closed) | corpus-supply index §3 |
| Shared NLP pins, token schema, verbal-complex layer outside `morph` | NLP index |
| "LLM or not" decision pattern; no external model API in production | NLP index §7 |
| Stack registry with self-check; exact pins | `docs/STATUS.md`, `AGENTS.md` §14 |
| Test suites with single membership; tests never write tracked paths | `tests/`, `AGENTS.md` §15 |
| Run reports with timezone-aware timing and `EXTERNAL_API_USAGE` | `docs/agent-runs/README.md` |
| Component indexes with a maintenance contract | architecture index §0, `AGENTS.md` §16 |

## 7. Deliberately not adopted

| Not adopted | Reason |
|---|---|
| ASR, diarization, speaker identity / sex / linking, speech mode, professional status, commercial mask, canonical audio timeline | audio and speech; no press counterpart |
| Orality projection, production-event detection, numeric join, punctuation-source policy, forced sentence terminals | artefacts of transcribed speech; press has authorial punctuation |
| KISSKI / MaRC3a access rules, Run Supervisor, Slurm contracts, deployment preflight, dual-backend adapter contract, HPC job sizing | the core needs no HPC; acquisition is I/O-bound and NLP runs on CPU |
| Provider-equivalence and target-provider-replay rules | no model provider exists; the principle is reduced to "no external model API in a production path" |
| API usage ledger, tariff files, cost model | no metered call exists; `AGENTS.md` §14 makes the accounting boundary a precondition of the first one |
| Experiment and human-review registries as files | nothing to register yet; the rules that will govern them are in the methodology document |
| Audio storage classes, audio-window and speaker-profile deletion gates, FLAC cache | audio |
| The heredoc-blocking hook (`.claude/settings.json` + hook script) | the written rule is adopted; installing a command-blocking hook into the operator's agent harness was not in the brief. Worth porting if the rule is broken here — an operator choice. |
| The "unset workspace root = historical in-checkout location" fallback | no history to stay compatible with |
| Lock-file-free dependency policy as a rule | recorded as an open point of the NLP index; pins must stay identical with CO.RA.PAN either way |
| CO.RA.PAN's `robots.txt` advisory policy | cited as the sibling's position; the press policy is an open institutional decision (O-1) and was not guessed |
| Copying any `corapan_playground` code | principles were transferred; the code relationship is an open item (O-8) |

## 8. Checks run

| Check | Result |
|---|---|
| `python -m pytest` (Python 3.12.10, pytest 9.1.1) | see §8.1 |
| `.gitignore` verified with `git check-ignore --no-index` in a throwaway repository **inside the session scratchpad** (38 paths that must be ignored, 28 that must stay trackable) | all as intended |
| Reference repositories not written to (`git rev-parse`, `git status --short` at start and end) | HEADs unchanged; `coprepan` clean; studies status identical; `corapan_playground` gained three untracked files of a parallel session (§2) |
| No `.git` in `coprepan_playground` | confirmed |

The throwaway repository for the ignore check was created and removed in the scratchpad, not in
this repository.

### 8.1 Test result

Recorded after the final run: see the last line of this section.

First run: 67 passed, 3 failed. The three failures and what was done:

- `is_outlet_id("el_pais")` is true — the legacy slug `el_pais` is lexically a well-formed
  `outlet_id` (`el` + `pais`). This is a real property of the pattern CO.RA.PAN and COPREPAN share,
  not a bug to hide: the form check cannot replace the registry. The wrong test expectations were
  corrected, a test now documents the limitation, and the naming document states it (§5.2).
- One further failure was the same expectation in `outlet_country`.
- The link check failed on this report, which did not exist yet.

Final run: recorded in §12.

## 9. Self-review against the brief's quality questions

| # | Question | Finding |
|---|---|---|
| 1 | Can a new agent understand what COPREPAN 3.0 is to become from this repository alone? | Yes: README → `AGENTS.md` → `STATUS.md` → architecture index → target documents. The audit is cited as evidence but is not needed to follow the plan. |
| 2 | Is it clear what is authoritative and what is historical? | Architecture index §1–§3 vs §5; every document has a status line. |
| 3 | Are the audit's results transferred into normative documents? | Yes, by topic; the audit itself is listed as historical evidence. |
| 4 | Are CO.RA.PAN principles adapted rather than copied? | §6–§7 above. The authenticity clause became "no silent normalisation of the published text"; the date-basis ranking, storage classes and roles were re-derived for press. |
| 5 | Is naming consistent? | One document, one decision, lexical rules in code. |
| 6 | Are generation, release and schema version separated? | Naming §2; tests refuse `coprepan3-…` ids. |
| 7 | Are legacy and native V3 separated? | Provenance classes; legacy index; `AGENTS.md` §11. |
| 8 | Any unnecessary radio/audio ballast? | None found; §7 lists what was left out. |
| 9 | Is the cross-corpus link visible? | Master plan §9, naming §4, NLP index. |
| 10 | Is it clear that no production pipeline exists? | `STATUS.md`, README banner, status line on every target document, a test that fails if a stage is marked active without implementation and validation. |
| 11 | Is `.gitignore` safe for a later `git init`? | Verified as in §8. |
| 12 | No absolute production storage paths in future domain logic? | Enforced by a test over `src/`, `config/`, `scripts/`, `tests/`. Absolute paths of the reference repositories appear only in `AGENTS.md`, `CLAUDE.md` and this report. |
| 13 | Are sensitive or large data excluded from the future git? | Secrets, local config, databases, WARC, columnar output, models, archives, logs: ignored and verified. |
| 14 | Redundant or contradictory authoritative documents? | Each topic has one home; the master plan summarises and links. Known deliberate overlap: `AGENTS.md` restates the binding rules in imperative form and links to the document that explains each. |

Limits of this self-review: it is the author's own reading. No second reader checked the documents
against each other, and the operator's review is the real check.

## 10. Open questions

Recorded with owner and what each blocks in the master plan §13 (O-1 … O-10). None was guessed;
none blocks the next run. The institutional ones: acquisition / robots / opt-out policy and raw
retention (O-1), crawler identity and contact (O-2), preservation target (O-3), storage capacity
(O-4), population of admitted press types and the country list shared with CO.RA.PAN (O-5).

Points an operator may want to change at review:

- the wording and bundling of CPD-0001 and CPD-0002;
- the human-facing style rule (O-7);
- whether to port the heredoc hook;
- whether the legacy freeze manifest should precede Foundation Core I (O-10) — the audit
  recommended the freeze first; this run recommends the core first because the freeze cannot be
  completed without a preservation target, while its manifest half can run any time.

## 11. Recommended next run

**Foundation Core I** (Phase 1), after operator review and `git init`. No network, no live storage
root. In order: (1) freeze id serialisation and the canonical URL key with property tests and a
CPD; (2) outlet registry schema and a read-only import of the legacy outlets and channels from a
copy of the legacy database, with the legacy-slug → `outlet_id` mapping as reviewable output;
(3) ledger and state-machine primitives; (4) fail-closed storage-root resolution and promotion
semantics, tested on temporary directories; (5) write-once layer store; (6) release-gate suite
scaffold. Cut line after (4). Detail: master plan §12.

## 12. Working tree at the end

Not a git repository, so there is no `git status`. Every file in the directory is one of the files
listed in §4. Python and pytest caches created by the test runs were removed.

Final test run: **72 passed**, 0 failed (`python -m pytest`). `python -m pytest --suite release_gate
tests` selects nothing (72 deselected, exit code 5), as intended for an empty gate.
