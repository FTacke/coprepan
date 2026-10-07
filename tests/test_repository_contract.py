"""Repository contracts that documents state and nothing else would enforce.

Each test names the rule it guards. None of them reads outside the repository.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

from conftest import SUITE_NAMES, suite_members
from coprepan import naming, stages

REPO = Path(__file__).resolve().parents[1]
DECISIONS = REPO / "docs" / "decisions"
DECISION_STATUSES = {
    "ACTIVE",
    "ACTIVE_WITH_VALIDATION_DEBT",
    "DIRECTION_NOT_STARTED",
    "PARTIALLY_SUPERSEDED",
    "SUPERSEDED",
    "REJECTED",
    "HISTORICAL",
}
FIXTURE_MAX_BYTES = 256 * 1024


def read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def status_assertions() -> dict:
    match = re.search(
        r"<!-- status_assertions:begin -->\s*```json\s*(.*?)```\s*<!-- status_assertions:end -->",
        read("docs/STATUS.md"),
        re.DOTALL,
    )
    assert match, "docs/STATUS.md has no machine-readable assertions block"
    return json.loads(match.group(1))


# --- docs/STATUS.md: planned / implemented / validated / activated ------------------------------


def test_status_block_names_exactly_the_pipeline_stages():
    block = status_assertions()
    assert naming.is_schema_id(block["schema"])
    assert tuple(block["stages"]) == stages.PIPELINE_STAGES


def test_no_stage_is_active_without_being_implemented_and_validated():
    block = status_assertions()
    problems = [
        problem
        for stage, status in block["stages"].items()
        for problem in stages.status_violations(stage, status)
    ]
    assert problems == []


def test_production_pipeline_flag_matches_the_stages():
    block = status_assertions()
    any_active = any(status["activation"] == "ACTIVE" for status in block["stages"].values())
    assert block["production_pipeline_exists"] is any_active


def test_no_stage_is_active_while_a_production_gate_is_open():
    block = status_assertions()
    if block["open_production_gates"]:
        active = [s for s, status in block["stages"].items() if status["activation"] == "ACTIVE"]
        assert active == [], f"active with open gates {block['open_production_gates']}: {active}"


def test_status_tables_agree_with_the_block():
    block = status_assertions()
    text = read("docs/STATUS.md")
    rows = re.findall(r"^\| \d+ \| .+? \| `(\w+)` \| `(\w+)` \| `(\w+)` \|$", text, re.MULTILINE)
    assert rows == [
        (status["implementation"], status["validation"], status["activation"])
        for status in block["stages"].values()
    ]


def test_nlp_pins_are_not_dependencies_while_nlp_is_not_started():
    project = tomllib.loads(read("pyproject.toml"))
    nlp_started = status_assertions()["stages"]["nlp"]["implementation"] != "NOT_STARTED"
    planned = project["tool"]["coprepan"]["nlp"]["status"] == "PLANNED"
    has_spacy = any(dep.lower().startswith("spacy") for dep in project["project"]["dependencies"])
    assert planned is not nlp_started
    assert has_spacy is nlp_started


def test_runtime_dependencies_are_exact_pins():
    project = tomllib.loads(read("pyproject.toml"))
    loose = [dep for dep in project["project"]["dependencies"] if "==" not in dep]
    assert loose == []


# --- no absolute workstation path in tracked logic or configuration ------------------------------

PATH_SCAN_ROOTS = ("src", "config", "scripts", "tests")
PATH_SCAN_SUFFIXES = {".py", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini", ".txt", ".ps1", ".sh"}
CONFIG_SUFFIXES = {".yml", ".yaml", ".json", ".toml", ".cfg", ".ini"}
DRIVE_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")
HOME_PATH = re.compile(r"(?<![\w.])/(?:home|Users)/\w")
UNC_PATH = re.compile(r"\\\\[A-Za-z0-9]")


def scanned_files():
    for root in PATH_SCAN_ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in PATH_SCAN_SUFFIXES:
                continue
            relative = path.relative_to(REPO)
            if relative.parts[:2] == ("tests", "fixtures") or "__pycache__" in relative.parts:
                continue
            yield path


def test_no_absolute_path_in_tracked_logic_or_config():
    hits = []
    for path in scanned_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            patterns = [DRIVE_PATH, HOME_PATH]
            if path.suffix in CONFIG_SUFFIXES:
                patterns.append(UNC_PATH)
            if any(pattern.search(line) for pattern in patterns):
                hits.append(f"{path.relative_to(REPO).as_posix()}:{number}: {line.strip()}")
    assert hits == []


def test_storage_targets_hold_only_environment_references():
    text = read("config/storage_targets.yml")
    roots = re.findall(r"^\s*root:\s*(.+?)\s*$", text, re.MULTILINE)
    assert roots, "no storage target declared"
    variables = []
    for root in roots:
        match = re.fullmatch(r"\$\{(COPREPAN_[A-Z]+_ROOT)\}", root)
        assert match, f"storage root is not an environment reference: {root!r}"
        variables.append(match.group(1))
    example = dict(
        line.split("=", 1)
        for line in read(".env.example").splitlines()
        if line and not line.startswith("#")
    )
    assert sorted(example) == sorted(variables)
    assert set(example.values()) == {""}, ".env.example must not carry a real path"


# --- decision registry -----------------------------------------------------------------------------


def decision_files():
    return sorted(path for path in DECISIONS.glob("*.md") if path.name != "README.md")


def test_decision_files_follow_the_namespace():
    bad = [p.name for p in decision_files() if not re.fullmatch(r"CPD-\d{4}_[a-z0-9]+(?:-[a-z0-9]+)*\.md", p.name)]
    assert bad == []


def test_decision_registry_and_files_agree():
    registry_ids = re.findall(r"^\| (CPD-\d{4}) \|", read("docs/decisions/README.md"), re.MULTILINE)
    file_ids = [path.name[:8] for path in decision_files()]
    assert len(set(file_ids)) == len(file_ids), "a decision number is used twice"
    assert registry_ids == file_ids


@pytest.mark.parametrize("path", decision_files(), ids=lambda path: path.name[:8])
def test_decision_record_header(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith(f"# {path.name[:8]} — ")
    status = re.search(r"^\| Status \| `(\w+)` \|$", text, re.MULTILINE)
    assert status and status.group(1) in DECISION_STATUSES
    assert re.search(r"^\| Date \| \d{4}-\d{2}-\d{2} \|$", text, re.MULTILINE)
    for heading in ("## Context", "## Decision", "## Alternatives considered", "## Not decided here"):
        assert heading in text, f"{path.name}: missing {heading}"


# --- documents ---------------------------------------------------------------------------------------

LINK = re.compile(r"\]\(([^)\s]+)\)")


def markdown_files():
    return sorted(
        path
        for path in REPO.rglob("*.md")
        if not {".git", ".venv", "venv", ".pytest_cache", "node_modules"} & set(path.relative_to(REPO).parts)
    )


def test_relative_links_resolve():
    broken = []
    for path in markdown_files():
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.exists():
                broken.append(f"{path.relative_to(REPO).as_posix()} -> {target}")
    assert broken == []


def test_run_reports_are_dated():
    reports = [p.name for p in (REPO / "docs" / "agent-runs").glob("*.md") if p.name != "README.md"]
    bad = [name for name in reports if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*\.md", name)]
    assert bad == []


# --- hygiene -----------------------------------------------------------------------------------------


def test_gitignore_has_no_blanket_rule_on_structured_text():
    rules = {line.strip() for line in read(".gitignore").splitlines()}
    forbidden = {"*.json", "*.jsonl", "*.yml", "*.yaml", "*.csv", "*.tsv", "*.md", "*.txt", "*.toml", "*"}
    assert rules & forbidden == set()


def test_fixtures_are_small():
    too_big = [
        f"{path.relative_to(REPO).as_posix()} ({path.stat().st_size} bytes)"
        for path in (REPO / "tests" / "fixtures").rglob("*")
        if path.is_file() and path.stat().st_size > FIXTURE_MAX_BYTES
    ]
    assert too_big == []


def test_every_test_module_belongs_to_exactly_one_suite():
    modules = sorted(path.name for path in (REPO / "tests").glob("test_*.py"))
    listed = [member for name in SUITE_NAMES for member in suite_members(name)]
    assert sorted(listed) == modules
