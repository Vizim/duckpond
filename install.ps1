<#
duckpond installer for Windows.

  irm https://raw.githubusercontent.com/Vizim/duckpond/main/install.ps1 | iex
  .\install.ps1 -Uninstall

Installs into a private virtualenv under $env:LOCALAPPDATA\duckpond, puts duckpond and fzf on the user PATH,
and registers the Start Menu shortcut.
#>
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$Repo = 'https://github.com/Vizim/duckpond'
$Home_ = if ($env:DUCKPOND_HOME) { $env:DUCKPOND_HOME } else { Join-Path $env:LOCALAPPDATA 'duckpond' }
$Venv = Join-Path $Home_ 'venv'
$Bin = Join-Path $Home_ 'bin'

function Add-UserPath($dir) {
  $current = [Environment]::GetEnvironmentVariable('Path', 'User')
  if (($current -split ';') -notcontains $dir) {
    [Environment]::SetEnvironmentVariable('Path', "$dir;$current", 'User')
  }
  if (($env:Path -split ';') -notcontains $dir) { $env:Path = "$dir;$env:Path" }
}

function Remove-UserPath($dir) {
  $current = [Environment]::GetEnvironmentVariable('Path', 'User')
  $new = ($current -split ';' | Where-Object { $_ -and $_ -ne $dir }) -join ';'
  [Environment]::SetEnvironmentVariable('Path', $new, 'User')
}

function Find-Python {
  foreach ($cmd in @('py -3', 'python3', 'python')) {
    try {
      $v = & cmd /c "$cmd -c `"import sys; print(sys.version_info >= (3, 9))`"" 2>$null
      if ($v -match 'True') { return $cmd }
    } catch {}
  }
  throw 'python 3.9 or newer is required (https://www.python.org/downloads/)'
}

function Install-Fzf {
  if (Get-Command fzf -ErrorAction SilentlyContinue) { return }
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host 'installing fzf with winget'
    winget install --id junegunn.fzf -e --silent --accept-source-agreements --accept-package-agreements | Out-Null
    if (Get-Command fzf -ErrorAction SilentlyContinue) { return }
  }
  $r = Invoke-WebRequest -Uri 'https://github.com/junegunn/fzf/releases/latest' -MaximumRedirection 0 -ErrorAction SilentlyContinue
  $ver = ($r.Headers.Location | Select-Object -First 1) -replace '.*/tag/v?', ''
  if (-not $ver) { $ver = (Invoke-RestMethod 'https://api.github.com/repos/junegunn/fzf/releases/latest').tag_name.TrimStart('v') }
  $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
  Write-Host "installing fzf $ver into $Bin"
  New-Item -ItemType Directory -Force -Path $Bin | Out-Null
  $zip = Join-Path $env:TEMP 'fzf.zip'
  Invoke-WebRequest "https://github.com/junegunn/fzf/releases/download/v$ver/fzf-$ver-windows_$arch.zip" -OutFile $zip
  Expand-Archive -Force $zip -DestinationPath $Bin
  Remove-Item $zip
  Add-UserPath $Bin
}

if ($Uninstall) {
  $duckpond = Join-Path $Venv 'Scripts\duckpond.exe'
  if (Test-Path $duckpond) { & $duckpond uninstall-launcher }
  Remove-UserPath (Join-Path $Venv 'Scripts')
  Remove-UserPath $Bin
  if (Test-Path $Home_) { Remove-Item -Recurse -Force $Home_ }
  Write-Host 'duckpond removed'
  exit 0
}

$py = Find-Python
New-Item -ItemType Directory -Force -Path $Home_ | Out-Null
Write-Host "creating virtualenv in $Venv"
& cmd /c "$py -m venv `"$Venv`""
$pip = Join-Path $Venv 'Scripts\python.exe'
$src = "git+$Repo"
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'pyproject.toml'))) { $src = $PSScriptRoot }
Write-Host "installing duckpond from $src"
& $pip -m pip install -q --upgrade pip
& $pip -m pip install -q --upgrade $src
Add-UserPath (Join-Path $Venv 'Scripts')
Install-Fzf
$duckpond = Join-Path $Venv 'Scripts\duckpond.exe'
try { & $duckpond install-launcher } catch { Write-Host "launcher not registered, run 'duckpond install-launcher' later" }
Write-Host ''
& $duckpond doctor
Write-Host ''
Write-Host 'done. open a new terminal and run: duckpond'
