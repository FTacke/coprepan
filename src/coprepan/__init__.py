"""COPREPAN 3.0 -- preservation-first pipeline for the CO.PRE.PAN press corpus.

The package carries the naming contract, the core primitives (identity, registry, ledger, storage
roots, promotion, outage spool, layer store) and the first core section of the pipeline for
*recorded* exchanges: acquisition run and fetch record, sealed WARC packs, raw preservation,
document identity, the extraction contract with a baseline extractor, and replay.

Nothing here touches the network, nothing has been acquired or preserved for the corpus, and no
component is validated or activated. See `docs/STATUS.md`.
"""

__version__ = "0.2.0"
