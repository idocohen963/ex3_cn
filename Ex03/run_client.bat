@echo off
echo Starting Reliable Transfer Client...

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Navigate to the project directory and the ReliableTCPModel package
cd /d "%~dp0\\ReliableTCPModel"

REM Run the client and keep the window open
python run_client.py

REM If there's an error, pause to show the message
if %ERRORLEVEL% NEQ 0 (
    echo Client failed to start
    pause
) else (
    REM Add pause after normal termination too
    pause
)
