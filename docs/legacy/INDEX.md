# Legacy COPREPAN — component index

**Status: NORMATIVE (rules in force now).** The freeze described in §5 is **PLANNED, not
executed**. Governing decision:
[CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md) §2.

Figures in this document are the audit's measurements of 2026-10-06 (audit §2, §4, §13) and were
not re-measured here.

---

## 1. What "legacy" is

The legacy system is the repository at the operator's legacy checkout (`coprepan`, HEAD `3e6bdd3`
of 2026-06-15 when the audit and this bootstrap read it) together with the data that live,
gitignored, only in that working copy. It plays the role for COPREPAN 3.0 that the CO.RA.PAN 1.0
repository plays for CO.RA.PAN 3.0: a **read-only behaviour and data reference**.

| Store (in the legacy working copy) | Content |
|---|---|
| `json_annotated/` | 926 files, 30,000 articles, 29,978 annotated, **17,069,158 body tokens** — "the legacy corpus" |
| `json_raw/` | 948 files, 30,482 article records of *extracted text* (not raw input) |
| `json_raw_extended/` | 1,347 files, 12,208 records rejected by the export policy; never annotated |
| `data/db/coprepan.sqlite` | 82 outlets, 352 feeds, 771 discovery runs, 32 crawl runs, 64,932 article rows |
| `state/annotation/annotation_state.sqlite` | one row per annotated input file, with hashes and versions |
| `backup/` | 18 daily files of an earlier schema generation |

The stores are not views of one another (2,980 `json_raw` records have no DB row; 22 files were
written after the annotation run; daily files were rewritten on every export).

## 2. Rules for agents

1. **The legacy repository and its data are read-only.** Do not modify, delete, move, rename,
   normalise, migrate, re-annotate or overwrite anything there. The only exception is a later,
   explicitly authorised legacy run whose brief says so.
2. **Do not run the legacy test suite.** Three files under its `tests/` start a real multi-outlet
   crawl or insert rows at import time; a `pytest` collection would crawl live sites and write to
   the production database (audit T-8).
3. **Do not open the live SQLite databases in place.** They carry an uncheckpointed WAL; opening
   them can write. Work on a copy outside the legacy tree.
4. **The legacy code is not a template.** It is a behaviour reference. Reuse is selective and
   listed in §6; everything else is reimplemented against the 3.0 contracts.
5. **Legacy names and ids are never silently rewritten** — in the legacy tree, in copies, or in
   mappings. See [naming](../architecture/TERMINOLOGY_AND_NAMING.md) §6.
6. If code, data and documentation of the legacy system disagree, inspect actual behaviour and
   data, document the discrepancy, and do not pick the convenient reading. About 40 legacy
   `docs/*SUMMARY.md` files describe layouts the code no longer writes.

## 3. Standing of the legacy corpus

The ~17-million-token legacy corpus:

- **remains scientifically usable** and is the **reproducibility basis of the existing studies**;
- **is not `native_v3`** and is never silently declared V3 material;
- **has known provenance and extraction limitations** (below);
- **must not be silently re-annotated or overwritten**.

Known limitations, each measured by the audit:

| Limitation | Evidence |
|---|---|
| No source object for any text; nothing upstream of the extracted text can be reprocessed | audit T-1, §13.1 |
| The extractor split real words (`crecimient o` 3,100 times against `crecimiento` 12) | T-2 |
| The downstream repair is lossy in both directions (residual splits and false merges such as `atenciónal`) | T-3 |
| Paragraphs deleted by substring and length — a lexically conditioned sampling bias inside every article | T-4 |
| 16 % of records carry the crawl date as publication date | T-5 |
| Weak identity: 101 `article_id` values repeat across daily files; 339 groups of byte-identical bodies | T-6 |
| Ids are positional and per file; dependency heads are stored as text only | T-10 |
| One outlet supplies ≥ 99 % of the tokens in 9 of 18 countries; 96 % of tokens are from three months | audit §7 |

Consequence for interpretation: lexical, lemma-frequency and word-length statistics on the legacy
corpus are affected; the effect on the tense studies is **unmeasured**. No statement about the
size of that effect may be made until the re-fetch canary (§7) has measured it.

## 4. Provenance classes and pooling

| `provenance_class` | May be pooled with |
|---|---|
| `native_v3` | — |
| `legacy_refetched` | `native_v3`, with the fetch delay as a recorded attribute |
| `legacy_text_reannotated` | nothing by default; a study opts in explicitly |
| `legacy_frozen` | nothing; it is the reproducibility basis of the existing studies |

Definitions: [naming](../architecture/TERMINOLOGY_AND_NAMING.md) §5.6.

## 5. The frozen legacy release (PLANNED)

Target: **`coprepan-legacy-2026-06`** — the legacy corpus exactly as the studies read it, as one
named, hash-manifested release.

Scope of the manifest: `json_annotated/`, `json_raw/`, `json_raw_extended/`, both SQLite databases
(as checkpointed copies), `backup/`, the section CSVs the annotation joined, and the code commit.

Procedure (reading only; nothing is written into the legacy tree):

1. hash manifest written outside the legacy repository;
2. verified copy on a preservation target;
3. restore check;
4. gate: manifest verified against the live tree, and a study loader reads the frozen copy with
   identical results on a sample.

Why it matters now: the freeze is also the only backup the legacy corpus would have. Whether any
copy exists outside the legacy working copy is unknown (master plan §13, O-9). No study pins its
corpus input today; after the freeze a study can pin a hash.

**Not executed by the bootstrap run**: the preservation target is undecided (O-3). The manifest
half (step 1) needs no preservation target and can proceed on operator go-ahead; the release is
complete only with steps 2–4. See master plan §11, Phase 0.

## 6. What is reused, and what is not

| Reused (as knowledge or small tested helper) | Use in 3.0 |
|---|---|
| Curated outlet and feed list with its discovery history | seed of the outlet registry and channel list |
| Discovery strategy and the extractor-based output probe | channel qualification gate |
| Feed feedback loop | channel health state |
| ASCII slug helper (`utils/slugify_ascii.py`, tested) | proposes an id at registration; never derives one at run time |
| Labelling instead of deleting (`date_published_source`, `policy_fail_reasons`) | the admission-label principle |
| Annotation-runner design: per-stage versions, input/clean/annotation hashes, offset-recorded cleaning report, `raw` kept beside `clean`, atomic writes, state DB | template for every derived-text stage |
| Section vocabulary (`config/sections/section_map_v1.yml`) | starting point of section mapping v2 |
| Tense taxonomy and its 11 unit cases | regression material for the shared verbal-complex layer |
| Operator dashboard idea | a read-only view on ledgers |

| Not reused | Why |
|---|---|
| Crawl loop, in-thread run state | no fetch record, no resume, state lost on restart |
| Database model | an article row is URL-seen set, extraction result and status in one |
| HTML extractor | T-2, T-4; unversioned, untested |
| Export / policy routing | four coexisting layouts; rewrites daily files |
| Tense layer written into `morph` | project features inside a UD field |

Anything reused is **copied into this repository with its origin recorded** (legacy commit, path),
then owned and tested here. The legacy repository is never imported as a dependency and never
installed into the same environment (both packages are named `coprepan`).

## 7. Later, separately gated legacy work

| Work | Phase | Condition |
|---|---|---|
| **Re-fetch canary**: a stratified sample of legacy URLs through the 3.0 pipeline; measures reachability, text drift and the size of the legacy extraction defects | 5 | Phases 2–4 running |
| Decision on a full `legacy_refetched` backfill of the 2025-12 to 2026-06 window | 5 | canary result |
| `legacy_text_reannotated` | 5 | only on a study's explicit request, flagged, never the default |

Never: in-place changes to the legacy tree; migrating the legacy annotation into 3.0 as corpus;
adding `json_raw_extended` to the corpus.

## 8. Existing studies

The cross-corpus studies repository is read-only for this repository as well. Its studies stay
reproducible by reading the frozen legacy release; they are not migrated to 3.0 data. Its
workarounds are **requirements on the new cross-corpus contract, not a blueprint for it** (master
plan §9). Changes that would break those studies are not made: moving, renaming or regenerating
the legacy `json_annotated` tree (the studies hold an absolute path to it); re-annotating in place;
changing `standard_section` values or slug directory names; normalising legacy country codes in
place.

## 9. Milestones

- 2026-10-06 — legacy rules recorded (repository bootstrap). Legacy repository read, not changed.
  Freeze not executed.
- 2026-10-07 — Foundation Core I: a read-only importer for the legacy outlets and feeds exists
  ([corpus supply](../corpus_supply/INDEX.md) §15). It was **not run** on the legacy database. Of
  the legacy repository only `src/coprepan/models.py` (table and column names of `sources`,
  `feeds` and `articles`) was read. The slug helper of §6 was not copied: `registry.propose_slug` is a new,
  tested function with the same purpose.
