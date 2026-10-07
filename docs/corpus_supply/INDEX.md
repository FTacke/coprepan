# Corpus Supply — component index

**Status: NORMATIVE TARGET — REGISTRY SCHEMA ONLY.** The registry schema, its validator and the
legacy importer exist (§15). **The registry holds no outlet: the legacy import has not been run on
the legacy database, and nothing is registered.** No supply snapshot and no acquired material
exist. Governing decision:
[CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md) §5.
Current state: [`docs/STATUS.md`](../STATUS.md).

Corpus supply answers: which outlets, in which countries, over which time, with which mix — and
how that is monitored. Its aim is **coverage by design**: a transparent, controlled and
documentable supply. It is *not* statistical representativeness of "the press of a country", which
has no enumerable population.

---

## 1. Why this exists

The legacy corpus was shaped by crawlability, not by design (audit §7.2, measured 2026-10-06):

- In 9 of 18 countries one outlet supplies at least 99 % of the tokens. A "country effect" there
  cannot be told from a house style.
- 96 % of the tokens are from three months (2025-12 to 2026-02); there is no temporal overlap with
  either radio corpus.
- Which outlets have data was decided by whether a flat feed existed and the generic extractor
  coped. The registry had no field for outlet type, ownership or region, so the mix cannot even be
  described.
- Genre mix differs by country as an artefact of per-outlet section capture.
- Syndicated copy crosses country cells undetected.

## 2. The supply cell

The unit of supply is the **corpus cell**:

```text
country × outlet × corpus cohort
```

- **corpus cohort** — the calendar quarter of the *publication date in the outlet's local time*
  (the CO.RA.PAN cohort rule, with the press date basis). A property of the material; derived on
  demand, never stored as an editable opinion.
- **processing cohort** — a batch of work (a run, a wave). A property of the work; it has no field
  that could hold a publication time, and it is never a batch boundary of the corpus.
- **Provenance is never an admission filter.** Material is not excluded from the corpus merely
  because it was first acquired by a canary, a pilot or a qualification run.

## 3. Publication date and its basis

Every date carries its basis. CO.RA.PAN 3.0 ranks its bases (broadcast date strong, publication
date as fallback, else undated); the press analogue below is a **proposed** ranking, not yet
validated on data:

| Rank | Basis | Source |
|---|---|---|
| 1 | structured metadata of the article | JSON-LD, OpenGraph, HTML meta |
| 2 | channel document | `pubDate` / `lastmod` of the feed or sitemap entry the URL was found in |
| 3 | URL pattern | a date encoded in the path, per outlet rule |
| — | `unknown` | belongs to no corpus cohort |

The ranking and the exact basis tokens are frozen with the extraction metadata schema (Phase 3).
What is decided now:

- **The fetch instant is never a publication date** and never routes a record into a cohort.
- Publication timestamps are converted with the outlet's registered **IANA time zone**. An outlet
  without a registered zone is a refusal — neither UTC nor the workstation's zone is a defensible
  substitute. DST gaps and folds resolve to named outcomes, not silently.
- Run/operator time, outlet-local publication time and fetch/processing time are three distinct
  fields, never substituted for one another.

## 4. Outlet registry attributes

All with an explicit `unknown`:

| Attribute | Values / content |
|---|---|
| `outlet_id`, `country_id`, display name(s) with validity | [naming](../architecture/TERMINOLOGY_AND_NAMING.md) §5 |
| `outlet_type` | `national_reference`, `popular_tabloid`, `regional`, `digital_native`, `state_official`, `news_agency`, `broadcaster_website` |
| `outlet_group` | publisher group — the handle for ownership and syndication analyses |
| seat `city`, `region`, scope | |
| orientation | optional, sourced |
| `access_model` | `open`, `metered`, `hard_paywall` |
| `medium` | `print_and_web`, `web_only` |
| editions, `web_origins[]` | |
| `timezone` | IANA zone |
| channels | each with id, kind, URL history and health state |
| `legacy_aliases[]` | every observed legacy slug variant, per country code |
| `same_outlet_basis` | the recorded basis for treating domains/editions as one outlet |

The registry is versioned in git and is the source of truth; a runtime never derives an id from a
display name. The vocabulary values above are the audit's proposal and are frozen by the Phase-1
registry schema.

Which outlet types count as "press" for the default release is an open scientific question (master
plan §13, O-5). The registry records the type either way.

## 5. Outlet eligibility

An outlet is eligible when it (a) publishes original editorial content in Spanish for the country
cell, (b) has at least one channel that passes the output probe, (c) is reachable without bypassing
an access control, and (d) can be dated on a strong basis for most of its articles. Eligibility is
**recorded with evidence**, not decided ad hoc in a UI.

## 6. Orientation targets

Targets steer acquisition. They are **not admission gates and not quotas**.

Per country:

- several independent outlets — at least three, from at least two publisher groups;
- at least one national reference outlet and at least one outlet of another type (regional,
  popular or digital-native);
- no single outlet above half of a country-cohort cell **at release time** — enforced by the
  release selection view, not by discarding data at ingest;
- continuous coverage: every calendar week of a cohort represented for the core outlets.

Each number addresses a confound named in §1; the numbers are to be justified against the studies'
sparse-cell thresholds before they are frozen (Phase 6). Until then they are orientation, and a
round number is not its own justification
([methodology](../methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md) §4).

## 7. Preserve first, balance later

> Acquisition takes everything a qualified channel offers and labels it. Selection and balancing
> happen as documented, versioned views at release time.

- Material is **never discarded at crawl time to force a target distribution**, and never to make
  cells equal. A later study must be able to choose a different balance from the same preserved
  material.
- Balancing and study selection belong to versioned release and selection views.
- "Preserve first" is not "acquire everything": what is acquired follows the registry and the
  acquisition policy; what has been legitimately acquired is preserved intact.

## 8. Channel health

A channel has a state (`ACTIVE`, `EMPTY`, `FAILING`, `BLOCKED`) with last success and freshness.
The legacy feed feedback loop (deactivation after empty runs) becomes this state; a state change is
ledgered and reversible, never a silent permanent deactivation.

## 9. Syndication and duplicates

Exact duplicates and near-duplicate / syndication clusters are recorded as relations
([target architecture](../architecture/TARGET_ARCHITECTURE.md) §6), per cell and across cells.
Whether a release keeps one representative or all is a selection-view decision. Agency credit
lines are kept as typed blocks, so agency copy can be labelled rather than lost.

## 10. Supply monitoring

A regenerable snapshot plus frozen, named snapshots. Per cell: fetched, preserved, admitted,
tokens; top-outlet share and effective number of outlets; days covered; date-basis mix; section and
article-type mix; duplicate and syndication rate; channel health; admission-label counts.

- An unmeasured axis reports **`NOT_YET_MEASURABLE`** — a `0` is a measurement claim.
- The snapshot is decision support, not an optimiser.
- Frozen snapshots pin their files by hash and are never edited.

## 11. Priority logic for expansion

1. countries where CO.RA.PAN acquires and press has no second outlet;
2. countries with no press at all in the legacy corpus (Ecuador, Nicaragua — registered outlets, no
   yield: they need archive/index discovery, not new names);
3. missing outlet types within a country;
4. depth in outlets already qualified.

Archive backfill follows the pattern census → select → arm → run → reconcile.

## 12. Legacy as seed

The legacy database holds the curated starting knowledge: 82 outlets in 20 countries, 352 feeds
with type, origin, score, status and failure reason, 771 discovery runs (audit §3). It seeds the
outlet registry and the channel list. Import is read-only against the legacy repository, records
every observed slug variant as an alias, and assigns `outlet_id` by review — it does not inherit
the legacy slugs as ids. See [`docs/legacy/INDEX.md`](../legacy/INDEX.md).

## 13. Open

| Item | Kind | Where |
|---|---|---|
| Population: which outlet types enter the default release | scientific | master plan §13, O-5 |
| Shared country list with CO.RA.PAN (Puerto Rico, United States, Equatorial Guinea) | scientific | master plan §13, O-5 |
| Orientation-target numbers and their rationale | scientific, Phase 6 | this document §6 |
| Registry schema and vocabulary freeze | **done 2026-10-07** (§15) | master plan §11 |
| Complete legacy-slug → `outlet_id` mapping | technical, Phase 0/1 — **importer built, not yet run on the legacy database**; then operator review | master plan §11 |
| Value set of `scope`; form of `orientation` | not frozen: free text with `unknown` | §15 |
| Channel health state | ledgered operational state, not a registry field; not built | §8 |

## 14. Milestones

- 2026-10-06 — supply model recorded (repository bootstrap). Nothing implemented.
- 2026-10-07 — Foundation Core I: registry schema `coprepan-outlet-registry/v1` frozen and
  validated by code; legacy importer built and tested on a synthetic database. The import itself
  was not executed. Run report:
  [`docs/agent-runs/2026-10-07_foundation-core-i.md`](../agent-runs/2026-10-07_foundation-core-i.md).

## 15. Registry schema `coprepan-outlet-registry/v1`

File: [`config/outlet_registry.json`](../../config/outlet_registry.json) — `{"schema", "outlets"}`,
outlets in `outlet_id` order. Code: `src/coprepan/registry.py`. Every field is required; a value
that is not known is the token `unknown`, never an omission.

| Field | Content |
|---|---|
| `outlet_id`, `country_id` | [naming](../architecture/TERMINOLOGY_AND_NAMING.md) §5; `country_id` must be the id's country |
| `registration_status` | `proposed` · `registered`. Only a registered outlet resolves (`Registry.resolve`). A registered outlet has at least one web origin and no open review note |
| `display_names[]` | `name`, `valid_from`, `valid_to` (ISO date, `unknown` or `not_applicable`) |
| `outlet_type` | `national_reference` · `popular_tabloid` · `regional` · `digital_native` · `state_official` · `news_agency` · `broadcaster_website` · `unknown` |
| `access_model` | `open` · `metered` · `hard_paywall` · `unknown` |
| `medium` | `print_and_web` · `web_only` · `unknown` |
| `outlet_group`, `city`, `region`, `scope`, `same_outlet_basis` | text, `unknown` when not known |
| `timezone` | IANA zone name or `unknown` (form checked; an outlet without a zone cannot be dated, §3) |
| `editions[]` | text |
| `web_origins[]` | normalised `scheme://host[:port]`; the first is the canonical origin of the URL key |
| `url_rules` | `version`, `significant_query_params[]`, `strip_path_prefixes[]`, `strip_path_suffixes[]` — [identity](../identity/INDEX.md) §3 |
| `channels[]` | `channel_id`, `kind` (`rss` · `atom` · `sitemap` · `sitemap_index` · `section_page` · `archive` · `unknown`), `url_history[]` (`url`, `valid_from`), `legacy_observed` |
| `legacy_aliases[]` | `country_code`, `slug` (exactly as observed), `observed_in`, `mapping_status` (`hypothesis` · `human_audited`) |
| `legacy_observed` | the legacy rows an entry was proposed from, verbatim; `{}` otherwise |
| `review_notes[]` | what a reviewer still has to settle |
| `orientation` | optional, free form, sourced |

**Legacy import** (`src/coprepan/legacy_registry_import.py`, §12): copies the legacy database file
to a work directory outside the legacy tree, reads only the copy, and writes a registry of
`proposed` outlets plus a review report with the legacy-name → `outlet_id` table and everything it
could not resolve. Proposed ids are `{country_id}_{ASCII slug of the legacy code}`; legacy sources
that fold to one proposed id are listed together with a review note, not silently merged as a
fact. Legacy country codes resolve through
[`config/legacy_country_codes.json`](../../config/legacy_country_codes.json) (`hypothesis`); a code
not listed there is reported as unresolved. Attributes the legacy database does not hold stay
`unknown`. Only the names in the database's `sources` table are visible to it; variants that exist
only in directory names or exported files are not covered.

```text
python -m coprepan.legacy_registry_import --database <legacy sqlite file> --work-dir <empty dir outside the legacy tree> --registry-out <new file> --report-out <new file>
```

Registration is a review step: a reviewer sets the final `outlet_id`, completes the attributes,
clears the review notes and sets `registered`, in a commit of `config/outlet_registry.json`.
