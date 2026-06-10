# Builds the MRT2 Studio distributable into dist\MRT2-Studio.zip
# Includes the installer, the Studio app (app), the WSL2 setup (install), and the cloud path (cloud),
# pruning secrets, logs, generated audio, virtual environments, and caches.
$ErrorActionPreference = 'Stop'
$root  = $PSScriptRoot
$dist  = Join-Path $root 'dist'
$stage = Join-Path $dist '_stage\MRT2-Studio'

if (Test-Path (Join-Path $dist '_stage')) { Remove-Item -Recurse -Force (Join-Path $dist '_stage') }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item -Recurse (Join-Path $root 'app')     (Join-Path $stage 'app')
Copy-Item -Recurse (Join-Path $root 'install') (Join-Path $stage 'install')
Copy-Item -Recurse (Join-Path $root 'cloud')   (Join-Path $stage 'cloud')
Copy-Item (Join-Path $root 'Setup-MRT2.bat')        (Join-Path $stage 'Setup-MRT2.bat')
Copy-Item (Join-Path $root 'MRT2-Studio.bat')       (Join-Path $stage 'MRT2-Studio.bat')
Copy-Item (Join-Path $root 'MRT2-Studio.command')   (Join-Path $stage 'MRT2-Studio.command')
Copy-Item (Join-Path $root 'README.md')             (Join-Path $stage 'README.md')
Copy-Item (Join-Path $root 'INSTALL.md')            (Join-Path $stage 'INSTALL.md')
Copy-Item (Join-Path $root 'LICENSE')               (Join-Path $stage 'LICENSE')
Copy-Item (Join-Path $root 'THIRD_PARTY_NOTICES.md')(Join-Path $stage 'THIRD_PARTY_NOTICES.md')

$readme = @'
MRT2 STUDIO - HOW TO START
==========================

1) Double-click  Setup-MRT2.bat
   It checks your PC and - only with your OK - installs what is needed
   (it tells you exactly what, and how big, before downloading anything).

2) When setup finishes, the app opens in your web browser.
   Type a vibe, press Generate, and music plays.

Next time, just double-click:  MRT2-Studio.bat

Requirements: Windows 10/11 and an NVIDIA GPU. The installer handles the rest.
'@
Set-Content -Path (Join-Path $stage 'READ-ME-FIRST.txt') -Value $readme -Encoding ASCII

# Prune unwanted directories.
Get-ChildItem -Path $stage -Recurse -Force -Directory |
  Where-Object { $_.Name -in '__pycache__','output','.venv' } |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Prune unwanted files.
Get-ChildItem -Path $stage -Recurse -Force -File |
  Where-Object { $_.Name -in 'secrets.local.json','.studio_port','.wsl_distro' -or $_.Extension -in '.log','.wav','.flac','.mp3','.pyc' } |
  Remove-Item -Force -ErrorAction SilentlyContinue

$zip = Join-Path $dist 'MRT2-Studio.zip'
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip

Remove-Item -Recurse -Force (Join-Path $dist '_stage')
$size = [math]::Round((Get-Item $zip).Length / 1MB, 2)
Write-Host "Created $zip ($size MB)"
