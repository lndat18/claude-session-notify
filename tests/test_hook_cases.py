"""Use-case tests for the hook (runtime/notify.py), black box.

Each "terminal" is a real shell process; the hook is started inside it so its process tree
contains the shell, like a real Claude session. `powershell.exe` and `wslpath` are shims that
record what would have been shown. Run: python3 -m unittest discover -s tests
"""

import base64
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

NOTIFY = Path(__file__).resolve().parent.parent / "plugins/session-notify/runtime/notify.py"
SHIM_POWERSHELL = """#!/bin/bash
echo "$@" >> "$SHIM_LOG"
case "$*" in
  *-File*) ;;                      # toast
  *) echo "someotherapp|Notepad" ;; # foreground query (fallback path)
esac
"""
SHIM_WSLPATH = '#!/bin/bash\necho "${@: -1}"\n'


def start_time(pid: int) -> str:
    stat_text = Path(f"/proc/{pid}/stat").read_text()
    return stat_text[stat_text.rfind(")") + 2 :].split()[19]


class HookCases(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.state = self.home / ".claude" / "session-notify"
        (self.state / "terminals").mkdir(parents=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "shim.log"
        for name, body in (("powershell.exe", SHIM_POWERSHELL), ("wslpath", SHIM_WSLPATH)):
            path = self.bin / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        self.shells: list[subprocess.Popen] = []

    def tearDown(self):
        for shell in self.shells:
            shell.kill()
            shell.wait()

    def shell(self) -> subprocess.Popen:
        proc = subprocess.Popen(["sleep", "60"])  # stands in for the terminal's shell
        self.shells.append(proc)
        return proc

    def publish(self, instance, terminals, focused=True, active=None, age=0.0):
        row = {
            "instance": instance,
            "timestamp": time.time() - age,
            "focused": focused,
            "activePid": active.pid if active else None,
            "terminals": [{"pid": t.pid, "start": start_time(t.pid), "name": "bash"} for t in terminals],
        }
        (self.state / "terminals" / f"{instance}.json").write_text(json.dumps(row))

    def toasts(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [line.split() for line in self.log.read_text().splitlines() if "-File" in line]

    def ticket_pids(self) -> list[int]:
        return sorted(json.loads(p.read_text())["terminalPid"] for p in (self.state / "tickets").glob("*.json"))


def run_in_terminal(case: HookCases, instance_rows, which: int, project="proj", event="Stop"):
    """Start a wrapper shell (the 'terminal'), publish rows including it, wait for the hook."""
    env = {
        **os.environ,
        "HOME": str(case.home),
        "PATH": f"{case.bin}:{os.environ['PATH']}",
        "SHIM_LOG": str(case.log),
    }
    payload = json.dumps({"hook_event_name": event, "cwd": f"/work/{project}", "transcript_path": ""})
    term = subprocess.Popen(
        ["bash", "-c", f"sleep 0.7; echo '{payload}' | python3 {NOTIFY} Asterisk"], env=env
    )
    case.shells.append(term)
    instance_rows(term)
    term.wait(timeout=20)
    return term


class Cases(HookCases):
    def test_1_other_terminal_active_notifies_and_ticket_points_to_origin(self):
        other = self.shell()

        def rows(term):
            self.publish("w1", [term, other], focused=True, active=other)  # user is on the other terminal

        term = run_in_terminal(self, rows, 0)
        self.assertEqual(len(self.toasts()), 1)
        self.assertEqual(self.ticket_pids(), [term.pid])

    def test_2_same_project_two_terminals_get_distinct_tickets(self):
        other = self.shell()
        rows_a = lambda t: self.publish("w1", [t, other], focused=False, active=None)
        a = run_in_terminal(self, rows_a, 0, project="same")
        # second session: the *other* shell's tree, same project -> separate ticket
        b = run_in_terminal(self, lambda t: self.publish("w1", [t], focused=False), 1, project="same")
        self.assertEqual(len(self.toasts()), 2)
        self.assertEqual(sorted(set(self.ticket_pids())), sorted([a.pid, b.pid]))

    def test_4_two_windows_ticket_carries_owning_instance(self):
        far = self.shell()
        self.publish("w2", [far], focused=False)

        def rows(term):
            self.publish("w1", [term], focused=False)

        run_in_terminal(self, rows, 0)
        tickets = [json.loads(p.read_text()) for p in (self.state / "tickets").glob("*.json")]
        self.assertEqual([t["instance"] for t in tickets], ["w1"])

    def test_7_resume_in_another_terminal_points_to_that_terminal(self):
        a = self.shell()  # old terminal, session exited there
        term = run_in_terminal(self, lambda t: self.publish("w1", [a, t], focused=False), 1)
        self.assertNotIn(a.pid, self.ticket_pids())
        self.assertEqual(self.ticket_pids(), [term.pid])

    def test_10_watching_active_terminal_suppresses_toast(self):
        term = run_in_terminal(self, lambda t: self.publish("w1", [t], focused=True, active=t), 0)
        self.assertEqual(self.toasts(), [])
        self.assertEqual(self.ticket_pids(), [])
        self.assertIsNotNone(term)

    def test_10b_window_focused_but_other_terminal_active_still_notifies(self):
        other = self.shell()
        run_in_terminal(self, lambda t: self.publish("w1", [t, other], focused=True, active=other), 0)
        self.assertEqual(len(self.toasts()), 1)

    def test_stale_heartbeat_falls_back_to_window_title_detection(self):
        # No fresh record -> window-title fallback (shim says Notepad is focused) -> toast, no ticket.
        run_in_terminal(self, lambda t: self.publish("w1", [t], focused=True, active=t, age=60), 0)
        self.assertEqual(len(self.toasts()), 1)
        self.assertEqual(self.ticket_pids(), [])

    def test_toast_args_carry_token_and_state_dir(self):
        run_in_terminal(self, lambda t: self.publish("w1", [t], focused=False), 0)
        (args,) = self.toasts()
        token = args[args.index("-Token") + 1]
        self.assertTrue((self.state / "tickets" / f"{token}.json").exists())
        self.assertEqual(args[args.index("-StateDir") + 1], str(self.state))
        self.assertTrue(base64.b64decode(args[args.index("-TitleB64") + 1]))


if __name__ == "__main__":
    unittest.main()
