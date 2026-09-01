@echo off
:loop
"C:\cloudflared\cloudflared.exe" tunnel --config C:\Users\99446\.cloudflared\config.yml run gmi-tunnel
echo cloudflared exited with code %errorlevel% at %time%, restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop
