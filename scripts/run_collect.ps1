# Monthly view-count collection, run by Windows Task Scheduler on this PC.
# (cafe24 shows a bot check to overseas data centers such as GitHub Actions, so we collect from Korea.)
# Usage: run_collect.ps1          -> skips if this month is already collected
#        run_collect.ps1 -Force   -> collect now anyway (each run adds +1 view per post on kosif.org)
param([switch]$Force)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = "C:\Users\KoSIF\AppData\Local\Programs\Python\Python312\python.exe"
$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "collect.log"
function Log($msg) { Add-Content -Path $log -Value ("{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg) -Encoding UTF8 }

Set-Location $repo
Log "start (Force=$Force)"

# Already collected this month? (a missed run on a PC that was off starts at next boot/logon)
$month = Get-Date -Format "yyyy-MM"
if (-not $Force -and (Get-ChildItem (Join-Path $repo "data\snapshots") -Filter "$month-*.json" -ErrorAction SilentlyContinue)) {
    Log "skip: $month already collected"
    exit 0
}

# Right after boot the network may not be ready yet: wait up to 15 minutes.
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-WebRequest -Uri "https://kosif.org/" -Method Head -UseBasicParsing -TimeoutSec 15 | Out-Null; $ok = $true; break }
    catch { Start-Sleep -Seconds 30 }
}
if (-not $ok) { Log "fail: kosif.org not reachable"; exit 1 }

try {
    git pull --quiet --rebase 2>&1 | Out-Null
    & $python collector\collect.py data 2>&1 | ForEach-Object { Log "collect: $_" }
    if ($LASTEXITCODE -ne 0) { Log "fail: collector exit $LASTEXITCODE"; exit 1 }
    git add data
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit --quiet -m ("data: {0} view-count snapshot" -f (Get-Date -Format "yyyy-MM-dd"))
        git push --quiet 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Log "fail: git push"; exit 1 }
    }
    Log "done"
} catch {
    Log ("fail: " + $_.Exception.Message)
    exit 1
}
