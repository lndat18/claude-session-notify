// Publishes this window's terminals + focus state, and focuses a terminal on request.
// State lives in ~/.claude/session-notify:
//   terminals/<instance>.json  heartbeat: terminal pids, window focus, active terminal
//   tickets/<token>.json       written by the hook: which terminal a toast belongs to
//   requests/<token>           created by the Windows click handler: "focus that ticket"
const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const TOKEN = /^[0-9a-f-]{36}$/;
const REQUEST_TTL_MS = 30000;

function activate(context) {
  const root = path.join(os.homedir(), '.claude', 'session-notify');
  const terminalsDir = path.join(root, 'terminals');
  const ticketsDir = path.join(root, 'tickets');
  const requestsDir = path.join(root, 'requests');
  for (const dir of [terminalsDir, ticketsDir, requestsDir]) fs.mkdirSync(dir, { recursive: true });

  const instance = crypto.randomUUID();
  const record = path.join(terminalsDir, instance + '.json');
  let busy = false;
  let disposed = false;

  // Process start time distinguishes a reused pid from the original shell.
  function startTime(pid) {
    try {
      const stat = fs.readFileSync(`/proc/${pid}/stat`, 'utf8');
      return stat.slice(stat.lastIndexOf(')') + 2).split(' ')[19];
    } catch (_) {
      return null;
    }
  }

  function writeAtomic(file, data) {
    fs.writeFileSync(file + '.tmp', JSON.stringify(data));
    fs.renameSync(file + '.tmp', file);
  }

  async function snapshot() {
    const rows = [];
    for (const terminal of vscode.window.terminals) {
      const pid = await terminal.processId;
      if (pid) rows.push({ terminal, pid, start: startTime(pid), name: terminal.name });
    }
    return rows;
  }

  function publish(rows) {
    const active = rows.find((r) => r.terminal === vscode.window.activeTerminal);
    writeAtomic(record, {
      instance,
      workspace: (vscode.workspace.workspaceFolders || []).map((f) => f.uri.fsPath),
      timestamp: Date.now() / 1000,
      focused: vscode.window.state.focused,
      activePid: active ? active.pid : null,
      terminals: rows.map(({ pid, start, name }) => ({ pid, start, name })),
    });
  }

  async function handleRequests(rows) {
    for (const name of fs.readdirSync(requestsDir)) {
      if (!TOKEN.test(name)) continue;
      const requestFile = path.join(requestsDir, name);
      let ticket;
      try {
        if (Date.now() - fs.statSync(requestFile).mtimeMs > REQUEST_TTL_MS) {
          fs.unlinkSync(requestFile);
          continue;
        }
        ticket = JSON.parse(fs.readFileSync(path.join(ticketsDir, name + '.json'), 'utf8'));
      } catch (_) {
        continue;
      }
      if (ticket.instance !== instance) continue; // another window owns this ticket
      try { fs.unlinkSync(requestFile); } catch (_) { continue; }
      const match = rows.find((r) => r.pid === ticket.terminalPid && r.start === ticket.terminalStart);
      if (!match) continue; // terminal was closed
      match.terminal.show(false);
      await vscode.commands.executeCommand('workbench.action.terminal.focus');
    }
  }

  async function tick() {
    if (busy || disposed) return;
    busy = true;
    try {
      const rows = await snapshot();
      if (disposed) return;
      publish(rows);
      await handleRequests(rows);
    } catch (_) {
      // best effort: the hook falls back to window-title detection
    } finally {
      busy = false;
    }
  }

  const timer = setInterval(tick, 1000);
  let watcher;
  try { watcher = fs.watch(requestsDir, () => tick()); } catch (_) {}

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTerminal(tick),
    vscode.window.onDidOpenTerminal(tick),
    vscode.window.onDidCloseTerminal(tick),
    vscode.window.onDidChangeWindowState(tick),
    {
      dispose() {
        disposed = true;
        clearInterval(timer);
        if (watcher) watcher.close();
        try { fs.unlinkSync(record); } catch (_) {}
      },
    },
  );
  tick();
}

function deactivate() {}

module.exports = { activate, deactivate };
