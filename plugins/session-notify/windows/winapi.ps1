# Shared window helpers, dot-sourced by focus.ps1 and toast.ps1.

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

$IdeHosts = 'Code', 'Code - Insiders', 'Cursor', 'Windsurf', 'idea64', 'pycharm64'

# First IDE window whose title contains the project name: @(handle, pid, title) or $null.
function Find-IdeWindow([string]$Project) {
  $pids = @{}
  Get-Process -Name $IdeHosts -ErrorAction SilentlyContinue | ForEach-Object { $pids[$_.Id] = $true }
  [Win]::TopWindows() |
    Where-Object { $pids.ContainsKey($_[1]) -and $_[2].IndexOf($Project, [StringComparison]::OrdinalIgnoreCase) -ge 0 } |
    Select-Object -First 1
}
