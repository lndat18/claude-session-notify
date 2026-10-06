#!/usr/bin/env python3
"""Claude Code hook (Stop / Notification): Windows toast + sound from WSL.

Skips the toast while the focused window is the terminal/IDE of this project.

Usage:
  notify.py [Asterisk|Exclamation|...]   # hook mode, JSON payload on stdin
  notify.py --test                       # always show a sample toast
"""

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_BODY = 180
MAX_TITLE = 60
TOAST_SCRIPT = Path(__file__).resolve().parent.parent / "windows" / "toast.ps1"

TEXTS = {
    "en": {"finished": "Finished responding", "waiting": "Claude is waiting for you"},
    "vi": {"finished": "Đã trả lời xong", "waiting": "Claude đang chờ bạn"},
}
LANG = os.environ.get("CLAUDE_SESSION_NOTIFY_LANG", "en")
T = TEXTS.get(LANG, TEXTS["en"])

# IDEs can have several windows open; the title contains the folder name,
# so the project name must match for the user to count as "watching".
IDE_HOSTS = {"code", "code - insiders", "cursor", "windsurf", "idea64", "pycharm64"}
# Plain terminals: tab titles do not carry the project, so any focus counts as watching.
TERMINAL_HOSTS = {"windowsterminal", "wezterm-gui", "alacritty"}

_FOREGROUND_PS = """
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class FG {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
}
"@
$h = [FG]::GetForegroundWindow()
$p = 0
[void][FG]::GetWindowThreadProcessId($h, [ref]$p)
$sb = New-Object Text.StringBuilder 512
[void][FG]::GetWindowText($h, $sb, 512)
$name = (Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName
[Console]::OutputEncoding = [Text.Encoding]::UTF8
"$name|$($sb.ToString())"
"""


def _trim(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _clean_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"[`*_#>|]", "", text)


def _read_transcript(path: str) -> tuple[str, str]:
    """Return (session title, last assistant text) from the session transcript."""
    title, last_text = "", ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                kind = d.get("type")
                if kind == "custom-title" and d.get("customTitle"):
                    title = d["customTitle"]
                elif kind == "ai-title" and d.get("aiTitle") and not title:
                    title = d["aiTitle"]
                elif kind == "assistant":
                    content = d.get("message", {}).get("content")
                    if isinstance(content, list):
                        texts = [
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                        if any(t.strip() for t in texts):
                            last_text = " ".join(texts)
    except OSError:
        pass
    return title, last_text


def _user_is_watching(project: str) -> bool:
    """True if the focused window is this project's terminal/IDE.

    Fails open: if detection errors, return False so the toast still shows.
    """
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", _FOREGROUND_PS],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    name, _, window_title = out.strip().partition("|")
    name = name.lower()
    if name in TERMINAL_HOSTS:
        return True
    return name in IDE_HOSTS and project.lower() in window_title.lower()


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _show_toast(title: str, body: str, project: str, sound: str) -> None:
    script = subprocess.check_output(["wslpath", "-w", str(TOAST_SCRIPT)], text=True).strip()
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script,
            "-TitleB64",
            _b64(title),
            "-MessageB64",
            _b64(body),
            "-ProjectB64",
            _b64(project),
            "-Sound",
            sound,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    if "--test" in sys.argv:
        _show_toast("Claude Code", "claude-session-notify is working", Path.cwd().name, "Asterisk")
        return

    sound = sys.argv[1] if len(sys.argv) > 1 else "Asterisk"
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}

    project = Path(data.get("cwd") or ".").name
    if _user_is_watching(project):
        return

    title, last_text = _read_transcript(data.get("transcript_path", ""))
    if data.get("hook_event_name") == "Notification":
        body = data.get("message") or T["waiting"]
    else:
        body = _clean_markdown(data.get("last_assistant_message") or last_text) or T["finished"]

    _show_toast(_trim(title or project or "Claude Code", MAX_TITLE), _trim(body, MAX_BODY), project, sound)


if __name__ == "__main__":
    main()
