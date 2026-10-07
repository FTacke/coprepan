# Test fixtures

Small, documented, non-production samples that tests replay instead of touching the network or a
storage root.

Rules:

- **Small.** A single fixture file stays under 256 KiB (`tests/test_repository_contract.py`
  enforces it). A fixture is a miniature, not a sample of the corpus.
- **Documented.** Every fixture is listed below with what it is, where it came from and why it may
  be versioned.
- **Not production material.** Prefer synthetic pages written for the test. A recorded real
  response is admissible only when the operator's acquisition policy allows it to be versioned and
  the entry below records its origin and fetch instant.
- **Byte-pinned.** Fixtures are stored verbatim (`tests/fixtures/** -text` in `.gitattributes`);
  never reformat or re-save one. A fixture whose bytes change is a new fixture. The SHA-256 of
  every fixture is pinned in `tests/fixtures/canary/MANIFEST.json` and checked by
  `tests/test_core_pipeline.py`.

| Fixture | Content | Origin | Used by |
|---|---|---|---|
| `canary/nota_v1.html` | an invented news article of an invented outlet (`diario-ejemplo.test`): JSON-LD, OpenGraph, `rel=canonical`, title, paragraphs (one very short, one containing "Suscribite", words such as *separar*, *preparar*, *crecimiento*), heading, list, block quote, caption, navigation, aside, footer | synthetic, written for the test on 2026-10-07; no third-party text | `tests/test_extraction.py`, `tests/test_core_pipeline.py` |
| `canary/nota_v2.html` | the same article at the same URL with a changed body (an added "Actualización" paragraph; list, quote and caption gone) | synthetic, 2026-10-07 | same |
| `canary/nota_republicada.html` | another URL of the same outlet carrying exactly the body text of `nota_v2.html` under another title and without metadata | synthetic, 2026-10-07 | same |
| `canary/sin_metadatos.html` | a page without `head`, metadata, `article` element or `h1`; text standing directly in `div` elements | synthetic, 2026-10-07 | same |

The fixtures belong to a test-only outlet id, `uy_diario_ejemplo`, that exists only inside the
tests' in-memory registry. It is not in `config/outlet_registry.json` and names no real outlet.
