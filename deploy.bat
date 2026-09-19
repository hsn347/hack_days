@echo off
chcp 65001 > nul
title IBRA BOT Deployer
cls
echo ==============================================================
echo       نظام نشر وتحديث IBRA BOT (Smart Auto-Resume Deployer)
echo ==============================================================
python "%~dp0deploy.py"
echo.
pause
