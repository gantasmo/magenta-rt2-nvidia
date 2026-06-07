# Builds the MRT2 Studio distributable into dist\MRT2-Studio.zip
# Includes the one-click app (port\oneclick) and the WSL2 GPU setup (port\wsl),
# pruning secrets, logs, generated audio, virtual environments, and caches.
$ErrorActionPreference = 'Stop'
$root  = $PSScriptRoot
$dist  = Join-Path $root 'dist'
$stage = Join-Path $dist '_stage\MRT2-Studio'

if (Test-Path (Join-Path $dist '_stage')) { Remove-Item -Recurse -Force (Join-Path $dist '_stage') }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item -Recurse (Join-Path $root 'port\oneclick') (Join-Path $stage 'oneclick')
Copy-Item -Recurse (Join-Path $root 'port\wsl')      (Join-Path $stage 'wsl')

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
