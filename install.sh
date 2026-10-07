#!/usr/bin/env bash
# One-step installer: registers this repo as a Claude Code marketplace and installs the plugin.
#
#   git clone https://github.com/lndat18/claude-session-notify.git && bash claude-session-notify/install.sh
#
# Options:
#   --local       register this clone (path) instead of the GitHub repo; keep the clone afterwards
#   --uninstall   remove the plugin and the marketplace
#   --dry-run     print what would run, change nothing
set -euo pipefail

REPO="lndat18/claude-session-notify"
MARKETPLACE="lndat-plugins"
PLUGIN="session-notify"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mode=install
source_ref="$REPO"
dry=0
for arg in "$@"; do
  case "$arg" in
    --local) source_ref="$DIR" ;;
    --uninstall) mode=uninstall ;;
    --dry-run) dry=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

run() {
  echo "+ $*"
  if [ "$dry" -eq 0 ]; then "$@"; fi
}

fail() { echo "ERROR: $*" >&2; exit 1; }

command -v claude >/dev/null || fail "Claude Code CLI ('claude') not found in PATH."

if [ "$mode" = uninstall ]; then
  run claude plugin uninstall "$PLUGIN@$MARKETPLACE" || true
  run claude plugin marketplace remove "$MARKETPLACE" || true
  echo "Removed. Optional cleanup on Windows: %LOCALAPPDATA%\\ClaudeSessionNotify and HKCU\\Software\\Classes\\AppUserModelId\\ClaudeSessionNotify"
  exit 0
fi

# Prerequisites (the plugin shows Windows toasts from WSL).
grep -qi microsoft /proc/version 2>/dev/null || fail "This plugin needs WSL (Windows toasts)."
command -v powershell.exe >/dev/null || fail "powershell.exe not reachable: enable WSL interop."
command -v wslpath >/dev/null || fail "wslpath not found."
command -v python3 >/dev/null || fail "python3 not found in WSL."

if grep -q "notify.py\|SystemSounds" "$HOME/.claude/settings.json" 2>/dev/null; then
  echo "WARNING: ~/.claude/settings.json already has notification hooks; remove them to avoid duplicate toasts."
fi

if claude plugin marketplace list 2>/dev/null | grep -q "$MARKETPLACE"; then
  run claude plugin marketplace update "$MARKETPLACE"
else
  run claude plugin marketplace add "$source_ref"
fi
run claude plugin install "$PLUGIN@$MARKETPLACE"

if [ "$dry" -eq 0 ]; then
  python3 "$DIR/plugins/$PLUGIN/runtime/notify.py" --test || true
fi
echo "Done. Restart Claude Code (or run /hooks) so the hooks load."
