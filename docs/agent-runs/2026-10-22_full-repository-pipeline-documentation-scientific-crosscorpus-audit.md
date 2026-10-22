# Full repository, pipeline, documentation, scientific and cross-corpus consistency audit — 2026-10-22

```text
run_started_at:      2026-10-22T07:20:20+02:00   (first clock reading of the run; the preflight began minutes earlier)
run_ended_at:        2026-10-22T07:53:03+02:00   (last clock reading before the commit)
timezone:            Europe/Berlin
wall_clock_seconds:  1963                        (between the two clock readings; the true run is a few minutes longer)
```

- **Kind of run:** diagnosis, with bounded repairs (category A: canonical documentation; category B: small local defects, each
  with a regression test). No scientific validation, no production activation, no gate closed.
- **Status: `PARTIAL`.** The audit covered every area of the brief; the repairs it was authorised to make are made and tested.
  It is `PARTIAL` because (1) one test stays red: the decision record CPD-0032 lacks its required section, and the edit was
  refused by the session's permission layer, which this run did not work around (F-02); (2) technical interoperability with
  CO.RA.PAN is `PARTIAL` and scientific interoperability `BLOCKED` (§E), for reasons that need joint decisions; (3) several
  findings are category C and wait for the operator (§F). **The status does not claim** that any stage is validated, that any
  extractor or annotation is adequate, that the acquired material is a scientifically suitable article population, or that
  the two corpora are comparable.
- `EXTERNAL_API_USAGE = NONE`. No network request of any kind; no request to any publisher; no model inference. Git commands in the
  reference repositories were read-only (`log`, `show`, `diff`, `ls-files`, `cat-file`, `status`). One read-only operating-system
  query (`Get-ScheduledTask`/`Get-ScheduledTaskInfo`) by a sub-audit.

## Objective and brief

The operator brief "CO.PRE.PAN_v3 — Full Repository, Pipeline, Documentation, Scientific & Cross-Corpus Consistency Audit"
(2026-10-22): audit architecture, implementation, scientific definitions and their operationalisation, documentation,
operational evidence, tests, export/release and the interfaces with CO.RA.PAN; repair clearly evidenced, bounded,
scientifically neutral defects (A, B); prepare decisions for everything else (C); CO.RA.PAN read-only; no live crawl, no
external provider, no production action; one report, own branch, no merge.

**Method.** After the preflight, five independent read-only sub-audits ran in parallel (acquisition and sources; storage and
preservation with the joint storage contract; identity, extraction, admission, normalisation, NLP and scientific definitions;
the joint release and analysis contracts and comparability; documentation consistency with a link check). Each returned
findings with file and line evidence. Every finding that led to a repair, and the key cross-corpus findings, were re-checked
by this run against the files before acting (named in §F); the rest are reported with the sub-audit's evidence and are
labelled as such where not re-checked.

## A. Starting position

| | |
|---|---|
| Repository | `C:\dev\panhispanic_media_corpora\coprepan`, branch `main`, HEAD `e9e291d`, working tree clean, no stash |
| Run worktree | `C:/dev/panhispanic_media_corpora/worktrees/coprepan/full-audit-2026-10-22`, branch `audit/2026-10-22-full-consistency` from `e9e291d` (the main checkout was not changed) |
| Other worktrees (foreign, untouched) | `legacy-archive-contract` (`17fac47`), `legacy-freeze` (`e9e291d`), `newfs-phase-b` (`881ae58`), `newfs-phase-d` (`a496b23`) |
| CO.RA.PAN 3.0 (read-only) | `C:\dev\panhispanic_media_corpora\corapan`, branch `main`, HEAD `cb627815e` (under active ASR production by other sessions); **foreign uncommitted changes present** (among them `config/storage_targets.yml`, `.gitignore`, untracked run reports) — read as found, nothing touched; none under `contracts/`, `config/crosscorpus/`, `docs/crosscorpus/` |
| Legacy COPREPAN (read-only) | `C:\dev\panhispanic_media_corpora\legacy\coprepan`, HEAD `0cde9aa`, clean; its tests not run, its databases not opened |
| Studies repository (read-only) | `…\legacy\corapan_coprepan_studies`, grep only |

**Authoritative sources used:** `AGENTS.md`, `docs/STATUS.md`, `docs/architecture/INDEX.md`, `TARGET_ARCHITECTURE.md`,
`PHASE3_SCIENTIFIC_ARCHITECTURE.md`, `TERMINOLOGY_AND_NAMING.md`, the methodology, the decision registry and CPD-0001 to CPD-0032,
every component index, the master plan, the pinned contract bundles, `config/`, `src/coprepan/`, `scripts/`, `tests/`, the intake
reports under `docs/intake/reports/`, the storage migration evidence under `docs/storage/migration/`; in CO.RA.PAN its pins,
contract bundles, decisions D93, D95, D100, D101, D116, D126, D127, D131, its crosscorpus handoff and its audit report of
2026-10-22 (`fbaaccce1`, read as its self-description).

**Starting state (from those sources, confirmed by the sub-audits):** a foundation with an acquisition path that has run
for real in bounded, armed-and-disarmed canaries, waves and intakes (last request 2026-10-11; the switch `disabled` since
`48446d3`; every authorisation record expired; no intake task left); a PRESERVATION primary on the institutional share with a
verified BACKUP; a LEGACY holding; an experimental baseline extractor; no normalisation, no NLP, no validated or activated stage.

**Baseline test run (measured 2026-10-22 on `e9e291d`, run worktree):** `python -m pytest tests` — **3 failed, 1645 passed, 14
skipped in 568.62 s**. The three failures exist on `main` since 2026-10-20 (its run report ran one suite only):
`test_storage_targets_hold_only_environment_references`, `test_the_tracked_files_hold_no_machine_location` (the three LEGACY
environment names of CPD-0032 in `.env.example`, not expected by the tests) and `test_decision_record_header[CPD-0032]` (the
record has no `## Alternatives considered`).

## B. Component and pipeline matrix

Implementation · validation · activation as in `docs/STATUS.md` §2 (unchanged by this run). "Real evidence" is what has run on
real material; it validates nothing.

| # | Component | Function | Governing decisions | Implementation · config | Tests | Real evidence | Scientific validation | State |
|---|---|---|---|---|---|---|---|---|
| 1 | Outlet registry, registration | which outlets, by record | CPD-0013, 0025, 0026, 0028 | `registry.py`; `config/outlet_registry.json`: 126 outlets, 114 registered, 12 proposed, 20 countries, no duplicate id or origin | `test_registry.py`, `test_source_qualification.py` | 145 hypotheses dispositioned | none; human review (O-11) open | PARTIAL · NOT_VALIDATED · INACTIVE |
| 2 | Discovery, candidate qualification | find item URLs | CPD-0006, 0019, 0020, 0025 | `discovery.py` (`channel-parser/6`, `expansion-order/2`, `candidate-budget-order/1`), `candidate_filter.py` (`generic/3`); outlet rules for 2 outlets | `test_discovery.py`, `test_source_structures.py`, `test_schedule.py` | 121 channels in the 24-hour intake | none | PARTIAL · NOT_VALIDATED · INACTIVE |
| 3 | Policy gate, robots, research-TDM, access controls | may this be asked | CPD-0013, 0017, 0027 | `policy.py` (`robots-decision/3`), `robots.py` (`robots-parser/3`), `access_control.py` (`access-control/4`, `access-hold-scope/1`); policy `canary/2026-10-10.1`, schema v3, **`external_acquisition: disabled`** | `test_policy.py`, `test_research_tdm_policy.py`, `test_canary_findings.py` | every real run; research override never used | not legal advice; no legal review | in force as a gate; nothing armed |
| 4 | HTTP fetch, schedule | ask, record every attempt | CPD-0006, 0007, 0009 | `fetcher.py` (`http-fetcher/1`), `schedule.py` (`fetch-planner/1`); schedule policy `canary/2026-10-08.1` | `test_fetcher.py`, `test_refetch_e2e.py` | 7 173 requests in 24 h over TLS, 0 errors; only first visits on real material | none; scheduled crawling (O-1) undecided | PARTIAL · NOT_VALIDATED · INACTIVE |
| 5 | Canary driver, delegation, bounded intake | orchestrate a bounded run | CPD-0016, 0019, 0023, 0024, 0029 | `canary_driver.py` (`/5`), `delegation.py`, `intake.py` (`intake-controller/1`), `intake_report.py` | `test_canary_*`, `test_delegated_operator.py`, `test_intake*.py` | canaries 2026-10-08…10; intakes pilot and 24 h, verification `PASS`, disarmed by task | — | tools, not stages; nothing running |
| 6 | Raw preservation, spool, recovery, ledger | keep the exact bytes | CPD-0005, 0009, 0010, 0015, 0030 | `pack.py`, `preservation.py`, `outage_spool.py`, `ledger.py`, `recovery.py`; primary on NEW_FS, BACKUP on `D:` | `test_preservation.py`, `test_crash_recovery.py`, `test_concurrency.py`, `test_integrity_invariants.py`, `test_storage_contract.py` | 8,816 objects migrated and verified unbuffered; 6,490 of 6,490 intake bodies `RAW_PRESERVED` and read back; daily backup task green 2026-10-22 05:45 (OS query) | n/a (technical); P2 now uncached (R4) | PARTIAL · NOT_VALIDATED · INACTIVE |
| 7 | Document identity, versions | what is the same document | CPD-0003, 0005, 0010, 0025, 0026, 0028 | `identity.py`, `document_identity.py`, `identity_rebuild.py`; tables in the runtime workspace adopted (CPD-0028 §2) | `test_identity.py`, `test_core_pipeline.py`, `test_evidence_integrity.py` | real tables; 131 duplicate-body pages in 24 h (false duplicates of near-empty bodies) | none; alias rule and syndication not implemented | PARTIAL · NOT_VALIDATED · INACTIVE |
| 8 | Extraction | title, body, other blocks, metadata | CPD-0005, 0007, 0018 | `extraction.py` (`baseline_html/0.1.0`, `EXPERIMENTAL`); three candidate wrappers (extra `phase3`) | `test_extraction.py`, `test_admission_eval.py`, `test_extractor_candidates.py` (tool tests skipped here) | ≈3,700 real pages; D1 observations | **none** (no gold) | PARTIAL · NOT_VALIDATED · INACTIVE; corpus export refused |
| 9 | Admission labels | technical usability | CPD-0007 §8 | `admission.py` (`admission-technical/1`) | `test_admission_eval.py` | 3,610 of 3,681 intake pages `TECHNICALLY_USABLE` | none; no content-level label | PARTIAL · NOT_VALIDATED · INACTIVE |
| 10 | Normalisation | recorded text operations | TARGET §7, CPD-0008 | not started (one whitespace collapse inside the extractor contract) | — | — | — | NOT_STARTED |
| 11 | NLP, annotation | shared instrument | nlp index; joint pin rule | pins `PLANNED`, not installed; equal to CO.RA.PAN's (spaCy 3.8.15, `es_dep_news_trf` 3.8.0) | — | — | — | NOT_STARTED |
| 12 | Enrichment (section, genre, opinion, language, syndication) | content classification | PHASE3 §7; vocabularies open | not started | — | — | — | NOT_STARTED |
| 13 | Release, export | native export, release mechanics | CPD-0011, 0012 | `release_export.py`, `release_contract.py` (revision 1 of the joint contract) | `test_release_export.py`, `test_release_contract.py` | none | none | PARTIAL · NOT_VALIDATED · INACTIVE |
| 14 | Cross-corpus analysis contract | shared analysis tables | CPD-0008 | `analysis_contract.py`, `analysis_export.py`; proposal, not adopted by CO.RA.PAN | `test_analysis_contract.py` | none | none | PARTIAL · NOT_VALIDATED · INACTIVE |

**LLM, models, prompts.** None exists in `src/`, `scripts/` or `config/`: no model inference, no prompt template, no external
API (searched for openai, anthropic, llm, transformers, spacy, stanza, torch, huggingface, ollama, gemini, mistral; no hit). The
only "prompt" is the terminal confirmation of `scripts/canary_operator.py`. The only third-party text tools are the three
classical extractor candidates, imported lazily inside their wrappers, `EXPERIMENTAL`, not runtime dependencies. No LLM
requirement is created by this audit; no LLM benefit has been claimed anywhere.

**Architecture consistency.** The stage order and contracts of the target architecture are what the code implements, with
clean producer–consumer boundaries (fetch record → sealed pack → `RAW_PRESERVED` → extraction by fingerprint → version →
label → export refused without an `ACTIVE` extractor). No component claims more than it does in code. The inconsistencies
found are between documentation and state (§D), at three interfaces (version identity tied to an experimental extractor,
SCI-1; analysis export without a lifecycle gate, SCI-9; date hints from channels, SCI-6), and with the sister repository (§E).

## C. Scientific consistency audit

For each area: (a) is the definition implemented as written; (b) is the definition adequate and complete; (c) is quality shown.

| Area | (a) as written | (b) adequate | (c) shown | Main findings |
|---|---|---|---|---|
| Source population | partly: crawl-time section capture (opinion- or sports-only channels for some outlets, an allow rule restricting `pr_noticel` to one section) and the intake's channel-date selection are not declared as selection | **incomplete**: no target population per country cell, no section-capture policy | no | SCI-11, ACQ-9, ACQ-10 |
| Document identity | yes, except the alias rule of CPD-0003 §8 (not implemented) and `duplicate_of` across all outlets (index said "of the outlet") | doubtful for versions: a version is the output of an `EXPERIMENTAL` extractor including `non_body` blocks, so boilerplate changes and an extractor change create versions | no | SCI-1, SCI-4, SCI-5 |
| Extraction | the contract yes, honestly labelled `EXPERIMENTAL` everywhere; corpus export refused | the contract yes; the baseline knowingly not (first `article/main/body` anywhere, first `h1` anywhere — confirmed by this run on synthetic probes) | **no gold, no measurement** | SCI-2, SCI-3, SCI-7, D1 |
| Normalisation | not built; whitespace collapse inside extraction now documented as part of the extractor contract | as specified, adequate (wording never changed) | no | SCI-8 |
| Article classification | not built | **not defined** beyond the review codebook's NOT_AN_ARTICLE list; "document" is equated with "article" in the terminology while every item fetch becomes a document | no | SCI-10, ACQ-9 |
| Register / section categories | the historical study conventions (`hard_news`, `local_regional`, `culture_lifestyle`, `sports`, opinion flag; excluded `service_misc`, `other_unclear`) are **not** used anywhere in code or config; they appear as history (archaeology, CPD-0004) and as soft carry-overs in three documents ("starts from the legacy `section_map_v1` vocabulary") without a decision; `coprepan_written` in the analysis contract is broader than the studies' alias of the same name (documented there) | open (CPD-0008 left the vocabularies open) | no | SCI-12 — **no historical selection convention is treated as a V3 production rule** |
| Dates | publication date never parsed or guessed in extraction; exports say `not_available`/`unknown` | the channel hints (`pubDate`, `lastmod`, offset-less values read as UTC) drive the intake's novelty classes and the D3 figures without that being stated; `lastmod` ranked as a publication-date basis | no | SCI-6 |
| Linguistic annotation | not built; pins equal CO.RA.PAN's | in principle; tense-v3 vs tense-v4 never tested | no | SCI-14, XC-10 |
| Validation design | partly: harness without multi-reviewer agreement and per-outlet summaries | **incomplete**: no development/fresh split in the gold design; per-outlet rules vs outlet-disjoint validation unresolved; the D1 development pages are not recorded by fetch id and cannot be excluded from a later gold sample | nothing validated, and no canonical document claims otherwise | SCI-13 |

**Methodological risks that remain** (none is a defect of code; each needs a decision): the "verified" source stock proves page
retrieval, not article acquisition (section shells, login pages, empty extractions are among the 86 verified outlets); country
totals follow the number of qualified outlets, not press output (Panama 8 outlets, Mexico 1 with almost no text); large, protected
outlets are systematically held; wire copy is counted under the outlet's country; section mix varies by outlet as an artefact of
channel registration — the legacy defect `corpus_supply` §1 names.

## D. Documentation consistency

**Inventory checked:** `AGENTS.md`, `CLAUDE.md`, `STATUS.md`, the architecture index and the three architecture documents, the
methodology, the master plan, the decision registry and every record header, all component indexes, the canary runbook, the
run-report conventions; a mechanical link check over 108 tracked Markdown files (536 relative links): **0 broken**.

**Contradictions found** (all between a stale canonical statement and the documented current state; none between two current
normative rules except item 13): STATUS §3 rows vs STATUS's own dated updates (roots, TLS, spool callers, policy version,
access-control version, outlet rules, readiness); STATUS §4 component versions vs code; the architecture index §0 and §2 vs
STATUS and the registry; the registry rows CPD-0028–0032 (four columns, no record link; CPD-0030 "cutover not executed");
storage index header, §5, §20.1, §20.6 vs §20.7 and STATUS; legacy index header and steps 2–3 vs its own §5 box; master plan
Phase 0 and §13 vs CPD-0032; acquisition, corpus-supply, identity, admission, extraction indexes and the runbook header vs
STATUS §5a–§5g; the crosscorpus index and the pin file ("equals CO.RA.PAN's pin") vs CO.RA.PAN's pin; terminology without
the terms of CPD-0023 and CPD-0030–0032; AGENTS §4 ("the operator initialises git"). **Item 13, recorded and not resolved:**
AGENTS §7 ("no live fetch … unless … the gates are closed … Today they are open: no run may fetch") reads against the
canary-scope gate passes and authorisations under which canaries and intakes ran (CPD-0016, 0023, 0029). How AGENTS §7 is to
read for a canary scope is the operator's decision (F-29).

**Corrected (category A), all as dated notes or corrections that say what they replaced — nothing historical rewritten:**
`docs/STATUS.md` (a current-state paragraph; §2 note on further outdated cells; §3 rows Decisions, Policy gate, Access controls,
Storage roles and roots, HTTP fetcher, Candidate qualification, Canary driver, Preservation-target readiness, Storage-target
configuration, Promotion and spool, Baseline manifest; §4 versions; §5 notes on O-3, O-10, O-11, Phase-2 — gate states unchanged;
§6 two debts; §7 `as_of`; §8 history 2026-10-11 to 2026-10-22), `docs/architecture/INDEX.md` (§0 rows; the storage contract as a
contract not owned; §2 CPD-0030–0032; §3 deletion-guard row, a stale "nothing registered", seven missing test rows),
`docs/decisions/README.md` (rows CPD-0028–0032), `docs/crosscorpus/INDEX.md` (§1a: the two revisions; D116), `docs/release/INDEX.md`,
`config/crosscorpus/contract_pins.json` (the `note` text only), `docs/storage/INDEX.md` (status note; new §20.8 Phase D),
`docs/legacy/INDEX.md`, `docs/acquisition/INDEX.md`, `docs/corpus_supply/INDEX.md`, `docs/identity/INDEX.md`,
`docs/extraction/INDEX.md`, `docs/admission/INDEX.md`, `docs/canary/RUNBOOK.md`, the master plan (§11 Phase 0, §13 note),
`docs/architecture/TERMINOLOGY_AND_NAMING.md` (§23), `config/storage_targets.yml` (a comment), `AGENTS.md` (one factual line).

**Open normative points (not changed):** decision records are not edited by this run (F-02, F-03); deliberately dated sections
(storage §19, §20.3–§20.6, STATUS §5a–§5g, every run report) keep their text; the stage states, gate states and the
`open_production_gates` list are unchanged. **Kept as historical evidence:** every run report (including header defects of the
reports of 2026-10-14 to 2026-10-20 and arithmetic slips in the report of 2026-10-10 §10–§11, F-37), every frozen baseline,
manifest, receipt and intake report.

## E. Cross-corpus compatibility (CO.PRE.PAN ↔ CO.RA.PAN)

**Digests** (bundle digest = SHA-256 over the sorted canonical-JSON lines of the `{path, sha256, size}` listing, the algorithm of
`release_contract.tree_listing`; recomputed by the sub-audits; the pins themselves read by this run in both repositories):

| Bundle | CO.PRE.PAN | CO.RA.PAN | Equal |
|---|---|---|---|
| `crosscorpus-storage/v1` | revision 2, `49a3ca88c084eee26e40caa1dd987155bf8062c99c81d8cb734a7990a8afb036` (copy recomputed = pin) | revision 2, same digest (canonical home; no change after `003ec84d5`) | **yes, byte-identical**; 110 shared cases reproduced on both sides |
| `crosscorpus-release/v1` | draft revision 1, `4fb72acf27abf09b29dba9de22b241471d0eb5fde3c9e75cc638d646426dbbe0` (49 files) | draft revision 2, `429f55eb1992be7adf230b501e9ecf80ba944478b3a91a31943f3cfef9442255` (commit `374d2e44e`, 2026-10-08; pin says "not yet taken by CO.PRE.PAN") | **no** — split since 2026-10-08 |
| `crosscorpus-analysis/v1` | canonical home here; proposal (CPD-0008) | `TECHNICAL_PROPOSAL__NOT_ADOPTED_BY_CORAPAN`; no implementation | n/a; CO.RA.PAN's recorded file digests of 2026-10-08 still match |

**Compatibility matrix**

| Area | Contract & version | CO.PRE.PAN | CO.RA.PAN | Technical conformance | Scientific comparability | Evidence & limits | Open decisions | Required actions |
|---|---|---|---|---|---|---|---|---|
| Storage | `crosscorpus-storage/v1` rev 2, IN_FORCE | pinned rev 2 (CPD-0031); PRODUCTION primary on NEW_FS (T2), BACKUP verified; LEGACY PRESENT | pinned rev 2 (D127); LEGACY in use (D131) | **conformant** (decision functions, 110/110 cases both sides) | n/a | pins, digests, both conformance suites (here run green) | a `legacy/crosscorpus` namespace would need a revision (D131 notes it) | status output: B3 wording, per-holding status (F-20) |
| Preservation | same, §7 P1–P9, §2.3 A1–A9 | P2 on the share now re-read past the client cache (R4); LEGACY tree PRESERVED | same functions | conformant after R4 | n/a | code; Phase-C/D evidence | Phase-1 gate with only PRESERVATION on the share | A6 enforced in code (F-21) |
| Release | `crosscorpus-release/v1` DRAFT | rev 1, 52/52 cases, CPD-0012 | rev 2, 93 cases + 30 pattern vectors, D93 | **split**: each side conforms to a different revision; CG3 fails | n/a | digests; CO.PRE.PAN's differences from rev 2 found by reading (T13, T16, T19, T20), not run | taking rev 2 over; joint adoption; Q3, Q5–Q12 | take rev 2 over, renew CPD-0012 (F-05); release sister check (F-06) |
| Export | `coprepan-export/v1` / CO.RA.PAN's export-ready contract | synthetic only; corpus export refused (no `ACTIVE` extractor) | real bundles (provisional exports) | both map to member records; disjoint id prefixes | n/a | no real CO.PRE.PAN export | — | — |
| Metadata | release §7, analysis §5 | lower-case date bases; ISO country | upper-case date bases; ISO country | compatible (each corpus's own vocabulary) | country sets differ (`pr` here, `us` there; 19 shared); time windows not aligned (radio 2026-Q3, press intake 2026-10, legacy press to 2026-06) | registries read at HEAD | joint country/variety scope and time window | joint note (F-09) |
| Identities | release §5.4; analysis `check_disjoint` | `cpx1-`, `coprepan-YYYY.n` | `expr1-`, `corapan-YYYY-MM-DD.NNN` | no collision except `outlet_id`: `gt_emisoras_unidas`, `hn_radio_progreso` registered in both; the analysis validator refuses any shared outlet id, the release contract does not | a broadcaster's website in the press population: undefined | registry intersection computed | per-corpus vs cross-corpus outlet-id uniqueness | joint decision (F-08) |
| Analysis populations | analysis §1 vs CO.RA.PAN D116 §1.6 | `production_mode` (`unscripted`, `scripted`, `prerecorded`, `written_edited`) | speech mode retired (D116, 2026-10-16); communicative situation type over professional-speaker core turns; stored `prerecorded` read as `unknown` (D101) | the analysis contract cannot represent the radio side's current population | **no joint definition**; press has no selection policy and no counterpart to the professional-speaker restriction | D116 read at source by this run | population definitions; a new analysis-contract version | joint scientific decision, then `crosscorpus-analysis/v2` (F-07) |
| Linguistic annotation | analysis §6, §10–§12 | annotator `PLANNED`, not installed | spaCy 3.8.15 / `es_dep_news_trf` 3.8.0, verbal complex v2, D126 join | same pins (the NER sub-layer `es_core_news_lg` not mirrored here) | not shown; tense-v3/v4 never tested; CO.RA.PAN's NLP index does not mention a shared contract | design only | equivalence run, tense bridge | Phase-4 joint run (F-10) |
| Scientific comparability | analysis §13 | design verdicts | own qualification | — | **none empirical**; token counts `not_available` on both sides | "nothing was measured" | everything marked caveat or undecided | the measurements §13 names |
| Provenance & reproducibility | release §10.1 three pins | implemented (CPD-0012 §2) | implemented (D93) | agree | — | fixtures | — | — |
| Governance & drift protection | pin files; release §14.3, §17 | pin had no revision or other-side record; documents claimed equality (corrected, R6) | pin records both revisions and the other side | no cross-repository check for the release bundle on either side; the split went unnoticed here for 14 days | — | git history | who triggers re-pinning | sister check (F-06) |

**Classification of the divergences:** release split — missing joint adoption, this side lagging (F-05); this repository's
"equal pins" statements — local documentation defect, corrected (R6); this checker's readings at the revision-2 points — local
implementation difference, to be repaired with the take-over (F-05); `production_mode` vs D116 — joint contract contradiction
and scientifically unresolved definition (F-07); comparison populations, country sets, time windows — scientifically unresolved
(F-07, F-09); `outlet_id` overlap — joint contract contradiction (F-08); annotation equivalence — evidence gap (F-10); CO.RA.PAN's
crosscorpus index header (2026-10-11, "no internal release frozen") and its pin placeholder `canonical_home_commit` — local
CO.RA.PAN findings, reported only (F-11); distinct id prefixes, the mirrored NLP pins, the shared canonical-JSON rule —
intended and documented.

**Technical interoperability: `PARTIAL`.** Storage is jointly in force and byte-identical; formats, id discipline, value states,
canonical JSON, digest rules and the three-pin study model agree. But the two repositories work against different release
bundles, neither contract on release or analysis is jointly adopted, the analysis contract has one implementation and refuses a
real outlet-id overlap.

**Scientific interoperability: `BLOCKED`.** No jointly decided comparison population exists; the analysis contract's shared
dimension was retired on the radio side; the press side has no selection policy, no adopted extractor, no annotation; neither
corpus can count under the shared denominator; equivalence and tense-bridge runs do not exist. The three-level model of the brief
(free spoken radio, scripted radio news, written press) is the model the analysis contract still encodes; CO.RA.PAN replaced its
radio half by D116. The assumed gradation of register and standard proximity remains a hypothesis.

## F. Findings and repairs

Severity: critical · high · medium · low. Category: A (documentation), B (local code, regression test), C (decision). "Evidence"
cites the sub-audit ids (ACQ, STO, SCI, XC, DOC) whose reports carry file:line evidence; ✔ = re-checked by this run at source.

**Repaired in this run**

| ID | Sev. | Scope | Norm | Defect | Evidence | Cat. | Repair | Validation | Status |
|---|---|---|---|---|---|---|---|---|---|
| F-01 | high | tests vs config | CPD-0032 §1 | two tests did not expect the LEGACY environment names; suite red since 2026-10-20 | DOC-20 ✔ baseline run | B | the tests expect the three names; exact equality and empty values still required | both tests pass | **fixed** |
| F-04 | high | registry | registry rules 1, 5 | rows CPD-0028–0032 lost two columns and their record links; CPD-0030 "cutover not executed"; CPD-0032 status inside the description; nothing tested it | DOC-1, DOC-6 ✔ | A + B | rows restored from the record headers; new test `test_decision_registry_row_is_complete_and_agrees_with_its_record` (6 columns, record link, status = header, decision in architecture index §2) | 32/32 pass; the same check flags exactly the five rows on `main` (counter-probe) | **fixed** |
| F-12 | high (latent) | preservation | storage contract P2; CPD-0030 | `RAW_PRESERVED`, the promotion check, the spool drain and the landed-bytes check re-hashed with a buffered read; on the share (primary since 2026-10-18) a re-read right after a write is served by the client cache (measured 2026-10-14) | STO-2 ✔ (`preservation._holds`, `_land`) | B | `preservation._holds` and the landed-bytes check read through `sha256_uncached` (the reader the migration and backup tools use) | new test `test_the_preserved_state_rests_on_a_read_past_the_client_cache` (staging and master read uncached; a server holding other bytes fails verification); 370 tests of the preservation path green | **fixed**; not yet exercised on the share (no production write) |
| F-13 | medium | gold instrument | extraction eval §6 (neutral side) | the reviewer's neutral view decoded every page as UTF-8; a non-UTF-8 page reached the reviewer as U+FFFD while the arms had the letters | SCI-3b ✔ (probe: `Pe\ufffdalol\ufffdn` before, `Peñalolén` after) | B | `visible_text` decodes by the arms' rule (BOM, HTTP charset, `<meta>`, UTF-8) | new test `test_visible_text_is_decoded_like_the_arms_and_not_always_as_utf8` | **fixed**; the pilot package outside the repository (built earlier) is not rebuilt |
| F-14 | high | STATUS, indexes, registry, terminology, plan | AGENTS §16; registry rule 5; AGENTS §12 | stale and contradictory canonical statements (§D) | DOC-2…19, ACQ-1…3, STO-9/10, SCI-15, XC-2 ✔ (versions, policy, pins, D116, counts re-read) | A | §D list | relative-link test; repository-contract suite | **fixed** |

**Not repaired — blocked, or a decision (category C), most severe first**

| ID | Sev. | Scope | Finding (evidence) | Why not repaired / what is needed |
|---|---|---|---|---|
| F-02 | high | decision record | CPD-0032 has no `## Alternatives considered`; `test_decision_record_header[CPD-0032]` stays **red** (DOC, baseline ✔) | the edit was refused by the session's permission layer (records are immutable once `ACTIVE`, registry rule 1); **the operator decides**: allow a format-only addition (proposed text: "None recorded at the time of the decision; point 4 weighs HISTORIC; the state replaced is CPD-0031 decision 3") or amend the test's rule |
| F-03 | medium | decision records | forward notes missing on superseded/amended records: CPD-0031 (by 0032), CPD-0014 (by 0015, 0030), CPD-0006, 0013, 0016, 0017, 0020; CPD-0030 header names Phase C only (DOC-4, DOC-5) | registry rule 1 allows a dated forward link, but this run edits no record (F-02); also whether CPD-0031 becomes `PARTIALLY_SUPERSEDED` |
| F-05 | high | release contract | the split of `crosscorpus-release/v1` (XC-1 ✔); this checker differs from revision 2 at T13 (patterns with Python `re`), T16 (freeze beside a provisional export), T19 (sums over no documents), T20 (forbidden suffixes in the check) (XC-3, by reading) | taking revision 2 over changes a shared-contract pin and a local adoption decision (CPD-0012 renewal) — C; then the code changes and the 93 cases are B |
| F-07 | high | analysis contract, science | `production_mode` vs CO.RA.PAN D116/D101; no joint comparison populations (XC-4, XC-5 ✔ D116) | joint scientific decision (O-6), then a new analysis-contract version |
| F-15 | high | science | "article" has no operational definition; `ACQUISITION_VERIFIED` and technical labels say nothing about articles; non-articles counted among verified outlets (SCI-10, ACQ-9) | content-level admission and an article definition: scientific decision |
| F-16 | high | science | source population shaped at crawl time without a policy: section-specific channels, an allow rule restricting one outlet to one section, channel-date selection; no target population per cell; coverage bias (SCI-11, ACQ-10) | selection/section-capture policy and target population: operator and scientific decision |
| F-17 | high | identity | version identity = output of an experimental extractor incl. boilerplate; adopting an extractor changes every version id; `duplicate_of` evidence does not record the extractor (SCI-1) | definition of a textual state: decision; the evidence field is B after it |
| F-18 | medium | extraction | baseline: body lost or navigation taken without a diagnostic (confirmed on synthetic probes ✔); `iso-8859-1` decoded as Latin-1, not windows-1252, mojibake uncounted (SCI-2, SCI-3a) | each changes extractor output, hence versions: a new extractor version is a decision (D1) |
| F-19 | medium | validation | no development/fresh split; per-outlet rules vs outlet-disjoint validation; D1 development pages not recorded by fetch id; one reviewer per case, no agreement, pooled summaries (SCI-13) | gold-sample design amendment: scientific decision; harness changes B after it |
| F-08 | medium | cross-corpus ids | `gt_emisoras_unidas`, `hn_radio_progreso` registered in both corpora; analysis validator refuses, release contract allows (XC-6) | joint decision |
| F-09 | medium | cross-corpus scope | country sets (`pr` vs `us`), time windows (XC-7, XC-5) | joint decision |
| F-20 | medium | storage tools | `storage_contract.py status` omits the B3 independence wording and LEGACY, and calls HISTORIC "planned" (STO-3); backup-state edge cases (STO-4); pending objects outside the spool not listed (STO-8) | B, deferred to an engineering run: output format changes beyond this audit's minimal scope |
| F-21 | medium | storage | A6 (LEGACY never a pipeline input) enforced by configuration only; LEGACY roots not run through S1–S4 (STO-5) | B, deferred (resolver change with its own tests) |
| F-22 | medium | storage tool | `scripts/qualify_storage_roots.py` writes and removes under `preservation_root.parent/_qualification/` — since the cutover that parent is the shared umbrella directory of both corpora (STO-6) | **do not run the tool until repaired**; B, deferred |
| F-23 | medium | intake | an unreachable robots answer is cached for the controller's life: one failure defers an origin for a whole intake (ACQ-4; `pe_elperuano`); intake budget, deadline and withdrawal refusals are recorded as policy `DENY`, so the candidates are deferred 7 days (ACQ-5: 18 in the 24 h) | re-read interval and refusal semantics: C, then B |
| F-24 | medium | access control | the small-body test of the classifier uses the compressed length; a gzipped article could be inspected for challenge markers (ACQ-7; no instance seen) | changes the classifier and so the re-derived holds: new `access-control` version — C |
| F-25 | medium | registry | nine registered outlets carry template or truncated channel URLs (`<tema>`, `TRUNCATED`); the validator checks non-emptiness only (ACQ-8) | registry amendment records (C), then a validator (B) |
| F-26 | medium | analysis export | `analysis_export.export_bundle` seals a `release`-kind bundle from `EXPERIMENTAL` text; `release_export` would refuse it (SCI-9) | a gate parity rule is not stated in CPD-0008: confirm, then B |
| F-27 | medium | dates | channel hints (`pubDate`, `lastmod`, offset-less as UTC) drive the intake's novelty and the D3 figures; corpus supply ranks `lastmod` as a publication-date basis (SCI-6) | C (date-basis ranking, D3); a renaming in the report is A after it |
| F-28 | low | intake robustness | `budget_respected` does not check the hourly ceiling (ACQ-13); `IntakeStopped` during pacing ends as a crash (ACQ-14); `BLOCKED` written outside the lock (ACQ-15); `fetch_started_at` before pacing (ACQ-16); two `transport_calls` totals (ACQ-12) | B, deferred to an intake engineering run |
| F-29 | low | rules | AGENTS §7 vs canary-scope gate passes (§D item 13) | operator's reading |
| F-30 | low | science, docs | historical register conventions as soft carry-overs ("starts from `section_map_v1`") without a decision; `coprepan_written` broader than the studies' alias (SCI-12) | vocabulary decision (CPD-0008 left it open) |
| F-31 | low | identity | alias rule of CPD-0003 §8 missing; CPD-0026 makes "rebuild under the rules in force" the rule for every URL-rule amendment — a key-changing amendment would re-key documents (SCI-4) | design before the next key-changing amendment |
| F-32 | low | wrappers | trafilatura's normalised date as `publication_date`; dropped text not recorded; jusText's length/stop-word rule (SCI-7) | explicit decision before adopting any candidate |
| F-33 | low | NLP | `es_core_news_lg` not mirrored; CO.RA.PAN's chain moved beyond the pins (canonical NLP contract, D126); CO.RA.PAN's NLP index names no shared contract (SCI-14) | joint |
| F-34 | low | fetcher | `http-fetcher/1` never bumped across five behaviour changes; it is part of the crawler identity (ACQ-17); robots redirects beyond 3 hops become `unreachable` (ACQ-18) | C |
| F-35 | low | registry | two `elnuevodia.com` channel URLs shared by a registered and a proposed outlet (ACQ-23) | the known identity case (O-11) |
| F-36 | low | evidence | CO.PRE.PAN's own LEGACY evidence (seal, backup receipt) lives only in the frozen legacy repository (STO-11); the CPD-0031 run has no report here (DOC-18) | a pointer file with digests (A) when the operator wants it |
| F-37 | info | history | arithmetic slips in the 2026-10-10 report §10–§11 (sum 3 770 for 3 681; 2 582 vs 2 572 2xx) (ACQ-20); headers of the reports of 2026-10-14–20 incomplete (DOC) | historical, never edited; STATUS uses the right numbers |
| F-06 | low | governance | no cross-repository drift check for the release bundle; pin without revision and other-side record (XC-11) | B with F-05 |
| F-10 | low | annotation | equivalence and tense-bridge never run (XC-10) | Phase 4, joint |
| F-11 | info | CO.RA.PAN (report only) | its crosscorpus index header (2026-10-11) says no internal release frozen; pin placeholder `canonical_home_commit`; `production_mode_hint` name close to the shared field; internal releases of kind `provisional_export` | for CO.RA.PAN; nothing done there |

## G. Overall assessment

1. **Architecturally consistent?** Yes in code: the stages, their order and their contracts are implemented as the target
   architecture and the decisions say, with no hidden shortcut found. Not yet in meaning at three interfaces (F-17, F-26, F-27).
2. **Acquisition and preservation robust and rule-conformant?** Technically robust within what was run: the switch is off, no
   default enables it, every arming was disarmed, the 24-hour intake's numbers verify, no false success found in preservation
   except the cached P2 re-read, now repaired (F-12). Conformant with the decided policy; three behaviours of the intake lose
   candidates silently (F-23) and are open. Long-term stability is not shown: one 24-hour intake, first visits only.
3. **Scientifically suitable article populations?** **Not shown, and not yet definable**: no article definition, no
   content-level label, no selection policy, a known coverage bias (F-15, F-16).
4. **Extraction and normalisation definition-conformant?** The contract yes; the baseline extractor is knowingly not adequate
   and is not adopted; normalisation does not exist. Wording is never changed.
5. **Annotation adequate and validated?** No annotation exists.
6. **Documentation, code, configuration and state agree?** Now largely yes (§D); one red test remains (F-02), and dated
   historical text stays as written.
7. **Repaired:** F-01, F-04, F-12, F-13, F-14.
8. **Remaining risks:** technical — F-20 to F-25, F-28; scientific — F-15 to F-19, F-27, F-30 to F-32.
9. **Technically compatible with CO.RA.PAN?** `PARTIAL` (§E).
10. **Joint analyses methodologically prepared?** No — `BLOCKED` (§E).
11. **Binding and matching cross-corpus contracts:** only `crosscorpus-storage/v1` revision 2 is in force in both and
    byte-identical. `crosscorpus-release/v1` is a draft adopted locally on both sides at different revisions;
    `crosscorpus-analysis/v1` is a proposal adopted by neither for joint use.
12. **Joint decisions needed:** release revision 2 and its joint adoption (F-05); the comparison populations and an analysis
    contract after D116 (F-07); cross-corpus outlet-id uniqueness (F-08); country scope and time windows (F-09); the token
    denominator in practice and the annotation equivalence (F-10); a `legacy/crosscorpus` namespace if wanted (D131).
13. **Production and release blockers:** no adopted extractor and no gold (D1); no article definition or content admission; no
    selection policy; O-1 for scheduled crawling; O-11 human review; the Phase-1 gate with only PRESERVATION on the share; for
    joint releases the release-contract split.
14. **Necessary next steps:** the operator decisions of F-02/F-03 and F-05; the scientific decisions F-07, F-15, F-16 before
    any further work on populations. **Expressly not necessary:** any new crawl or intake to answer these findings; any LLM
    component; any change in CO.RA.PAN; re-processing of preserved material.

## Files created or changed

Created: this report. Changed (all in the run worktree, committed on `audit/2026-10-22-full-consistency`):
`src/coprepan/preservation.py`, `src/coprepan/extraction_eval.py`; `tests/test_repository_contract.py`,
`tests/test_storage_architecture.py`, `tests/test_preservation.py`, `tests/test_admission_eval.py`; `config/crosscorpus/contract_pins.json`
(note text only; digests, paths and keys unchanged), `config/storage_targets.yml` (comment only); `AGENTS.md`, `docs/STATUS.md`,
`docs/architecture/INDEX.md`, `docs/architecture/TERMINOLOGY_AND_NAMING.md`, `docs/decisions/README.md`, `docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md`,
`docs/storage/INDEX.md`, `docs/legacy/INDEX.md`, `docs/acquisition/INDEX.md`, `docs/corpus_supply/INDEX.md`, `docs/identity/INDEX.md`,
`docs/extraction/INDEX.md`, `docs/admission/INDEX.md`, `docs/crosscorpus/INDEX.md`, `docs/release/INDEX.md`, `docs/canary/RUNBOOK.md`.
**Nothing was moved, deleted or overwritten**; no decision record, contract bundle, frozen artefact, run report, intake report,
receipt or preserved object was changed. Scratch scripts (read-only probes) are in the session scratchpad only.

## Commands and checks

- Baseline: `python -m pytest -q tests` on `e9e291d` — 3 failed, 1645 passed, 14 skipped, 568.62 s (measured).
- Targeted after the repairs: `tests/test_admission_eval.py tests/test_storage_architecture.py tests/test_repository_contract.py` —
  84 passed, 1 failed (F-02); preservation path and neighbours (`test_preservation`, `test_core_pipeline`, `test_storage_contract`,
  `test_integrity_invariants`, `test_preservation_migration`, `test_primary_backup`, `test_offline_e2e`, `test_crash_recovery`,
  `test_concurrency`, `test_admission_eval`) — 370 passed, 130 s (measured).
- Counter-probes (scratchpad, read-only): the old `visible_text` on `main` returns `Pe\ufffdalol\ufffdn`; the registry check on
  `main` flags exactly CPD-0028–0032; the baseline extractor on two synthetic decoy pages (logo as title and the story `non_body`;
  menu items and a cookie banner as body).
- Final full run, run worktree with every change of this run: `python -m pytest -q tests` — **1 failed, 1681 passed, 14 skipped in
  491.68 s** (measured). The one failure is `test_decision_record_header[CPD-0032]` (F-02). Against the baseline: the two
  environment-name tests now pass, 34 test cases were added (1,648 → 1,682 run: 32 registry rows and two regression tests), and
  no other result changed. After the run, no tracked file outside this run's changes was modified.
- Not run: the legacy test suite (never); any CO.RA.PAN test or tool; `storage_contract.py status` (it reads the sister checkout's
  `.env` and probes the real roots); any acquisition, intake, backup, migration or qualification tool.

## Measurements

All counts quoted from the repository's evidence files are *sourced* (their files named in §B/§F); the test results and the
probe outputs above are *measured* (2026-10-22, this workstation). The bundle digests are *measured* by the sub-audits'
recomputation and agree with the pins read by this run. Nothing was estimated.

## Gates

None touched. O-1 (scheduled crawling), O-3 (long-term target), O-4, O-11, O-12, Phase-1, Phase-2 stay as `docs/STATUS.md` §5
records them; this run added dated notes only.

## Working-tree classification at the end

- Every file changed or created by this run: **committed** on branch `audit/2026-10-22-full-consistency` (one commit; pushed to
  `origin` as that branch; not merged — merging into `main` is the operator's act).
- The run worktree `C:/dev/panhispanic_media_corpora/worktrees/coprepan/full-audit-2026-10-22`: **left in place** for the
  operator's review; clean after the commit. It can be removed with `git worktree remove` after the merge decision.
- The main checkout (`main`, `e9e291d`): unchanged and clean.
- Scratch probes and test outputs: in the session scratchpad, outside the repository.

## Recommended next run (exactly one)

**Release-contract revision-2 take-over and drift check**, after the operator's decision on F-05: copy `crosscorpus-release/v1`
draft revision 2 verbatim from CO.RA.PAN, move the pin, add the 41 cases and 30 pattern vectors to this repository's checks,
repair the four reading differences (T13, T16, T19, T20) with regression tests, renew the local adoption (successor of CPD-0012),
and add a read-only sister comparison for the release bundle like the storage contract's. It is the one finding that blocks
technical interoperability and that this repository can close on its own; the scientific blockers (F-07, F-15, F-16) need
decisions first, not a run.

## Operator report

1. **Decisive result:** the foundation is architecturally sound, and acquisition and preservation are technically robust within
   what has run. But the documentation had drifted from the state of 2026-10-10 to 2026-10-20 in every canonical index, and the
   suite was red on `main`. Both are repaired, except one decision record the permission layer protected. The cross-corpus
   release contract is split between revision 1 here and revision 2 in CO.RA.PAN. The radio side's D116 has overtaken the
   analysis contract's comparison model.
2. **Status `PARTIAL`.** It does not claim validation, adequacy of any extractor, a suitable article population, or
   comparability with CO.RA.PAN. Technical interoperability `PARTIAL`; scientific interoperability `BLOCKED`.
3. **Consequence:** RAW_PRESERVED on the share now rests on a read past the client cache. Reviewers will see non-UTF-8 pages
   correctly. The registry cannot silently lose its columns again. STATUS and the indexes say what exists.
4. **Next run:** the release-contract revision-2 take-over (above), after the operator's decision.
5. **Files:** listed above; nothing moved, deleted or overwritten; no decision record, contract bundle or evidence changed.
6. **Untouched:** CO.RA.PAN (read-only; its foreign working-tree changes left as found), the legacy repository, the studies
   repository, the main checkout's working tree, every storage root. No network, no external API, no publisher request.
