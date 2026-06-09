# Builds the MRT2 Studio distributable into dist\MRT2-Studio.zip
# Includes the installer, the one-click app (oneclick), and the WSL2 setup (wsl),
# pruning secrets, logs, generated audio, virtual environments, and caches.
$ErrorActionPreference = 'Stop'
$root  = $PSScriptRoot
$dist  = Join-Path $root 'dist'
$stage = Join-Path $dist '_stage\MRT2-Studio'

if (Test-Path (Join-Path $dist '_stage')) { Remove-Item -Recurse -Force (Join-Path $dist '_stage') }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item -Recurse (Join-Path $root 'port\oneclick') (Join-Path $stage 'oneclick')
Copy-Item -Recurse (Join-Path $root 'port\wsl')      (Join-Path $stage 'wsl')
Copy-Item (Join-Path $root 'setup.ps1')      (Join-Path $stage 'setup.ps1')
Copy-Item (Join-Path $root 'Setup-MRT2.bat') (Join-Path $stage 'Setup-MRT2.bat')

$readme = @'
MRT2 STUDIO - HOW TO START
==========================

1) Double-click  Setup-MRT2.bat
   It checks your PC and - only with your OK - installs what is needed
   (it tells you exactly what, and how big, before downloading anything).

2) When setup finishes, the app opens in your web browser.
   Type a vibe, press Generate, and music plays.

Next time, just double-click:  oneclick\studio\MRT2-Studio.vbs

Requirements: Windows 10/11 and an NVIDIA GPU. The installer handles the rest.
'@
Set-Content -Path (Join-Path $stage 'READ-ME-FIRST.txt') -Value $readme -Encoding ASCII

# Prune unwanted directories.
Get-ChildItem -Path $stage -Recurse -Force -Directory |
  Where-Object { $_.Name -in '__pycache__','output','.venv' } |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Prune unwanted files.
Get-ChildItem -Path $stage -Recurse -Force -File |
  Where-Object { $_.Name -eq 'secrets.local.json' -or $_.Extension -in '.log','.wav','.flac','.mp3','.pyc' } |
  Remove-Item -Force -ErrorAction SilentlyContinue

$zip = Join-Path $dist 'MRT2-Studio.zip'
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip

Remove-Item -Recurse -Force (Join-Path $dist '_stage')
$size = [math]::Round((Get-Item $zip).Length / 1MB, 2)
Write-Host "Created $zip ($size MB)"
