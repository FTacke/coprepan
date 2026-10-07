# CPD-0002 — Terminology and naming model

| Field | Value |
|---|---|
| Date | 2026-10-06 |
| Status | `ACTIVE` |
| Decided by | the operator, in the brief of the repository-foundation bootstrap run (2026-10-06), which made naming part of the foundation and fixed its principles; consolidated from audit §15–§17. Recorded by that bootstrap run; the wording of this record is subject to the operator's review that follows the bootstrap. |
| Kind | naming |
| Scope | every human-facing name, machine identifier, vocabulary value and schema id newly written by COPREPAN 3.0 |
| Builds on / amends / supersedes | builds on CPD-0001 |
| Does not change | any existing name, id or value in the legacy repository, the legacy corpus, the studies repository or `corapan_playground`; CO.RA.PAN 3.0's own conventions (they are extended, not altered) |
| Run report | [`docs/agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md`](../agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md) |
| Evidence | audit §15 (inventory of names in use and their conflicts), §16 (proposed model), §17 (legacy compatibility); CO.RA.PAN 3.0 decision S0/D9 and `config/radio_registry.json` `id_convention`, read 2026-10-06 |

## Context

Three repositories use three country conventions and eight column names for a country; one outlet
appears under two slugs and slugs repeat across countries; "source", "segment", "raw", "v3",
"batch" and "document" each mean several things; ids repeat across files and shift when a file
grows (audit §15). The studies carry workarounds for each of these.

## Decision

The normative text is
[`docs/architecture/TERMINOLOGY_AND_NAMING.md`](../architecture/TERMINOLOGY_AND_NAMING.md). This
record fixes what that document may not change without a new decision:

1. **Levels are kept apart.** `corpus_id` (`coprepan`, `corapan`); pipeline `generation` (`legacy`,
   `v3`) as an attribute; `release_id`; schema ids `<namespace>-<thing>/v<n>`. A generation number
   is not a release number and not a schema version, and never appears in a `corpus_id`, a
   `release_id` or a schema id.
2. **Human-facing style.** *CO.PRE.PAN* names the corpus, *COPREPAN 3.0* names the pipeline
   generation and this engineering project, *CO.RA.PAN* / *CO.RA.PAN 3.0* the sibling as its
   repository writes it. No "1.0" or "2.0" is retro-assigned to the legacy press system.
3. **`country_id`** is ISO 3166-1 alpha-2, lower case. Alpha-3 is a display and compatibility
   label.
4. **`outlet_id`** is `{country_id}_{outlet}`, pattern
   `^[a-z]{2}_[a-z0-9]+(?:_[a-z0-9]+)*$`, registry-assigned, never derived from a display name at
   run time.
5. **Persistent ids are permanent; slugs and display names may evolve.** The id kinds are
   `country_id`, `outlet_id`, `channel_id`, `fetch_id`, `document_id`, `document_version_id`,
   `unit_id`, `sentence_id`, `token_id`, `release_id`. Content-addressed where the content is the
   identity, registry-assigned where an institution is. Sentence, unit and token ids hang on the
   document version and are never positional in a container file.
6. **One term per level**, as defined in the terminology table; "raw" is reserved for source
   objects, "source" is retired as a name for the outlet.
7. **Vocabulary.** Canonical machine values are English lower-case snake case; state tokens are
   upper case; closed vocabularies carry explicit value states; unmeasured is
   `NOT_YET_MEASURABLE`.
8. **Forward-only legacy naming.** Nothing historical is renamed. Legacy names resolve through
   versioned mappings with a `mapping_status`. Legacy token, sentence, segment and file ids are
   valid only inside the frozen legacy release and are not mapped.
9. **Own decision namespace** `CPD-<nnnn>`; environment prefix `COPREPAN_`; schema namespace
   `coprepan-`.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Encode the generation in the corpus id (`coprepan3`) | A corpus outlives a pipeline generation; a release may mix provenance classes; and the CO.RA.PAN 1.0 schema ids named `…/v3` show how a number inside a name is later misread. |
| Keep alpha-3 upper-case country codes, as the legacy corpus and the studies do | CO.RA.PAN 3.0 has already decided alpha-2 lower case; a second canonical convention is the problem being solved. Alpha-3 stays available as a label. |
| Derive `outlet_id` from the display name with the slug helper | That is how the legacy system produced `elpaís`, `laestrelladepanamá` and two slugs for one outlet. |
| Map legacy token and sentence ids to 3.0 ids | No stable correspondence exists: the legacy ids are positional and per file, and the legacy text differs from any re-extracted text. |

## Consequences

- `src/coprepan/naming.py` implements the lexical rules of clauses 1, 3, 4 and the provenance
  classes; `tests/test_naming.py` pins them.
- The complete legacy-slug → `outlet_id` mapping is a deliverable of the registry work (master
  plan §11).

## Not decided here

- The **byte-level serialisation** of `fetch_id`, `document_id`, `document_version_id`,
  `unit_id`, `sentence_id` and `token_id` (hash inputs, encodings, separators, truncation). The
  forms in the terminology document are the target; they are frozen with tests by the Phase-1
  identity run under a new CPD. Until then no id of these kinds is minted for production material.
- The name of the **shared cross-corpus namespace** (working name `crosscorpus-`) and the name of
  the shared register field (working name `production_mode`) — joint decisions with CO.RA.PAN 3.0.
- The **country list** of the corpus.
- The exact value sets of registry vocabularies (`outlet_type`, `access_model`, …): proposed in
  the corpus-supply index, frozen with the registry schema.
- Publication branding of the generation name.
