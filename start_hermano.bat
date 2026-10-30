@echo off
title Hermano
cd /d "%~dp0"
call venv\Scripts\activate
python main.py voice
pause
