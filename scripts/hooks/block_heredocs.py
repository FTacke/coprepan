#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse heredocs and PowerShell here-strings (AGENTS.md §5).

On this Windows setup they mangle line breaks, backslashes and quotes. The rule has been in AGENTS.md since the
bootstrap and was still broken in four runs of 2026-10-09 (empty no-op heredocs, and twice a real one that appended
to a test file). This makes it mechanical: exit code 2 blocks the call and shows the message to the agent.

The mechanism is CO.RA.PAN's (its ``scripts/hooks/block_heredocs_v1.py``), written again here; nothing in that
repository was changed. Reads the hook's JSON from stdin (``tool_input.command``); anything else passes.

Refused: ``<<EOF``, ``<<-EOF``, ``<< 'EOF'``, ``<<"EOF"``, ``<<\\EOF`` and a PowerShell ``@'`` / ``@"`` that ends its line.
Not refused: a bash here-*string* (``<<<``, one line, not named by the rule), a numeric shift (``1 << 3``), and the
characters inside an ordinary quoted argument that does not open a heredoc.
"""

from __future__ import annotations

import json
import re
import sys

# bash heredoc:  <<EOF  <<-EOF  << 'EOF'  <<"EOF"  <<\EOF   (not <<<, not a numeric shift such as 1 << 3)
BASH_HEREDOC = re.compile(r"(?:^|[^<\w])<<-?\s*(?:'\w+'|\"\w+\"|\\?[A-Za-z_]\w*)")
# PowerShell here-string: @' ... '@ / @" ... "@  (the opening token ends its line)
PS_HERESTRING = re.compile(r"@['\"][ \t]*(?:\r?\n|$)")

MESSAGE = ("BLOCKED (AGENTS.md section 5, 'no heredocs'): heredocs and PowerShell here-strings break line breaks, backslashes and "
           "quotes on this Windows setup. Write file content with the Write/Edit tools, put code in a script file and run it, "
           "and use `git commit -F <file>`.")


def violates(command: str) -> bool:
    return bool(BASH_HEREDOC.search(command) or PS_HERESTRING.search(command))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, str) and violates(command):
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
