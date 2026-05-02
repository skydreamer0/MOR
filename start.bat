@echo off
echo [MOR] Starting setup...
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies. Please check if Python is installed.
    pause
    exit /b %ERRORLEVEL%
)
echo [MOR] Dependencies checked.
echo [MOR] Starting application...
python app.py
pause
