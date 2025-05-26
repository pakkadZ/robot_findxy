@echo off
cd /d %~dp0
call .venv\Scripts\activate
python src\Main_robot.py
pause
