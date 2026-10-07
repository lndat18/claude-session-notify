# Claude Session Notify

Windows toast + sound for Claude Code in VS Code + WSL, shown only when you are **not** looking at that session.

Thông báo Windows (toast + âm thanh) cho Claude Code trong VS Code + WSL, chỉ hiện khi bạn **không** đang xem session đó.

## Install / Cài đặt

**One line from a WSL terminal / Một dòng từ terminal WSL:**

```bash
git clone https://github.com/lndat18/claude-session-notify.git && bash claude-session-notify/install.sh
```

The script checks prerequisites, registers the marketplace, installs the plugin and shows a test toast. `--local` registers the clone instead of GitHub, `--uninstall` removes everything, `--dry-run` previews. Update later with `/plugin marketplace update lndat-plugins`.

Script tự kiểm tra điều kiện, đăng ký marketplace, cài plugin và hiện toast thử. Có thể xoá thư mục clone sau khi cài (trừ khi dùng `--local`).

**Or manually inside Claude Code / Hoặc thủ công trong Claude Code:**

```text
/plugin marketplace add lndat18/claude-session-notify
/plugin install session-notify@lndat-plugins
```

Then restart the session (or run `/hooks`) so the hooks load. Test it / Thử:

```bash
python3 ~/.claude/plugins/marketplaces/lndat-plugins/plugins/session-notify/runtime/notify.py --test
```

## Features / Tính năng

- Toast + sound when Claude finishes (`Stop`) and when it needs you (`Notification`).
- Toast shows the **session title** (your `/rename`, or the auto title), a **trimmed preview** of the answer, and the project name.
- Header shows "Claude Code" with the Claude logo instead of "Windows PowerShell".
- **Focus-aware:** no toast while the focused window is this project's VS Code window. With two VS Code windows on two projects, the toast still fires for the project you are not looking at.
- **Click to return:** clicking the toast brings that project's VS Code window to the foreground (restores it if minimized).
- **Exact terminal (VS Code extension):** with the bundled extension installed, the plugin knows which terminal runs which session. No toast while *that* terminal is the active one in the focused window (other terminals in the same window still notify), and clicking the toast selects that exact terminal.
- Installed once as a user plugin: applies to every project.

## VS Code extension (exact terminal) / Extension VS Code

`install.sh` installs it automatically when run from a VS Code integrated terminal. Otherwise, from a VS Code terminal:

```bash
python3 ~/.claude/plugins/marketplaces/lndat-plugins/plugins/session-notify/runtime/install_extension.py
```

Then run **Developer: Reload Window** in each open VS Code WSL window. Remove it with `--uninstall`. Without the extension everything still works, at window level.

How it works: the extension publishes its terminals' shell pids in `~/.claude/session-notify/`. The hook walks up its process tree to find the terminal shell, stores a ticket, and the toast carries only an opaque token. The Windows click handler focuses the window, then drops a request file that the extension turns into `terminal.show()`.

**Speed:** `powershell.exe` takes 1.3-2.8 s to start from WSL, so the click handler avoids it. `focus.vbs` (run by `wscript.exe`, ~0.1 s) calls `AppActivate` with the end of the window title ("`<folder> [WSL: Ubuntu] - Visual Studio Code`", saved by the toast script; it does not change when the active file changes) and creates the request file: click to terminal in ~0.1 s. PowerShell still runs hidden afterwards as a safety net that restores a minimized window, and does the whole job if the fast path fails. The toast itself still needs one PowerShell start (~1.5 s after Claude finishes).

*Tried and dropped:* a small native `.exe` helper (80 ms start). Windows Application Control / Smart App Control blocked the locally compiled, unsigned binary after a few runs, so a click could silently do nothing.

## Requirements / Yêu cầu

- Windows 10/11 + WSL with interop (`powershell.exe`, `wslpath` reachable).
- Python 3.8+ in WSL; Claude Code with plugin support.

## Configuration / Cấu hình

| Setting | How |
| --- | --- |
| Language of fallback texts (`en` default, `vi`) | env `CLAUDE_SESSION_NOTIFY_LANG=vi` |
| Custom icon | put a PNG at `%LOCALAPPDATA%\ClaudeSessionNotify\claude.png` |
| Which windows count as "watching" | edit `IDE_HOSTS` / `TERMINAL_HOSTS` in `runtime/notify.py` |

The Claude logo is copied at first run from your local Claude Desktop install; it is not bundled in this repo. Without Claude Desktop the toast has no logo unless you provide a PNG.

## Limitations / Giới hạn

- Without the VS Code extension, several Claude sessions in the same VS Code window cannot be told apart.
- Claude run from the Claude Code VS Code panel (not a terminal) is not a terminal, so it uses window-level detection.
- Two VS Code windows whose folder names contain each other's name can be confused.
- Plain terminals (Windows Terminal, WezTerm, Alacritty): any focus counts as watching, since tab titles lack the project name.
- The `Stop` hook reads the transcript; if it is not flushed yet the preview may show the previous reply.
- Terminal-exact focus needs the extension; without it a click focuses the window only.
- If you already added Stop/Notification hooks in `~/.claude/settings.json` for the same purpose, remove them to avoid duplicate toasts.

## Uninstall / Gỡ

```text
/plugin uninstall session-notify@lndat-plugins
```

Also remove the extension with `install.sh --uninstall`. Registry keys `HKCU\Software\Classes\AppUserModelId\ClaudeSessionNotify` and `HKCU\Software\Classes\claude-session-notify`, and the folder `%LOCALAPPDATA%\ClaudeSessionNotify\`, can be deleted manually.

## Tests / Kiểm thử

```bash
node tests/extension_cases.js          # extension: terminal selection, two windows, closed/renamed/reused terminals
python3 -m unittest discover -s tests  # hook: process-tree lookup, tickets, watching rules (shimmed powershell.exe)
```

Both run without VS Code or Windows (fake `vscode` API, real processes, shimmed `powershell.exe`).

## License

MIT
