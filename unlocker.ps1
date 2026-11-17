# Antigravity Unlocker 2.1 - PowerShell Native Management Script
# Compliant with PowerShell Windows strict engineering rules:
# - No unicode/emojis (ASCII markers only: [+], [-], [*], [OK])
# - Parenthesized cmdlet logical comparisons
# - Safe null/variable access
# - Self-elevation via UAC when required

[CmdletBinding()]
param (
    [ValidateSet("Unlock", "Rollback", "Status", "Patch", "Unpatch", "CleanCache", "TuneTCP", "DaemonInstall", "DaemonRemove")]
    [string]$Action = "Status",

    [string]$CustomProxy = ""
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-SelfElevation {
    Write-Host "[*] Requesting Administrator privileges (UAC elevation)..." -ForegroundColor Yellow
    $scriptPath = $PSCommandPath
    if (-not $scriptPath) {
        $scriptPath = "$PSScriptRoot\unlocker.ps1"
    }
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Action $Action"
    if ($CustomProxy) {
        $argList += " -CustomProxy $CustomProxy"
    }
    Start-Process powershell.exe -ArgumentList $argList -Verb RunAs
    exit 0
}

# Require elevation for write operations
if (($Action -ne "Status") -and (-not (Test-IsAdmin))) {
    Invoke-SelfElevation
}

$ScriptDir = $PSScriptRoot
$PythonCmd = "python"
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    if (Get-Command "py" -ErrorAction SilentlyContinue) {
        $PythonCmd = "py"
    } else {
        Write-Host "[-] Python 3 not found in PATH." -ForegroundColor Red
        exit 1
    }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Antigravity Unlocker 2.1 [PowerShell Orchestrator]" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

switch ($Action) {
    "Status" {
        Write-Host "[*] Executing system diagnostics..." -ForegroundColor Cyan
        & $PythonCmd "$ScriptDir\tools\diagnostics.py"
    }
    "Unlock" {
        Write-Host "[*] Applying complete geo-unblock..." -ForegroundColor Green
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --apply
    }
    "Rollback" {
        Write-Host "[*] Executing full rollback..." -ForegroundColor Yellow
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --restore
    }
    "Patch" {
        Write-Host "[*] Patching binaries..." -ForegroundColor Green
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --patch-only
    }
    "Unpatch" {
        Write-Host "[*] Restoring binaries..." -ForegroundColor Yellow
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --unpatch-only
    }
    "CleanCache" {
        Write-Host "[*] Cleaning V8 bytecode cache..." -ForegroundColor Magenta
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --clean-cache
    }
    "TuneTCP" {
        Write-Host "[*] Tuning Windows TCP/IP stack..." -ForegroundColor Green
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --tune-tcp
    }
    "DaemonInstall" {
        Write-Host "[*] Registering scheduler daemon task..." -ForegroundColor Green
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --daemon-install
    }
    "DaemonRemove" {
        Write-Host "[*] Removing scheduler daemon task..." -ForegroundColor Yellow
        & $PythonCmd "$ScriptDir\tools\unlocker.py" --daemon-remove
    }
}
