' Runs focus.ps1 with no visible console window. Argument 1: the claude-session-notify:// URL.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
If WScript.Arguments.Count = 0 Then WScript.Quit 0
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & dir & "\focus.ps1"" """ & WScript.Arguments(0) & """", 0, False
