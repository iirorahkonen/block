: << 'CMDBLOCK'
@echo off
REM Polyglot entry point - works as both Windows batch and Unix shell
REM Calls protect_directories.py with Python

setlocal
set "HOOK_DIR=%~dp0"

where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%HOOK_DIR%protect_directories.py"
    exit /b %errorlevel%
)

echo {"decision":"block","reason":"Python not found. Please install Python 3.8 or later."}
exit /b 0
CMDBLOCK

# Unix: here-doc above discards batch code
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v python3 &> /dev/null; then
    python3 "$HOOK_DIR/protect_directories.py"
    exit $?
fi

if command -v python &> /dev/null; then
    python "$HOOK_DIR/protect_directories.py"
    exit $?
fi

echo '{"decision":"block","reason":"Python not found. Please install Python 3.8 or later."}'
exit 0
