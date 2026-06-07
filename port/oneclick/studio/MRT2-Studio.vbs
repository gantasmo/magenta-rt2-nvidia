' ============================================================================
'  MRT2 Studio launcher  —  double-click this file.
'  Starts the music engine inside WSL2 with NO console window, then opens
'  your web browser to the Studio.  No terminal, no typing, ever.
'
'  Path-robust: it figures out its OWN location and converts it to the matching
'  WSL path (any drive: C:\App\ becomes /mnt/c/App/). Works from anywhere — no
'  hardcoded drive letter to go stale.
' ============================================================================
Option Explicit
Dim sh, folder, drive, rest, wslDir, serverPath, cmd
Set sh = CreateObject("WScript.Shell")

' --- Where am I? Folder that contains this .vbs (with trailing backslash). ---
folder = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' --- Convert this folder's Windows path to its WSL path (C:\App\ -> /mnt/c/App/) ---
drive = LCase(Left(folder, 1))            ' drive letter, lowercased
rest  = Mid(folder, 3)                     ' path after the colon, backslashes
rest  = Replace(rest, "\", "/")            ' backslashes -> forward slashes
wslDir = "/mnt/" & drive & rest            ' /mnt/<drive>/<path>/
serverPath = wslDir & "studio_server.py"

' --- Start the server HIDDEN inside WSL (window style 0 = invisible). ---
' If it is already running, this second copy can't grab the port and exits
' quietly — harmless. "exec" keeps it as the single foreground process.
cmd = "wsl.exe -d Ubuntu -- bash -lc ""exec ~/mrt2/.venv/bin/python '" & serverPath & "'"""
sh.Run cmd, 0, False

' --- Give the web server a moment to bind, then open the browser. ---
' (The page shows its own "waking up the musician" screen while the model loads,
'  and keeps retrying if the server isn't up yet — so timing here isn't critical.)
WScript.Sleep 2000
sh.Run "http://localhost:8777", 1, False

Set sh = Nothing
