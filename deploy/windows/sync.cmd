@echo off
rem BoardInsight: sincronizacao agendada (tarefa "BoardInsight\Sync", a cada 30 min, conta SYSTEM).
rem Log em %ProgramData%\BoardInsight\logs\sync.log, rodado acima de 10 MB.
setlocal
set "BOARDINSIGHT_ENV_FILE=%ProgramData%\BoardInsight\.env"
set "PYTHONUNBUFFERED=1"
set "PYTHONUTF8=1"
set "LOG=%ProgramData%\BoardInsight\logs\sync.log"
if exist "%LOG%" for %%F in ("%LOG%") do if %%~zF GTR 10485760 move /y "%LOG%" "%LOG%.1" >nul
"%~dp0python\python.exe" -m app.jobs.sync >> "%LOG%" 2>&1
exit /b %ERRORLEVEL%
