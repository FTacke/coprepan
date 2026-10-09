# CPD-0020 — Candidate budget newest-first; HTML listings (pagination, dates, waiting candidates); incremental index reading; outlets new to the registry; the operator's canary workflow

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Amended by (2026-10-09) | [CPD-0023](CPD-0023_delegated-operator-authorisation-in-force.md): beside the interactive mode described here, a commissioned agent may arm and freeze under a versioned authorisation record (delegated mode). This record is otherwise unchanged |
| Decided by | the operator, in the brief of the integrated source-expansion run of 2026-10-09, which ordered F7 worked on with the smallest fitting solution, generic improvements for HTML archives and listings where they stand in the way of new sources, the new research consolidated without a second registry, a further canary wave prepared, and the gate procedure made easier to operate without replacing the operator's confirmation; technical choices were delegated to the run and are recorded here. Subject to the operator's review |
| Kind | architecture · procedure |
| Scope | discovery (allotment of the candidate budget, HTML listings, index expansion across passes), candidate qualification, canary channel selection, how an outlet outside the legacy import enters the registry, the consolidated qualification overview, the operator's workflow tool |
| Builds on / amends / supersedes | builds on CPD-0007, CPD-0013, CPD-0016, CPD-0019. **Amends CPD-0019 §9** (a listing channel is read without an allow rule; its candidates wait) and **§7** (corrects a reading of the measurement; orders the allotment). Amends CPD-0013 §1 by one case (an outlet that was never in the legacy system). Supersedes nothing |
| Does not change | any identifier or stored artefact; any request limit, depth, document or candidate budget; the pace; the three layers of CPD-0017; the arming protocol and the operator's freeze of CPD-0016 §4; the rule that registration is a review step with a record |
| Run report | [`docs/agent-runs/2026-10-09_integrated-source-expansion-and-acquisition-qualification.md`](../agent-runs/2026-10-09_integrated-source-expansion-and-acquisition-qualification.md) |
| Evidence | `tests/test_source_structures.py` (14), `tests/test_source_expansion.py` (9); `config/source_discovery/candidate_budget_replay_2026-10-09.json` |

Validation debt: everything here is shown on synthetic documents and on one preserved listing. No
real listing page, paginated archive or sitemap child has been read by this project.

## Context

Research names sources the earlier waves do not reach: outlets with no feed but a chronological
archive or a section page, publisher-documented RSS catalogues, outlets that were never in the legacy
system. The pipeline could not take them: a listing channel needed an allow rule nobody can write
without seeing a page; pagination was followed only through `<link rel="next">`; a listing gave no
dates; the registry had no way in for an outlet without a legacy row. And CPD-0019 left open whether
the candidate budget should be ordered.

## Decision

### 1. F7 corrected and settled: the budget goes to the newest (`candidate-budget-order/1`)

**Correction of CPD-0019 §7.** It read the measurement "44 of the 303 entries turned away are newer
than the oldest entry kept" as "the listing is not strictly newest-first". That reading was wrong.
The preserved sitemap *is* newest-first; the 44 arose because the measure counted as "kept" also
entries whose address a feed had already made a candidate, some of them older. Held against what
that pass itself kept, **0 of 303** are newer (`discovery-coverage/2`:
`turned_away_newer_than_oldest_newly_kept`; replayed from an empty table in both orders, the same 200
entries are kept: `candidate_budget_replay_2026-10-09.json`). The budget of 2026-10-08 cut the old
end of the listing and nothing else.

**Decision all the same**, as a rule of form rather than a repair of a measured loss: when a document
lists more new candidates than a pass has budget for, the budget goes to the newest dated entries
first (publication hint, else `updated`, else `lastmod`), then to the undated in document order.
Events stay in document order. Reason: a listing in ascending order — a known form of sitemap — would
otherwise give its budget to its oldest entries. **Not shown necessary on real material**; shown on a
synthetic listing. The limit of 200 is unchanged.

### 2. HTML listings (`channel-parser/3`)

- **Next page.** Besides `<link rel="next">`: an anchor with `rel="next"`; and numbered pagination
  (`numbered-pagination/1`) — the one anchor that is "this listing, one page further" by a trailing
  `/page/N` or `/pagina/N` or a query parameter `page`, `pagina`, `paged`, `pg` (never `p`). Only a
  link the page carries is followed, one page at a time; what the page declares by `rel` wins. Depth,
  document and request budgets bound it as they bound an index.
- **Dates.** The first `<time datetime>` inside an `<article>` is the publication hint of that
  article's links, as written. A hint orders entries; it never dates a document.
- **What a listing lists waits for a rule** (`candidate-filter-generic/2`). A candidate first listed
  by a channel of kind `archive` or `section_page` is `DEFERRED` until the outlet has a reviewed
  allow pattern. A canary therefore **reads and preserves a listing without a rule** (amending
  CPD-0019 §9, which did not select such a channel at all) and requests nothing it lists. The rule is
  then written from the preserved pages — from evidence, not from a guess — and a later canary
  acquires under it (`canary-driver/4`).

### 3. An index is read incrementally (`expansion-order/2`)

A child of an index that an earlier pass read completely — parsed, no entry turned away by a
candidate budget — and that the index still states with the same `lastmod` is not asked for again.
The budget of a later pass therefore moves on to the next children in the order of CPD-0019 §4. A
child without a `lastmod` is never called unchanged. What the *same run* read is not skipped: a run
that is resumed repeats its own requests, so that it records the same evidence (CPD-0009; the
crash-recovery tests found the first version of this rule breaking exactly that). No frontier is
stored: it is derived from the events and inputs.

### 4. No adapter

Nothing in the research requires a source-specific adapter. RSS 1.0, Atom, Arc-style and
WordPress-style feeds, feeds on a foreign host and feed addresses that are query strings are read by
the generic parsers (tested on synthetic documents). A publisher's RSS *hub page* is evidence for
the feeds it names and is not a channel.

### 5. The consolidated qualification overview

`config/source_discovery/source_qualification_overview_<version>.json` (page:
`docs/corpus_supply/SOURCE_COVERAGE_REPORT.md`): one record per registry outlet and per outlet
candidate outside the registry; the classification of every entry of a research supplement against
the registry, earlier research and earlier proposals; identity cases as facts with what stays open;
coverage per country. **It is not a registry**: a candidate has a *proposed* id only. Analytic
stages — `RESEARCHED`, `CANDIDATE`, `TECHNICALLY_QUALIFIED`, `REGISTERED`, `ACQUISITION_VERIFIED`,
`OPERATIONALLY_STABLE` — are listed per record; they are the flags of CPD-0019 §8 under the names of
the brief, in the order of the evidence they need, and no registry state. Addresses are compared
without scheme, a leading `www.` and a trailing slash, with the query sorted; a match that ignores
the query is a variant, not a duplicate. A version is written once.

### 6. An outlet that was never in the legacy system

Such an outlet enters the registry **only through an applied registration proposal**
(`new_outlets`), together with its registration record: it is never a `proposed` row, because the
registry's proposed rows are the legacy import. Its `outlet_id` is assigned by the proposal the
operator approves; it has no legacy alias and no legacy row. The script refuses an id the registry
holds and an origin host that is an origin of another outlet. `country_id` is the country the outlet
reports on; where the newsroom sits is not recorded as the country.

### 7. The operator's workflow in one command

`scripts/canary_operator.py` runs runbook §0–§6 for the person who arms: arm, tests on the arming
commit, baseline, **the digest shown and typed by hand**, freeze, commit, push, preflight, run,
verify, measure, evidence into the checkout, disarm, commit, push. Two confirmations (`ARM`, the
digest) are read from a terminal only; a pipe, a file or an argument is refused, so an agent's shell
cannot give them. Once armed, the disarming is attempted whatever happens. It adds no permission and
changes no check of the driver. **It does not move the gate**: the act of CPD-0016 §4 stays the
operator's, now as one command instead of a dozen.

## Alternatives considered

| Alternative | Why not |
|---|---|
| leave the allotment in document order | harmless on the one listing seen, wrong by construction on an ascending one |
| raise the candidate limit | not shown binding; forbidden without evidence |
| follow every numbered page link | page 5 from page 1 skips what lies between and multiplies requests |
| guess an allow pattern per CMS | a pattern is an outlet rule, set by review from evidence |
| keep listing channels unread until a rule exists | no rule can be written without a preserved page |
| a stored frontier table | derivable from evidence; a second state to keep consistent |
| proposed rows for new outlets | the registry's proposed rows are defined as the legacy import and tested as such |
| let the tool take the digest as an argument | then anything that can start a process can freeze |

## Not decided here

- every allow rule: none is evidenced; they follow from the preserved listings of the third wave;
- the licence and TDM question of `co_el_tiempo` (its publisher's RSS page restricts use): the operator's, before any registration;
- the identity cases of the overview (`pr_primera_hora`, `cl_el_mercurio`, origin changes, closed outlets); a registry attribute for a closed outlet or for a newsroom's seat;
- a schedule for outlets that publish in editions (`sv_el_faro`);
- how an access-control hold is lifted (open since CPD-0019).
