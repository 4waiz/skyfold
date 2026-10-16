# One-command pipeline: configure the project, build the scene from code, validate, build the
# release player, optionally run QA scenarios, then package (ZIP + Desktop shortcuts).
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\build.ps1                 # build only
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\build.ps1 -QA smoke demo   # build + QA
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\build.ps1 -Package         # build + package
param([string[]]$QA = @(), [switch]$Package, [switch]$Dev)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$unity = "C:\Program Files\Unity\Hub\Editor\6000.6.2f1\Editor\Unity.exe"
if (-not (Test-Path $unity)) { throw "Unity 6000.6.2f1 not found at $unity" }
$method = if ($Dev) { "Skyfold.EditorTools.BuildPipelineCLI.BatchAllDev" } else { "Skyfold.EditorTools.BuildPipelineCLI.BatchAllRelease" }
$log = Join-Path $root ("Logs\build_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
New-Item -ItemType Directory -Force -Path (Join-Path $root "Logs") | Out-Null

Write-Output "Building with $method (log: $log)"
$p = Start-Process $unity -ArgumentList "-batchmode", "-projectPath", $root, "-executeMethod", $method, "-logFile", $log -PassThru -Wait
Select-String -Path $log -Pattern "error CS|Shader error|\[SKYFOLD\] (Scene built|Validation|Build )" | ForEach-Object { $_.Line }
if ($p.ExitCode -ne 0) { throw "Unity build failed with exit code $($p.ExitCode). See $log" }

if ($QA.Count -gt 0) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "qa\run_qa.ps1") @QA
}
if ($Package) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "package.ps1")
}
