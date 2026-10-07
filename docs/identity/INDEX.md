# Identity — component index

**Status: NORMATIVE for id serialisation and the canonical URL key (implemented, unit-tested).
The identity stage — document and version assignment, append-only identity tables, the
`duplicate_of` and `moved_to` relations — is implemented and tested on recorded exchanges of
synthetic fixtures only (§7). Syndication clusters are NOT IMPLEMENTED. No id has been minted for
corpus material.** Governing decisions:
[CPD-0002](../decisions/CPD-0002_terminology-and-naming-model.md) (forms),
[CPD-0003](../decisions/CPD-0003_id-serialisation-and-canonical-url-key.md) (bytes),
[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) §4 (identity policy).
Current state: [`docs/STATUS.md`](../STATUS.md).

Entry point for: how an id is serialised, how a canonical URL key is computed, and what the
identity stage still has to build. Terms and forms:
[`TERMINOLOGY_AND_NAMING.md`](../architecture/TERMINOLOGY_AND_NAMING.md) §5. Design of the stage:
[`TARGET_ARCHITECTURE.md`](../architecture/TARGET_ARCHITECTURE.md) §6.

---

## 1. What exists

| Thing | Code | Test |
|---|---|---|
| Canonical bytes for hashing; SHA-256 helpers | `src/coprepan/canonical.py` | `tests/test_identity.py`, `tests/test_layer_store.py` |
| `fetch_id`, `channel_id`, `document_id`, `document_version_id`, `unit_id`, `sentence_id`, `token_id`: builders, validators, parser | `src/coprepan/identity.py` | `tests/test_identity.py` |
| Canonical URL key, rule set `coprepan-url-key/v1` | `src/coprepan/identity.py` | `tests/test_identity.py` (stated cases; properties over 400 generated URLs with a fixed seed) |

**Nothing is minted.** These functions compute and check ids; an id belongs to production material
only when a stage has recorded it.

## 2. Serialisation

One rule for every hashed structure: SHA-256 over the UTF-8 JSON text with sorted keys, separators
`,` `:`, non-ASCII written literally. Lower-case hexadecimal. A truncation is a prefix.

| Id | Bytes |
|---|---|
| `fetch_id` | `ft1:` + 64 hex over `{"schema":"coprepan-fetch-id/v1","requested_url":…,"fetch_started_at":…,"body_sha256":…}`; the instant as `YYYY-MM-DDTHH:MM:SS.ffffffZ` (UTC); the URL exactly as requested |
| `document_id` | `{outlet_id}:doc:` + first 16 hex of SHA-256 over the UTF-8 canonical URL key |
| `document_version_id` | `{document_id}:v:` + first 12 hex of the SHA-256 of the extracted text |
| `unit_id` / `sentence_id` | `{document_version_id}:UNIT:{i}` / `:SENT:{i}`, zero-based, decimal, unpadded |
| `token_id` | `{document_version_id}:TOKEN:{i:08d}`, zero-based; an index of 10⁸ or more is refused |
| `channel_id` | `{outlet_id}:ch:{slug}` |

## 3. Canonical URL key (`coprepan-url-key/v1`)

Input: the outlet's rules from the registry (`web_origins`, `url_rules`) and up to three URLs of a
fetch. Output: the key plus the record needed to recompute it (`url_key`, `url_key_basis`,
`url_key_input`, `url_key_ruleset`, `outlet_url_rules_version`).

1. Take the first of `rel=canonical`, final URL, requested URL that is a well-formed absolute
   `http(s)` URL on a registered web origin. None → `OffOriginError`: the fetch has no key under
   this outlet.
2. Replace its origin by the outlet's first registered origin.
3. Normalise the path: escapes upper-cased, unreserved characters unescaped, non-ASCII escaped,
   dot segments removed, empty path → `/`. **The case of the path is kept.**
4. Remove the outlet's declared variant prefixes and suffixes at segment boundaries.
5. Keep only the declared significant query parameters, normalised and sorted. Drop the fragment.

Properties the tests hold the key to: deterministic; idempotent (the key of a key is the key);
independent of fragment, insignificant parameters, parameter order, host case and origin alias;
never independent of path case.

## 4. Rules

- An id function refuses malformed input; it never repairs it.
- A hash parameter is named for what it covers (`body_sha256`, `extracted_text_sha256`).
- An `outlet_id` that is merely well-formed is not enough to key a URL: rules come from a
  *registered* outlet (`Registry.url_rules`).
- A change of serialisation or of the generic rule set is a new version under a new decision; ids
  already recorded are not recomputed.

## 5. Open

| Item | Kind | Where |
|---|---|---|
| URL-key aliases after a rule change (a superseded key kept as an alias) | technical, with the first rule revision | CPD-0003 §8 |
| Syndication (near-duplicate) clusters across outlets | enrichment, Phase 4 | target architecture §6 |
| Durable location of the identity tables (today: the runtime workspace) | technical | CPD-0005, "Not decided here" |
| A content index for the duplicate check (today a scan of the version table) | technical | §7 |
| Per-outlet URL rules | registry content, by review | [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md) |
| Shared index bases in the cross-corpus contract | joint with CO.RA.PAN 3.0 | master plan §13, O-6 |

## 6. Milestones

- 2026-10-07 — id serialisation and canonical URL key frozen (CPD-0003), implemented and
  unit-tested (Foundation Core I). No identity stage, no minted id.
- 2026-10-07 — CPD-0003 reviewed against CO.RA.PAN 3.0 (§8): both of its own choices kept.
  Identity policy decided (CPD-0005 §4); identity tables implemented (§7).
- 2026-10-07 — revalidation observations (CPD-0007 §4): a 304 confirms an existing version and
  creates none.

## 7. The identity stage (CPD-0005 §4)

Code: `src/coprepan/document_identity.py`; tests: `tests/test_core_pipeline.py`.

| Table (append-only, one JSON object per line) | Row |
|---|---|
| `identity/documents.jsonl` (`coprepan-document-identity/v1`) | `document_id`, `outlet_id`, `url_key`, rule-set ids, `first_fetch_id` |
| `identity/observations.jsonl` (`coprepan-document-observation/v1`) | per fetch: `document_id`, requested URL, final URL, `rel_canonical`, the URL-key record, `head_scan` version |
| `identity/versions.jsonl` (`coprepan-document-version/v1`) | per (version, fetch): `document_version_id`, `document_id`, `extracted_text_sha256`, `body_text_sha256`, extractor and version, extraction fingerprint |
| `identity/relations.jsonl` (`coprepan-document-relation/v1`) | `relation` (`duplicate_of` · `moved_to`), document, target, evidence |

| Case | Outcome |
|---|---|
| the same bytes fetched again, or the same article under a tracking, mobile or AMP URL | one document, one version, one more observation |
| the same URL with changed text | the same document, a new version |
| another URL of the outlet with the same BODY text | another document, `duplicate_of` the first |
| a URL that now redirects to, or declares as canonical, another existing document | `moved_to` from the old document to the new |
| a response that cannot be extracted (PDF, image) | a document, no version |
| a 304 that revalidates a fetch the tables know *(CPD-0007 §4)* | one more observation (`url_key_basis: revalidation`) of that fetch's document and version; no new version, no extraction |
| a 304 that revalidates a fetch the tables do not know | nothing assigned (`revalidation_target_unknown`); the fetch stays preserved |
| a permanent redirect to another URL of the outlet *(CPD-0007 §5)* | the candidate moves ([acquisition](../acquisition/INDEX.md) §11); the document follows the rules above |
| no URL of the fetch on a registered origin | no document; the fetch stays preserved |
| a truncated id that would stand for two keys or two texts | refused (`DocumentIdCollision`) |

*Added 2026-10-07 (CPD-0006 §1, audit of the identity policy):*

- **Only a fetch of kind `item` becomes a document.** A channel document or a robots file is
  preserved evidence and never enters the identity tables.
- Each observation also keeps `requested_url_key` and `final_url_key` — the keys of the request
  and of the final URL on their own.
- **A canonical on another site** (typical of syndicated copy) never keys the document; it is
  kept in the observation for a later syndication layer.
- **Many pages declaring one canonical** (a section or home page — a template defect) are filed
  as one document with many versions. The rule is not bent to hide this:
  `IdentityTables.canonical_collapse_suspects()` lists documents keyed by `rel=canonical` whose
  fetches were answered at several different final URLs. It is a diagnosis for review and
  changes no id; the correction is an outlet URL rule with a new version, and every fetch's own
  key is on record to re-derive from. Legitimate variants of one article that the outlet's rules
  do not fold yet produce the same picture — hence a list to look at, not an automatic split.
- The head scan reads the body after undoing its content coding; an undecodable body has no
  readable head and is keyed by its URLs.

Ablation behind "an article is not its URL": `tests/test_core_pipeline.py`,
`test_ablation_url_as_identity_versus_canonical_key_plus_text`. On one controlled set (one
article under four URLs in two textual states; two pages whose paths differ only in case) the
observed URL yields 6 "articles", the legacy lower-cased URL 5 (splitting the article and merging
the two pages), the canonical key 3 documents with 4 versions. This is a check on a constructed
set, not a measurement on corpus data.

## 8. Review of CPD-0003 against CO.RA.PAN 3.0 (2026-10-07)

| Choice of CPD-0003 | CO.RA.PAN 3.0, as read on 2026-10-07 | Outcome |
|---|---|---|
| full SHA-256 digest in `fetch_id` | has no fetch or capture id; uses full SHA-256 for content hashes and truncations of 8 to 32 digits for derived ids | **KEEP.** A fetch id is not embedded in other ids, there will be very many of them, and the full digest needs no collision argument. |
| zero-based unit, sentence and token indexes | token index is spaCy `token.i` (zero-based, punctuation included); sentence index is `enumerate(doc.sents)` (zero-based); no decision fixes either — the base lives only in code | **KEEP.** Same base; no reason to differ. |

Differences that remain, deliberately: CO.RA.PAN writes `…:SENTENCE:{i:05d}` and counts tokens
*per analysis unit (turn)*; COPREPAN writes `…:SENT:{i}` (the form of CPD-0002) and counts
*per document version*, because a press document has no turn and its ids hang on the version. A
second, one-based index space exists inside CO.RA.PAN's canonical record; it is not the id base.
Mapping the two conventions is a matter of the cross-corpus contract (master plan §13, O-6).
For Phase 4: the head of a root token is the token itself in CO.RA.PAN, not a sentinel.
Regression tests: `test_index_base_is_zero_as_reviewed_for_cpd_0003`,
`test_fetch_id_keeps_the_full_digest_as_reviewed_for_cpd_0003`.
