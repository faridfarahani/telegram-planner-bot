@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo Python launcher "py" was not found.
    echo Install Python 3.12 or newer, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist ".env" (
    copy .env.example .env >nul
    echo.
    echo Created .env. Put your Telegram BOT_TOKEN inside it before running the bot.
)

echo.
echo Installation completed.
pause
