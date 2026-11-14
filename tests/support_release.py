"""Test support for ``crosscorpus-release/v1``: the bundle, its vectors, and how a vector case runs.

The expected values are **the bundle's**, read from ``conformance/VECTORS.json`` of the pinned copy.
Nothing here computes an expectation of its own. The operations a case declares are executed as the
vectors' own note describes them; every case runs on a copy of ``fixtures/`` under ``tmp_path``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable, Mapping

from coprepan import release_contract as R
from coprepan.canonical import record_json

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / R.BUNDLE_PATH
PINS = REPO / R.PINS_PATH
VECTORS = json.loads((BUNDLE / "conformance" / "VECTORS.json").read_text(encoding="utf-8"))
CASES = VECTORS["cases"]
PATTERNS = VECTORS["patterns"]  # since draft revision 2: schema patterns with values and verdicts (contract §12)


def fixtures_copy(tmp_path: Path) -> Path:
    """A copy of the bundle's fixtures in a new directory; paths of a case are relative to it."""
    return Path(shutil.copytree(BUNDLE / "fixtures", tmp_path / "fixtures"))


def mutate(root: Path, mutation: Mapping[str, Any]) -> None:
    """One declared manipulation of a copy of ``fixtures/``."""
    operation, path = mutation["op"], root / mutation["path"]
    if operation == "append_bytes":
        with open(path, "ab") as handle:
            handle.write(bytes.fromhex(mutation["hex"]))
    elif operation == "delete":
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    elif operation == "write_file":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes.fromhex(mutation["hex"]))
    elif operation == "replace_bytes":
        data, find = path.read_bytes(), mutation["find"].encode("utf-8")
        assert data.count(find) == 1, f"{mutation['find']!r} occurs {data.count(find)} times in {mutation['path']}"
        path.write_bytes(data.replace(find, mutation["replace"].encode("utf-8")))
    elif operation == "reverse_lines":
        path.write_bytes(b"".join(reversed(path.read_bytes().splitlines(keepends=True))))
    elif operation == "compact_json":
        value = json.loads(path.read_text(encoding="utf-8"))
        path.write_bytes(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    elif operation == "set_record_set":
        path.write_bytes(R.record_set_bytes(mutation["records"]))
        change_document(root / mutation["manifest"], lambda manifest: _at(manifest, mutation["pointer"]).update(
            records=len(mutation["records"]), sha256=R.record_set_digest(mutation["records"])))
    elif operation == "set_json":  # revision 2: set the value at a JSON pointer, adding the last key when absent
        change_document(path, lambda document: _set_at(document, mutation["pointer"], mutation["value"]))
    elif operation == "refreeze":  # revision 2: the freeze record names the manifest as it is at this point
        manifest = R.parse_strict((root / mutation["manifest"]).read_bytes())
        digest = R.document_digest(manifest)
        change_document(path, lambda freeze: freeze.update(corpus_id=manifest["corpus_id"], release_id=manifest["release_id"],
                                                           release_manifest_sha256=digest))
    else:
        raise AssertionError(f"unknown operation {operation!r}")


OPERATIONS = ("append_bytes", "delete", "write_file", "replace_bytes", "reverse_lines", "compact_json", "set_record_set",
              "set_json", "refreeze")


def _tokens(pointer: str) -> list[str]:
    """The reference tokens of a JSON pointer (RFC 6901)."""
    assert pointer.startswith("/"), f"not a JSON pointer: {pointer!r}"
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def _at(document: Any, pointer: str) -> Any:
    for part in _tokens(pointer):
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def _set_at(document: Any, pointer: str, value: Any) -> None:
    *parents, last = _tokens(pointer)
    for part in parents:
        document = document[int(part)] if isinstance(document, list) else document[part]
    if isinstance(document, list):
        document[int(last)] = value
    else:
        document[last] = value


def change_document(path: Path, change: Callable[[dict], Any]) -> dict:
    """Rewrite a stored document after ``change`` and return it."""
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_bytes(record_json(document))
    return document


def run_case(root: Path, case: Mapping[str, Any], contract: R.Contract) -> R.Verdict:
    target = root / case["target"]
    if case["check"] == "release":
        return R.verify_release(target / "release", exports_root=target / "exports", require_exports=True, contract=contract)
    if case["check"] == "package":
        return R.verify_package(target, contract=contract)
    assert case["check"] == "study"
    return R.verify_study(target, releases_of(root), contract=contract)


def releases_of(root: Path) -> dict[str, Path]:
    return {release_id: root / place for release_id, place in VECTORS["releases"].items()}


def refreeze(release: Path) -> str:
    """Make the freeze record of a (changed) fixture release name its manifest again."""
    digest = R.release_manifest_digest(release)
    change_document(release / R.RELEASE_FREEZE, lambda freeze: freeze.update(release_manifest_sha256=digest))
    return digest


def change_release(release: Path, change: Callable[[dict], Any]) -> str:
    """Change a fixture release manifest and freeze it again; return the new manifest digest."""
    change_document(release / R.RELEASE_MANIFEST, change)
    return refreeze(release)


def set_records(release: Path, name: str, file_name: str, records: list[dict]) -> None:
    """Replace a pinned record set of a fixture release and re-pin it (no re-freeze)."""
    (release / file_name).write_bytes(R.record_set_bytes(records))
    change_document(release / R.RELEASE_MANIFEST, lambda manifest: manifest[name].update(
        records=len(records), sha256=R.record_set_digest(records)))


def records_of(path: Path) -> list[dict]:
    return R.parse_records(path.read_bytes())
