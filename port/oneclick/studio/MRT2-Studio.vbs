' ============================================================================
'  MRT2 Studio launcher  —  double-click this file.
'  Starts the music engine inside WSL2 with NO console window, then opens
'  your web browser to the Studio.  No terminal, no typing, ever.
'
'  Path-robust: derives its own WSL path from wherever it lives (any drive).
'  Port-robust: the server picks a free port if the default is busy, writes it
'  to .studio_port, and this launcher opens whatever port it actually used.
' ============================================================================
Option Explicit
Dim sh, fso, folder, drive, rest, wslDir, serverPath, cmd
Dim portFile, port, waited, ts
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' --- Where am I? Folder that contains this .vbs (with trailing backslash). ---
folder = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' --- Convert this folder's Windows path to its WSL path (C:\App\ -> /mnt/c/App/) ---
drive = LCase(Left(folder, 1))            ' drive letter, lowercased
rest  = Mid(folder, 3)                     ' path after the colon, backslashes
rest  = Replace(rest, "\", "/")            ' backslashes -> forward slashes
wslDir = "/mnt/" & drive & rest            ' /mnt/<drive>/<path>/
serverPath = wslDir & "studio_server.py"

' --- Clear any stale port marker so we read a fresh one. ---
portFile = folder & ".studio_port"
If fso.FileExists(portFile) Then fso.DeleteFile portFile, True

' --- Start the server HIDDEN inside WSL (window style 0 = invisible). ---
' If a Studio is already running, the server reuses it and just reports its port.
cmd = "wsl.exe -d Ubuntu -- bash -lc ""exec ~/mrt2/.venv/bin/python '" & serverPath & "'"""
sh.Run cmd, 0, False

' --- Wait for the server to announce which port it bound, then open it. ---
port = ""
waited = 0
Do While waited < 20000
  WScript.Sleep 500
  waited = waited + 500
  If fso.FileExists(portFile) Then
    On Error Resume Next
    Set ts = fso.OpenTextFile(portFile, 1)
    If Not (ts Is Nothing) Then
      port = Trim(ts.ReadAll)
      ts.Close
    End If
    On Error GoTo 0
    If port <> "" And IsNumeric(port) Then Exit Do
  End If
Loop

If port = "" Or Not IsNumeric(port) Then port = "8777"
sh.Run "http://localhost:" & port, 1, False

Set sh = Nothing
Set fso = Nothing
