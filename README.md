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
- Installed once as a user plugin: applies to every project.

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

- Several Claude sessions in the same VS Code window cannot be told apart: that window being focused counts as watching.
- Two VS Code windows whose folder names contain each other's name can be confused.
- Plain terminals (Windows Terminal, WezTerm, Alacritty): any focus counts as watching, since tab titles lack the project name.
- The `Stop` hook reads the transcript; if it is not flushed yet the preview may show the previous reply.
- Clicking the toast does not switch windows (see [codex-session-notify](https://github.com/lndat18/codex-session-notify) for that).
- If you already added Stop/Notification hooks in `~/.claude/settings.json` for the same purpose, remove them to avoid duplicate toasts.

## Uninstall / Gỡ

```text
/plugin uninstall session-notify@lndat-plugins
```

The registry key `HKCU\Software\Classes\AppUserModelId\ClaudeSessionNotify` and `%LOCALAPPDATA%\ClaudeSessionNotify\` can be deleted manually.

## License

MIT
