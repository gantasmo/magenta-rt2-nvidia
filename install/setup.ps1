<#
  MRT2 Studio - Setup & Doctor
  Double-click Setup-MRT2.bat (which runs this).

  It checks your system first (read-only), shows you EXACTLY what needs to be
  downloaded/installed and how big it is, and does nothing until you agree.
  Then it fixes what it can automatically and gives clear steps for the rest.

  Switches (optional, for advanced users):
    -Yes        skip the confirmation prompts (assume "yes")
    -Elevated   internal: set when the script relaunches itself as admin
#>
[CmdletBinding()]
param([switch]$Yes, [switch]$Elevated)

$ErrorActionPreference = 'Stop'
$env:WSL_UTF8 = '1'   # make wsl.exe list output parseable UTF-8

# --------------------------------------------------------------------------- #
#  pretty printing
# --------------------------------------------------------------------------- #
function Line(){ Write-Host ("-" * 64) -ForegroundColor DarkGray }
function Head($t){ Write-Host ""; Line; Write-Host "  $t" -ForegroundColor Cyan; Line }
function OK($t){   Write-Host "  [OK]  $t" -ForegroundColor Green }
function WARN($t){ Write-Host "  [!!]  $t" -ForegroundColor Yellow }
function BAD($t){  Write-Host "  [XX]  $t" -ForegroundColor Red }
function Info($t){ Write-Host "        $t" -ForegroundColor Gray }
function Ask($q){
  if($Yes){ return $true }
  Write-Host ""
  $a = Read-Host "  $q  [Y/n]"
  return ($a -eq '' -or $a -match '^(y|yes)$')
}
function Done($code){ Write-Host ""; if(-not $Yes){ Read-Host "  Press Enter to close" }; exit $code }

# --------------------------------------------------------------------------- #
#  locate our own scripts (works in the repo AND in the released zip)
# --------------------------------------------------------------------------- #
$root = $PSScriptRoot
function Find-Rel([string[]]$rels){
  foreach($r in $rels){ $p = Join-Path $root $r; if(Test-Path $p){ return (Resolve-Path $p).Path } }
  return $null
}
$setupSh   = Find-Rel @('setup_all.sh','wsl\setup_all.sh','port\wsl\setup_all.sh')
$studioVbs = Find-Rel @('..\app\MRT2-Studio.vbs','app\MRT2-Studio.vbs','oneclick\studio\MRT2-Studio.vbs','port\oneclick\studio\MRT2-Studio.vbs')

function To-Wsl([string]$winPath){
  $d = $winPath.Substring(0,1).ToLower()
  $rest = ($winPath.Substring(2)) -replace '\\','/'
  return "/mnt/$d$rest"
}
function Test-Admin(){
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator)
}
# Record which WSL distro we used so MRT2-Studio.vbs targets the same one
# (don't let the launcher hardcode "Ubuntu" when the user's distro differs).
function Write-DistroMarker($name){
  if(-not $studioVbs -or -not $name){ return }
  try{
    $studioDir = Split-Path -Parent $studioVbs
    Set-Content -LiteralPath (Join-Path $studioDir '.wsl_distro') -Value $name -Encoding ASCII -NoNewline
  }catch{ }
}

# --------------------------------------------------------------------------- #
#  Auto-size %UserProfile%\.wslconfig to THIS machine, on ANY machine.
#  A hand-edited or stale .wslconfig (e.g. processors greater than the host's
#  logical CPUs, or memory set to ~100% of RAM) makes WSL print warnings,
#  ignore the value, and can stall the whole system mid-generation. We force
#  three safe, hardware-derived values and preserve everything else the user
#  may have set. Returns a result object, or $null on failure.
# --------------------------------------------------------------------------- #
function Set-WslConfig(){
  try{
    $cs      = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    $logical = [int]$cs.NumberOfLogicalProcessors; if($logical -lt 1){ $logical = 1 }
    $totalGB = [int][math]::Floor([double]$cs.TotalPhysicalMemory / 1GB)
    if($totalGB -lt 2){ $totalGB = 2 }
    $memGB   = [int][math]::Max(2, [math]::Floor($totalGB * 0.75))   # leave Windows ~25%
    $swapGB  = [int][math]::Max(2, [math]::Round($memGB * 0.25))     # cushion vs OOM
    # Desired [wsl2] keys (order preserved).
    $want = [ordered]@{ processors = "$logical"; memory = "${memGB}GB"; swap = "${swapGB}GB" }

    $cfg   = Join-Path $env:USERPROFILE '.wslconfig'
    $lines = @()
    if(Test-Path $cfg){ $lines = @(Get-Content -LiteralPath $cfg) }
    $before = ($lines -join "`n")

    $out = New-Object System.Collections.Generic.List[string]
    $inWsl2 = $false; $hasWsl2 = $false; $seen = @{}
    foreach($k in $want.Keys){ $seen[$k] = $false }
    foreach($ln in $lines){
      $t = $ln.Trim()
      if($t -match '^\[(.+)\]$'){
        if($inWsl2){ foreach($k in $want.Keys){ if(-not $seen[$k]){ $out.Add("$k=$($want[$k])"); $seen[$k]=$true } } }
        $inWsl2 = ($matches[1] -ieq 'wsl2'); if($inWsl2){ $hasWsl2 = $true }
        $out.Add($ln); continue
      }
      if($inWsl2 -and $t -match '^\s*([A-Za-z0-9_]+)\s*='){
        $key = $matches[1]
        if($want.Contains($key)){ $out.Add("$key=$($want[$key])"); $seen[$key]=$true; continue }
      }
      $out.Add($ln)
    }
    if($inWsl2){ foreach($k in $want.Keys){ if(-not $seen[$k]){ $out.Add("$k=$($want[$k])"); $seen[$k]=$true } } }
    if(-not $hasWsl2){
      if($out.Count -gt 0 -and $out[$out.Count-1].Trim() -ne ''){ $out.Add('') }
      $out.Add('[wsl2]')
      foreach($k in $want.Keys){ $out.Add("$k=$($want[$k])") }
    }

    $after   = ($out -join "`n")
    $changed = ($after -ne $before)
    if($changed){ Set-Content -LiteralPath $cfg -Value $out -Encoding ASCII }
    return [pscustomobject]@{ Path=$cfg; Processors=$logical; Memory="${memGB}GB"; Swap="${swapGB}GB"; Changed=$changed }
  }catch{ return $null }
}

Clear-Host
Write-Host ""
Write-Host "  MRT2 STUDIO - SETUP" -ForegroundColor Magenta
Write-Host "  Make music from a text prompt on your own GPU." -ForegroundColor Gray
if($setupSh)  { } else { BAD "Could not find install\setup_all.sh next to this installer."; Done 1 }

# =========================================================================== #
#  PHASE 1 - SYSTEM CHECK (read-only, nothing is installed yet)
# =========================================================================== #
Head "Checking your system (nothing is installed yet)"

$todo = New-Object System.Collections.ArrayList   # human list of what we'd install
$blockers = New-Object System.Collections.ArrayList

# --- Windows build (WSL2 needs Win10 2004 / build 19041+) ---
$build = [int](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuildNumber
if($build -ge 19041){ OK "Windows build $build (supports WSL2)" }
else{ BAD "Windows build $build is too old for WSL2 (need 19041+). Update Windows."; [void]$blockers.Add("Update Windows to a recent version (Settings > Windows Update).") }

# --- Right-size WSL to THIS machine (fixes bad/oversized processors+memory) ---
$wc = Set-WslConfig
if($wc){
  if($wc.Changed){ WARN "Tuned WSL to your hardware: $($wc.Processors) CPUs, $($wc.Memory) RAM, $($wc.Swap) swap (corrected unsafe values)." }
  else{ OK "WSL is already sized to your hardware ($($wc.Processors) CPUs, $($wc.Memory) RAM)." }
}

# --- WSL present? ---
$wslCmd = Get-Command wsl.exe -ErrorAction SilentlyContinue
$wslOk = $false; $ubuntuOk = $false; $ubuntuName = 'Ubuntu'
if($wslCmd){
  $wslOk = $true; OK "WSL is installed"
  $distros = (& wsl.exe -l -q) 2>$null | ForEach-Object { ($_ -replace "`0","").Trim() } | Where-Object { $_ -ne '' }
  $ub = $distros | Where-Object { $_ -match 'Ubuntu' } | Select-Object -First 1
  if($ub){ $ubuntuOk = $true; $ubuntuName = $ub; OK "Ubuntu distro found: $ub"; Write-DistroMarker $ubuntuName }
  else{ WARN "WSL is present but no Ubuntu distro is installed"; [void]$todo.Add("Ubuntu for WSL2 (a few hundred MB)") }
}else{
  BAD "WSL is not installed"
  [void]$todo.Add("WSL2 + Ubuntu (a few hundred MB; needs admin + one reboot)")
}

# --- Apply the new WSL limits before we boot the engine (needs a WSL restart) ---
if($wc -and $wc.Changed -and $wslOk){
  Info "Applying the new WSL limits (a quick WSL restart)..."
  try{ & wsl.exe --shutdown 2>$null }catch{ }
}

# --- NVIDIA GPU on Windows ---
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if(-not $smi){ $p="$env:SystemRoot\System32\nvidia-smi.exe"; if(Test-Path $p){ $smi=$p } }
if($smi){
  $gpu = (& $smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
  if($gpu){ OK "NVIDIA GPU: $($gpu.Trim())" } else { WARN "nvidia-smi present but returned no GPU" }
}else{
  BAD "No NVIDIA GPU / driver detected"
  [void]$blockers.Add("This app needs an NVIDIA GPU with a recent driver. Install/update it from https://www.nvidia.com/Download/index.aspx (the driver includes WSL GPU support).")
}

# --- Disk space (the Linux engine + model need room; usually on C:) ---
try{
  $freeGB = [math]::Round((Get-PSDrive C).Free/1GB,1)
  if($freeGB -ge 12){ OK "Free disk space on C: ${freeGB} GB" }
  else{ WARN "Only ${freeGB} GB free on C: - the engine + model need ~6 GB. Free up space to be safe." }
}catch{ }

# --- Is the Linux engine already set up? (best-effort, only if Ubuntu exists) ---
$engineReady = $false
if($ubuntuOk){
  $probe = (& wsl.exe -d $ubuntuName -- bash -lc "test -f ~/Documents/Magenta/magenta-rt-v2/checkpoints/mrt2_small.safetensors && ~/mrt2/.venv/bin/python -c 'import jax,magenta_rt,soundfile,fastapi,uvicorn' 2>/dev/null && echo READY") 2>$null
  if($probe -match 'READY'){ $engineReady = $true; OK "Music engine + model already installed" }
  else{ WARN "Music engine / model not fully installed yet"; [void]$todo.Add("Python engine + CUDA libraries (~3 GB) and the music model (~1.1 GB)") }
}

# --- Hard blockers stop us here with clear guidance ---
if($blockers.Count -gt 0){
  Head "Action needed before setup can continue"
  foreach($b in $blockers){ BAD $b }
  Info "Fix the above, then double-click Setup-MRT2 again."
  Done 1
}

# --- Nothing to do? Skip straight to launch ---
if($todo.Count -eq 0 -and $engineReady){
  Head "Everything is ready"
  OK "No downloads needed."
  if(Ask "Launch MRT2 Studio now?"){ if($studioVbs){ Start-Process wscript.exe "`"$studioVbs`"" } }
  Done 0
}

# =========================================================================== #
#  CONSENT - show exactly what will be downloaded/installed, then ask
# =========================================================================== #
Head "Your OK before anything is downloaded or installed"
Write-Host "  To finish setup, the following will be downloaded and installed:" -ForegroundColor White
foreach($t in $todo){ Write-Host "    - $t" -ForegroundColor White }
Write-Host ""
Info "Everything installs inside WSL2/Linux on your PC. Nothing leaves your machine."
Info "The model is downloaded from Hugging Face (public, no account needed)."
if(-not (Ask "Download and install the items above?")){
  WARN "No problem - nothing was changed. Run Setup-MRT2 again whenever you're ready."
  Done 0
}

# =========================================================================== #
#  PHASE 2 - RESOLUTIONS
# =========================================================================== #

# --- Install WSL itself (needs admin + reboot) ---
if(-not $wslOk){
  if(-not (Test-Admin)){
    Head "Administrator approval needed to install WSL"
    Info "Windows will ask for permission - click Yes."
    try{
      Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @(
        '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`"",'-Elevated') | Out-Null
    }catch{ BAD "Elevation was declined. Right-click Setup-MRT2 and 'Run as administrator'."; Done 1 }
    Done 0
  }
  Head "Installing WSL2 + Ubuntu"
  Info "This downloads WSL and Ubuntu, then needs ONE restart."
  & wsl.exe --install -d Ubuntu
  Head "RESTART REQUIRED"
  Info "1. Restart your PC now."
  Info "2. After restart, a black 'Ubuntu' window opens - create any username + password."
  Info "3. Then double-click Setup-MRT2 again to finish."
  Done 0
}

# --- Install Ubuntu (WSL present, distro missing) ---
if(-not $ubuntuOk){
  Head "Installing Ubuntu"
  & wsl.exe --install -d Ubuntu
  Head "ONE MORE STEP"
  Info "A black 'Ubuntu' window may open asking you to create a username + password."
  Info "Do that (any simple values), close it, then double-click Setup-MRT2 again."
  Done 0
}

# --- Make sure the distro is WSL2 (not WSL1) ---
try{
  $verLines = (& wsl.exe -l -v) 2>$null | ForEach-Object { ($_ -replace "`0","") }
  $line = $verLines | Where-Object { $_ -match [regex]::Escape($ubuntuName) } | Select-Object -First 1
  if($line -match '\s1\s*$'){ WARN "Upgrading $ubuntuName to WSL2..."; & wsl.exe --set-version $ubuntuName 2 }
}catch{ }

# --- Install the engine + model inside WSL (the big step) ---
Head "Installing the music engine + model (this can take a while)"
Info "Downloading CUDA libraries (~3 GB) and the model (~1.1 GB). Grab a coffee."
$wslSetup = To-Wsl $setupSh
& wsl.exe -d $ubuntuName -- bash -lc "bash '$wslSetup'"
$rc = $LASTEXITCODE

if($rc -ne 0){
  Head "Setup hit a snag - here is how to fix it"
  BAD "The Linux setup did not finish (exit $rc)."
  Info "Most common causes and fixes:"
  Info "  - Internet dropped mid-download  ->  just run Setup-MRT2 again (it resumes)."
  Info "  - Low disk space                 ->  free up ~6 GB on C:, then re-run."
  Info "  - GPU driver too old             ->  update your NVIDIA driver, then re-run."
  Info "Re-running is always safe - finished steps are skipped."
  Done 1
}

# =========================================================================== #
#  DONE
# =========================================================================== #
Head "Setup complete"
OK "Music engine + model installed and verified on your GPU."
if(Ask "Launch MRT2 Studio now?"){
  if($studioVbs){ Start-Process wscript.exe "`"$studioVbs`""; Info "Your browser will open at http://localhost:8777 in a moment." }
  else{ WARN "Could not find the Studio launcher; open app\MRT2-Studio.vbs manually." }
}
Info "From now on, just double-click MRT2-Studio.bat in the main folder to make music."
Done 0
