"""The heredoc hook (AGENTS.md §5): what it refuses, what it lets through, and that the project wires it in."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts" / "hooks" / "block_heredocs.py"


def load():
    spec = importlib.util.spec_from_file_location("block_heredocs", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load()
OPEN = "<" + "<"          # written apart so that this file never contains a heredoc of its own in a command it runs

REFUSED = [
    f"cat > file.txt {OPEN}EOF\ntext\nEOF",
    f"cat >> tests/test_x.py {OPEN}'PYEOF'\ndef test():\n    pass\nPYEOF",
    f"python - {OPEN}'EOF'\nEOF",
    f"python - {OPEN}EOF 2>/dev/null\nEOF\ntrue",
    f"git commit -F - {OPEN}-MSG\n\tsubject\n\tMSG",
    f'cat {OPEN} "END"\nx\nEND',
    f"cat {OPEN}\\EOF\nx\nEOF",
    f"cd /repo && python - {OPEN}'EOF'\nprint(1)\nEOF",
    "$text = @'\nline\n'@\nSet-Content x $text",
    'git commit -m @"\nsubject\n"@',
]
ALLOWED = [
    "git status --short",
    "python -m pytest -q tests",
    "python scripts/canary_operator.py --operator x --label second --outlet bo_el_deber < /dev/null",
    f"grep -c pattern {OPEN}< \"$TEXT\"",                      # a bash here-string: one line, not named by the rule
    "echo $(( 1 << 3 ))",
    "python -c \"print(1 << 3)\"",
    "git log --format='%H %s' -3",
    "Get-Content file.txt | Select-Object -First 3",
    "echo 'user@example.test'",
    "git commit -F message.txt",
]


@pytest.mark.parametrize("command", REFUSED)
def test_a_heredoc_or_a_here_string_is_refused(command):
    assert hook.violates(command)


@pytest.mark.parametrize("command", ALLOWED)
def test_an_ordinary_command_passes(command):
    assert not hook.violates(command)


def run_hook(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK)], input=payload, text=True, capture_output=True)


def test_as_a_hook_it_blocks_with_exit_2_and_a_message_and_passes_everything_else():
    blocked = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": REFUSED[0]}}))
    assert blocked.returncode == 2 and "AGENTS.md section 5" in blocked.stderr and "Write/Edit" in blocked.stderr
    for payload in (json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}), json.dumps({"tool_input": {"file_path": "x"}}),
                    json.dumps({"tool_input": None}), json.dumps([1, 2]), "", "not json"):
        passed = run_hook(payload)
        assert passed.returncode == 0 and passed.stderr == "", payload


def test_the_project_settings_run_the_hook_for_both_shells_and_grant_nothing():
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert set(settings) == {"hooks"}                                             # a hook, and no permission rule of any kind
    (entry,) = settings["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Bash|PowerShell"
    assert entry["hooks"] == [{"type": "command", "command": 'python "$CLAUDE_PROJECT_DIR/scripts/hooks/block_heredocs.py"'}]
    assert HOOK.is_file()
