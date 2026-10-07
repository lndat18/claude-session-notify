// Use-case tests for extension/extension.js against a fake `vscode` API.
// Run: node tests/extension_cases.js
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const Module = require('module');

const EXT = path.resolve(__dirname, '../plugins/session-notify/extension/extension.js');
const home = fs.mkdtempSync(path.join(os.tmpdir(), 'sn-ext-'));
process.env.HOME = home;
const root = path.join(home, '.claude', 'session-notify');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Fake pids need a /proc entry for the start-time check, so use real processes' pids.
const pidOf = { A: process.pid, B: process.ppid, C: 1 };

function makeTerminal(label, name = 'bash') {
  return { label, name, shown: 0, processId: Promise.resolve(pidOf[label]), show() { this.shown += 1; } };
}

function openWindow(terminals, active, folder) {
  const calls = [];
  const vscode = {
    window: {
      terminals,
      activeTerminal: active,
      state: { focused: true },
      onDidChangeActiveTerminal: () => ({ dispose() {} }),
      onDidOpenTerminal: () => ({ dispose() {} }),
      onDidCloseTerminal: () => ({ dispose() {} }),
      onDidChangeWindowState: () => ({ dispose() {} }),
    },
    workspace: { workspaceFolders: [{ uri: { fsPath: folder } }] },
    commands: { executeCommand: async (c) => calls.push(c) },
  };
  const original = Module._load;
  Module._load = function (req, ...rest) {
    return req === 'vscode' ? vscode : original.call(this, req, ...rest);
  };
  delete require.cache[EXT];
  const subs = [];
  require(EXT).activate({ subscriptions: subs });
  Module._load = original;
  return { vscode, calls, dispose: () => subs.forEach((s) => s.dispose && s.dispose()) };
}

function startOf(pid) {
  const stat = fs.readFileSync(`/proc/${pid}/stat`, 'utf8');
  return stat.slice(stat.lastIndexOf(')') + 2).split(' ')[19];
}

async function instanceOf(win) {
  await sleep(1300);
  for (const f of fs.readdirSync(path.join(root, 'terminals'))) {
    if (!f.endsWith('.json')) continue;
    const rec = JSON.parse(fs.readFileSync(path.join(root, 'terminals', f)));
    if (rec.workspace[0] === win.vscode.workspace.workspaceFolders[0].uri.fsPath) return rec.instance;
  }
  throw new Error('no record');
}

let n = 0;
function token() { n += 1; return `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`; }

function click(instance, terminalPid, terminalStart, project = 'proj') {
  const t = token();
  fs.writeFileSync(path.join(root, 'tickets', t + '.json'),
    JSON.stringify({ instance, terminalPid, terminalStart, project, created: 1 }));
  fs.writeFileSync(path.join(root, 'requests', t), '');
  return t;
}

const results = [];
async function check(name, fn) {
  try { await fn(); results.push(['PASS', name]); }
  catch (e) { results.push(['FAIL', name + ' -> ' + e.message]); }
}

(async () => {
  // Case 1: session in A, user moved to B in the same window -> click selects A.
  await check('1  focus A while B is active', async () => {
    const A = makeTerminal('A'), B = makeTerminal('B');
    const win = openWindow([A, B], B, '/w/one');
    const inst = await instanceOf(win);
    click(inst, pidOf.A, startOf(pidOf.A));
    await sleep(1500);
    assert.strictEqual(A.shown, 1); assert.strictEqual(B.shown, 0);
    assert.deepStrictEqual(win.calls, ['workbench.action.terminal.focus']);
    win.dispose();
  });

  // Cases 2 + 3: same project dir, two requests back to back -> each selects its own terminal.
  await check('2/3 two tickets, each selects its own terminal', async () => {
    const A = makeTerminal('A'), B = makeTerminal('B');
    const win = openWindow([A, B], A, '/w/two');
    const inst = await instanceOf(win);
    click(inst, pidOf.A, startOf(pidOf.A), 'same-project');
    click(inst, pidOf.B, startOf(pidOf.B), 'same-project');
    await sleep(2500);
    assert.strictEqual(A.shown, 1); assert.strictEqual(B.shown, 1);
    win.dispose();
  });

  // Case 4: A and B in different windows -> only the owning window reacts.
  await check('4  two windows: only the owner window selects', async () => {
    const A = makeTerminal('A'), B = makeTerminal('B');
    const w1 = openWindow([A], A, '/w/win1');
    const w2 = openWindow([B], B, '/w/win2');
    const i1 = await instanceOf(w1), i2 = await instanceOf(w2);
    assert.notStrictEqual(i1, i2);
    click(i2, pidOf.B, startOf(pidOf.B));
    await sleep(1800);
    assert.strictEqual(B.shown, 1); assert.strictEqual(A.shown, 0);
    assert.strictEqual(w1.calls.length, 0);
    w1.dispose(); w2.dispose();
  });

  // Case 6: terminal renamed after the toast -> still found (matched by pid + start time, not name).
  await check('6  rename terminal after notification', async () => {
    const A = makeTerminal('A', 'old-name');
    const win = openWindow([A], A, '/w/six');
    const inst = await instanceOf(win);
    const start = startOf(pidOf.A);
    A.name = 'renamed';
    click(inst, pidOf.A, start);
    await sleep(1500);
    assert.strictEqual(A.shown, 1);
    win.dispose();
  });

  // Case 8: terminal A closed, old toast clicked -> nothing selected, request consumed.
  await check('8  closed terminal: no wrong selection', async () => {
    const A = makeTerminal('A'), B = makeTerminal('B');
    const terminals = [A, B];
    const win = openWindow(terminals, B, '/w/eight');
    const inst = await instanceOf(win);
    const startA = startOf(pidOf.A);
    terminals.splice(terminals.indexOf(A), 1); // A closed
    const t = click(inst, pidOf.A, startA);
    await sleep(1800);
    assert.strictEqual(A.shown, 0); assert.strictEqual(B.shown, 0);
    assert.strictEqual(win.calls.length, 0);
    assert.ok(!fs.existsSync(path.join(root, 'requests', t)), 'request left behind');
    win.dispose();
  });

  // Case 9: A closed, new terminal with the SAME name but another shell -> old toast must not match it.
  await check('9  new terminal with same name is not matched', async () => {
    const oldA = makeTerminal('A', 'zsh');
    const newA = makeTerminal('B', 'zsh'); // different pid, same name
    const terminals = [newA];
    const win = openWindow(terminals, newA, '/w/nine');
    const inst = await instanceOf(win);
    click(inst, pidOf.A, startOf(pidOf.A)); // ticket of the closed one
    await sleep(1800);
    assert.strictEqual(newA.shown, 0);
    // pid reuse: same pid but different start time must not match either.
    const reused = makeTerminal('B', 'zsh');
    terminals.splice(0, 1, reused);
    click(inst, pidOf.B, String(Number(startOf(pidOf.B)) + 1));
    await sleep(1800);
    assert.strictEqual(reused.shown, 0);
    win.dispose();
  });

  // Stale request (older than the TTL) must be dropped, not acted upon late.
  await check('   stale request is discarded', async () => {
    const A = makeTerminal('A');
    const win = openWindow([A], A, '/w/stale');
    const inst = await instanceOf(win);
    const t = click(inst, pidOf.A, startOf(pidOf.A));
    const old = new Date(Date.now() - 60000);
    fs.utimesSync(path.join(root, 'requests', t), old, old);
    await sleep(1800);
    assert.strictEqual(A.shown, 0);
    win.dispose();
  });

  for (const [status, name] of results) console.log(status, name);
  process.exit(results.some(([s]) => s === 'FAIL') ? 1 : 0);
})();
