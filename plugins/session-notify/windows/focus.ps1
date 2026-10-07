param([string]$Uri, [switch]$RestoreOnly)

# Click handler's PowerShell part. focus.vbs already focused the window with AppActivate and asked for the
# terminal (fast, ~0.1 s); it starts this with -RestoreOnly as a safety net, because AppActivate can leave a
# minimized window minimized when Windows denies the focus change. Without -RestoreOnly it does everything.
# 1. Brings the VS Code (or other IDE) window whose title contains the project name to the foreground.
# 2. If the URL carries a ticket token, asks the VS Code extension to focus that exact terminal.
# The URL is untrusted input (any web page can open a registered protocol): only a UUID token and a
# project name are read from it, and file locations come from config.json written by toast.ps1.

$project = ''
if ($Uri -match 'project=([^&]*)') { $project = [Uri]::UnescapeDataString($Matches[1]) }

$token = ''
if ($Uri -match 'token=([0-9a-fA-F-]{36})(&|$)') { $token = $Matches[1] }
$state = ''
$ticket = $null
if ($token) {
  try {
    $state = (Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'config.json') | ConvertFrom-Json).stateDir
    $ticketFile = Join-Path $state "tickets\$token.json"
    if (Test-Path $ticketFile) {
      $ticket = Get-Content -Raw -Encoding UTF8 $ticketFile | ConvertFrom-Json
      if ($ticket.project) { $project = $ticket.project }
    }
  } catch {}
}
if (-not $project) { exit 0 }

. (Join-Path $PSScriptRoot 'winapi.ps1')

$target = Find-IdeWindow $project
if ($target) {
  $h = $target[0]
  if ([Win]::IsIconic($h)) { [void][Win]::ShowWindow($h, 9) }   # SW_RESTORE; maximized windows stay maximized

  if (-not [Win]::SetForegroundWindow($h)) {
    # Windows may deny focus stealing; a balanced ALT press lets the call through.
    [Win]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)
    [Win]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
    [void][Win]::SetForegroundWindow($h)
  }
}

# Window is in front; now have the extension select the terminal that runs the session.
if ($ticket -and $state -and -not $RestoreOnly) {
  New-Item -ItemType File -Path (Join-Path $state "requests\$token") -Force | Out-Null
}
