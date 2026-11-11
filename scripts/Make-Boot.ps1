#requires -Version 5.1
<#
Interactive Windows entry point. Repacking only: no reboot or flashing.
Python 3.10+ and Android Platform Tools (adb on PATH) are required.
#>
[CmdletBinding()]
param(
    [string]$Boot,
    [string]$KernelZip,
    [string]$Output,
    [string]$Serial,
    [switch]$Make,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if ($Make -and $CheckOnly) { throw 'Choose -Make or -CheckOnly, not both.' }
if (-not $Boot) { $Boot = Read-Host 'Path to STOCK boot.img from your currently installed ROM' }
if (-not $KernelZip) { $KernelZip = Read-Host 'Path to the downloaded AnyKernel ZIP' }
$Boot = $Boot.Trim().Trim('"')
$KernelZip = $KernelZip.Trim().Trim('"')
$pythonLauncher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$pythonExe = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$arguments = @((Join-Path $PSScriptRoot 'make_boot.py'), '--boot', $Boot, '--kernel-zip', $KernelZip)
if ($Output) { $arguments += @('--output', $Output) }
if ($Serial) { $arguments += @('--serial', $Serial) }
if ($CheckOnly) { $arguments += '--check-only' }
if ($Make) { $arguments += '--make' }
$versionProbe = 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
$usePython = $false
$useLauncher = $false
if ($pythonExe) {
    & $pythonExe.Source -c $versionProbe 2>$null
    $usePython = ($LASTEXITCODE -eq 0)
}
if (-not $usePython -and $pythonLauncher) {
    & $pythonLauncher.Source -3 -c $versionProbe 2>$null
    $useLauncher = ($LASTEXITCODE -eq 0)
}
if ($usePython) {
    & $pythonExe.Source @arguments
}
elseif ($useLauncher) {
    & $pythonLauncher.Source -3 @arguments
}
else {
    throw 'Install Python 3.10+ from python.org and enable its launcher/PATH, then retry.'
}
if ($LASTEXITCODE -ne 0) { throw 'Boot preparation stopped. Read the error above; no flashing was performed.' }
