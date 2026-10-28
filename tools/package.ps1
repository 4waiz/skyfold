# Packages the release build for players.
#   Stages  Release\SKYFOLD\  (game + README + licenses + docs + icons + demo launcher)
#   Writes  Release\SKYFOLD_v<version>_win64.zip
#   Creates the two Desktop shortcuts (laptop and Quest 3) pointing at the staged folder.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File tools\package.ps1 [-NoShortcuts]
param([switch]$NoShortcuts)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root "Builds\Release\SKYFOLD"
$releaseDir = Join-Path $root "Release"
$stage = Join-Path $releaseDir "SKYFOLD"
$version = ((Select-String -Path (Join-Path $root "ProjectSettings\ProjectSettings.asset") -Pattern "^\s*bundleVersion: (.+)" -CaseSensitive).Matches[0].Groups[1].Value).Trim()
$zip = Join-Path $releaseDir ("SKYFOLD_v{0}_win64.zip" -f $version)
$utf8 = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path (Join-Path $build "SKYFOLD.exe"))) { throw "No release build at $build. Run BuildPipelineCLI.BatchAllRelease first." }

# Close a running copy so files are not locked.
Get-Process SKYFOLD -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$stage*" } | Stop-Process -Force -ErrorAction SilentlyContinue

# 1) Stage: copy the player, leaving out folders Unity marks as not-for-shipping.
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Get-ChildItem $build | Where-Object { $_.Name -notlike "*DoNotShip*" -and $_.Name -notlike "*ButDontShipItWithYourGame*" } |
    ForEach-Object { Copy-Item $_.FullName -Destination $stage -Recurse -Force }

# 2) Icons and the portable demo launcher.
$icons = Join-Path $stage "icons"
New-Item -ItemType Directory -Force -Path $icons | Out-Null
foreach ($n in "skyfold_desktop", "skyfold_vr", "skyfold_demo", "skyfold_icon") {
    Copy-Item (Join-Path $root "Assets\Skyfold\Art\Icons\$n.ico") $icons -Force
}
[System.IO.File]::WriteAllText((Join-Path $stage "Play Demo (3 min).cmd"), "@echo off`r`nstart `"`" `"%~dp0SKYFOLD.exe`" --demo`r`n", $utf8)
[System.IO.File]::WriteAllText((Join-Path $stage "Play in VR (Quest 3 Link).cmd"), "@echo off`r`nstart `"`" `"%~dp0SKYFOLD.exe`" --mode=vr`r`n", $utf8)
[System.IO.File]::WriteAllText((Join-Path $stage "Play on this laptop.cmd"), "@echo off`r`nstart `"`" `"%~dp0SKYFOLD.exe`" --mode=desktop`r`n", $utf8)

# 3) Licences and notices.
$lic = Join-Path $stage "licenses"
New-Item -ItemType Directory -Force -Path $lic | Out-Null
Copy-Item (Join-Path $root "Assets\Skyfold\Fonts\Unbounded-OFL.txt") (Join-Path $lic "Unbounded-OFL.txt")
Copy-Item (Join-Path $root "Assets\Skyfold\Fonts\AtkinsonHyperlegible-OFL.txt") (Join-Path $lic "AtkinsonHyperlegible-OFL.txt")
Copy-Item (Join-Path $root "Assets\TextMesh Pro\Fonts\LiberationSans - OFL.txt") (Join-Path $lic "LiberationSans-OFL.txt")
Copy-Item (Join-Path $root "tools\package_notices.txt") (Join-Path $lic "THIRD_PARTY_NOTICES.txt")

# 4) Player docs.
$docs = Join-Path $stage "docs"
New-Item -ItemType Directory -Force -Path (Join-Path $docs "manifest") | Out-Null
foreach ($d in "CONTROLS.md", "QUEST_LINK_SETUP.md", "ASSET_MANIFEST.md", "QA_REPORT.md") {
    $p = Join-Path $root "docs\$d"
    if (Test-Path $p) { Copy-Item $p $docs }
}
Copy-Item (Join-Path $root "docs\manifest\*.md") (Join-Path $docs "manifest")
Copy-Item (Join-Path $root "tools\README_release.txt") (Join-Path $stage "README.txt")

# 5) Guard: nothing secret, cached or personal in the package.
$bad = Get-ChildItem $stage -Recurse -File | Where-Object {
    $_.Name -match '\.(env|pem|key|pfx|log|pdb|blend)$' -or $_.Name -match 'cookie|token|secret|credential' -or $_.FullName -match '\\(Library|Temp|Logs|qa)\\'
}
if ($bad) { $bad | ForEach-Object { Write-Output ("BLOCKED: " + $_.FullName) }; throw "Package guard failed." }

# 6) ZIP (contains the SKYFOLD folder).
if (Test-Path $zip) { Remove-Item $zip -Force }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
# Entries are added one by one so their paths use forward slashes (the ZIP standard); Windows
# PowerShell's CreateFromDirectory writes backslashes, which other unzip tools mishandle.
$zipStream = [System.IO.File]::Open($zip, [System.IO.FileMode]::CreateNew)
$archive = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem $stage -Recurse -File | ForEach-Object {
        $entry = "SKYFOLD/" + $_.FullName.Substring($stage.Length + 1).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $entry, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
}
finally {
    $archive.Dispose()
    $zipStream.Dispose()
}
$zipMb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
$stageMb = [math]::Round(((Get-ChildItem $stage -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
Write-Output "Staged: $stage ($stageMb MB)"
Write-Output "ZIP:    $zip ($zipMb MB)"

# 7) Desktop shortcuts (one game, two ways to play).
if (-not $NoShortcuts) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shell = New-Object -ComObject WScript.Shell
    $exe = Join-Path $stage "SKYFOLD.exe"
    $defs = @(
        @{ Name = "SKYFOLD"; Args = "--mode=desktop"; Icon = "skyfold_desktop.ico"; Desc = "SKYFOLD: The Clean Flight - play on this laptop (keyboard and mouse)" },
        @{ Name = "SKYFOLD - Quest 3"; Args = "--mode=vr"; Icon = "skyfold_vr.ico"; Desc = "SKYFOLD: The Clean Flight - play in VR on Meta Quest 3 through Link" }
    )
    foreach ($d in $defs) {
        $lnk = Join-Path $desktop ($d.Name + ".lnk")
        $s = $shell.CreateShortcut($lnk)
        $s.TargetPath = $exe
        $s.Arguments = $d.Args
        $s.WorkingDirectory = $stage
        $s.IconLocation = (Join-Path $icons $d.Icon) + ",0"
        $s.Description = $d.Desc
        $s.Save()
        Write-Output "Shortcut: $lnk -> $exe $($d.Args)"
    }
}
