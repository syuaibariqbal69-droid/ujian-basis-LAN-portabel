@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist runtime\python\python.exe (set PY=runtime\python\python.exe) else (set PY=python)
"%PY%" portable.py
pause
