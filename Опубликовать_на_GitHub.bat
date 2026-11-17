@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Публикация Antigravity Unlocker на GitHub
python tools\github_publisher.py
if errorlevel 1 pause

