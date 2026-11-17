import os
import sys
import socket
import subprocess
import ssl
import json
import re
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from tools.unlocker_core import get_binary_paths, get_daemon_status, parse_tcp_global, SIG_INELIGIBLE, SIG_INEXIGIBLE, SIG_HTTPS_PROXY, SIG_AG_PROXY

TARGET_DOMAINS = [
    "antigravity.google",
    "cloudcode-pa.googleapis.com",
    "generativelanguage.googleapis.com",
    "daily-cloudcode-pa.googleapis.com",
    "aicode.googleapis.com",
    "antigravity-unleash.goog",
    "cloudaicompanion.googleapis.com",
    "accounts.google.com",
    "oauth2.googleapis.com"
]

KNOWN_DIRECT_GOOGLE_PREFIXES = ("172.217.", "142.250.", "216.58.", "173.194.", "74.125.")

def check_hosts_pinning():
    print("=" * 60)
    print("[1] Проверка привязки хостов в файле hosts:")
    hosts_path = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "drivers", "etc", "hosts")
    found_pins = []
    if os.path.exists(hosts_path):
        try:
            with open(hosts_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in lines:
                line_str = line.strip()
                if line_str and not line_str.startswith("#"):
                    parts = line_str.split()
                    if len(parts) >= 2 and any(d in parts[1] for d in ("googleapis.com", "antigravity")):
                        found_pins.append((parts[0], parts[1]))
        except Exception as e:
            print(f"  [-] Ошибка чтения hosts: {e}")

    if found_pins:
        print(f"  [+] Обнаружено {len(found_pins)} активных привязок в hosts:")
        for ip, host in found_pins:
            print(f"      {ip:16} -> {host}")
    else:
        print("  [!] Внимание: Привязки в hosts отсутствуют! Используется системный DNS.")

def check_nrpt_rules():
    print("=" * 60)
    print("[2] Проверка таблицы правил NRPT (Windows Name Resolution Policy Table):")
    cmd = ["powershell", "-NoProfile", "-Command", "Get-DnsClientNrptRule -ErrorAction SilentlyContinue | Select-Object Namespace, NameServers, Comment | Format-Table -AutoSize"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out = res.stdout.strip()
    if out:
        print(out)
        if "111.88.96.50" in out or "111.88.96.51" in out:
            print("  [!] ВНИМАНИЕ: Обнаружен сбойный DNS (111.88.96.50)! Возможна утечка в российский IP.")
        else:
            print("  [+] Активные правила NRPT зафиксированы.")
    else:
        print("  [+] Правила NRPT отсутствуют (Безопасно: исключен риск fallback-утечки).")

def check_dns_resolving():
    print("=" * 60)
    print("[3] Проверка разрешения целевых доменов (Анализ IP-адресов):")
    leak_detected = False
    for domain in TARGET_DOMAINS:
        try:
            ips = socket.gethostbyname_ex(domain)[2]
            ip_str = ", ".join(ips)
            is_direct = any(any(ip.startswith(p) for p in KNOWN_DIRECT_GOOGLE_PREFIXES) for ip in ips)
            
            if is_direct and "accounts" not in domain and "oauth" not in domain:
                print(f"  [!] ОПАСНОСТЬ: {domain:35} -> {ip_str} (ПРЯМОЙ GOOGLE IP — БУДЕТ GEO-BLOCK!)")
                leak_detected = True
            else:
                print(f"  [+] {domain:35} -> {ip_str}")
        except Exception as e:
            print(f"  [-] {domain:35} -> ОШИБКА: {e}")
    
    if leak_detected:
        print("\n  [ВНИМАНИЕ] Обнаружена утечка прямых IP Google! Рекомендуется выполнить 'python tools/unlocker_core.py'.")

def check_tls_connectivity():
    print("=" * 60)
    print("[4] Проверка TCP и TLS 443 хэндшейка (Стриминг и API):")
    for domain in TARGET_DOMAINS[:4]:
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=3.0) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    issuer = dict(x[0] for x in cert.get('issuer', [])).get('commonName', 'Unknown')
                    print(f"  [+] TLS 443 OK: {domain:35} (Issuer: {issuer})")
        except socket.timeout:
            print(f"  [-] TLS 443 TIMEOUT: {domain:35} -> Таймаут сокета")
        except ConnectionResetError:
            print(f"  [-] TLS 443 RESET (10054): {domain:35} -> Соединение сброшено узлом")
        except Exception as e:
            print(f"  [-] TLS 443 FAIL: {domain:35} -> {e}")

def check_binary_patches():
    print("=" * 60)
    print("[5] Проверка бинарных патчей (Обход блокировки и изоляция прокси):")
    bins = get_binary_paths()
    if not bins:
        print("  [-] Исполняемые файлы Antigravity не найдены.")
        return

    for bp in bins:
        try:
            with open(bp, "rb") as f:
                data = f.read()
            inel = data.count(SIG_INELIGIBLE)
            inex = data.count(SIG_INEXIGIBLE)
            hproxy = data.count(SIG_HTTPS_PROXY)
            agproxy = data.count(SIG_AG_PROXY)

            status_parts = []
            if inex > 0 and inel == 0:
                status_parts.append("РЕГИОН: OK")
            elif inel > 0:
                status_parts.append("РЕГИОН: ТРЕБУЕТСЯ ПАТЧ")
            else:
                status_parts.append("РЕГИОН: НЕТ СИГНАТУР")

            if agproxy > 0:
                status_parts.append("ПРОКСИ: ИЗОЛИРОВАН (AG_LS_PROXY)")
            elif hproxy > 0:
                status_parts.append("ПРОКСИ: СТАНДАРТНЫЙ (https_proxy)")

            print(f"  File: {os.path.basename(bp)} ({bp})")
            print(f"    - 'ineligible' / 'inexigible': {inel} / {inex}")
            print(f"    - 'https_proxy' / 'AG_LS_PROXY': {hproxy} / {agproxy}")
            print(f"    -> СТАТУС: {' | '.join(status_parts)}")
        except Exception as e:
            print(f"  File: {bp} -> Ошибка чтения: {e}")

def get_candidate_log_paths():
    """Поиск всех актуальных файлов логов Language Server, IDE и CLI."""
    logs = []
    appdata = os.environ.get("APPDATA", "")
    user_home = Path.home()

    # 1. Desktop LS log
    desktop_log = os.path.join(appdata, "Antigravity", "logs", "language_server.log")
    if os.path.isfile(desktop_log):
        logs.append(desktop_log)

    # 2. IDE сессионные логи (самая свежая папка)
    ide_logs_dir = os.path.join(appdata, "Antigravity", "logs")
    if os.path.isdir(ide_logs_dir):
        try:
            sessions = [d for d in os.listdir(ide_logs_dir) if os.path.isdir(os.path.join(ide_logs_dir, d))]
            sessions.sort()
            for s in reversed(sessions[-3:]):
                ls_main = os.path.join(ide_logs_dir, s, "ls-main.log")
                if os.path.isfile(ls_main) and ls_main not in logs:
                    logs.append(ls_main)
        except Exception:
            pass

    # 3. CLI логи в ~/.gemini/
    for sub in ("antigravity", "antigravity-cli"):
        cli_log_dir = user_home / ".gemini" / sub / "log"
        if cli_log_dir.is_dir():
            for p in sorted(cli_log_dir.glob("cli-*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:2]:
                logs.append(str(p))

    return logs

def detect_model_activity():
    """
    Интеллектуальный анализ живых логов (подход ls_log):
    1. Ищет доказательство успешного ответа модели (streamGenerateContent + ResponseID).
    2. Ищет отказ сервера по геолокации (FAILED_PRECONDITION 400 / PERMISSION_DENIED 403).
    """
    logs = get_candidate_log_paths()
    if not logs:
        return {
            "status": "NO_LOGS",
            "message": "Логи не найдены (запустите Antigravity и сделайте запрос)",
            "details": None
        }

    latest_success = None
    latest_block = None

    for log_path in logs:
        try:
            with open(log_path, "rb") as f:
                # Читаем хвост файла (до 256 КБ)
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 256 * 1024))
                raw_bytes = f.read()
            text = raw_bytes.decode("utf-8", errors="ignore")

            for line in text.splitlines():
                if "streamGenerateContent" in line and "ResponseID:" in line:
                    latest_success = line.strip()
                elif any(k in line for k in ("User location is not supported", "UNSUPPORTED_LOCATION", "LOCATION_NOT_ELIGIBLE")):
                    latest_block = line.strip()
        except Exception:
            pass

    if latest_block and (not latest_success or latest_block > latest_success):
        return {
            "status": "BLOCKED",
            "message": "Отказ сервера по геолокации (User location is not supported)",
            "details": latest_block
        }
    elif latest_success:
        return {
            "status": "WORKING",
            "message": "Работает. Модель успешно ответила (streamGenerateContent OK)",
            "details": latest_success
        }
    else:
        return {
            "status": "IDLE",
            "message": "Ожидание активности (ошибок геоблокировки в логах нет)",
            "details": None
        }

def check_model_activity_report():
    print("=" * 60)
    print("[6] Анализ живых логов Language Server (Детектор ответов модели):")
    res = detect_model_activity()
    status = res["status"]
    msg = res["message"]
    if status == "WORKING":
        print(f"  [+] СТАТУС: {msg}")
    elif status == "BLOCKED":
        print(f"  [!] СТАТУС: {msg}")
        if res.get("details"):
            print(f"      Детали: {res['details'][:120]}")
    else:
        print(f"  [i] СТАТУС: {msg}")

def check_system_services():
    print("=" * 60)
    print("[7] Сетевой стек TCP и фоновый автопатчер:")
    tcp = parse_tcp_global()
    autotuning = tcp.get("receive window auto-tuning level", "unknown")
    fastopen = tcp.get("fast open", "unknown")
    ecn = tcp.get("ecn capability", "unknown")
    print(f"  - TCP Auto-Tuning Level:  {autotuning} {'[OK]' if autotuning == 'normal' else '[SUBOPTIMAL]'}")
    print(f"  - TCP Fast Open:          {fastopen}")
    print(f"  - ECN Capability:         {ecn}")

    daemon_active = get_daemon_status()
    print(f"  - Автопатчер в Планировщике (Daemon): {'АКТИВЕН [OK]' if daemon_active else 'НЕ УСТАНОВЛЕН'}")

if __name__ == "__main__":
    print("Комплексная диагностика Antigravity Unlocker 2.1...")
    check_hosts_pinning()
    check_nrpt_rules()
    check_dns_resolving()
    check_tls_connectivity()
    check_binary_patches()
    check_model_activity_report()
    check_system_services()
    print("=" * 60)
