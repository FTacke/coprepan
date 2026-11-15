"""Build the pinned extract of an IPTC NewsCodes vocabulary (CPD-0039) from one retrieved file.

Usage:
  python scripts/build_iptc_extract.py --source <retrieved .json> --url <retrieval URL> --retrieved-at <ISO time>
                                       --out config/taxonomy/<name>.json

The IPTC CV server's JSON (``?format=json&lang=x-all``) is reduced to what the mappings need -- the concept's qcode and URI, its
English and Spanish preferred labels, its broader concepts, and its retirement date -- and written with the digest of the exact
retrieved bytes, the scheme's release date, its licence and the attribution IPTC asks for. The retrieved file itself is not
versioned (it is IPTC's, regenerable and large); its SHA-256 names it. An update of the vocabulary is a new extract file beside
the old one, never an edit of it: a mapping pins the extract it was written against (``coprepan.iptc``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from coprepan.canonical import record_json  # noqa: E402

SCHEMA = "coprepan-iptc-extract/v1"
ATTRIBUTION = ("Contains IPTC NewsCodes, (c) IPTC, International Press Telecommunications Council (https://iptc.org), "
               "licensed under the Creative Commons Attribution 4.0 International licence (CC BY 4.0, "
               "https://creativecommons.org/licenses/by/4.0/). Reduced to identifiers, English and Spanish labels and the "
               "broader relation; no other change.")


def qcode_of(uri: str, alias: str, base: str) -> str:
    return f"{alias}:{uri[len(base):]}" if uri.startswith(base) else uri


def build(source: Path, url: str, retrieved_at: str) -> dict:
    data = source.read_bytes()
    scheme = json.loads(data.decode("utf-8"))
    base, alias = scheme["uri"], scheme["prefSchemeAlias"]
    concepts = []
    for concept in scheme["conceptSet"]:
        labels = concept.get("prefLabel") or {}
        concepts.append({
            "qcode": concept["qcode"], "uri": concept["uri"],
            "label_en": labels.get("en-GB") or labels.get("en-US"), "label_es": labels.get("es"),
            "broader": sorted(qcode_of(uri, alias, base) for uri in concept.get("broader") or [] if uri.startswith(base)),
            "retired": concept.get("retired"), "modified": concept.get("modified"),
        })
    concepts.sort(key=lambda c: c["qcode"])
    return {
        "schema": SCHEMA,
        "scheme": {"uri": base, "alias": alias, "label": (scheme.get("prefLabel") or {}).get("en-GB"),
                   "date_released": scheme.get("dateReleased"), "copyright_holder": scheme.get("copyrightHolder"),
                   "licence": scheme.get("licenceLink")},
        "source": {"url": url, "retrieved_at": retrieved_at, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                   "format": "IPTC CV server JSON (format=json, lang=x-all)"},
        "attribution": ATTRIBUTION,
        "top_concepts": sorted(qcode_of(uri, alias, base) for uri in scheme.get("hasTopConcept") or []),
        "concepts": concepts,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.out.exists():
        print(f"refused: {arguments.out} exists; an extract is written once (a new vocabulary release is a new file)")
        return 1
    extract = build(arguments.source, arguments.url, arguments.retrieved_at)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_bytes(record_json(extract))
    print(json.dumps({"out": str(arguments.out), "concepts": len(extract["concepts"]), "source_sha256": extract["source"]["sha256"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
