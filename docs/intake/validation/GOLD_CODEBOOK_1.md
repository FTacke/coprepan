# Gold codebook `gold-body-codebook/1` (CPD-0044)

**Status: `PROPOSED`** — binding for a package once its gold is frozen under this id; a change is a new codebook version, never an
edit. It defines what a reviewer marks on the text view `docview/1` of a stored page. It follows the decisions in force:
CORE is text quality, not origin (CPD-0039: AI-made and agency texts are wanted); captions, credits and embeds are typed and kept
out of the BODY (TRANSFORMATION_AND_VALIDATION_PRINCIPLES §3, CPD-0041); no social post belongs to the BODY (CPD-0041/0042).

## 1. The text view

Every text of the page body, split at the HTML block boundaries (`p`, `div`, `li`, `h1`–`h6`, `td`, `br`, …); scripts, styles,
`noscript` and the head are not shown. Each segment shows its tag and markup facts (in a navigation, header, footer, aside,
figure, form, table, list, heading, quote; hidden; mostly link text) — facts of the page, not decisions. Navigation, footer and
selection lists are folded into one line each; they open on a double click. The inert original stands beside it.

## 2. Labels (per segment, or per span inside a segment)

| Key | Label | What belongs here |
|---|---|---|
| B | `body` | the article's running editorial text: paragraphs, its subheadings, lists, tables, quotations within the text, a recipe's ingredients and steps, the entries of a live ticker, an interview's questions and answers, a correction or update the outlet adds to the text |
| T | `title` | the article's headline |
| V | `standfirst` | the subtitle, dek or summary above the text that is **not** a paragraph of it |
| C | `caption` | photo and video captions, with their credits |
| E | `embed` | embedded social-media posts, external players and embedded third-party content |
| F | `foreign` | everything else: navigation, author / date / credit lines, labels, advertising, "Lea también" and other links to other articles, newsletter and channel promotions, teasers of other articles, comments, pull quotes (a repeat of text), footers, cookie and paywall notices |
| U | `unsure` | not decidable — a legitimate answer, never recoded |
| — | unlabelled | at closing, confirmed **not article text** (`foreign_implicit`); kept apart from an explicit `foreign` |

Rules of thumb:

- **Spans.** When one segment mixes article text with something else (a paragraph ending "… Foto: EFE", a credit glued to the last
  paragraph), mark the segment and then the deviating part as a span. Do not split hairs below a word.
- **A lead that is a paragraph of the text** is `body`; a summary set apart above the text is `standfirst`. When unsure: `unsure`.
- **Repeated text** (a pull quote, a teaser repeating the first paragraph): the first occurrence in the text is `body`, the repeat
  `foreign`.
- **Agency and AI notes** ("Con información de EFE", "Este artículo fue creado con IA"): `foreign` — they are production notes, kept
  in provenance, not running text.
- **Hidden segments** (grey, italic): text the reader does not see; usually `foreign`; if it is the article itself hidden by a
  script, `body` and say so in the source state.

## 3. Case questions

- **Source**: `complete` (the article text is visible in the stored page), `truncated` (paywall, "read more", teaser), `not_visible`
  (only in scripts or data — see "Angaben der Seite"), `not_an_article_page` (index, gallery, error, service page),
  `not_assessable`.
- **Text outside the view**: article text visible in the original but absent from the text view (beginning / middle / end), with a
  short note — never the text itself.
- **CORE** (`yes` / `no` / `unsure`, with reasons and a note; a reason or note is required for `no` and `unsure`): an editorial
  press text in connected prose with at least about 150 words of article text; not a live ticker or updates page, not an index,
  list or service page, not paid content, not a paywall teaser or truncated text, in Spanish. AI-made and agency texts qualify.
  Duplicates across pages are not judged here. Structured articles (recipes, match reports with tables) are judged as they stand;
  mark the page type — whether they belong in CORE is an open decision (CPD-0043 §4), and the gold must show it, not settle it.
- **Page types** (optional, several) and a **comment**.

## 4. Closing and correcting

Closing confirms that every unlabelled segment is not article text. A closed case is locked; reopening it is an event of its own,
and every correction stays in the log. After the freeze nothing is accepted.
