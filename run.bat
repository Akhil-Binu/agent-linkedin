@echo off
title LinkedBot - Autonomous LinkedIn Agent
cls
echo Starting LinkedBot Interactive Menu...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" menu.py
) else (
    python menu.py
)
pause
