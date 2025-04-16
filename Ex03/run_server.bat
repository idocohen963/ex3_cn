@echo off
echo Starting Reliable Transfer Server...

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Get the directory where the batch file is located
cd /d "%~dp0\\ReliableTCPModel"

REM Run the server and keep the window open
python run_server.py

REM If there's an error, pause to show the message
if %ERRORLEVEL% NEQ 0 (
    echo Server failed to start
    pause
) else (
    REM Add pause after normal termination too
    pause
)