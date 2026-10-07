# COPREPAN 3.0 — Foundation closure, legacy archaeology, architecture decisions and core pipeline

```text
run_started_at:      2026-10-07T21:06:50+02:00   (first clock reading)
run_ended_at:        2026-10-07T21:30:59+02:00   (last clock reading before this report; commits and push followed)
timezone:            Europe/Berlin
wall_clock_seconds:  1449   (between the two readings above)
status:              PASS   — for the scope of §0; see what it does not claim
kind of run:         diagnosis (legacy archaeology, CO.RA.PAN comparison) + decision + implementation,
                     with reproducibility and robustness checks. No scientific validation. No activation.
EXTERNAL_API_USAGE = NONE   (no model API, no external service, no crawl, no feed or sitemap fetch.
                             Network use: `git fetch` / `git push` to `origin` only.)
CORE_I_REAL_IMPORT = DONE   (not BLOCKED_EXTERNAL: the copy was permitted in this session)
```

## 0. What `PASS` covers, and what it does not

**Covers:** (a) Foundation Core I is closed as infrastructure; (b) the legacy system is
reconstructed and every relevant component has an explicit disposition; (c) the core contracts
from acquisition run to document version are decided; (d) those contracts are implemented and
pass a vertical canary, replay, interruption and ablation tests — **on recorded exchanges of
synthetic fixtures, on temporary directories**.

**Does not cover, and must not be read into it:** any statement about real outlets, real pages or
a real storage root; the quality of the baseline extractor; conformance of the pack file with
third-party WARC tools; any scientific taxonomy; replicability or generalisability of anything.
No stage is validated or activated; no gate of `docs/STATUS.md` §5 is closed; one gate was added.
No outlet is registered. There is still no network code.

## 1. State at the start (measured 21:06 +02:00)

| Item | State |
|---|---|
| this repository | `main` `879efc8bcc5efe83f76bdfdee16804669c4e8367`, one commit ahead of `origin/main` `5827cd4`; working tree clean, nothing ignored, no foreign change |
| tests | 328 passed (the predecessor's figure, same commit) |
| predecessor run | [`2026-10-07_foundation-core-i.md`](2026-10-07_foundation-core-i.md): `PARTIAL`, because the legacy import had not run |
| `legacy\coprepan` | `main` `3e6bdd3350913d55c07efe500036bf752de65cc2`, clean (checked after the import) |
| `corapan`, `legacy\corapan_coprepan_studies` | read only; not inspected with git |

Documents read against each other: `AGENTS.md`, `CLAUDE.md`, `docs/STATUS.md`, the master plan,
the four run reports, all component indexes and decisions. No conflict between authoritative
documents was found. One stale statement was found and corrected by this run's own work: the
"registry is empty / import not run" lines.

## 2. Foundation Core I

### 2.1 The real import (preflight 1)

The importer was run with the legacy database file as input and a work directory in the session
scratchpad. It copies the file and its WAL siblings there and opens only the copy.

| Check | Result (measured 2026-10-07) |
|---|---|
| source `data/db/coprepan.sqlite` | 166,174,720 bytes, SHA-256 `7fe499073599978a7ead9224f048d4706e322baf320c7de909517b5e918ed5b7`; `-wal` 4,396,072 bytes and `-shm` present |
| source after the import | same SHA-256 as recorded by the importer before copying; last-write times of the three files still in June 2026 (main file and WAL 2026-06-15, SHM 2026-06-12); legacy `git status` clean, HEAD unchanged |
| copy after being read | 166,711,296 bytes, another SHA-256 — expected: SQLite folded the copied WAL into the copy when it was opened. This is why the import works on a copy. |
| real schema against the assumed one | `sources` and `feeds` have exactly the columns of the legacy model; `articles`, `crawl_runs`, `discovery_runs` also present. No importer change was needed. |
| result | 82 sources → 82 proposed outlets; 352 feeds → 352 proposed channels; 0 unresolved; 0 ids folding several sources |
| determinism | a second import into fresh directories: both outputs byte-identical (`51d8e5a7…46f54e`, `3709f343…ad2e9f27`) |
| registration | none: every entry is `proposed`; a test asserts it |

Outputs committed: `config/outlet_registry.json` (the proposal) and
`config/registry_review/legacy_registry_import_2026-10-07.json` (review report with the
legacy-name → `outlet_id` table). What a reviewer has to settle: corpus-supply index §16.

### 2.2 CPD-0003 review (preflight 2)

| Choice | Evidence from CO.RA.PAN 3.0 (read 2026-10-07) | Decision |
|---|---|---|
| full SHA-256 digest in `fetch_id` | no fetch or capture id exists there; content hashes are full SHA-256, derived ids are truncated to 8–32 digits | **KEEP** |
| zero-based unit, sentence, token indexes | token index = spaCy `token.i`, sentence index = `enumerate(doc.sents)`: both zero-based; no decision there fixes a base | **KEEP** |

Not made equal on purpose: `…:SENTENCE:{i:05d}` per turn there, `…:SENT:{i}` per document version
here. Recorded in identity index §8 and as a status note on CPD-0003; two regression tests added.
No id had been minted, so either outcome would have been free.

### 2.3 Re-assessment (preflight 3)

| Condition | State |
|---|---|
| the six Core-I items technically present | yes (predecessor report §3) |
| importer validated against a copy of the real database | yes (§2.1) |
| outputs deterministic and reviewable | yes |
| CPD-0003 settled | yes: kept |
| full suite green | yes (§11) |

**Foundation Core I: PASS** — reproducibility / infrastructure integrity. The human review of the
proposal is a separate, open gate before any acquisition (master plan O-11).

## 3. Legacy archaeology

Method: three read-only surveys of the legacy code and the studies repository (nothing run, no
database opened in place), cross-checked against the audit of 2026-10-06, plus measurements on
the database *copy* of §2.1. The full reconstruction is
[`docs/legacy/ARCHAEOLOGY.md`](../legacy/ARCHAEOLOGY.md). In short:

- **Acquisition** was a thread started from a web dashboard: outlets in sequence, feed URLs
  collected, each URL fetched once, extracted in memory and stored as text. No HTML, status,
  headers or final URL were kept; no record says which feed listed a URL.
- **Discovery** found 352 feeds for 82 outlets; sitemap indexes were found and then forced
  inactive. A score decided activity; its one sound component is the output probe.
- **Data holding** was a database and rewritten daily JSON files under two different keys.
- **Extraction** was an unversioned heuristic that collected only `<p>`, filtered paragraphs by
  substring and length, and split long words; a later cleaner partly re-joined them.
- **Linguistic layers** were a separate, well-engineered annotation runner whose project labels
  were written into `morph`.
- **Operations**: no resume, no scheduler, tests that crawl at import.

Measured on the copy (2026-10-07): article statuses `ok` 35,810, `too_short` 13,989,
`discarded_gallery` 8,663, `discarded_homepage` 4,255, `discarded_binary` 2,128, `fetch_error` 64,
`discarded_paywall_teaser` 23 (total 64,932); date basis `page_metadata` 37,162, none 15,133,
`crawl_date` 7,791, `url_pattern` 4,846.

## 4. Failure archaeology

Twenty-two failure *mechanisms* (F-1 … F-22) with their evidence class, in archaeology §6. The
ones that shaped this run's decisions:

| Mechanism | Consequence taken |
|---|---|
| F-1 no raw data | raw bytes sealed and promoted before anything is derived; extraction reads only `RAW_PRESERVED` |
| F-2 / F-3 / F-4 word splitting, lossy repair, substring filters | structural rules only; tests assert that short paragraphs and words containing `epa` survive |
| F-6 fabricated dates | metadata value as published plus basis; no parsing, no substitute |
| F-7 / F-8 URL as identity, once-only fetch | five identities; versions; ablation test |
| F-9 silent loss of URLs and feeds | failed fetches are records; nothing is blacklisted; legacy feed status imported as observation only |
| F-12 no resume | run record without result = visible interruption; resumable acquisition |
| F-13 store drift | one write-once path per layer; no rewritten files |
| F-14 / F-15 unversioned parser, provenance gaps | extractor version in every fingerprint; record without volatile fields |
| F-16 / F-17 mixed stages, positional ids | layers kept apart; ids on document versions |

**Negative evidence kept:** no legacy handling of updates, authors, agencies or snapshots; no
second section-map version; the `backup/` directory and `data/sources_seed.json` have no writer
or reader in the code.

## 5. Component matrix

The full matrix — 31 components, each with a disposition for concept, implementation and data —
is the decision [CPD-0004](../decisions/CPD-0004_legacy-component-dispositions.md). Summary:

| Disposition | Count over the three columns | Examples |
|---|---|---|
| `REUSE_AS_IS` | 0 | — |
| `PORT_WITH_TESTS` | 0 decided (one candidate) | tense rule cases, once the shared layer exists |
| `REIMPLEMENT_FROM_CONTRACT` | most concepts | registry, channel health, output probe, run state, extraction, label-don't-delete, normalisation report, annotation-runner design |
| `DATA_ONLY` | data | the 82 sources and 352 feeds; the corpus files within the frozen release; `article_id` as an alias |
| `REFERENCE_ONLY` | several | slug helper, run tables, section map, language guard |
| `DISCARD` | most implementations | crawl loop, article store, extractor, export routing, feed scoring, dashboard, tests, `morph` labels |
| `UNDECIDED` | 2 | robots / opt-out handling (O-1); tense rules |

## 6. CO.RA.PAN 3.0 comparison (read-only)

| Principle there | Verdict for COPREPAN | State here |
|---|---|---|
| Named roots; tracked config names a root, `.env` locates it; "an address is never an identity" | **adopt** | roles and fail-closed resolution exist; tested that no record contains a location |
| Stable, content-addressed ids; order carried separately; collision fails closed | **adopt** | CPD-0003; `DocumentIdCollision` |
| Fixity at promotion, on resume and on demand; no time-based schedule there either | **adopt as is**; a schedule stays an open point | `verify_sealed`, `verify_master` |
| Raw preservation: validate → identity → hash → manifest → immutable master; `.part-` staging; never overwrite | **adopt** (done in Core I) | `preservation.py` |
| Ready stores between stages; promotion only under the planned fingerprint | **adopt the mechanism**, one generic store instead of several | `layer_store.py` |
| Fingerprint excludes paths, hosts, timestamps | **adopt** | extraction record has no volatile field |
| Schema-versioned manifests, old versions readable | **adopt** | every record carries a schema id |
| Gates as named tokens backed by run evidence | **adopt** | `docs/STATUS.md` §5 |
| One dated run report per run; failed-run evidence written once | **adopt** (already a rule) | this file |
| Forward-only versions; backfill needs a change decision | **adopt** (already a rule) | new extractor version = new fingerprint, old artefact stays |
| Acquisition manifest per asset (URLs, retrieved at, status, type, size, hash, basis markers) | **adopt, adapted**: the fetch record | `acquisition.py` |
| No generated run id for ingest there; waves are operator labels | **differ**: COPREPAN gives every run a derived id, because legacy shows what an unidentifiable run costs (F-12) | `run_id` |
| Duplicate raw content raises by default there | **differ**: recorded, not copied twice (storage §6) | `duplicate_recorded` |
| A second answer for a fingerprint returns a status there | **differ**: it raises (target architecture §2) | `FingerprintConflict` |
| Token index per turn, 5-digit sentence padding | **differ**: per document version; form of CPD-0002 | identity index §8 |

**Not transferred** (audio-, ASR- or HPC-specific): canonical audio and its identity, capture-gap
rules, diarization foundations and speaker ids, turn identity over ASR words, ASR text repair and
forced sentence starts, speech-mode, cluster adapters and cost gates, live-stream capture.

## 7. Architecture decisions

[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md), status
`ACTIVE_WITH_VALIDATION_DEBT`. In one paragraph each:

- **Source registry.** The source entity is the *outlet*. Publisher is an attribute, domain is a
  list of web origins, endpoints are channels with URL history. No active period, no policy field.
- **Acquisition run.** `acq1-<UTC start>-<hash12>` over what was asked; a run record at the start
  and a result at the end, each written once; a run without a result is visibly interrupted.
- **Raw preservation.** One fetch record per retrieval; `FETCHED` means a response came back,
  whatever its status. WARC/1.1 packs per outlet and UTC day; a body is stored exactly; the index
  is derived at seal time, bound by the manifest and re-checked on every read.
- **Article identity.** Five identities. An article is its canonical URL key within an outlet;
  a textual state is the digest of the extracted blocks. Same URL / new text = new version;
  other URL / same body = `duplicate_of`; a URL now leading elsewhere = `moved_to`. Nothing merges,
  nothing is rewritten.
- **Extraction.** A pure, versioned function of the preserved body: typed blocks with structural
  roles, metadata with basis and all candidates, decoding recorded, "not extractable" as a label.
  BODY is the primary linguistic surface; title and non-body blocks are kept apart.
- **Layers.** `RAW` → `EXTRACTED` → `ANNOTATED` → `RELEASE`; none overwrites another; each reads
  the previous one by id and hash and only when the ledger allows.

**Scientific layers, to the reliable limit only.** Section, register, genre, opinion and the
verbal complex are *enrichment layers* keyed on document versions, blocks or tokens, each with its
own version and validation status. Extraction hands them the published section value with its
basis, structural roles and stable ids — and nothing interpreted. The studies' evidence
(archaeology §8) fixes what those layers must eventually deliver: section and an orthogonal
opinion flag, title and body separable (the studies counted them together without deciding to),
author where published, a real acquisition identifier, token head indexes, sentence neighbours by
id. **No taxonomy was decided, mapped or validated in this run**; `section_map_v1.yml` remains a
legacy reference. For cross-corpus alignment the token and sentence index *base* now agrees with
CO.RA.PAN 3.0; scope and padding differ and are a matter of the joint contract (O-6).

## 8. Implemented

| Component (priority of the brief) | Module | What it does |
|---|---|---|
| 1 Source registry | `registry.py` (Core I) + the executed import | 82 proposed outlets; only `registered` resolves |
| 2 Acquisition run contract | `acquisition.py` | run identity, write-once run record and result, unfinished-run listing |
| 3 Raw document identity and fixity | `acquisition.py`, `pack.py` | fetch record with `body_sha256`; block and payload digests per record; pack and index hashes |
| 4 Raw preservation | `pack.py`, `core_pipeline.py` (+ `preservation.py`, `ledger.py` of Core I) | open pack → seal → promote pack and index → verify → `RAW_PRESERVED` |
| 5 Article identity | `document_identity.py`, `jsonl.py` | append-only tables; documents, observations, versions, relations; collision refusal |
| 6 Extraction contract | `extraction.py` | record, digests, `Extractor` wrapper, baseline extractor |
| 7 Replay / re-extraction | `core_pipeline.py` | `replay_extraction` from the preservation root; new extractor version beside the old |

Package version 0.1.0 → 0.2.0 (recorded in run records and layer manifests). No runtime
dependency was added.

## 9. Not implemented, and why

| Component | Why not in this run |
|---|---|
| Discovery (feeds, sitemaps, index expansion, channel documents, discovery events) | implementable on recorded channel documents without network, but a separate stage with its own failure modes; left as the next run rather than half-built |
| Live fetcher, politeness, retries, re-fetch schedule | forbidden: acquisition gates open (O-1, O-2); `AGENTS.md` §7 |
| Channel health state | needs discovery |
| Admission labels | Phase 3; the label vocabulary is partly scientific |
| An adopted extractor, per-outlet rules | needs a gold sample and a preregistered comparison |
| Date parsing, time zones, cohort assignment | needs registered outlets with time zones; ranking of bases is unvalidated |
| Normalisation, NLP, enrichment, release, cross-corpus contract | later phases; the NLP pins are not installed |
| Syndication clusters | enrichment, Phase 4 |
| WARC conformance check with a third-party reader | no such library installed, none may be downloaded in this run |
| Run against a real preservation target | O-3 open |
| Legacy freeze manifest | O-10 not given |

## 10. Canary

`tests/test_core_pipeline.py`, class `Canary`. Input: nine recorded exchanges for one invented,
test-only outlet (`uy_diario_ejemplo`, origins under `.test`), built from four synthetic pages
(`tests/fixtures/canary/`, hashes pinned in `MANIFEST.json`), a fake PDF, a timeout and one
off-origin URL.

```text
recorded exchange → fetch record → open pack → sealed pack → promotion (pack + index)
   → RAW_PRESERVED → document identity → extraction (layer store) → document version → replay
```

What it shows (measured in the test run of §11):

| Property | Result |
|---|---|
| same inputs → same identities | a second, independent pass yields identical fetch, document, version, fingerprint and artifact ids, byte-identical identity tables and ledger, and a byte-identical sealed pack |
| raw unchanged | every body read back from the preservation root equals the fixture bytes; master hash = pack manifest hash |
| re-extraction from raw | replay of every extraction returns the stored artefact; with the workspace pack removed and an empty layer store, identity and extraction are rebuilt identically from the preservation root and the ledger |
| provenance complete | from one `document_version_id`: extractor and version → fetch → URL-key record → ledger history → pack → promotion manifest → fetch record (status, headers, run) → run record (software, components) → stored extraction and its input hash |
| no workstation dependency | no JSON record written by the canary contains the directory it ran in |
| the cases | 8 fetched + 1 failed; 4 documents, 4 versions; one article under three observed URLs and a redirect = one document with two versions; a republished body = `duplicate_of`; the redirecting URL = `moved_to`; PDF = document without version; off-origin = no document |

## 11. Tests and ablations

`python -m pytest -p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, Python 3.12.10, pytest 9.1.1.
Measured 2026-10-07 21:30 +02:00, before this report existed: **424 collected, 423 passed, 1
failed** — `test_relative_links_resolve`, because five documents link to this report. Final figure
with the report in place: see the operator's closing message (expected 424 passed).

| Module | Tests | New in this run |
|---|---|---|
| `test_acquisition_pack.py` | 46 | all |
| `test_extraction.py` | 24 | all |
| `test_core_pipeline.py` | 21 | all |
| `test_identity.py` | 68 | +2 (CPD-0003 review regressions) |
| `test_registry.py` | 60 | +1 (tracked proposal agrees with its review report) |
| `test_repository_contract.py` | 21 | +2 (decision-header test over CPD-0004, CPD-0005) |
| `test_preservation.py` | 39 | one test widened to every module of the package |
| others | 145 | — |

Cases required by the brief, and where they are tested:

| Case | Test |
|---|---|
| identical content again | canary exchange 1; `test_the_fetch_id_separates_two_fetches_of_the_same_bytes` |
| same URL, changed content | canary exchange 2 (new version, same document) |
| different URLs, identical content | canary exchange 3 (`duplicate_of`) |
| missing metadata | `sin_metadatos.html`; `test_missing_metadata_is_stated_not_invented`; `test_dates_are_stored_as_published_and_never_invented` |
| invalid content types | `test_what_cannot_be_extracted_is_labelled_not_guessed`; canary exchange 5 |
| interrupted acquisition | three crash points in the append, a crash between pack and ledger, an interrupted promotion, three torn-tail positions in the pack |
| repeated replay | `test_extraction_is_re_derived_from_preserved_bytes_alone`; `test_every_stage_can_be_repeated_without_a_second_effect` |
| extractor version change | `test_a_new_extractor_version_is_a_new_answer_and_the_old_one_stays`; non-determinism raises |
| deterministic ids | `test_same_inputs_give_the_same_identities_and_bytes`; pinned preimages |
| unchanged raw hashes | `test_raw_bytes_are_unchanged_on_the_preservation_root`; `test_raw_bytes_survive_the_pack_exactly` (including an empty body and a body containing WARC and gzip markers) |

**Ablation — what identifies an article?** One constructed set: one article under four observed
URLs in two textual states, plus two different pages whose paths differ only in case.

| Rule | "Articles" found | Error |
|---|---|---|
| (a) observed URL | 6 | splits the article four ways; its revision is unrelated |
| (b) legacy id (lower-cased URL, query kept) | 5 | still splits it four ways **and** merges the two different pages |
| (c) canonical URL key + text digest | 3 documents, 4 versions | none on this set |

This is a check on a set built to contain the known cases. It shows the rules differ as argued;
it is not a rate measured on corpus data.

**Structural check widened:** the test that preservation code has no deletion path now enumerates
every module of the package and allows exactly five named calls.

## 12. Validation classification

| Check | Kind |
|---|---|
| pinned preimages and record formats; byte-identical second pass; deterministic import; replay from preserved bytes | **reproducibility** |
| interrupted append / ledger / promotion; torn tails; crash between seal steps; damaged pack, index, manifest, layer artefact; non-deterministic extractor | **robustness** (failures injected in-process, not by killing a process) |
| the import on the real legacy database | **reproducibility** of the importer on its one real input |
| identity ablation | reproducibility of a *comparison on a constructed set* |
| — | **replicability: none** (no independent re-implementation or second environment) |
| — | **generalisability: none** (four synthetic pages, one invented outlet) |

## 13. Known limitations

- **The extractor is a baseline.** Its body-container rule is the simplest possible; on real
  templates it will be wrong in ways not yet known. It collapses whitespace inside a block.
- **The pack writer is unverified against other WARC software.** The HTTP header block in a
  response record is rendered from the fetch record. Whether stored bodies are wire bytes or
  transfer-decoded bytes is undecided and matters for conformance.
- gzip output is deterministic for one zlib build; byte-identical packs across machines are not
  guaranteed and not required (a pack is identified by the bytes that were sealed).
- Identity tables, ledger and layer store live in the runtime workspace, have no cross-process
  lock, and the duplicate check scans the version table.
- A body fetched twice is stored twice (no `revisit` records).
- The registry proposal inherits the legacy codes' inconsistent styles and has no attribute
  beyond what the legacy database held. Names that exist only in legacy directories or exported
  files are not in it.
- "Robustness" tests do not kill processes and do not run on a network share.
- The clock readings in the header bound the session; they include delegated read-only surveys
  that ran in parallel.

## 14. Remaining real decisions

Only what code and data cannot answer.

| Decision | Owner | Blocks |
|---|---|---|
| **Registry review** (O-11): which proposed outlets are registered, under which ids, with which attributes and URL rules | operator, scientific | any acquisition |
| Acquisition policy, crawler identity (O-1, O-2) | institutional | any live fetch |
| Preservation target and capacity (O-3, O-4) | institutional | second half of the Phase-1 gate; scheduled crawling |
| Review of CPD-0004 and CPD-0005 as recorded | operator | nothing now; they are in force as recorded |
| Go-ahead for the legacy freeze manifest (O-10) | operator | Phase 0 closure |
| Population and country list (O-5); cross-corpus naming and index conventions (O-6) | scientific, joint | Phases 6, 7 |

## 15. Files, working tree, next step

**Created:** `src/coprepan/` `acquisition.py`, `pack.py`, `document_identity.py`, `extraction.py`,
`core_pipeline.py`, `jsonl.py`; `tests/` `test_acquisition_pack.py`, `test_extraction.py`,
`test_core_pipeline.py`; `tests/fixtures/canary/` (four pages, `MANIFEST.json`);
`config/registry_review/legacy_registry_import_2026-10-07.json`; `docs/decisions/` CPD-0004,
CPD-0005; `docs/legacy/ARCHAEOLOGY.md`; `docs/acquisition/INDEX.md`; `docs/extraction/INDEX.md`;
this report.

**Changed:** `config/outlet_registry.json` (empty → the proposal); `pyproject.toml` and
`src/coprepan/__init__.py` (version, docstring); `tests/test_identity.py`, `test_registry.py`,
`test_preservation.py`, `tests/suites/foundation_contract.txt`, `tests/fixtures/README.md`;
`docs/STATUS.md`; the master plan (dated notes under §12, O-11 in §13); the architecture index,
terminology (§9 added), target architecture (dated note); the storage, corpus-supply, identity and
legacy indexes; the decision registry; CPD-0003 (one dated status-note row, as the registry rules
allow); `README.md`.

**Moved, deleted, overwritten:** nothing in the repository's history or evidence. Earlier run
reports unchanged. Outside the repository: the two work copies of the legacy database in the
session scratchpad were removed at the end of the run (they were this run's own temporary files);
nothing was written into any reference repository.

**Working-tree classification:** every created and changed file is committed with explicit
pathspecs in three commits (Core I closure data; core pipeline code and tests; decisions and
documentation). Nothing ignored, nothing untracked. Hashes and push result: operator's closing
message — a commit cannot name itself.

**Recommended next run (exactly one):** *discovery on recorded channel documents* — feed and
sitemap parsing with index expansion, the channel document as a preserved fetch, discovery events
linked to fetch records — without network, on fixtures; together with the WARC conformance check
if a reader can be made available. In parallel, and independent of any agent run: the operator's
registry review (O-11).

## 16. Operator report

1. **Result:** Foundation Core I is closed with the real import; the legacy system is
   reconstructed and dispositioned; the core contracts are decided and run end to end on
   recorded, synthetic input.
2. **Status:** `PASS` for the scope of §0. Claims reproducibility and robustness on fixtures;
   claims nothing about real outlets, extraction quality, WARC interoperability or any taxonomy.
3. **Consequence:** later work builds on fixed records for run, fetch, pack, identity and
   extraction. Nothing can be acquired: no fetcher, no registered outlet, gates open.
4. **Next:** discovery on recorded channel documents; the operator's registry review.
5. **Files:** §15. Nothing moved, deleted or overwritten.
6. **Untouched:** the legacy repositories and their data (read; one database file copied out and
   read as a copy), CO.RA.PAN 3.0 and the studies archive (read only), `C:\dev\corapan`. No crawl,
   no external API, no model call.
