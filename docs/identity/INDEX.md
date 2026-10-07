# Identity — component index

**Status: NORMATIVE for id serialisation and the canonical URL key (implemented, unit-tested).
The identity *stage* — assigning documents and versions, identity tables, duplicate and
syndication relations — is NOT IMPLEMENTED.** Governing decisions:
[CPD-0002](../decisions/CPD-0002_terminology-and-naming-model.md) (forms),
[CPD-0003](../decisions/CPD-0003_id-serialisation-and-canonical-url-key.md) (bytes).
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
| Identity stage: document and version assignment from fetch records, append-only identity tables, collision check, URL-key aliases | technical, Phase 2 | master plan §11 |
| Duplicate and syndication relations | technical, Phase 2 / Phase 4 | target architecture §6 |
| The bytes of "the extracted text" | technical, Phase 3 | CPD-0003, "Not decided here" |
| Per-outlet URL rules | registry content, by review | [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md) |
| Shared index bases in the cross-corpus contract | joint with CO.RA.PAN 3.0 | master plan §13, O-6 |

## 6. Milestones

- 2026-10-07 — id serialisation and canonical URL key frozen (CPD-0003), implemented and
  unit-tested (Foundation Core I). No identity stage, no minted id.
