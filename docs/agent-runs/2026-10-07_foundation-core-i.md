# COPREPAN 3.0 — Foundation Core I

```text
run_started_at:      2026-10-07T20:42:17+02:00   (first clock reading)
run_ended_at:        2026-10-07T21:02:21+02:00   (last clock reading, before this report and the commit)
timezone:            Europe/Berlin
wall_clock_seconds:  1204   (between the two readings above)
status:              PARTIAL
kind of run:         implementation, with reproducibility / infrastructure-integrity checks
EXTERNAL_API_USAGE = NONE   (no model call, no external API, no crawl, no feed or sitemap fetch;
                             the only network use was `git fetch origin` at the start)
```

**Status `PARTIAL`.** Five of the six items of Foundation Core I are implemented and tested.
Item 2 is half done: the outlet registry schema and the legacy importer exist, but
**the import was not run on the legacy database**, so no legacy outlet is in the registry and the
legacy-slug → `outlet_id` mapping does not exist (§7). The status claims code and tests on
temporary directories. It is **not** a scientific validation, **not** a production activation, and
it closes no gate of `docs/STATUS.md` §5.

## 1. Objective and operator brief

Implement, completely and without pulling later phases forward, what the master plan calls
Foundation Core I; test it; document it; commit on `main`; push if the run is completely green.
The brief delegated the choice between technically equivalent implementations to this run.

## 2. Repository states at the start (measured 20:42 +02:00)

| Repository | State |
|---|---|
| this repository | `main` `5827cd4a354cc99cf49cd71519434fdab749525f` = `origin/main` (after `git fetch`); working tree clean, nothing ignored; no foreign change |
| `legacy\coprepan` | not inspected with git in this run; one source file read (§4) |
| `corapan` (CO.RA.PAN 3.0) | read-only survey of its storage, ledger and layer-store code (§4); nothing run, nothing changed |
| `legacy\corapan_coprepan_studies`, `C:\dev\corapan` | not touched |

Baseline suite: 72 passed (the closure run's figure, same commit).

## 3. Scope, derived from the master plan

Master plan §12 item 3 defines Foundation Core I as six items; §11 Phase 1 lists the same
deliverables and its gate. Existing code was compared against each item before anything was
written.

| # | Item (master plan §12.3) | Found at start | After this run |
|---|---|---|---|
| 1 | id serialisation and canonical URL key — code, property tests, a CPD | forms only (`naming.py`: lexical rules of four id kinds) | **done**: `identity.py`, `canonical.py`, CPD-0003, `docs/identity/INDEX.md` |
| 2 | outlet registry schema; read-only import of the legacy outlets and channels from a *copy* of the legacy database; aliases; reviewable mapping | nothing | **half**: schema, validator, lookup, importer and tests exist; **import not executed**, registry empty |
| 3 | ledger and state-machine primitives | nothing | **done**: `ledger.py` |
| 4 | storage contracts: fail-closed root resolution and promotion semantics, on temporary directories | `config/storage_targets.yml` (contract only) | **done**: `storage_roots.py`, `preservation.py`, `outage_spool.py` |
| 5 | write-once layer store with fingerprint and artifact id | nothing | **done**: `layer_store.py` |
| 6 | release-gate suite scaffold and stage-status self-check | **both present** since the bootstrap (`tests/suites/release_gate.txt`, `tests/test_repository_contract.py`) | unchanged; not re-implemented. The self-check now also covers the new stage states |

Not pulled forward: pack format and sealing, fetch records, the identity stage (assignment,
identity tables, collision check), channel health, fixity, backup, any network code, any run
against a real storage root.

## 4. Inputs inspected

- This repository: `AGENTS.md`, `CLAUDE.md`, `docs/STATUS.md`, the master plan, the architecture
  index, target architecture, terminology and naming, the storage, corpus-supply and legacy
  indexes, the decision registry and CPD-0002, the closure report, all source and test files.
- CO.RA.PAN 3.0, read-only, through a delegated read-only survey (no script run): root resolution
  and its refusals, `promote_raw` and its on-disk conventions, the outage spool, the structural
  no-delete test, the ledgers, the layer store, canonical JSON. Plus one search for its token id
  form. Purpose: `AGENTS.md` §2 (inspect the working implementation first) and target
  architecture §11 (implement against the same on-disk contracts).
- Legacy COPREPAN: **one file**, `src/coprepan/models.py` (the `sources`, `feeds` and `articles`
  model definitions), found by a search for table definitions. Reason: the importer of item 2
  needs the table and column names, which the master plan does not give. Only names were taken; no
  legacy code or architecture was carried over, no legacy data was read, no legacy database was
  opened, the legacy suite was not run.

## 5. What was implemented

| Module | Provides | Design points |
|---|---|---|
| `src/coprepan/canonical.py` | canonical JSON bytes for hashing; record and line renderings; SHA-256 helpers; atomic small-file write | one preimage rule for every hashed structure; the only `unlink` is the cleanup of a `.part-` staging file and refuses any other name |
| `src/coprepan/identity.py` | `fetch_id`, `channel_id`, `document_id`, `document_version_id`, `unit_id`, `sentence_id`, `token_id` (builders, validators, parser); `canonical_url_key` | CPD-0003; functions compute and check, they mint nothing; malformed input is refused, never repaired |
| `src/coprepan/registry.py` | schema `coprepan-outlet-registry/v1`: full validation, `Registry.resolve` (registered only), `url_rules`, `legacy_alias`, `propose_slug` | every field required, `unknown` instead of omission; `registration_status` `proposed` / `registered`; a well-formed id is not a registered id |
| `src/coprepan/legacy_registry_import.py` | copy → read the copy → proposed registry + review report; command line | never opens the database in place; refuses a work directory or output inside the database's tree; never overwrites an output; proposes, registers nothing; unresolved rows are reported, not guessed |
| `src/coprepan/ledger.py` | `StateMachine`, the preservation machine of storage §4, `Ledger`, `quarantine_torn_tail` | state is the replay of the ledger, so it cannot run ahead of it; an edited, reordered or cut ledger is refused on open; a torn last line is moved to a sidecar, not dropped |
| `src/coprepan/storage_roots.py` | reader for `config/storage_targets.yml`; `resolve_root`; `probe`; `read_env_file` | refusals for unset, relative, filesystem-root, inside-checkout, unreachable, read-only; never creates a root; no fallback between roles; unreachable reports unknown usage |
| `src/coprepan/preservation.py` | `promote`, `verify_master`, `find_by_content` | `.part-<hex>` staging, landed bytes re-hashed, atomic rename, manifest after master; `promoted` / `already_preserved` / `repaired` / `duplicate_recorded`; `HashMismatch`, `IdentityConflict`; **no deletion call in the module** |
| `src/coprepan/outage_spool.py` | `preserve_or_spool`, `drain`, `SpoolPolicy` | spools only on unavailability; content refusals propagate; both bounds mandatory; the spool copy is released only after the promoted master verified |
| `src/coprepan/layer_store.py` | `fingerprint`, `artifact_id`, `LayerStore.put/get/read/manifest` | same answer again is a no-op, a different answer is `FingerprintConflict`; execution provenance is in the manifest and in neither id; an unmarked directory is never an answer |

Configuration: `config/outlet_registry.json` (valid, **empty**), `config/legacy_country_codes.json`
(22 ISO alpha-3 → alpha-2 pairs, `mapping_status: hypothesis`). No new dependency: the package
still has none at run time.

### Design decisions taken under the brief's authority

1. **CPD-0003** records the id serialisation and the URL key rule set. Two points in it are
   choices of this run and are marked so for the operator's review: the full digest in `fetch_id`,
   and zero-based unit, sentence and token indexes. The decision registry asks that a decision be
   the operator's; the basis here is the master plan's "a CPD" in item 1 together with the brief —
   the same basis on which CPD-0002 was recorded by the bootstrap run.
2. **No YAML dependency.** `config/storage_targets.yml` is read by a strict reader for exactly its
   shape; anything else is refused. CO.RA.PAN 3.0 uses a pinned PyYAML; adding a pin here was not
   needed for five scalar entries.
3. **`registration_status`** (new vocabulary, recorded in terminology §5.5): the corpus-supply
   index says the import "assigns `outlet_id` by review", so an importer may only propose.
4. **Duplicates** follow this repository's storage §6 ("recorded, not copied twice"), not the
   CO.RA.PAN default of raising: a manifest with `duplicate_of` is written, no bytes are copied.
5. **`FETCH_FAILED → FETCH_PLANNED`** is implemented although the diagram of storage §4 does not
   draw it; `retry_at` and "never a permanent blacklist" imply it. Flagged in storage §13 for the
   fetch stage to confirm.
6. **A second answer for one fingerprint raises** (target architecture §2: "an error, not a new
   version"); CO.RA.PAN 3.0 returns a status instead.

## 6. Files

Created (20): the nine modules of §5 under `src/coprepan/`; six test modules
(`tests/test_identity.py`, `test_registry.py`, `test_ledger.py`, `test_storage_roots.py`,
`test_preservation.py`, `test_layer_store.py`); `config/outlet_registry.json`,
`config/legacy_country_codes.json`;
`docs/decisions/CPD-0003_id-serialisation-and-canonical-url-key.md`; `docs/identity/INDEX.md`;
this report.

Changed (13): `docs/STATUS.md` (header, stage table and block for stages 1, 4, 5, foundation
table, Phase-1 gate row, history); `docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md` (dated status
note under §12 item 3); `docs/architecture/INDEX.md` (component, decision, contract tables);
`docs/architecture/TERMINOLOGY_AND_NAMING.md` (three dated additions); `docs/storage/INDEX.md`
(status line, open items, milestone, new §13); `docs/corpus_supply/INDEX.md` (status line, open
items, milestone, new §15); `docs/legacy/INDEX.md` (milestone); `docs/decisions/README.md`
(registry row); `README.md` (status sentence, layout); `config/storage_targets.yml` (header
comment only); `src/coprepan/__init__.py`, `src/coprepan/naming.py` (docstrings only);
`tests/suites/foundation_contract.txt` (six members).

Moved, deleted, overwritten: nothing. Earlier run reports: unchanged.

## 7. What was not done, and why

**The legacy import was not executed.** Item 2 requires reading a *copy* of the legacy database.
The command that would have copied `data/db/coprepan.sqlite` (with its WAL siblings) from the
legacy tree to the session scratchpad was refused by the session's permission layer, before it
ran. The refusal was not worked around: the database was not read by any other route. The same
command would also have printed the legacy slug helper; that file was therefore not read either,
and `registry.propose_slug` is a new function rather than the copy that legacy index §6 foresees.

Consequences, stated plainly:

- `config/outlet_registry.json` contains no outlet. Phase 1's deliverable "the legacy outlets
  imported and aliased" and Phase 0's "complete legacy-slug → `outlet_id` mapping" are open.
- The importer has only ever seen a synthetic database built from the column names of the legacy
  *model*. Whether the real database matches the model is **unverified**; the importer checks the
  columns it needs and fails closed if they are missing, and it carries every other column through
  verbatim.
- How many legacy sources lack a listed country code, fold to one proposed id, or have an unusable
  `base_url` is **unknown** until the import runs.

A second refusal concerned a one-line check of which optional Python packages are installed. It
had no consequence: no dependency was added.

## 8. Tests

`python -m pytest -p no:cacheprovider` with `PYTHONDONTWRITEBYTECODE=1`, Python 3.12.10,
pytest 9.1.1, from the repository root. Measured 2026-10-07, 21:02 +02:00, before this report
existed:

```text
328 collected: 327 passed, 1 failed
failed: test_repository_contract.py::test_relative_links_resolve — four documents linked to this
        report, which had not been written yet
```

After this report was written: see §12 for the final figure.

| Test module | Tests | Kind |
|---|---|---|
| `test_identity.py` | 66 | reproducibility: pinned preimages, refusals; **properties** over 400 generated URLs (fixed seed, no generator dependency): determinism, idempotence, invariance to fragment, insignificant parameters, parameter order, host case and origin alias; path case never folded |
| `test_registry.py` | 59 | reproducibility: schema acceptance and 32 refusals, lookup, slug proposal; importer on a synthetic database — proposals, verbatim legacy values, unresolved rows, legacy tree byte-identical afterwards, determinism, refusals |
| `test_ledger.py` | 24 | reproducibility: every undeclared transition raises, ledger before state, pinned record bytes, edited ledgers refused; **robustness**: torn-tail detection and quarantine |
| `test_storage_roots.py` | 44 | reproducibility: configuration refusals, fail-closed resolution, no fallback, inside-checkout refusal, `.env` parsing |
| `test_preservation.py` | 39 | reproducibility: promotion, idempotence, conflict, duplicate, repair, structural no-deletion check, spool routing and bounds, drain; **robustness**: interrupted copy, corrupted landing, crash between master and manifest, stale `.part-` file |
| `test_layer_store.py` | 23 | reproducibility: pinned fingerprint preimage, write-once behaviour, provenance not identity; **robustness**: abandoned write, tampered payload, manifest and marker |
| `test_naming.py`, `test_repository_contract.py`, `test_test_guards.py` | 51, 19, 3 | regression of the foundation guarantees; `test_repository_contract.py` grew from 18 to 19 because the decision-header test is parametrised over decision files |

All new tests write only under `tmp_path`, pass an explicit environment mapping, and touch neither
the network, a storage root nor a reference repository. `--suite release_gate` still selects no
test (328 deselected), as intended.

What these tests are **not**: a run on a real preservation target (second half of the Phase-1
gate, needs O-3); a test with a real legacy database; a concurrency test; a test on a network
share. The "robustness" tests inject failures in-process; they do not kill a process.

## 9. Deviations from the master plan

None in scope or order. Two things the plan asks for were not delivered (§7): the executed import
and its mapping. One thing was added that the plan implies but does not name: the outage spool,
which storage §6 lists under promotion semantics.

The plan itself was amended only by a dated status note under §12 item 3.

## 10. Known limitations

- Single writer: the ledger and the layer store have no cross-process lock.
- The duplicate check scans the manifests of an area linearly.
- No directory `fsync` after a rename (as in CO.RA.PAN 3.0); durability of a rename across a power
  loss depends on the filesystem.
- The time-zone check of the registry is lexical; it does not consult a zone database.
- `scope` and `orientation` have no closed vocabulary.
- The promotion unit is a generic sealed file: pack id, area name and relative path are parameters
  until Phase 2 defines the pack.
- CPD-0003 leaves open which bytes are "the extracted text"; `document_version_id` cannot be
  computed for real material before Phase 3.
- The index base of CO.RA.PAN 3.0's token ids was not verified; CPD-0003 names this.

## 11. Gates of the brief

| # | Condition for `PASS` | State |
|---|---|---|
| 1 | the complete Core-I scope is implemented | **not met** — item 2: import not executed (§7) |
| 2 | no later phase silently presupposed | met — every not-yet-existing dependency is named (§3, §10) |
| 3 | all new tests green | met (§12) |
| 4 | the full existing suite green | met (§12) |
| 5 | no active absolute legacy path introduced | met — `test_no_absolute_path_in_tracked_logic_or_config` passes over `src/`, `config/`, `tests/`; the importer takes its paths as arguments |
| 6 | working tree clean after the commit | see §12 |
| 7 | documentation and `docs/STATUS.md` state what was reached | met — stages 1, 4, 5 `PARTIAL` with an explicit exists / does-not-exist table; the missing import is stated in STATUS, the master plan and two component indexes |

Result: `PARTIAL`. Gates of `docs/STATUS.md` §5: none closed. The Phase-1 core gate stays open;
its temporary-directory half now has passing tests.

## 12. Final test figure, commit and working tree

Final suite after this report was written (measured before the commit): **328 passed**, exit 0.

The commit that contains this report cannot name itself; its hash is `HEAD` of `main` after this
run and is given in the operator's closing message. **It was not pushed**: the brief allows the
push for a completely green run, and this run is `PARTIAL`. `origin/main` stays at `5827cd4`.

Working-tree classification: every created and changed file of §6 is committed with explicit
pathspecs; no ignored and no untracked entry remains. Outside the repository: commit-message files
in the session scratchpad and nothing else (the copy of the legacy database was never made).

## 13. Recommended next run

One short run, on the operator's decision about the refused step: execute the legacy import on a
copy of the legacy database, commit the proposed registry and its review report, and correct the
importer if the real database differs from the model. Then the operator reviews the proposal. The
next step of the master plan after that is Phase 2, which stays blocked by O-1 to O-4.

## 14. Operator report

1. **Result:** the core primitives of Phase 1 exist and are tested — identity, registry schema,
   ledger, storage roots, promotion, spool, layer store. The registry is empty.
2. **Status:** `PARTIAL`. Claims code and tests on temporary directories; claims no validation,
   no activation, no closed gate, and no test against real legacy data or a real storage root.
3. **Consequence:** later stages can be built on fixed id bytes and fixed storage semantics.
   Nothing can be acquired: the acquisition gates are open and no outlet is registered.
4. **Next:** the legacy import run (§13).
5. **Files:** §6. Moved, deleted, overwritten: nothing.
6. **Untouched:** the legacy repositories and their data (one legacy source file read, nothing
   else), CO.RA.PAN 3.0 (read only), `C:\dev\corapan`, the studies archive; no crawl, no external
   API; `origin/main` unchanged.
