"""COPREPAN 3.0 -- preservation-first pipeline for the CO.PRE.PAN press corpus.

The package carries the naming contract, the core primitives (identity, registry, ledger, storage
roots, promotion, outage spool, layer store) and the acquisition pipeline: discovery, an HTTP
fetcher behind a policy gate, sealed WARC packs, raw preservation, document identity, the
extraction contract with a baseline extractor, and replay.

Nothing has been requested from a real site, and nothing can be as committed: the tracked policy
is undecided, the tracked crawler identity is not configured and no outlet is registered. Nothing
has been acquired or preserved for the corpus; no component is validated or activated. See
`docs/STATUS.md`.
"""

__version__ = "0.3.0"
