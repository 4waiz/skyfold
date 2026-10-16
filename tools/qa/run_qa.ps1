# Runs automated desktop QA scenarios against the built player, one after another.
# Usage: powershell -File tools\qa\run_qa.ps1 smoke episode1east demo
# Each scenario writes qa\_captures\<name>\qa_report.txt plus screenshots and a copy of Player.log.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Scenarios)

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$exe = Join-Path $root "Builds\Release\SKYFOLD\SKYFOLD.exe"
$playerLog = Join-Path $env:USERPROFILE "AppData\LocalLow\Team Kanban\SKYFOLD\Player.log"
if (-not (Test-Path $exe)) { Write-Error "Build not found: $exe"; exit 2 }
if (-not $Scenarios -or $Scenarios.Count -eq 0) { $Scenarios = @("smoke") }

$summary = @()
foreach ($s in $Scenarios) {
    $out = Join-Path $root "qa\_captures\$s"
    if (Test-Path $out) { Get-ChildItem $out -File | Remove-Item -Force }
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $start = Get-Date
    $p = Start-Process $exe -ArgumentList "--qa=$s", "--qa-out=$out", "-screen-width", "1920", "-screen-height", "1080", "-screen-fullscreen", "0" -PassThru -Wait
    $secs = [int]((Get-Date) - $start).TotalSeconds
    if (Test-Path $playerLog) { Copy-Item $playerLog (Join-Path $out "Player.log") -Force }
    $report = Join-Path $out "qa_report.txt"
    $last = if (Test-Path $report) { (Get-Content $report -Encoding UTF8 | Select-String "QA finished").Line } else { "no report" }
    $summary += "{0,-14} exit {1}  {2,4}s  {3}" -f $s, $p.ExitCode, $secs, $last
}
$summary | ForEach-Object { Write-Output $_ }
