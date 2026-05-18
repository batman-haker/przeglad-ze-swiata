# ============================================================
#  Tablica Swiat — automatyczny pipeline
#  Uruchamiany przez Task Scheduler o 12:00 i 22:00
# ============================================================

$ProjectDir = "c:\tablica-swiat\tablica-swiat"
$LogDir     = "$ProjectDir\logs"
$LogFile    = "$LogDir\pipeline_$(Get-Date -Format 'yyyyMMdd_HHmm').log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

Log "=== START PIPELINE ==="

# 1. Pobierz nowe posty
Log "Krok 1: fetch.py"
$fetch = & py "$ProjectDir\scripts\fetch.py" 2>&1
$fetch | ForEach-Object { Log "  [fetch] $_" }
if ($LASTEXITCODE -ne 0) { Log "BLAD fetch.py (kod $LASTEXITCODE)"; exit 1 }

# 2. Wzbogac przez AI i zapisz events.json
Log "Krok 2: build.py"
$build = & py "$ProjectDir\scripts\build.py" "$ProjectDir\data\fetched_posts.txt" 2>&1
$build | ForEach-Object { Log "  [build] $_" }
if ($LASTEXITCODE -ne 0) { Log "BLAD build.py (kod $LASTEXITCODE)"; exit 1 }

Log "=== PIPELINE ZAKONCZONY ==="

# Usun logi starsze niz 14 dni
Get-ChildItem "$LogDir\pipeline_*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
    Remove-Item -Force
