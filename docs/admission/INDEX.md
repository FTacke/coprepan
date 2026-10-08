# Admission labels — component index

**Status: TECHNICAL LABEL IMPLEMENTED, OFFLINE — NOT VALIDATED, NOT ACTIVATED. NO CONTENT-LEVEL
LABEL EXISTS.** No corpus material has been labelled. Governing decision:
[CPD-0007](../decisions/CPD-0007_refetch-qualification-admission-labels-and-evaluation-instruments.md) §8; principle: CPD-0001 (labels, not deletion; selection at release).
Current state: [`docs/STATUS.md`](../STATUS.md). Design background:
[`TARGET_ARCHITECTURE.md`](../architecture/TARGET_ARCHITECTURE.md) §3.

---

## 1. What exists

| Thing | Code | Test |
|---|---|---|
| Label record, closed reason vocabulary, pure labelling function | `src/coprepan/admission.py` | `tests/test_admission_eval.py` |
| Append-only label table; labelling of a preserved pack | same | same; `tests/test_refetch_e2e.py` |

## 2. Record (`coprepan-admission-label/v2`, rule set `admission-technical/1`)

One label per fetch of kind `item` and rule set, in `admission/labels.jsonl` of the workspace: a
**chained** table (CPD-0010; `v1` until 2026-10-08, when no label of corpus material existed).

| Field | Content |
|---|---|
| `fetch_id`, `document_id`, `document_version_id` | what is labelled |
| `technical_status` | `TECHNICALLY_USABLE` · `TECHNICALLY_UNUSABLE` |
| `reasons[]` | `reason`, `effect` (`blocks` · `informs`), `evidence` |
| `blocking_reasons` | the reasons with effect `blocks`; empty exactly when usable |
| `measurements` | counts read off the extraction (blocks, body blocks, body characters, whitespace tokens) — descriptions, not thresholds |
| `ruleset`, `run_id`, `labelled_at`, `extraction_fingerprint`, `extraction_payload_sha256` | provenance of the label; the extractor is named by the fingerprint's extraction and, when not adopted, by the `extractor_not_active` reason |

| Reason | Effect |
|---|---|
| `http_error_status`, `http_redirect_answer`, `not_modified_answer`, `http_status_other`, `not_extractable`, `no_document`, `no_body_text` | blocks |
| `superseded_attempt`, `no_title`, `publication_date_unknown`, `author_unknown`, `section_unknown`, `language_undeclared`, `decoding_replaced_characters`, `duplicate_body_of_other_document`, `moved_from_other_document`, `extractor_not_active` | informs |

A 304 that revalidated is `TECHNICALLY_UNUSABLE` as a fetch (it has no body) and names the
document version it confirmed; the version's own label is that of the fetch holding the body.

## 3. Rules

- **A label removes nothing.** The fetch, its bytes, its extraction and its document stay.
  Whether labelled material enters a release is a selection made at release.
- **Technical only.** `TECHNICALLY_USABLE` means: a complete 2xx answer on a registered origin,
  extractable, with body text. It does not mean "an article", and it is no statement about genre,
  register, section, opinion, access class or language. A necessary condition, never a
  sufficient one.
- Labels are append-only, keyed by fetch and rule set. A new rule set labels again beside the old
  labels.
- A label made with an extractor that is not `ACTIVE` carries `extractor_not_active`.

## 4. Open

| Item | Kind | Where |
|---|---|---|
| Content-level labels: article / not article, access class (paywall, consent wall), language from content, length, type | scientific, Phase 3; needs the gold sample | master plan §11; [gold-sample design](../extraction/GOLD_SAMPLE_DESIGN.md) |
| Durable home of the label table (today the runtime workspace) | technical | storage §11 |
| The technical label on real pages | validation debt | STATUS §6 |

## 5. Milestones

- 2026-10-07 — technical admission label decided (CPD-0007 §8), implemented and tested on
  synthetic material. Stage 7 `PARTIAL`.
  Run report: [`docs/agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md`](../agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md).
