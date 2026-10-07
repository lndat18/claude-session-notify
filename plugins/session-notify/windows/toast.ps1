param(
  [string]$TitleB64,
  [string]$MessageB64,
  [string]$ProjectB64,
  [string]$Sound = 'Asterisk',
  [string]$Token = '',
  [string]$StateDir = ''
)

# Text arrives as UTF-8 Base64 so non-ASCII survives the WSL -> Windows command line.
function Decode([string]$b) {
  if ([string]::IsNullOrEmpty($b)) { return '' }
  [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b))
}
function Esc([string]$s) { [System.Security.SecurityElement]::Escape($s) }

$Title = Decode $TitleB64
$Message = Decode $MessageB64
$Project = Decode $ProjectB64

try { [System.Media.SystemSounds]::$Sound.Play() } catch {}

[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

# Icon: reuse the Claude Desktop logo from the local install (not redistributed in this repo).
# Drop your own PNG at %LOCALAPPDATA%\ClaudeSessionNotify\claude.png to override.
$dir = Join-Path $env:LOCALAPPDATA 'ClaudeSessionNotify'
$icon = Join-Path $dir 'claude.png'
New-Item -ItemType Directory -Path $dir -Force | Out-Null
if (-not (Test-Path $icon)) {
  $pkg = Get-AppxPackage | Where-Object { $_.Name -like '*Claude*' } | Select-Object -First 1
  if ($pkg) {
    $src = Join-Path $pkg.InstallLocation 'assets\Square150x150Logo.png'
    if (Test-Path $src) { Copy-Item $src $icon -Force }
  }
}
$hasIcon = Test-Path $icon

# Own AppUserModelID so the toast header says "Claude Code" instead of "Windows PowerShell".
$appId = 'ClaudeSessionNotify'
$key = "HKCU:\Software\Classes\AppUserModelId\$appId"
if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
Set-ItemProperty -Path $key -Name DisplayName -Value 'Claude Code'
if ($hasIcon) { Set-ItemProperty -Path $key -Name IconUri -Value $icon }

# Click-to-focus: copy the handler to a local folder (works even if WSL is idle, survives plugin
# updates) and register the claude-session-notify:// protocol under HKCU.
foreach ($f in 'focus.ps1', 'focus.vbs') {
  Copy-Item (Join-Path $PSScriptRoot $f) (Join-Path $dir $f) -Force
}
$proto = 'HKCU:\Software\Classes\claude-session-notify'
$cmdKey = "$proto\shell\open\command"
if (-not (Test-Path $cmdKey)) { New-Item -Path $cmdKey -Force | Out-Null }
Set-ItemProperty -Path $proto -Name '(default)' -Value 'URL:Claude Session Notify'
Set-ItemProperty -Path $proto -Name 'URL Protocol' -Value ''
$vbs = Join-Path $dir 'focus.vbs'
Set-ItemProperty -Path $cmdKey -Name '(default)' -Value "wscript.exe `"$vbs`" `"%1`""
# Handler config comes from this script, never from the URL: the URL only carries an opaque token.
if ($StateDir) {
  [IO.File]::WriteAllText((Join-Path $dir 'config.json'), (ConvertTo-Json @{ stateDir = $StateDir }))
}
$launch = 'claude-session-notify://focus?project=' + [Uri]::EscapeDataString($Project)
if ($Token -match '^[0-9a-fA-F-]{36}$') { $launch += '&token=' + $Token }

$logo = ''
if ($hasIcon) { $logo = "<image placement='appLogoOverride' src='$(Esc $icon)'/>" }
$attr = ''
if ($Project) { $attr = "<text placement='attribution'>$(Esc $Project)</text>" }

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast activationType='protocol' launch='$(Esc $launch)'><visual><binding template='ToastGeneric'>$logo<text>$(Esc $Title)</text><text>$(Esc $Message)</text>$attr</binding></visual><audio silent='true'/></toast>")

$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
