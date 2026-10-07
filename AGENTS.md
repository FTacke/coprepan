# Agent Instructions for `coprepan` (COPREPAN 3.0; working name until 2026-10-07: `coprepan_playground`)

These rules apply to the entire repository and to every agent and developer working in it.

**What this repository is.** The development repository of COPREPAN 3.0, the preservation-first
pipeline for the CO.PRE.PAN press corpus. **It is a foundation, not a pipeline:** as of the
bootstrap (2026-10-06) nothing discovers, fetches, preserves, extracts, annotates or releases.
[`docs/STATUS.md`](docs/STATUS.md) says what actually exists; read it before assuming anything is
built.

## 1. Required context and authority

Read in this order before doing work:

1. This file.
2. [`docs/STATUS.md`](docs/STATUS.md) — what is planned, implemented, validated, activated.
3. [`docs/architecture/INDEX.md`](docs/architecture/INDEX.md) — which document is authoritative
   for what. It is the only map; do not guess authority from a file's name or age.
4. The authoritative document for the area you touch, and the decisions it cites
   ([`docs/decisions/README.md`](docs/decisions/README.md)).
5. [`docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md`](docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md)
   for phase, gate and open-decision context.

Authority rules:

- **The current repository state outranks historical chat knowledge, memory and earlier run
  reports.** A run report (`docs/agent-runs/`) is a historical record of one execution, never a
  specification. An old result never becomes a de facto current configuration.
- Authority order: decisions (`CPD-*`) → normative documents listed in the architecture index →
  the master plan → everything else. `docs/STATUS.md` alone is authoritative for *what exists*.
- A statement marked open, proposed, target, working name, scenario assumption or example is **not
  an accepted specification**. Do not infer a final schema from an example.
- If code, data and documentation differ, inspect actual behaviour and data, document the
  discrepancy, and do not silently pick one. Do not resolve a conflict between two authoritative
  documents by choice: record it and raise it.
- Strategy C (CPD-0001) and the naming model (CPD-0002) are decided. Do not reopen them unless new
  hard evidence contradicts them; then bring the evidence, not a redesign.

## 2. Reference repositories (read-only)

On the operator's workstation, since the path migration of 2026-10-07 (this repository:
`C:\dev\panhispanic_media_corpora\coprepan`):

| Path | Role |
|---|---|
| `C:\dev\panhispanic_media_corpora\legacy\coprepan` | **Legacy COPREPAN**: legacy system and legacy corpus, archived unchanged (formerly `C:\dev\coprepan`). Behaviour and data reference. |
| `C:\dev\panhispanic_media_corpora\corapan` | **CO.RA.PAN 3.0** (repository name `corapan_playground`, formerly `C:\dev\corapan_playground`): the technical and methodological reference; source of the shared NLP instrument contract. |
| `C:\dev\panhispanic_media_corpora\legacy\corapan_coprepan_studies` | Cross-corpus studies, archived unchanged (formerly `C:\dev\corapan_coprepan_studies`): evidence of what interfaces real studies need. |
| `C:\dev\corapan` | CO.RA.PAN 1.0 (legacy radio system), referenced by the two above. Not moved. |

- **All four, and the corpus data they reference, are read-only.** Do not modify, delete, move,
  rename, normalise, migrate, re-annotate or overwrite anything there. The single exception is a
  later run whose operator brief explicitly authorises a named change in a named repository.
- **Never run the legacy test suite**: collecting it starts a real crawl and writes to the legacy
  production database. **Never open a legacy SQLite database in place**: copy it outside the legacy
  tree first. See [`docs/legacy/INDEX.md`](docs/legacy/INDEX.md) §2.
- Before reimplementing something the legacy system or CO.RA.PAN 3.0 already does, inspect the
  working implementation there first. Adapt the mechanism; do not copy radio-, audio-, ASR-,
  diarization-, speaker- or HPC-specific rules into a press pipeline.
- The legacy code is a behaviour reference, not a template. The studies' workarounds are
  requirements on the new contract, not a blueprint.
- These absolute paths belong in this file and in run reports only — never in tracked domain
  logic or configuration (§6).

## 3. Filesystem and data safety

- All writes stay inside this repository or, once they exist, the storage roots resolved from the
  environment. Resolve and check a path before writing.
- **Treat existing worktree changes as the operator's or another agent's work.** Do not revert,
  overwrite, reformat or "tidy" them without explicit instruction. Parallel sessions are normal.
- **Never delete a historical artefact silently** — a run report, a decision, an evaluation
  result, a negative result, an unknown file. Superseded text is marked superseded and kept.
- **Frozen evidence is immutable.** Gold sets, freeze inventories and manifests, completed reviewer
  files, frozen predictions, frozen supply snapshots and evaluation results are never edited to fit
  a later conclusion. A later qualification is added separately, dated, with a link to what
  motivates it. A `FAIL` may stay historically true.
- **Respect hashes.** A file pinned by a hash is not rewritten, re-encoded or line-ending-converted.
  If a hash does not verify, that is a finding to report, not something to repair by recomputing
  the hash.
- **No productive data in the repository.** No fetched pages, WARC packs, extracted corpora, NLP
  output, databases, model files or logs are committed. `.gitignore` is the second line of
  defence, not the first: the first is that such data is written to a storage root.
- Small, documented, non-production fixtures under `tests/fixtures/` are the only corpus-like
  material that may be versioned.

## 4. Git and working-tree hygiene

The bootstrap run created no git metadata; the operator initialises git. From then on:

- **Commit or push only when the operator asks.** Never rewrite history, force-push, or change
  remotes on your own initiative.
- **Commit with explicit pathspecs.** Never `git add -A` / `git add .`; never `git stash` or a
  worktree to fake a clean tree. The index is shared with parallel sessions.
- **Classify the tree at the end of every run.** Every changed or untracked entry is exactly one
  of: *committed*; *outside git by a documented `.gitignore` rule*; or *left in place for a reason
  stated in the run report*. "Untracked, will look later" is not a class.
- No temporary artefacts in the repository root or in versioned evidence directories. Scratch,
  probes and one-off scripts go to the session scratchpad or a `tmp_path`; a probe worth keeping is
  named, dated, documented and committed under `scripts/`.
- **Never hide results behind a blanket ignore** (`*.json`, `*.jsonl`, `artifacts/**`). A new
  `.gitignore` rule is minimal, anchored and commented with why the file is regenerable or not
  evidence.
- **Runtime is never the evidence, and git is not a job-state backend.** Operational state
  (ledgers in flight, frontier, job state, logs) lives in the runtime workspace outside the
  checkout. What is versioned is a compact, hash-bound evidence record of a finished run — never
  raw runtime trees, never `*.log`.
- Never delete scientific output, evidence or an unknown file to make a status look clean.

## 5. Shell tooling: no heredocs (hard rule)

This repository runs on Windows (PowerShell 5.1 / Git Bash, nested quoting). Heredocs and
here-strings mangle line breaks, backslashes, quotes and line endings here.

- **Never use a heredoc (`<<EOF`, `cat > file <<…`, `python - <<…`) or a PowerShell here-string
  (`@'…'@`, `@"…"@`)** — not for file creation, code rewrites, test patches, multi-line snippets or
  commit messages. There is no "short and harmless" exception.
- Instead: change files with the edit tool; create files with the write tool; for anything
  scripted, write a real script file (scratchpad or `scripts/`) and run it; write a commit message
  to a file and use `git commit -F <file>`.
- All text files in this repository are LF (`.gitattributes`, `.editorconfig`). When a script
  writes text, write LF explicitly.

## 6. Storage roots and paths

- **No absolute workstation or network path in tracked domain logic or configuration** — no drive
  letter, UNC path or home directory under `src/`, `config/`, `scripts/` or `tests/`. Tracked
  config holds logical roles and `${ENV}` references. A test enforces this.
- Storage roots are **resolved fail-closed from the environment** (`COPREPAN_*_ROOT`). Unset,
  unreachable or read-only is a refusal — never a default, never a fallback to local disk or into
  the checkout. An unreachable target is never reported as empty.
- One role per function: `REPOSITORY`, `RUNTIME`, `PRESERVATION`, `SPOOL`, `DISTRIBUTION`,
  `EXCHANGE`, `BACKUP`. Detail: [`docs/storage/INDEX.md`](docs/storage/INDEX.md).
- Prefer central configuration and shared path utilities over paths in individual scripts.

## 7. Network and acquisition safety

- **No live network access from a test, ever.** Tests replay recorded fixtures. `tests/conftest.py`
  blocks socket connections; do not bypass it.
- **No live fetch of any outlet** — no crawl, no feed or sitemap retrieval, no "quick check whether
  the site is up" — unless the operator brief of the run authorises acquisition **and** the gates
  for it are closed (`docs/STATUS.md` §5). Today they are open: no run may fetch.
- **Never bypass an access control**: no authentication circumvention, no paywall evasion, no
  header spoofing to impersonate another client, no CAPTCHA solving, no rate-limit evasion. A
  refusal is recorded as a refusal with its evidence.
- The acquisition policy (robots and opt-out handling, crawler identity and contact, retention of
  raw copies) is an **open institutional decision**. Do not guess it, and do not encode a guess as
  a default. A configured policy that is not enforced by tested code is a defect.
- No external API and no model inference unless the run's brief calls for it. A run that made no
  external call states `EXTERNAL_API_USAGE = NONE` in its report.

## 8. Diagnosis ≠ implementation ≠ validation ≠ activation

Four different acts ([methodology](docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md) §1).
Name which one a run performs, and never let a `PASS` of one stand in for another.

- **Respect gates.** A gate is passed by evidence recorded in a run report, never by argument, by
  elapsed time or because a later stage happens to work. **Never weaken a gate to make something
  pass**; changing a gate is a decision with its own record.
- **No production activation while a relevant gate is open.** An institutional gate binds like a
  technical one.
- Implementing a stage does not activate it. Benchmarking a model does not make it production.
  An evaluated alternative stays a candidate until a decision adopts it.
- A diagnostic run changes nothing it diagnoses. If a diagnosis finds a defect, it reports it;
  the fix is a separate, authorised step.
- **A failed run never authorises its own retry**, and produces no measurement of what it failed to
  do. Its artefacts are evidence, written once.

## 9. Interpretation discipline

- **Never guess** field meanings, label semantics, path mappings or category equivalences. Never
  guess an institutional answer.
- **Preserve observed legacy values.** Do not silently normalise or reinterpret them; a legacy →
  canonical mapping is a hypothesis until human-audited.
- **Never invent a number.** No accuracy, error rate, coverage, volume, cost, runtime or
  confidence interval unless measured or explicitly sourced. Label every quantity: *measured*
  (date, population), *sourced*, *estimated*, *scenario assumption* or *unknown*. An unmeasured
  axis is `NOT_YET_MEASURABLE`, never `0`.
- Figures quoted from the audit are the audit's measurements of 2026-10-06; cite them as such and
  do not present them as re-measured.
- Do not add theoretical or linguistic claims during technical work.
- Do not create parallel implementations of working infrastructure, and avoid broad refactors
  without concrete benefit to the task.

## 10. Preservation and provenance (engineering rules)

- **Preservation-first.** The primary raw object is the fetch with its exact response bytes.
  Extraction, normalisation and NLP are derived layers. **No derived layer may be the only copy of
  a source.** Extraction reads only objects that are `RAW_PRESERVED`.
- **Provenance is retained**: inputs by id and hash, component versions, parameters, timestamps
  with offset. For a released text the full chain must be answerable from stored records alone.
- **A digest must cover what it claims to identify, and an index must be proven to fit the stream
  it addresses.** Name a hash field for what it covers. When a derived input is fetched by index,
  check that source and index share a basis and fail closed when they do not.
- **Write-once layers.** An artefact is never overwritten in place; a different answer is a new
  artefact. Fingerprint (what was asked), artifact id (which answer) and execution provenance
  (when, where, by which run) are three different things.
- **A derived-text stage is traceable and replayable**: it records the upstream identity and hash,
  the component and version, the operations applied and the rendered result, and a deterministic
  replay path exists that does not redo the upstream stage.
- **Ledger before state**; illegal transitions raise; states are closed vocabularies.
- **Label, do not delete.** Admission is labelling with reasons. Exclusion is a decision of a
  release or selection view.
- **No delete function** in preservation code. Deletion of preserved material exists only as a
  gated, tombstoned, separately decided path. Nothing is deleted by age.
- Keep every stage modular, replaceable and separately evaluable; add a focused validation check
  with each new stage.

## 11. Forward-only evolution; no silent backfill

**Backfill is a decision, not a consequence.**

- A new version of a component applies to new work. An artefact produced correctly under its
  recorded version stays valid for that version.
- A newer model, a better rule set, a faster stage, a benchmark or a changed fingerprint never by
  itself makes old outputs invalid or eligible for reprocessing.
- Reprocessing needs an explicit, operator-approved change decision (a `CPD` record with the
  change-decision fields), runs on the smallest causal stage scope, and never touches raw
  preservation.
- Never point a run with a changed stage version at an output location holding outputs of another
  version: it must not be able to overwrite them.
- **Legacy is forward-only too**: no historical name, id, value or file is rewritten. The legacy
  corpus is not `native_v3` and is never silently promoted, re-annotated or pooled.

## 12. Naming

[`docs/architecture/TERMINOLOGY_AND_NAMING.md`](docs/architecture/TERMINOLOGY_AND_NAMING.md) is
binding. In particular: one term per level; `corpus_id` is `coprepan` and the generation is an
attribute, never part of an id; generation, release and schema version are three different things;
persistent ids never change, slugs and display names may; an id is assigned in a registry or
derived from content, never from a display name at run time; "raw" means source bytes only.
A new term, id kind or vocabulary value is added to that document in the same run that
introduces it.

## 13. Transformations, NLP and LLM

- [`docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md`](docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md)
  is binding for every automated transformation: evaluate against the realistic baseline; no
  generic hard floors; development and fresh data separated; the evaluation-plan checklist answered
  before a fresh validation.
- **Never silently normalise the published text.** Encoding may be normalised as a recorded
  operation; wording may not be changed. No lexical repair heuristics, no substring-based deletion
  of prose, no reconstructed metadata — unknown stays unknown.
- **One NLP instrument contract with CO.RA.PAN 3.0** ([`docs/nlp/INDEX.md`](docs/nlp/INDEX.md)).
  Do not change a pin unilaterally; do not write a project feature into `morph`; declare modality
  differences instead of standardising them away.
- **Classical first.** No LLM stage is part of the foundation path. An LLM layer is activated only
  on a clear, reproducible net benefit against a realistic baseline on human gold; the baseline
  wins ties. No external model API in a production path. Linguistic variety is never
  machine-labelled.

## 14. Stack registry and pins — maintenance contract

- Every runtime dependency is an exact pin (`==`). A range specifier lets a component state move
  under a result.
- **Any accepted change** to which model, tool, extractor, rule set, pin or stage placement is used
  for a pipeline task is incomplete until, in the same run: code and config agree;
  `docs/STATUS.md` (tables and machine-readable block) agrees and the self-check passes; the
  component index has been checked; and the decision registry links the evidence.
- If repository code ever makes an externally metered API call, it goes through one accounting
  boundary that records every attempt, and the run report carries a cost section generated from
  that record — never hand-calculated, never "free". No such code exists; building that boundary is
  a precondition for the first such call.

## 15. Testing

- Run with `python -m pytest`. Suites: `python -m pytest --suite <name> tests`; every
  `tests/test_*.py` belongs to exactly one suite manifest under `tests/suites/`.
- The release gate is `python -m pytest --suite release_gate tests`. It is empty until there is
  something to release; do not put a placeholder test in it.
- **Tests never touch the network, a storage root, a production ledger or a reference
  repository.** They write only under `tmp_path`. After a full run no tracked file is modified; if
  one is, that is a test bug to fix and name in the run report.
- A test that asserts a line of configuration exists does not validate behaviour. Validate a
  mechanism by exercising it.
- Fixtures are small, documented, non-production and byte-pinned (`tests/fixtures/README.md`).
- Do not delete or weaken a failing test to get a green run. A test frozen as evidence of a
  historical state is never edited to pass.

## 16. Documentation — maintenance contract

- **One dated run report per run**: `docs/agent-runs/YYYY-MM-DD_short-descriptive-title.md`,
  updated while working, not only at the end. Convention and skeleton:
  [`docs/agent-runs/README.md`](docs/agent-runs/README.md).
- **Decisions** go to `docs/decisions/` only when actually made, under the `CPD-<nnnn>` namespace.
  Do not manufacture a decision from an open planning note.
- **Layering** — link to the authoritative layer instead of copying its narrative:
  component index = current local state, rules and navigation; decision = what was decided and why;
  `docs/STATUS.md` = what exists; master plan = order, gates, open decisions; methodology =
  scientific method; run report = one execution.
- A scientifically or architecturally material change is incomplete until the component index, the
  architecture index and, where a state changed, `docs/STATUS.md` have been checked in the same
  run. Minor code fixes need no documentation churn.
- **No document may read as if the target architecture were implemented.** Target documents carry
  a status line; state changes are made in `docs/STATUS.md` with evidence.
- Do not create a second authoritative document for a topic that has one. Extend the existing one.

## 17. Operator report

End every run with a short report to the operator:

1. the decisive result;
2. **status**: `PASS`, `PARTIAL`, `FAIL` or `BLOCKED` — and what that status does *not* claim;
3. the productive or methodological consequence;
4. exactly one recommended next run;
5. files created or changed, and whether anything was moved, deleted or overwritten;
6. confirmation of what was left untouched (reference repositories, git state, network / external
   API usage).

Report outcomes faithfully: a failed check is reported with its output, a skipped step is named as
skipped, and an unverified claim is labelled unverified.
