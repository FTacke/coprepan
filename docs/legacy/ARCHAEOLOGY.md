# Legacy COPREPAN — how it actually worked, and how it failed

**Status: HISTORICAL EVIDENCE — not normative.** A reconstruction of the legacy system from its
code, made on 2026-10-07 (legacy HEAD `3e6bdd3`), as the evidence base of
[CPD-0004](../decisions/CPD-0004_legacy-component-dispositions.md) and
[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md). Rules for working with the legacy
system: [`INDEX.md`](INDEX.md).

Evidence labels used throughout:

- **[code]** read in the legacy source on 2026-10-07 (path relative to the legacy repository);
- **[copy]** measured on 2026-10-07 on a *copy* of `data/db/coprepan.sqlite` made outside the
  legacy tree (source file SHA-256 `7fe49907…8ed5b7`, 166,174,720 bytes, with its WAL sibling);
- **[audit]** a measurement of the audit of 2026-10-06, quoted with that date and not re-measured;
- **[studies]** read in the archived studies repository on 2026-10-07.

Nothing in the legacy tree was changed, no legacy test was run, no legacy database was opened in
place.

---

## 1. Acquisition

**Outlet register.** The truth was the `sources` table (82 rows [copy]), seeded from a CSV or
created ad hoc from the dashboard. Attributes: alpha-3 `country_code`, `newspaper_code`, `name`,
`base_url`, `language`, `legal_basis`, `is_active`, `notes` — no outlet type, publisher or time
zone [code `src/coprepan/models.py`]. Codes created from the dashboard were
`name.lower().replace(" ", "").replace(".", "")[:20]`: unseparated, truncated, non-ASCII
[code `services/discovery_service.py:101`]; the ASCII slug helper was applied only when files were
written, never at registration. Result: six non-ASCII codes [copy], mixed styles (`el_pais`
beside `elpais`), two directories for one outlet.

**Discovery.** `robots.txt` sitemap lines, eleven standard paths, `<link rel=alternate>` on the
home page [code `discovery/core.py`]. 352 feeds: 146 RSS, 116 sitemaps, 82 sitemap indexes, 7
unknown, 1 Atom; discovered by robots (208), heuristic (87), HTML head (57); status `active` 143,
`technically_empty` 118, `inactive` 91 [copy]. A feed was scored 0–100 and crawled from 40 up; the
good idea in the score is the **output probe** — fetch a few of the feed's URLs and run the real
extractor on them. Sitemap indexes were forced inactive ("expansion not implemented"), closing
the main route to archives.

**Crawl.** A daemon thread started from the web dashboard; outlets in sequence, all feed URLs
collected, then fetched in order under a per-outlet word limit and a hard-coded 300-second wall
clock [code `services/crawl_service.py`]. The "seen" set was every stored URL string, loaded into
memory. 32 crawl runs and 771 discovery runs are recorded [copy]. No scheduler.

**HTTP.** `requests` with a 15 s timeout, three retries on 429/5xx, one second per host; user agent
with a placeholder contact address. Redirect target, status and headers were never stored.
`respect_robots_txt: true` was configured, and the function that would enforce `Disallow` had no
caller [code `utils/http.py:290`].

## 2. Data holding

- **Database** [copy]: `sources`, `feeds`, `crawl_runs`, `discovery_runs`, `articles` (64,932
  rows). An article row held the URL (unique as a raw string), `fetched_at`, title, extracted
  text, word count, `date_published` with its source label, language, section, status. **Not
  stored: the HTML, the HTTP status, the headers, the final URL, the feed that listed the URL, any
  content hash, any extractor version.**
- **Article statuses** [copy]: `ok` 35,810; `too_short` 13,989; `discarded_gallery` 8,663;
  `discarded_homepage` 4,255; `discarded_binary` 2,128; `fetch_error` 64;
  `discarded_paywall_teaser` 23. The content of a discarded article was set to `NULL` [code].
- **`date_published_source`** [copy]: `page_metadata` 37,162; none 15,133; `crawl_date` 7,791;
  `url_pattern` 4,846.
- **JSON stages** [code]: after each outlet, the run's `ok` rows were exported to one file per
  outlet and publication date. `json_raw` took what passed an *adaptive* policy (age up to 30 days;
  the first of 200/180/160/140/120 words that at least one article reached, per outlet and run);
  the rest went to `json_raw_extended` with `policy_fail_reasons`. On every export the existing
  file was loaded, merged, de-duplicated, re-sorted and rewritten. "Raw" here means extracted text.
- **Identity** [code `json_raw/schema_v1.py`]: `article_id` = SHA-256 of the lower-cased URL
  without fragment and trailing slash, query kept. The database de-duplicated on the raw URL
  string — a different key from the files'.
- **Provenance**: none for acquisition and extraction. The annotation step recorded per-stage
  versions and three hashes (input file, cleaned text, annotation).

## 3. Article processing

- **Extractor** [code `crawler/extractors.py`]: own heuristics on BeautifulSoup, unversioned,
  dependencies unpinned. Body = the `<p>` elements of the first `<article>`, else `<main>`, else
  the largest block — **only `<p>`**: headings, lists, quotations and tables were not collected.
- **Paragraph filter**: dropped paragraphs under 120 characters; any paragraph containing one of
  `foto:`, `crédito`, `reuters`, `afp`, `ap `, `epa`, `getty`; any paragraph containing a
  subscription phrase (`suscrib`, `registrat`, `inicia sesión`, …); paragraphs mostly in capitals.
- **Word splitting**: a "joined words" repair split every word of eleven or more letters that ends
  in a function-word string (`crecimiento` → `crecimient o`), in the body only.
- **Title**: `og:title`, else `<title>` cut at the first ` | ` or ` - `, else `h1`; no suffix
  removal on `og:title`.
- **Date**: page metadata, else the first `<time>`, else a URL pattern (a `/YYYY/MM/` path gave
  day 01), else **today's date labelled `crawl_date`**; parsed with a fuzzy parser, time zone
  dropped.
- **Section**: `article:section` or a breadcrumb at crawl time; later a per-outlet URL rule and a
  mapping file (`section_map_v1.yml`) to six `standard_section` values plus a separate
  `is_opinion` flag. **Author: no code. Tags: extracted, then discarded.** Language: `<html lang>`,
  else `es`.
- **Updates and revisions**: none. A URL was fetched once; a non-200 answer became `fetch_error`
  and was never retried, because the URL was then in the "seen" set.

## 4. Linguistic layers

A separate, later script: clean (`clean-v6`) → segment → spaCy (`es_dep_news_trf`, once per
paragraph) → tense rules (`tense-v3`) → validation [code `scripts/annotation/`]. It kept `raw`
beside `clean` with a per-correction report carrying offsets, wrote atomically, and skipped inputs
whose hashes and versions were current — the best-engineered part of the system. The tense layer
was written **into the UD `morph` field** (`PastType`, `TenseRole`, `FutureType`, …). The token
record had `head_text` but no head index. No genre or article-type classification existed.

## 5. Operations

Eleven console scripts and an unauthenticated web dashboard that could start, pause and cancel
crawls, delete outlets and feeds and reset all runs. On start-up every unfinished run was set to
`failed`: there was no resume. 48 test files, no isolation; several start a real crawl, live HTTP
or a write to the production database at import time. The extractor, the HTTP layer and the crawl
loop had no tests.

---

## 6. Failure mechanisms

Each row is a mechanism, not an anecdote: it says *why* the system produced the defect.

| # | Failure | Mechanism | Evidence |
|---|---|---|---|
| F-1 | No raw data | fetch, extraction and storage were one in-memory step; only the extracted text was kept | [code]; audit T-1 |
| F-2 | Words split inside the text | an unconditional regex "repair" in the extractor | [code `extractors.py:633-646`]; [audit] T-2: `crecimient o` 3,100 times against `crecimiento` 12 |
| F-3 | Lossy downstream repair | the cleaner re-joins only ` o` / ` al` after listed endings — not the inverse of the split, and it merges genuine sequences (`atención al` → `atenciónal`), also in titles that were never split | [code `lib/cleaning.py`]; [audit] T-3 |
| F-4 | Body loss, lexically conditioned | substring and length filters on prose (`epa` hits *separar*, *preparar*); `<p>`-only collection | [code `extractors.py:507-535`]; [audit] T-4 |
| F-5 | Boilerplate and title contamination | fixed class lists for removal; no suffix handling on `og:title` | [code]; [audit] §10 |
| F-6 | Fabricated publication dates | crawl date and day 01 written into the date field; they then drove file names and the age filter | [code]; [copy] 7,791 rows labelled `crawl_date`, 15,133 without a basis |
| F-7 | Weak identity | lower-cased URL as id; query kept, so tracking variants are distinct "articles" while case-distinct paths merge; a second, different key in the database | [code]; [audit] T-6: 101 ids in two files, 339 groups of identical bodies; [studies] composite key `source_file|article_id` |
| F-8 | Same URL, changed content: invisible | once-only fetch; file-level de-duplication keeps "more words", no history | [code] |
| F-9 | Silent permanent loss of URLs and feeds | failed URLs never retried; a feed is deactivated after three runs without *new* usable articles — which a healthy, fully crawled feed also produces; errors while reading a feed are swallowed and logged as `ok` | [code `crawl_service.py:859-878`, `crawler/core.py:233-236`] |
| F-10 | Configuration that is not behaviour | `respect_robots_txt` never enforced; `require_date_for_daily` hard-coded; several keys read by nothing | [code] |
| F-11 | Hidden defaults | language `es`; adaptive word threshold per outlet and run; 300 s, 100 words, score 40 as literals | [code] |
| F-12 | No resume; state in a thread | a restart fails every running job; a rollback on one URL drops the uncommitted articles of the batch while counters stay incremented | [code `dashboard/app.py:30-61`, `crawl_service.py:722-737`]; [audit] T-10 |
| F-13 | Database / file drift | two stores with two keys, files rewritten on every export, discarded rows never exported | [code]; [audit] §2.3: 2,980 file records without a row, 8,409 `ok` URLs not in the files |
| F-14 | Unversioned parser, unpinned stack | no extractor version anywhere; `spacy>=3.7.0`; the model version not recorded | [code] |
| F-15 | Provenance gaps in annotation | section metadata joined from a CSV *after* the annotation hash was computed; a reprocessing script overwrote the recorded library version without re-parsing | [code `annotate_articles.py:433,457,499`] |
| F-16 | Mixed pipeline stages | project features inside `morph`; a metadata field changing type between stages; admission decided at crawl time | [code] |
| F-17 | Positional ids | segment and sentence ids contain the article's position in a file that is re-sorted on export; token ids unique per file only | [code] |
| F-18 | Section inconsistency | section taken from page metadata for some outlets and from hard-coded URL rules for others; labels in two classes with order deciding; `other_unclear` large | [code `section_map_v1.yml`]; [audit] §7.1: 21.8 %; [studies] 6,534 articles dropped as `other_unclear` |
| F-19 | No corpus snapshot | no manifest, no release, data directories git-ignored and "migrated manually"; no study pins its input | [code]; [studies] |
| F-20 | Non-reproducible interventions | layout and schema migration scripts, an ad-hoc backfill tool, `--reset-state` used repeatedly while the cleaner went through six versions in a day | [code]; legacy run notes |
| F-21 | Dangerous tests and tools | tests that crawl or write at import; dashboard endpoints that delete without authentication | [code] |
| F-22 | Supply shaped by crawlability | no outlet attributes; outlets with data are those whose flat feed and generic extraction happened to work | [code]; [audit] §7.2; [studies]: a domain result "flips" when dominant outlets are removed |

**Negative evidence, kept on purpose.** Not found in the legacy code: any handling of updates,
revisions or liveblogs; any author or agency capture; any snapshot or manifest mechanism; a second
version of the section mapping (so no taxonomy drift across versions — the inconsistency is inside
version 1). Artefacts whose origin can no longer be established: the `backup/` directory of 18
files in an older schema has no writer in the code; `data/sources_seed.json` has no reader.

## 7. What was good

Worth keeping as concepts (dispositions: CPD-0004): the curated outlet and feed list with its
discovery history; the output probe; labelling instead of deleting (`date_published_source`,
`policy_fail_reasons`, the extended store); `raw` beside `clean` with an offset-carrying report;
per-stage versions with input, clean and annotation hashes; atomic writes and skip-if-current; the
language guard that labels instead of annotating; section detection method and confidence with a
mapping version; `is_opinion` orthogonal to the section; deterministic, sentence-local tense
rules with an explicit label inventory.

## 8. What the studies needed

[studies] The four studies read, from the press corpus: country, outlet slug, date, language,
`standard_section`, `is_opinion`, the title and body segments with sentences and tokens (`lemma`,
`pos`, `dep`, `head_text`, `morph` with the tense labels). Counts covered **title and body
together** — no script separated them, although the field was recorded. What they wanted and could
not get: an author identifier, a real acquisition-batch identifier, a usable section for the
material classed `other_unclear`, a pinned corpus input. What they worked around: repeated ids,
region derived from the country code, the file date used as the press date, sentence context
re-read from the raw files. Consequences for 3.0: master plan §9; CPD-0005 §6.
