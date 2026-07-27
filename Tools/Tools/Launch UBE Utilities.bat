@echo off
setlocal
cd /d "%~dp0"

where pyw >nul 2>&1
if not errorlevel 1 (
    start "" pyw -3 "%~dp0ube_utilities_gui.py"
    exit /b 0
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw "%~dp0ube_utilities_gui.py"
    exit /b 0
)

python "%~dp0ube_utilities_gui.py"
if errorlevel 1 pause
