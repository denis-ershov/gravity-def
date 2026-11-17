@echo off
chcp 65001 >nul
cd /d "%~dp0crates\gravity-cli"
title Сборка Antigravity Unlocker Rust Core

echo ============================================================
echo   Сборка высокопроизводительного ядра gravity-cli (Rust)
echo ============================================================
echo [*] Проверка Rust toolchain...
cargo --version
if errorlevel 1 (
    echo [-] Rust / Cargo не обнаружен в системе.
    echo [*] Установите Rust с официального сайта: https://rustup.rs/
    pause
    exit /b 1
)

echo.
echo [*] Компиляция release сборки...
cargo build --release
if errorlevel 1 (
    echo [-] Ошибка компиляции.
    pause
    exit /b 1
)

echo.
echo [+] Сборка успешно завершена!
echo [*] Бинарный файл: target\release\gravity-cli.exe
pause
