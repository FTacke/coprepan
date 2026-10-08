# Joint storage-management contract in force; the outage spool wired into the acquisition path

```text
run_started_at:      2026-10-08T12:50:23+02:00 (first clock reading of the joint run)
run_ended_at:        see the joint report (this file is committed before the run closes)
timezone:            Europe/Berlin
```

**Status: PASS** for this repository's part: `crosscorpus-storage/v1` is pinned and in force
(CPD-0015), this repository's implementation passes every shared reference case, the outage spool
is in the acquisition path, and the joint check with the sister checkout is `OK`.

**What the status does not claim.** No backup exists. The interim primary on `D:` is a sole copy
and holds its target marker only. The outage path has run on temporary directories with synthetic
packs; no real outage has occurred, and no driver calls the path yet (the canary driver is not
built). The institutional file system is not configured, not created and qualified by nothing. No
request was made to any outlet; the acquisition policy's enabling switch is still off. Nothing is
validated scientifically. The pinned release contract (`crosscorpus-release/v1`, revision 1) was
not touched.

**Kind of run:** decision and implementation. Not a scientific validation, not an activation.

`EXTERNAL_API_USAGE = NONE`. No network use at all.

**This is the CO.PRE.PAN part of one joint run.** The run was carried out from the CO.RA.PAN
repository with explicit write scope over both sister repositories. The joint report — starting and
implementation commits of both repositories, the contract, the topology matrix of both corpora,
all test results, the copy / pending / backup status and the remaining external prerequisites — is
in CO.RA.PAN:

```text
corapan: docs/agent-runs/2026-10-08_crosscorpus-storage-contract-implementation-and-migration-preparation.md
```

## 1. Starting state

`main` = `origin/main` = `98682c413d1aff92d52b019d9908939a6a925783`, tree clean. Baseline suite on
that commit: 1119 passed, 1 skipped (the symbolic-link test this account cannot run).

Inputs read: `AGENTS.md`; CPD-0005, CPD-0009, CPD-0014; `docs/storage/INDEX.md`;
`docs/agent-runs/2026-10-08_crawler-site-storage-o2-o3-interim.md`; `src/coprepan/storage_roots.py`,
`preservation.py`, `outage_spool.py`, `core_pipeline.py`, `recovery.py`, `exclusive.py`,
`release_contract.py`; `config/storage_targets.yml`, `.env.example`; the names (not values beyond the
storage roots) of this workstation's `.env`.

## 2. What was found

- Roles, fail-closed resolution, separation, promotion and the spool module already satisfied the
  contract's invariants; `tests/test_storage_architecture.py` and `tests/test_preservation.py`
  guard them.
- **One runtime deviation:** the spool was not in the acquisition path (CPD-0014 §8 recorded it).
  An unavailable target left the pack pending in the workspace — safe, but the spool role existed
  without being used, and the contract's P-invariants about a spooled pending copy were untested on
  the path that matters.
- **One latent defect found while wiring:** a pending record was named by object id alone. A pack
  and its index have the same object id in two areas, so spooling both would have made the second
  record overwrite the first. No spool held a record; nothing was lost.

## 3. What was changed

| File | Change |
|---|---|
| `contracts/crosscorpus-storage-v1/CONTRACT.md`, `conformance/CASES.json` | new: verbatim copy of the bundle, digest `8d17fc214076b21e47774d228e016dfe36484b29ce0ecad693456c07f9018fb3` |
| `config/crosscorpus/contract_pins.json` | new entry `crosscorpus-storage/v1`, status `IN_FORCE`; the release-contract entry untouched |
| `src/coprepan/storage_contract.py` | new: this repository's implementation of the contract's decisions; pin and bundle check |
| `src/coprepan/storage_roots.py` | `separation_codes`; `validate_role_separation` decides by the contract's function and accepts the sister's roots |
| `src/coprepan/outage_spool.py` | pending record per (area, object); `spool_object` as the public entry for an already known outage |
| `src/coprepan/core_pipeline.py` | `preserve_pack`, `drain_spooled_packs`, `PackPreservation`; `seal_and_preserve` unchanged in behaviour |
| `src/coprepan/http_acquisition.py` | module documentation names `preserve_pack` as the step that follows |
| `scripts/storage_contract.py` | new, read-only: `check`, `status`, `compare-sister`, `migration-inventory`, `migration-verify` |
| `tests/test_storage_contract.py` | new, 99 tests; registered in suite `foundation_contract` |
| `tests/test_preservation.py` | one expectation: the pending record's new name |
| `docs/decisions/CPD-0015_…`, `docs/decisions/README.md`, `docs/architecture/INDEX.md`, `docs/architecture/TERMINOLOGY_AND_NAMING.md` §18, `docs/storage/INDEX.md` §5 / §19 / §20, `docs/STATUS.md` | decision, registry rows, terms, mapping, the preservation step, topology record, migration parameters, status |

Nothing was moved, deleted or overwritten in any storage root. No `.env` was changed. The
workspace, the spool and the interim primary were read by `status` only.

## 4. Checks and results

| Check | Result |
|---|---|
| `python -m pytest -p no:cacheprovider -q tests/test_storage_contract.py` | 99 passed |
| full suite after the code changes (`python -m pytest -p no:cacheprovider -q`) | 1218 passed, 1 skipped |
| storage modules with their temporary files on the interim primary's file system (`--basetemp` in a directory of this run below `…\coprepan\_qualification`, removed afterwards; `test_storage_contract`, `test_preservation`, `test_core_pipeline`, `test_storage_architecture`, `test_storage_roots`) | 222 passed |
| `python scripts/storage_contract.py check` | no problems; the copy is the pinned bundle |
| `python scripts/storage_contract.py status` | `PRESERVATION`, `RUNTIME`, `SPOOL`, `REPOSITORY` `AVAILABLE`; `BACKUP`, `DISTRIBUTION`, `EXCHANGE` `NOT_CONFIGURED`; separation `SEPARATED` (the sister's roots included); 0 pending records; backup of the preservation primary `NOT_CONFIGURED` |
| `python scripts/storage_contract.py compare-sister` | `joint_check: OK` (pins equal, bundle copies identical, no overlap) |
| full suite on the final tree, with the documentation | see the joint report §6 |

The first attempt at the `--basetemp` run failed with 125 setup errors because the parent
directory did not exist; it was created and the run repeated. The `222 passed` figure is the
repeated run. That result is from local NTFS and qualifies no network file system.

## 5. Gates

None touched. `O-3` stays as CPD-0014 left it (interim). Open production gates unchanged.

## 6. Working tree at the end

Only this run's files, committed with explicit pathspecs; no foreign change was present.

## 7. Recommended next run

The canary driver, calling `preserve_pack` — a separate order (not in this run's scope).

## 8. Operator report

See the joint report §11.
