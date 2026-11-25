@echo off
title UstaBor - Sayt (5002), Mijoz Paneli (5003), Admin Paneli (5004) & Telegram Bot
cd /d "%~dp0"
echo ====================================================
echo   UstaBor ishga tushmoqda...
echo   Mijoz sayti:  http://127.0.0.1:5002/
echo   Mijoz paneli: http://127.0.0.1:5003/
echo   Admin paneli: http://127.0.0.1:5004/
echo ====================================================
start "" http://127.0.0.1:5002/
".venv\Scripts\python.exe" run.py
pause
