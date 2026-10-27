# Creates or updates the Desktop shortcuts for SKYFOLD: Clean Energy Challenge.
# They keep their names ("SKYFOLD" and "SKYFOLD - Quest 3"), so existing shortcuts are replaced in place and
# open the newest build.
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\make_shortcuts.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\make_shortcuts.ps1 -StartChallenge   # skip the title, straight into the challenge
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\make_shortcuts.ps1 -Exe D:\SKYFOLD\SKYFOLD.exe
param([string]$Exe = "", [switch]$StartChallenge)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not $Exe) {
    # Prefer the packaged copy (what package.ps1 stages), then the raw release build.
    foreach ($c in @((Join-Path $root "Release\SKYFOLD\SKYFOLD.exe"), (Join-Path $root "Builds\Release\SKYFOLD\SKYFOLD.exe"))) {
        if (Test-Path $c) { $Exe = $c; break }
    }
}
if (-not $Exe -or -not (Test-Path $Exe)) { throw "No SKYFOLD.exe found. Build first (tools\build.ps1), or pass -Exe <path to SKYFOLD.exe>." }
$Exe = (Resolve-Path $Exe).Path
$dir = Split-Path -Parent $Exe

# Icons: next to the packaged game, else straight from the project.
$icons = Join-Path $dir "icons"
if (-not (Test-Path (Join-Path $icons "skyfold_desktop.ico"))) { $icons = Join-Path $root "Assets\Skyfold\Art\Icons" }

$extra = if ($StartChallenge) { " --demo" } else { "" }
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$defs = @(
    @{ Name = "SKYFOLD"; Args = "--mode=desktop$extra"; Icon = "skyfold_desktop.ico"; Desc = "SKYFOLD: Clean Energy Challenge - play on this laptop (keyboard and mouse). A project by Awaiz Ahmed." },
    @{ Name = "SKYFOLD - Quest 3"; Args = "--mode=vr$extra"; Icon = "skyfold_vr.ico"; Desc = "SKYFOLD: Clean Energy Challenge - play in VR on Meta Quest 3 through Link. A project by Awaiz Ahmed." }
)
foreach ($d in $defs) {
    $lnk = Join-Path $desktop ($d.Name + ".lnk")
    $s = $shell.CreateShortcut($lnk)
    $s.TargetPath = $Exe
    $s.Arguments = $d.Args
    $s.WorkingDirectory = $dir
    $s.IconLocation = (Join-Path $icons $d.Icon) + ",0"
    $s.Description = $d.Desc
    $s.Save()
    Write-Output "Shortcut: $lnk -> $Exe $($d.Args)"
}
