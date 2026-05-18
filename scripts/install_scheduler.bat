@echo off
:: Uruchom jako Administrator!
echo Rejestrowanie zaplanowanych zadan dla Tablica Swiat...

set PS_SCRIPT=c:\tablica-swiat\tablica-swiat\scripts\run_pipeline.ps1
set PS_CMD=powershell.exe -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "%PS_SCRIPT%"

schtasks /Create /TN "TablicaSwiat_Noon" ^
  /TR "%PS_CMD%" ^
  /SC DAILY /ST 12:00 ^
  /RL HIGHEST /F ^
  /SD 01/01/2026 ^
  /IT

schtasks /Create /TN "TablicaSwiat_Evening" ^
  /TR "%PS_CMD%" ^
  /SC DAILY /ST 22:00 ^
  /RL HIGHEST /F ^
  /SD 01/01/2026 ^
  /IT

echo.
echo Gotowe! Aktywne zadania:
schtasks /Query /TN "TablicaSwiat_Noon"    /FO LIST | findstr "Task Name\|Next Run"
schtasks /Query /TN "TablicaSwiat_Evening" /FO LIST | findstr "Task Name\|Next Run"
echo.
pause
