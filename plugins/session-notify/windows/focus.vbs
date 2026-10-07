' Click handler for claude-session-notify:// (argument 1: the URL). Registered by toast.ps1.
'
' Fast path (~0.2 s, no PowerShell): AppActivate the window by the END of its title (the
' "<folder> [WSL: ...] - Visual Studio Code" part toast.ps1 saved in tickets\<token>.title, which
' does not change when the active file changes), then create requests\<token> so the VS Code
' extension selects the terminal. Then focus.ps1 runs hidden in the background: with -RestoreOnly as a safety
' net (AppActivate can leave a minimized window minimized), or doing everything if the fast path failed.
Option Explicit
On Error Resume Next

Dim sh, fso, dir, url
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
If WScript.Arguments.Count = 0 Then WScript.Quit 0
url = WScript.Arguments(0)

Function ReadUtf8(path)
  Dim s
  ReadUtf8 = ""
  If Not fso.FileExists(path) Then Exit Function
  Set s = CreateObject("ADODB.Stream")
  s.Type = 2
  s.Charset = "utf-8"
  s.Open
  s.LoadFromFile path
  ReadUtf8 = Trim(s.ReadText)
  s.Close
End Function

Dim re, m, token, state, title, done, ok
done = False
Set re = New RegExp
re.Pattern = "token=([0-9a-fA-F-]{36})(&|$)"
Set m = re.Execute(url)
If m.Count > 0 Then
  token = m(0).SubMatches(0)
  state = ReadUtf8(dir & "\state.txt")
  title = ReadUtf8(state & "\tickets\" & token & ".title")
  If Len(state) > 0 And Len(title) > 0 Then
    Err.Clear
    ok = sh.AppActivate(title)
    If Err.Number = 0 And ok = True Then
      Err.Clear
      fso.CreateTextFile(state & "\requests\" & token, True).Close
      done = (Err.Number = 0)
    End If
  End If
End If
Err.Clear

Dim extra
extra = ""
If done Then extra = " -RestoreOnly"
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & dir & "\focus.ps1"" """ & url & """" & extra, 0, False
