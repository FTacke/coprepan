# Test fixtures

Small, documented, non-production samples that tests replay instead of touching the network or a
storage root. None exists yet.

Rules:

- **Small.** A single fixture file stays under 256 KiB (`tests/test_repository_contract.py`
  enforces it). A fixture is a miniature, not a sample of the corpus.
- **Documented.** Every fixture is listed below with what it is, where it came from and why it may
  be versioned.
- **Not production material.** Prefer synthetic pages written for the test. A recorded real
  response is admissible only when the operator's acquisition policy allows it to be versioned and
  the entry below records its origin and fetch instant.
- **Byte-pinned.** Fixtures are stored verbatim (`tests/fixtures/** -text` in `.gitattributes`);
  never reformat or re-save one. A fixture whose bytes change is a new fixture.

| Fixture | Content | Origin | Used by |
|---|---|---|---|
| — | — | — | — |
