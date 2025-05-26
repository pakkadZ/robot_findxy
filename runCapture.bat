@echo off
cd /d %~dp0
call .venv\Scripts\activate
python src\capture.py
pause
