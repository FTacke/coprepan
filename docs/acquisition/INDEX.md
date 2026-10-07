# Acquisition — component index

**Status: CONTRACTS IMPLEMENTED FOR RECORDED EXCHANGES ONLY. There is no discovery, no fetcher and
no network code; nothing has been acquired.** Governing decision:
[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) §2–§3. Current state:
[`docs/STATUS.md`](../STATUS.md). The acquisition gates (STATUS §5) are open: **no run may fetch.**

Entry point for: the acquisition run, the fetch record, the open and sealed pack. Storage roles,
promotion and retention: [`docs/storage/INDEX.md`](../storage/INDEX.md).

---

## 1. What exists

| Thing | Code | Test |
|---|---|---|
| Acquisition run: identity, run record, result, unfinished-run listing | `src/coprepan/acquisition.py` | `tests/test_acquisition_pack.py` |
| Fetch record: builder from a recorded exchange, validator | `src/coprepan/acquisition.py` | same |
| Pack: WARC writer, scan, seal, index, manifest, fixity check, torn-tail quarantine | `src/coprepan/pack.py` | same |
| Wiring: recorded exchanges → open pack → ledger; seal → promotion → `RAW_PRESERVED` | `src/coprepan/core_pipeline.py` | `tests/test_core_pipeline.py` |

## 2. Run

`run_id` = `acq1-<UTC start>-<hash12>`. Files in the runtime workspace:
`runs/<run_id>/run.json` (written once at the start: kind, start, outlets, discovery method,
software and component versions, configuration with its hash) and `runs/<run_id>/result.json`
(written once at the end: finish, `COMPLETED` / `FAILED`, counts, pack ids, errors). A run
directory without `result.json` is an interrupted or running run; calling the acquisition again
with the same run resumes it. Run kinds: `recorded_replay` only.

## 3. Fetch record (`coprepan-fetch-record/v1`)

| Field | Content |
|---|---|
| `fetch_id` | CPD-0003: over requested URL, start instant, body hash |
| `run_id`, `outlet_id` | the run and the registered outlet |
| `outcome` | `FETCHED` (a complete response came back, any status) · `FETCH_FAILED` |
| `failure_reason` | `timeout` · `connection_error` · `incomplete_response` · `unknown` · `not_applicable` |
| `request` | `method`, `requested_url` (as requested), `headers` |
| `response` | `status`, `final_url`, `redirect_chain`, `headers` (ordered pairs, repetitions kept), `content_type` (declared media type, or `unknown`) |
| `fetch_started_at`, `fetch_finished_at` | UTC instants, microseconds |
| `body_sha256`, `body_size_bytes` | of the stored payload bytes |
| `discovery` | `channel_id`, or `unknown` |
| `policy` | `robots_decision`, `robots_txt_sha256`, `access_class_observed`, `crawler_version`, `policy_version` — all `not_applicable` for a replay |

## 4. Pack

Layout in the workspace: `packs/<pack_id>.warc.gz.open` while open; after sealing
`<pack_id>.warc.gz`, `<pack_id>.index.jsonl`, `<pack_id>.pack.json`. Format and rules: CPD-0005 §3.

State of a fetch, ledgered in `ledgers/preservation.jsonl`:

```text
DISCOVERED → FETCH_PLANNED → (bytes appended and flushed) → FETCHED → (pack sealed, every record
re-read) → RAW_VERIFIED → PRESERVATION_PENDING → (master promoted and re-read) → RAW_PRESERVED
```

## 5. Rules

- No fetch without a registered outlet; no fetch outside its run's outlets.
- The ledger is written before the state is claimed: a fetch is `FETCH_PLANNED` before its bytes
  are written and `FETCHED` only after they are on disk.
- A fetch is whole or absent in a pack. Interrupted bytes are quarantined, never dropped.
- A sealed pack is never appended to and never rewritten.
- A response with an error status or a non-HTML body is a preserved fetch. Nothing is discarded
  at acquisition time.

## 6. Open

| Item | Kind | Where |
|---|---|---|
| Acquisition policy; crawler identity | institutional | master plan §13, O-1, O-2 |
| Discovery: channel documents, discovery events, index expansion, channel health | technical, Phase 2 | master plan §11 |
| Live fetcher: politeness, retries, conditional requests, re-fetch schedule | technical, Phase 2, behind O-1 / O-2 | master plan §11 |
| Wire bytes or transfer-decoded bytes as the stored body | technical, with the fetcher | CPD-0005, "Not decided here" |
| Conformance of `pack-writer/1` against an independent WARC reader | validation debt | STATUS §6 |
| Pack rollover by size; `revisit` records; codec | technical, Phase 2 | storage §3 |

## 7. Milestones

- 2026-10-07 — run, fetch record and pack contracts decided (CPD-0005), implemented and tested on
  recorded exchanges of synthetic fixtures. No network code.
