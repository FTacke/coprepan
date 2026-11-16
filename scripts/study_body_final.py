"""The final BODY/CORE study (CPD-0043): the measurements behind the open questions, on every stored page under the preferred
candidates (``article_html/0.4.2``, ``content-features/2``, ``content-quality/4``, ``body-quality/2``). Offline, read-only; the
result holds numbers, outlets and fetch-id prefixes only.

Usage:
  python scripts/study_body_final.py measure (--runtime <workspace> | --page-cache <pages.jsonl.gz>) --out <study.json>

Measured (each a technical variant beside the gate, never adopted here):

* ``coverage``: where the page states an articleBody of at least 1,000 text characters, how much of it (5-word shingles of
  letter words) the BODY covers, at the beginning (first 30 shingles), at the end (last 30) and overall;
* ``prose_only_variant``: CORE if only running prose counted (BODY paragraphs, quotes and loose text of at least 25 letter words,
  or of at least 8 ending with a sentence mark), for the 150 words and the function-word share -- the CORE flips against /4;
* ``word_definition``: CORE flips if the 150 words counted white-space tokens or ``\\w+`` tokens instead of letter words;
* ``stated_body_only``: pages whose BODY is under half the stated text -- is the stated text distinct per address, and how many
  pages of one outlet state the same text;
* ``residue_patterns``: credit lines, teaser lines and channel promotions inside the BODY of accepted pages (patterns used to
  *measure*, never as rules);
* ``live_signals``: accepted pages whose title or address says live, or with three or more time-led BODY blocks.
"""

from __future__ import annotations

import argparse
import hashlib
import html as _html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
sys.path.insert(0, str(REPOSITORY / "scripts"))

from coprepan import body_quality as BQ, content_quality as Q, extraction as E, extraction_body as B  # noqa: E402
import study_phase3_metadata as S3  # noqa: E402
import study_body_quality as SB  # noqa: E402

END = re.compile("[.!?…»”\")]\\s*$")
PROSE_KINDS = {"paragraph", "quote_block", "unstructured_text"}
RESIDUE = {
    "credit_line": re.compile(r"^\s*(fotos?|imagen(es)?|cr[eé]ditos?|cortes[ií]a|ilustraci[oó]n|video|infograf[ií]a)\s*[:|/]", re.I),
    "teaser_line": re.compile(r"^\s*(lee|lea|leer|te puede interesar|le puede interesar|puede leer|ver tambi[eé]n|mira|nota relacionada|"
                              r"tambi[eé]n puedes leer|sigue leyendo|recomendado)\b[^.]{0,25}:", re.I),
    "channel_promotion": re.compile(r"(s[ií]guenos|únete|suscr[ií]be|whatsapp|telegram|google news|newsletter)", re.I),
}
LIVE_TITLE = re.compile(r"(\ben vivo\b|\ben directo\b|\bminuto a minuto\b|\blive\b|\búltima hora\b|\bal momento\b)", re.I)
LIVE_SLUG = re.compile(r"[-/](en-vivo|vivo|en-directo|directo|minuto-a-minuto|live|ultima-hora|al-minuto)[-/.]", re.I)
TIME_LED = re.compile(r"^\s*\d{1,2}[:.h]\d{2}\b")


def _grams(text):
    w = Q._WORD.findall(text.lower())
    return [tuple(w[i:i + 5]) for i in range(max(0, len(w) - 4))]


def _stated_text(html):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("articleBody"), str):
                found.append(Q.stated_body_text(node["articleBody"]))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    for d in Q._json_ld(html):
        walk(d)
    return max(found, key=len, default="")


def measure(arguments) -> int:
    rows = []
    for page, body in S3.stored_pages(arguments):
        x = B.PREFERRED.run(body, body_sha256=page["body_sha256"], **page["args"])
        if x.outcome != E.OUTCOME_EXTRACTED:
            continue
        html = SB._decoded(page, body)
        f = Q.features(x.record, http_status=page["status"], html=html)
        blocks = [b for b in x.record["blocks"] if b["role"] == E.ROLE_BODY]
        stated = _stated_text(html)
        prose = []
        for b in blocks:
            w = Q._WORD.findall(b["text"].lower())
            if b["kind"] in PROSE_KINDS and (len(w) >= 25 or (len(w) >= 8 and END.search(b["text"]))):
                prose.extend(w)
        body_text = "\n\n".join(b["text"] for b in blocks)
        row = {"fetch": page["fetch_id"][4:14], "outlet": page["outlet_id"], "url": page["url"], "fetched_at": page["fetched_at"] or "",
               "fetch_id": page["fetch_id"], "f": f, "title": f["title_text"] or "",
               "prose_words": len(prose), "prose_fw": (sum(1 for w in prose if w in Q.FUNCTION_WORDS) / len(prose)) if prose else 0.0,
               "white_words": len(body_text.split()), "alnum_words": len(re.findall(r"\w+", body_text)),
               "time_led": sum(1 for b in blocks if TIME_LED.match(b["text"])),
               "bq": BQ.assess(x.record, html=html, version=BQ.VERSION_2)["state"],
               "residue": Counter(), "residue_words": Counter()}
        for b in blocks:
            w = len(b["text"].split())
            for name, p in RESIDUE.items():
                if w <= (30 if name == "channel_promotion" else 40) and p.search(b["text"]):
                    row["residue"][name] += 1
                    row["residue_words"][name] += w
                    break
        row["body_words_white"] = row["white_words"]
        if len(stated) >= 1000:
            sg = _grams(stated)
            bg = {g for b in blocks for g in _grams(b["text"])}
            head, tail = sg[:30], sg[-30:]
            row["coverage"] = (sum(1 for g in sg if g in bg) / len(sg) if sg else 0.0,
                               sum(1 for g in head if g in bg) / len(head) if head else 0.0,
                               sum(1 for g in tail if g in bg) / len(tail) if tail else 0.0)
            row["stated_sha"] = hashlib.sha256(stated.encode("utf-8")).hexdigest()[:16]
            row["stated_chars"] = len(stated)
        rows.append(row)
    decisions = Q.assess_corpus([{"fetch_id": r["fetch_id"], "outlet_id": r["outlet"], "url": r["url"], "fetched_at": r["fetched_at"],
                                  "features": r["f"], "extracted": True} for r in rows], ruleset=Q.RULESET_4)
    for r in rows:
        r["core"] = decisions[r["fetch_id"]]
    accepted = [r for r in rows if r["core"]["decision"] == Q.ACCEPT]
    other = {r["fetch_id"]: [x for x in r["core"]["reasons"] if x not in ("too_short", "not_running_prose")] for r in rows}

    # coverage of the stated articleBody
    cov = [r for r in rows if "coverage" in r]
    coverage = {"pages_stating_1000_characters": len(cov),
                "overall": {"under_0_5": sum(1 for r in cov if r["coverage"][0] < 0.5),
                            "0_5_to_0_8": sum(1 for r in cov if 0.5 <= r["coverage"][0] < 0.8),
                            "at_least_0_8": sum(1 for r in cov if r["coverage"][0] >= 0.8)},
                "beginning_under_0_2_overall_at_least_0_6": dict(Counter(r["outlet"] for r in cov if r["coverage"][1] < 0.2 and r["coverage"][0] >= 0.6)),
                "end_under_0_2_overall_at_least_0_6": dict(Counter(r["outlet"] for r in cov if r["coverage"][2] < 0.2 and r["coverage"][0] >= 0.6)),
                "accepted_with_overall_under_0_8": sum(1 for r in cov if r["coverage"][0] < 0.8 and r["core"]["decision"] == Q.ACCEPT)}

    # prose-only variant
    flips = []
    for r in rows:
        if not r["f"]["words"]:
            continue
        variant = not other[r["fetch_id"]] and r["prose_words"] >= 150 and r["prose_fw"] >= 0.30
        if variant != (r["core"]["decision"] == Q.ACCEPT):
            flips.append({"fetch": r["fetch"], "outlet": r["outlet"], "to": "ACCEPT" if variant else "REJECT", "words": r["f"]["words"],
                          "prose_words": r["prose_words"], "function_word_share": r["f"]["function_word_share"],
                          "prose_function_word_share": round(r["prose_fw"], 3)})
    prose_variant = {"accept_to_reject": sum(1 for x in flips if x["to"] == "REJECT"),
                     "reject_to_accept": sum(1 for x in flips if x["to"] == "ACCEPT"), "pages": flips}

    # word definitions at the threshold (pages no other rule rejects and running prose holds)
    words = {"white_space_tokens": [], "word_character_tokens": []}
    for r in rows:
        if other[r["fetch_id"]] or r["f"]["function_word_share"] < 0.30:
            continue
        letters = r["f"]["words"]
        for name, n in (("white_space_tokens", r["white_words"]), ("word_character_tokens", r["alnum_words"])):
            if (letters >= 150) != (n >= 150):
                words[name].append({"fetch": r["fetch"], "outlet": r["outlet"], "letter_words": letters, "tokens": n})
    word_definition = {k: {"flips": len(v), "pages": v} for k, v in words.items()}
    word_definition["accepted_150_to_169_letter_words"] = sum(1 for r in accepted if 150 <= r["f"]["words"] < 170)
    word_definition["rejected_only_too_short_130_to_149"] = sum(1 for r in rows if r["core"]["reasons"] == ["too_short"] and 130 <= r["f"]["words"] < 150)

    # pages whose text stands only in the stated articleBody
    short = [r for r in cov if r["f"]["body_characters"] < 0.5 * r["stated_chars"]]
    same = Counter((r["outlet"], r["stated_sha"]) for r in cov)
    stated_only = {"pages": len(short), "by_outlet": dict(Counter(r["outlet"] for r in short).most_common()),
                   "pages_whose_stated_text_another_address_of_the_outlet_also_states": sum(1 for r in short if same[(r["outlet"], r["stated_sha"])] > 1),
                   "rejected_reasons": dict(Counter(r["core"]["reasons"][0] if r["core"]["reasons"] else "ACCEPT" for r in short)),
                   "fetch_prefixes": sorted(r["fetch"] for r in short)}

    # residue and live signals on accepted pages
    total_words = sum(r["body_words_white"] for r in accepted)
    residue = {"accepted_pages": len(accepted), "body_words": total_words}
    for name in RESIDUE:
        n = sum(r["residue_words"][name] for r in accepted)
        residue[name] = {"blocks": sum(r["residue"][name] for r in accepted), "words": n,
                         "share_of_body_words": round(n / total_words, 6) if total_words else None,
                         "pages": sum(1 for r in accepted if r["residue"][name])}
    live = Counter()
    for r in accepted:
        flags = [n for n, c in (("title", LIVE_TITLE.search(r["title"])), ("address", LIVE_SLUG.search(r["url"])), ("time_led", r["time_led"] >= 3)) if c]
        if flags:
            live["+".join(flags)] += 1
    out = {"schema": "coprepan-body-final-study/v1", "decision": "CPD-0043", "date": arguments.date,
           "versions": {"extractor": f"article_html/{B.PREFERRED.version}", "templates_sha256": B.body_templates_sha256(),
                        "features": Q.FEATURES_VERSION, "quality": Q.RULESET_4, "body_quality": BQ.VERSION_2},
           "population": {"pages": len(rows), "accepted": len(accepted),
                          "body_quality": dict(Counter(r["bq"] for r in rows))},
           "coverage": coverage, "prose_only_variant": prose_variant, "word_definition": word_definition,
           "stated_body_only": stated_only, "residue_patterns": residue,
           "live_signals_on_accepted_pages": dict(live)}
    arguments.out.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(json.dumps({k: out[k] for k in ("population", "coverage", "stated_body_only")}, ensure_ascii=False)[:2500])
    print(json.dumps({"prose": [prose_variant["accept_to_reject"], prose_variant["reject_to_accept"]],
                      "words": {k: v["flips"] for k, v in word_definition.items() if isinstance(v, dict)}}))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("measure")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--runtime", type=Path)
    source.add_argument("--page-cache", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--date", required=True)
    arguments = parser.parse_args(argv)
    return {"measure": measure}[arguments.command](arguments)


if __name__ == "__main__":
    sys.exit(main())
