# Launches SKYFOLD through a shortcut (.lnk) or the exe, waits, captures only the game window,
# prints the relevant log lines, then closes the game.
# Usage: powershell -File tools\qa\launch_test.ps1 -Shortcut "<path.lnk>" -Name desktop [-Seconds 12]
param([Parameter(Mandatory = $true)][string]$Shortcut, [string]$Name = "launch", [int]$Seconds = 12)

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$out = Join-Path $root "qa\_captures\launch"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$playerLog = Join-Path $env:USERPROFILE "AppData\LocalLow\Team Kanban\SKYFOLD\Player.log"

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

Get-Process SKYFOLD -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
$t0 = Get-Date
Start-Process $Shortcut
$proc = $null
for ($i = 0; $i -lt 40 -and -not $proc; $i++) { Start-Sleep -Milliseconds 250; $proc = Get-Process SKYFOLD -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $proc) { Write-Output "FAIL: SKYFOLD did not start"; exit 1 }
Start-Sleep -Seconds $Seconds
$proc.Refresh()
$h = $proc.MainWindowHandle
if ($h -ne [IntPtr]::Zero) {
    [Win]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 600
    $r = New-Object Win+RECT
    [Win]::GetWindowRect($h, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left; $hgt = $r.Bottom - $r.Top
    if ($w -gt 0 -and $hgt -gt 0) {
        $bmp = New-Object System.Drawing.Bitmap $w, $hgt
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
        $png = Join-Path $out "$Name.png"
        $bmp.Save($png, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
        Write-Output "Window $w x $hgt captured: $png"
    }
}
$alive = -not $proc.HasExited
Write-Output ("Process alive after {0}s: {1}" -f $Seconds, $alive)
if (Test-Path $playerLog) {
    Copy-Item $playerLog (Join-Path $out "$Name.Player.log") -Force
    Select-String -Path $playerLog -Pattern "\[SKYFOLD\] (Launch options|Active rig|XR|GPU|SKYFOLD )" | ForEach-Object { $_.Line }
}
Get-Process SKYFOLD -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Output ("Total {0:0.0}s" -f ((Get-Date) - $t0).TotalSeconds)
