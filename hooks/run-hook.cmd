@echo off
REM Simple wrapper: runs .sh scripts via Git Bash
REM Usage: run-hook.cmd <script-name> [args...]

REM Debug trace
echo [%date% %time%] run-hook.cmd called with: %* >> "%~dp0..\tests\manual\debug-output\run-hook-trace.log" 2>&1

if "%~1"=="" (
    echo {"decision": "block", "reason": "run-hook.cmd: missing script name"}
    exit /b 0
)

REM Run the bash script
"C:\Program Files\Git\bin\bash.exe" -l "%~dp0%~1" %2 %3 %4 %5 %6 %7 %8 %9
