# Commits and pushes the SKYFOLD repo to origin on a fixed interval.
# Uses the repo's own git identity (Awaiz Ahmed); adds no co-author trailers.
# Files over 50 MB are never committed (GitHub's hard limit is 100 MB).
param(
    [int]$IntervalSeconds = 180,
    [string]$Repo = "C:\UnityProjects\SKYFOLD"
)

$ErrorActionPreference = "Continue"
Set-Location $Repo
$log = Join-Path $Repo "Logs\autosync.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $log -Value $line
    Write-Output $line
}

Write-Log "autosync started (every $IntervalSeconds s)"
while ($true) {
    try {
        if (-not (Test-Path (Join-Path $Repo ".git\index.lock"))) {
            git add -A 2>&1 | Out-Null
            foreach ($f in (git diff --cached --name-only)) {
                if (Test-Path -LiteralPath $f) {
                    $len = (Get-Item -LiteralPath $f).Length
                    if ($len -gt 50MB) {
                        git reset -q -- "$f"
                        Write-Log ("skipped large file {0} ({1:N1} MB)" -f $f, ($len / 1MB))
                    }
                }
            }
            git diff --cached --quiet
            if ($LASTEXITCODE -ne 0) {
                $count = (git diff --cached --name-only | Measure-Object).Count
                git commit -q -m ("Autosave: {0} files changed ({1})" -f $count, (Get-Date -Format "yyyy-MM-dd HH:mm")) 2>&1 | Out-Null
            }
            $ahead = git rev-list --count "@{u}..HEAD" 2>$null
            if ($ahead -and [int]$ahead -gt 0) {
                git push -q origin main 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) { Write-Log "pushed $ahead commit(s)" } else { Write-Log "push failed (exit $LASTEXITCODE)" }
            }
        }
    } catch {
        Write-Log "error: $_"
    }
    Start-Sleep -Seconds $IntervalSeconds
}
