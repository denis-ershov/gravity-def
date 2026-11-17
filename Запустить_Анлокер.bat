@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Antigravity Unlocker 2.1

:: Проверка прав Администратора
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Запрос прав Администратора (UAC)...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   Antigravity Unlocker 2.1 (Запуск от Администратора)
echo ============================================================
echo [*] Инициализация графической панели управления...

where python >nul 2>&1
if %errorlevel% equ 0 (
    python gui.py
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        py gui.py
    ) else (
        echo.
        echo [-] Ошибка: Python 3 не найден в системном PATH.
        echo [*] Установите Python 3.10+ с сайта python.org (отметьте 'Add Python to PATH').
        pause
    )
)
