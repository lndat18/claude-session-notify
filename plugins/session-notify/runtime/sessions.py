"""Find the VS Code terminal that runs this hook's Claude session, and create click tickets.

The VS Code extension (extension/) publishes terminal pids in ~/.claude/session-notify/terminals.
A hook is a descendant of the terminal's shell, so walking up the process tree finds the terminal.
"""

import json
import os
import time
import uuid
from pathlib import Path

STATE = Path.home() / ".claude" / "session-notify"
HEARTBEAT_MAX_AGE = 5  # seconds; older records belong to a closed or frozen window
TICKET_MAX_AGE = 86400


def _stat_fields(pid: int) -> list[str] | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    return stat[stat.rfind(")") + 2 :].split()


def _start_time(pid: int) -> str | None:
    fields = _stat_fields(pid)
    return fields[19] if fields and len(fields) > 19 else None


def _ancestors(pid: int) -> set[int]:
    seen: set[int] = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        fields = _stat_fields(pid)
        if not fields:
            break
        pid = int(fields[1])
    return seen


def find_terminal() -> dict | None:
    """Return {instance, pid, start, focused, active} for this process's VS Code terminal, or None."""
    ancestors = _ancestors(os.getpid())
    for path in (STATE / "terminals").glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if time.time() - row.get("timestamp", 0) > HEARTBEAT_MAX_AGE:
            continue
        for terminal in row.get("terminals", []):
            pid = terminal.get("pid")
            if pid in ancestors and terminal.get("start") == _start_time(pid):
                return {
                    "instance": row["instance"],
                    "pid": pid,
                    "start": terminal["start"],
                    "focused": bool(row.get("focused")),
                    "active": row.get("activePid") == pid,
                }
    return None


def make_ticket(terminal: dict, project: str) -> str:
    """Write a ticket the click handler and extension use to find the terminal; return its token."""
    tickets = STATE / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)
    token = str(uuid.uuid4())
    path = tickets / f"{token}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {
                "instance": terminal["instance"],
                "terminalPid": terminal["pid"],
                "terminalStart": terminal["start"],
                "project": project,
                "created": time.time(),
            }
        ),
        encoding="utf-8",
    )
    tmp.replace(path)
    for old in tickets.glob("*.json"):
        try:
            if time.time() - old.stat().st_mtime > TICKET_MAX_AGE:
                old.unlink()
        except OSError:
            pass
    return token
