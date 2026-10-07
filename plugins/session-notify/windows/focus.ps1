param([string]$Uri)

# Invoked by the claude-session-notify:// protocol when a toast is clicked.
# Brings the VS Code (or other IDE) window whose title contains the project name to the foreground.

$project = ''
if ($Uri -match 'project=([^&]*)') { $project = [Uri]::UnescapeDataString($Matches[1]) }
if (-not $project) { exit 0 }

Add-Type @"
using System;
using System.Collections.Generic;
using System.Text;
using System.Runtime.InteropServices;
public class Win {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);

  // Every visible top-level window: handle, owning process id, title.
  public static List<object[]> TopWindows() {
    var list = new List<object[]>();
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(512);
      GetWindowText(h, sb, 512);
      if (sb.Length == 0) return true;
      uint pid; GetWindowThreadProcessId(h, out pid);
      list.Add(new object[] { h, (int)pid, sb.ToString() });
      return true;
    }, IntPtr.Zero);
    return list;
  }
}
"@

$hosts = 'Code', 'Code - Insiders', 'Cursor', 'Windsurf', 'idea64', 'pycharm64'
$pids = @{}
Get-Process -Name $hosts -ErrorAction SilentlyContinue | ForEach-Object { $pids[$_.Id] = $true }

$target = [Win]::TopWindows() |
  Where-Object { $pids.ContainsKey($_[1]) -and $_[2] -like "*$project*" } |
  Select-Object -First 1
if (-not $target) { exit 0 }

$h = $target[0]
if ([Win]::IsIconic($h)) { [void][Win]::ShowWindow($h, 9) }   # SW_RESTORE; maximized windows stay maximized

if (-not [Win]::SetForegroundWindow($h)) {
  # Windows may deny focus stealing; a balanced ALT press lets the call through.
  [Win]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)
  [Win]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
  [void][Win]::SetForegroundWindow($h)
}
