' ============================================================================
'  MRT2 Studio launcher.  Double-click this file.
'  Starts the music engine inside WSL2 with NO console window, then opens
'  your web browser to the Studio.  No terminal, no typing, ever.
'
'  Path-robust: derives its own WSL path from wherever it lives (any drive).
'  Distro-robust: uses the Ubuntu distro that Setup recorded in .wsl_distro
'                 (falls back to "Ubuntu" if that file isn't there yet).
'  Port-robust: the server picks a free port if the default is busy, writes it
'               to .studio_port, and this launcher opens whatever port it used.
'  Fail-safe: if the engine never comes up, we open offline.html, a friendly
'             page that explains how to fix it, instead of a dead browser tab.
' ============================================================================
Option Explicit
Dim sh, fso, folder, drive, rest, wslDir, serverPath, cmd, distro, distroFile, offPath
Dim portFile, port, waited, ts, d
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

' --- Which WSL distro did Setup install/use? Read .wsl_distro if present. ---
distro = "Ubuntu"
distroFile = folder & ".wsl_distro"
If fso.FileExists(distroFile) Then
  On Error Resume Next
  Set ts = fso.OpenTextFile(distroFile, 1)
  If Not (ts Is Nothing) Then
    d = Trim(ts.ReadAll) : ts.Close
    If d <> "" Then distro = d
  End If
  On Error GoTo 0
End If

' --- Clear any stale port marker so we read a fresh one. ---
portFile = folder & ".studio_port"
If fso.FileExists(portFile) Then fso.DeleteFile portFile, True

' --- Start the server HIDDEN inside WSL (window style 0 = invisible). ---
' If a Studio is already running, the server reuses it and just reports its port.
cmd = "wsl.exe -d " & distro & " -- bash -lc ""exec ~/mrt2/.venv/bin/python '" & serverPath & "'"""
sh.Run cmd, 0, False

' --- Wait for the server to announce which port it bound, then open it. ---
port = ""
waited = 0
Do While waited < 25000
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

If port <> "" And IsNumeric(port) Then
  ' Engine is up (or being reused). Open the real Studio.
  sh.Run "http://localhost:" & port, 1, False
Else
  ' Engine never reported a port. Don't dump the user on a dead "can't connect"
  ' tab. Open the friendly offline page. It keeps probing and auto-forwards to
  ' the Studio if the engine was just slow, and otherwise shows how to fix it.
  offPath = folder & "offline.html"
  If fso.FileExists(offPath) Then
    sh.Run """" & offPath & """", 1, False
  Else
    sh.Run "http://localhost:8777", 1, False
  End If
End If

Set sh = Nothing
Set fso = Nothing
