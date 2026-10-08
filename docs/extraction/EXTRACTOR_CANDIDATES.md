# Extractor candidates for Phase 3 — a list, not a choice

**Status: §1–§5 A SURVEY FROM GENERAL KNOWLEDGE (2026-10-07); §6 THE SELECTION OF THE FIRST COMPARISON
(2026-10-08, CPD-0018). Nothing is adopted.** For §1–§5: nothing there was installed, run, measured or checked
against a current release. No package was installed and no network was used (repository
rules). Every statement about a tool is **unverified** in the sense of this repository: it is what
is generally known about it, not something observed here. Versions, licences and maintenance state
must be confirmed from the primary source before a tool is admitted to a comparison.

Purpose: name the classical (non-LLM) candidates a Phase-3 comparison would reasonably consider,
and the questions each must answer. Adoption is decided by the comparison on a gold sample
([design](GOLD_SAMPLE_DESIGN.md)), never by this list.

## 1. What a candidate must be able to do here

From the extraction contract ([index](INDEX.md) §2–§5):

| Requirement | Why |
|---|---|
| runs offline on preserved bytes, with no request of its own | extraction reads the preservation root only |
| deterministic for a pinned version | one answer per fingerprint; the harness runs every arm twice |
| exact version pin; licence compatible with the project | runtime dependencies are exact pins |
| output mappable to typed blocks with `body` / `non_body` roles | the record's shape; nothing dropped silently |
| metadata reportable with its basis | value as published plus where it came from |
| no silent text change beyond what is recorded | legacy failures F-2, F-4 ([archaeology](../legacy/ARCHAEOLOGY.md) §6) |

A tool that only returns one cleaned string can still enter as an arm; it would need a wrapper
that states what was lost (block structure, non-body material), and that loss counts.

## 2. Candidates

| Candidate | Kind | Generally known strengths | Questions for this project (all open) |
|---|---|---|---|
| `baseline_html/0.1.0` (this repository) | first-container rule, standard library | deterministic, transparent, typed blocks, keeps everything | expected to be wrong on real templates; it is the floor, not a contender |
| trafilatura | heuristic main-text extraction with metadata | widely used for web corpora; reported strong in published comparisons; extracts date, author, title; has precision / recall modes | block structure of its output; what it discards and whether that can be kept; behaviour on Spanish-language press templates; licence of the current release; fallbacks it calls internally and whether they are deterministic |
| readability-lxml (and other Readability ports) | port of the Readability algorithm | simple, well understood | returns cleaned HTML of one container: metadata weak; boilerplate inside the container |
| jusText | paragraph classification by stop-word density and link density | built for corpus linguistics; language-aware stop lists including Spanish | no metadata; short paragraphs (briefs, captions) are its known weak point — the legacy extractor's length filter dropped paragraphs under 120 characters (archaeology §3, F-4), and that loss must not come back by another route |
| goose3 | article extractor with metadata | title, image, metadata | maintenance state; determinism |
| newspaper3k / newspaper4k | news-oriented extraction with metadata | built for news pages | maintenance state; it fetches by itself by default and must be prevented from doing so; determinism |
| boilerpy3 (Boilerpipe port) | shallow text features | established baseline in the literature | no metadata; age |
| resiliparse / inscriptis and similar | HTML-to-text with layout | fast, faithful rendering | not article extractors: useful as the *neutral rendering* for reviewers rather than as an arm |
| extruct (or direct parsing) for JSON-LD, microdata, OpenGraph | structured metadata only | publisher-declared title, date, author, section | complements a text extractor; the baseline already reads JSON-LD, OpenGraph and `meta` itself |
| per-outlet rules (selectors per template) | hand-written | highest precision where a template is stable | maintenance cost per outlet; versioning ([index](INDEX.md) §6); only for outlets in production |

A combination — a general extractor, per-outlet rules where it fails, structured metadata beside
both — is a plausible outcome. It is an arm like any other and is compared as one.

## 3. Deliberately not on the list

- **LLM-based extraction.** CPD-0001: classical first; an LLM stage only on a demonstrated net
  benefit, and none is under consideration at this stage.
- **Rendering in a browser.** Deferred by the master plan (Phase 2, "deliberately later"). If a
  share of pages has no article text in the served HTML, the canary will show it; that is a
  finding for acquisition, not something an extractor can repair.
- **Hosted extraction services.** No external API in the production path.

## 4. The legacy extractor as an arm

The legacy extractor is the project's own heuristic code on BeautifulSoup, unversioned
([archaeology](../legacy/ARCHAEOLOGY.md) §3) — not one of the libraries above. It cannot be
replayed on the legacy pages: no raw HTML was kept (F-1).
It can enter a comparison in one of two ways, both a `PrecomputedArm` of the harness:

1. the legacy code, run in its own environment on pages preserved by 3.0, its outputs imported —
   this is the "net benefit against the legacy extractor on the same pages" of the Phase-3 gate;
2. the stored legacy text of a URL beside a fresh fetch of the same URL — confounded by whatever
   changed on the page in between, and usable only as an illustration.

Running legacy code is an operator-ordered task with its own environment (both packages are named
`coprepan`); it was not done.

## 5. Before a comparison starts

1. confirm each admitted tool's current version, licence and maintenance from its source;
2. pin versions; record them as arm versions;
3. write the wrapper that maps each tool to the extraction record, and test its determinism;
4. preregister the comparison: sample, metrics, thresholds, adoption criterion;
5. only then open the reference.

## 6. Selection for the first comparison (added 2026-10-08, CPD-0018)

The survey above stands as written on 2026-10-07. On 2026-10-08 three of its candidates were installed, pinned and
wrapped ([CPD-0018](../decisions/CPD-0018_classical-extractor-candidates-of-the-first-comparison.md), with the
criteria and the reasons for leaving the others out):

| Arm | Tool and version (package index, read 2026-10-08) | Licence as the distribution states it |
|---|---|---|
| `trafilatura/2.3.1.w1` | trafilatura 2.3.1 | Apache-2.0 |
| `readability_lxml/0.9.w1` | readability-lxml 0.9 | Apache-2.0 |
| `justext/3.0.2.w1` | jusText 3.0.2, Spanish stop list | BSD 2-Clause |

Of §5, items 1–3 are done for these three (version and licence from the distribution's own metadata — maintenance
was not assessed beyond "a current release installs"; pins in `pyproject.toml`, extra `phase3`; wrappers in
`src/coprepan/extractor_candidates.py`, determinism tested). Items 4 and 5 are **not** done: nothing is preregistered
and there is no reference.
