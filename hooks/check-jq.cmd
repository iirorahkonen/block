@echo off
REM Windows wrapper for check-jq.sh
REM Calls bash with full path since PATH may not include Git

setlocal

set "HOOK_DIR=%~dp0"
set "BASH_PATH=C:\Program Files\Git\bin\bash.exe"

if not exist "%BASH_PATH%" (
    echo {"decision":"block","reason":"Git Bash not found at expected location"}
    exit /b 0
)

"%BASH_PATH%" -l "%HOOK_DIR%check-jq.sh"
