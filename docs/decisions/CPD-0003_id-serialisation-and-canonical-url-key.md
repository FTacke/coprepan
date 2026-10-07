# CPD-0003 — Id serialisation and canonical URL key

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Status | `ACTIVE` |
| Decided by | the operator, in the brief of the Foundation Core I run (2026-10-07), which ordered the freeze the master plan schedules (§12 item 3.1: "code, property tests, a CPD") and delegated the choice between technically equivalent serialisations to that run. Recorded by that run; the wording of this record and the choices marked *chosen here* are subject to the operator's review. |
| Kind | naming |
| Scope | the byte-level form of `fetch_id`, `document_id`, `document_version_id`, `unit_id`, `sentence_id`, `token_id`, `channel_id`; the generic rule set of the canonical URL key |
| Builds on / amends / supersedes | builds on CPD-0002, which fixed the forms and left the serialisation open ("Not decided here", first item) |
| Does not change | the forms of CPD-0002 and [`TERMINOLOGY_AND_NAMING.md`](../architecture/TERMINOLOGY_AND_NAMING.md) §5.4; any legacy id; any CO.RA.PAN 3.0 id |
| Run report | [`docs/agent-runs/2026-10-07_foundation-core-i.md`](../agent-runs/2026-10-07_foundation-core-i.md) |
| Evidence | `src/coprepan/identity.py`, `src/coprepan/canonical.py`; `tests/test_identity.py` (pinned preimages, properties over generated URLs); CO.RA.PAN 3.0 as read on 2026-10-07: canonical JSON of `reservoir/asr_ready.py` (`sort_keys`, `(",", ":")`, `ensure_ascii=False`, UTF-8) and the token id form `…:TOKEN:{index:08d}` of `ling_elab/provenance.py` |

## Context

CPD-0002 decided *what* the ids look like and deferred *how their bytes are produced* to the
Phase-1 identity run. Until that was fixed, no id of these kinds could be minted, and every later
stage (fetch records, identity tables, token tables) would have had to invent its own answer.

## Decision

The normative statement of the rules is [`docs/identity/INDEX.md`](../identity/INDEX.md); the code
is `src/coprepan/identity.py`. This record fixes what may not change without a new decision.

1. **Hash function and preimage.** SHA-256, lower-case hexadecimal, everywhere. A structured
   preimage is the UTF-8 encoding of its JSON text with sorted keys, separators `,` and `:`,
   non-ASCII characters written literally, and no NaN or infinity. A truncated digest is a prefix
   of the full one.
2. **Instants** inside an id are UTC with microsecond precision and a `Z` suffix
   (`2026-10-07T18:42:17.249461Z`). A naive instant is refused.
3. **`fetch_id`** = `ft1:` + the full digest (64 hex digits) over the object
   `{"schema": "coprepan-fetch-id/v1", "requested_url", "fetch_started_at", "body_sha256"}`.
   The requested URL enters exactly as requested, without normalisation. *Chosen here:* the full
   digest instead of a truncated one.
4. **`document_id`** = `{outlet_id}:doc:` + the first 16 hex digits of SHA-256 over the UTF-8 bytes
   of the canonical URL key.
5. **`document_version_id`** = `{document_id}:v:` + the first 12 hex digits of the SHA-256 of the
   extracted text. The function takes the full digest; which bytes are "the extracted text" is
   defined with the extraction layer schema.
6. **`unit_id`, `sentence_id`, `token_id`** = `{document_version_id}:UNIT:{i}`, `:SENT:{i}`,
   `:TOKEN:{i:08d}`. `i` is the **zero-based** position within the document version, a
   non-negative integer written in decimal without padding, except for tokens, which are padded to
   eight digits (and refused beyond them) so that token ids sort in token order. *Chosen here:*
   zero-based.
7. **`channel_id`** = `{outlet_id}:ch:{slug}`, slug `[a-z0-9]+(_[a-z0-9]+)*`.
8. **Canonical URL key, rule set `coprepan-url-key/v1`.**
   - Candidate order: `rel=canonical`, final URL, requested URL. The first candidate that is a
     well-formed absolute `http(s)` URL **on a registered web origin of the outlet** is used and
     recorded as the key's basis. With no such candidate there is no key: the case is refused, not
     folded into the outlet.
   - Origin: scheme and host lower-cased, default port and trailing dot removed, IDNA-encoded;
     every registered origin folds to the outlet's first registered origin.
   - Path: **case kept**; percent-escapes upper-cased, escapes of unreserved characters decoded,
     non-ASCII characters escaped as UTF-8, dot segments removed, an empty path written `/`.
     Empty segments and a trailing slash are kept.
   - Variants: path prefixes and suffixes the outlet's rules declare (`/amp`, `/print`) are removed
     at a segment boundary, repeatedly, so the key of a key is the key.
   - Query: only the parameters the outlet's rules declare significant are kept, normalised like
     the path and sorted; every other parameter and the fragment are dropped.
   - URLs with credentials, whitespace or control characters are refused.
   - A key is recorded with its basis, its input URL, this rule-set id and the version of the
     outlet's rules, so it can be recomputed. A change of rules is a new version; the old key stays
     as an alias.
9. **Serialisation versions are part of the id or its record** (`ft1`, `coprepan-fetch-id/v1`,
   `coprepan-url-key/v1`). A different serialisation is a new version under a new decision; ids
   already minted are never recomputed (forward-only).

## Alternatives considered

| Alternative | Why not |
|---|---|
| A delimiter-joined string as the `fetch_id` preimage | A URL may contain almost any delimiter; a keyed JSON object cannot be made ambiguous by its values, and it is the serialisation CO.RA.PAN 3.0 already hashes. |
| A truncated `fetch_id` | The id is not embedded in other ids, so its length costs little; the full digest needs no collision argument. |
| One-based or padded unit and sentence indexes | Zero-based matches the positions the annotator emits; padding is only needed where lexical order must equal numeric order, which is the token table. |
| Lower-casing the path, or folding a trailing slash, in the generic rule set | The legacy `article_id` was a hash of the lower-cased URL (naming §6); case and trailing slash are significant on some servers. Folding either is an outlet rule with its own version, not a generic default. |
| Treating an off-origin canonical or redirect as the document's key | It would file a login wall or an agency original under the outlet. Off-origin is a named failure mode of the fetch and identity stages. |
| Including the rule-set version in the hashed key | The key would change on every rule revision even where the rule did not touch the URL; the version is recorded beside the key instead. |

## Consequences

- The serialisation is implemented and pinned by tests; **no id has been minted**, because no stage
  that would record one exists (`docs/STATUS.md`).
- `document_id` carries 64 bits and `document_version_id` 48 bits of a digest. The identity stage
  must therefore check, when it assigns an id, that an existing id maps to the same key (or text
  digest) and refuse otherwise; a silent collision is not acceptable. That check belongs to the
  stage that keeps the identity tables (Phase 2) and does not exist yet.
- Outlet URL rules live in the outlet registry (`url_rules`, with `web_origins`).

## Not decided here

- Which bytes constitute "the extracted text" that a document version hashes, and the name of the
  extractor version it is bound to (extraction layer schema, Phase 3).
- The per-outlet URL rules themselves (which parameters are significant, which variants fold):
  registry content, set by review per outlet.
- The discovery event id, the pack id and the syndication cluster id.
- How a superseded URL key is stored as an alias (identity tables, Phase 2).
- Whether the bases of unit and sentence indexes are shared with CO.RA.PAN 3.0 in the cross-corpus
  contract (master plan §13, O-6). The token id *form* is the one CO.RA.PAN 3.0 uses; its index
  base there was not verified by this run.
