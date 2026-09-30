@echo off
chcp 65001 >nul
setlocal

echo ==================================================
echo Telegram API connectivity check
echo ==================================================
echo.

echo [1/3] DNS lookup...
nslookup api.telegram.org
echo.

echo [2/3] Testing TCP port 443...
powershell -NoProfile -Command "Test-NetConnection api.telegram.org -Port 443 | Select-Object ComputerName,RemoteAddress,RemotePort,TcpTestSucceeded"
echo.

echo [3/3] Testing HTTPS response...
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'https://api.telegram.org' -UseBasicParsing -TimeoutSec 15; Write-Host ('HTTP status: ' + [int]$r.StatusCode) } catch { Write-Host ('HTTPS failed: ' + $_.Exception.Message) -ForegroundColor Red }"
echo.
echo If TcpTestSucceeded is False or HTTPS failed, the problem is network access to Telegram.
pause
