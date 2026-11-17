"""
FastMCP Server для программного управления Antigravity Unlocker из AI-агентов.
Позволяет проверять статус, активировать разблокировку, выполнять откат,
бенчмаркать прокси, управлять тюнингом TCP, очисткой кэша и фоновым демоном.
"""

import os
import sys
import json
from typing import Optional, Dict, Any, List

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.unlocker_core import (
    is_admin, execute_unlock, execute_rollback,
    patch_binaries, unpatch_binaries, get_binary_paths,
    clean_ide_cache, tune_tcp_stack, restore_tcp_stack,
    parse_tcp_global, install_task_daemon, uninstall_task_daemon,
    get_daemon_status, SIG_INELIGIBLE, SIG_INEXIGIBLE,
    SIG_HTTPS_PROXY, SIG_AG_PROXY
)
from tools.proxy_manager import (
    find_best_proxy, pin_hosts, unpin_hosts,
    get_current_pinned_ip, PROXIES_POOL, probe_single_host
)
from tools.backup_manager import list_backups, restore_backup, create_backup
from tools.diagnostics import detect_model_activity

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Antigravity Unlocker MCP Server")
except ImportError:
    mcp = None


def get_system_status() -> Dict[str, Any]:
    """Получить полный текущий статус компонентов Antigravity Unlocker."""
    pinned_ip = get_current_pinned_ip()
    binaries = get_binary_paths()
    
    bin_status = {}
    for b in binaries:
        fname = os.path.basename(b)
        try:
            with open(b, "rb") as f:
                data = f.read()
            inel = data.count(SIG_INELIGIBLE)
            inex = data.count(SIG_INEXIGIBLE)
            hproxy = data.count(SIG_HTTPS_PROXY)
            agproxy = data.count(SIG_AG_PROXY)

            bin_status[fname] = {
                "path": b,
                "region_patch": "patched" if inex > 0 else "unpatched" if inel > 0 else "unknown",
                "proxy_var": "AG_LS_PROXY" if agproxy > 0 else "https_proxy" if hproxy > 0 else "unknown",
                "counts": {
                    "ineligible": inel,
                    "inexigible": inex,
                    "https_proxy": hproxy,
                    "AG_LS_PROXY": agproxy
                }
            }
        except Exception as e:
            bin_status[fname] = {"error": str(e)}

    model_act = detect_model_activity()
    tcp_info = parse_tcp_global()

    return {
        "is_admin": is_admin(),
        "hosts_pinned_ip": pinned_ip,
        "is_hosts_pinned": pinned_ip is not None,
        "binaries_status": bin_status,
        "model_activity": model_act,
        "tcp_tuning": {
            "autotuninglevel": tcp_info.get("receive window auto-tuning level", "unknown"),
            "fastopen": tcp_info.get("fast open", "unknown"),
            "ecn": tcp_info.get("ecn capability", "unknown")
        },
        "daemon_installed": get_daemon_status(),
        "backups_count": len(list_backups())
    }


if mcp:
    @mcp.tool()
    def status() -> str:
        """Проверить полный статус Antigravity Unlocker (hosts, патчи, модель, TCP, daemon)."""
        return json.dumps(get_system_status(), indent=2, ensure_ascii=False)

    @mcp.tool()
    def unlock(proxy_ip: Optional[str] = None) -> str:
        """Активировать обход (hosts, патчинг, очистка V8 кэша, тюнинг TCP)."""
        if not is_admin():
            return "Ошибка: требуются права Администратора для модификации hosts и бинарников."
        success = execute_unlock(target_ip=proxy_ip)
        return "Успешно активировано" if success else "Ошибка активации"

    @mcp.tool()
    def rollback() -> str:
        """Полный откат системы в исходное состояние (очистка hosts, откат бинарников, TCP)."""
        if not is_admin():
            return "Ошибка: требуются права Администратора для выполнения отката."
        success = execute_rollback()
        return "Откат успешно выполнен" if success else "Ошибка отката"

    @mcp.tool()
    def benchmark_proxies() -> str:
        """Протестировать доступность и задержку всех SNI-прокси из пула."""
        best_ip = find_best_proxy(verbose=False)
        return json.dumps({
            "recommended_ip": best_ip
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    def clean_cache() -> str:
        """Очистить скомпилированный байткод-кэш V8/Electron."""
        cnt = clean_ide_cache()
        return f"Очищено {cnt} директорий кэша V8."

    @mcp.tool()
    def tune_tcp(enable: bool = True) -> str:
        """Включить или вернуть исходные параметры TCP стека Windows (Window Auto-tuning, Fast Open)."""
        if not is_admin():
            return "Ошибка: требуются права Администратора."
        ok = tune_tcp_stack(enable)
        return "Настройки TCP успешно применены" if ok else "Ошибка применения TCP настроек"

    @mcp.tool()
    def manage_daemon(action: str = "status") -> str:
        """Управление фоновым автопатчером в Планировщике Windows (status, install, uninstall)."""
        if action == "status":
            return f"Фоновый автопатчер: {'АКТИВЕН' if get_daemon_status() else 'НЕ УСТАНОВЛЕН'}"
        if not is_admin():
            return "Ошибка: требуются права Администратора для изменения Планировщика задач."
        if action == "install":
            ok = install_task_daemon()
            return "Задача успешно зарегистрирована" if ok else "Ошибка регистрации задачи"
        elif action == "uninstall":
            ok = uninstall_task_daemon()
            return "Задача успешно удалена" if ok else "Ошибка удаления задачи"
        else:
            return f"Неизвестное действие: {action}"

    @mcp.tool()
    def list_system_backups() -> str:
        """Список доступных резервных копий конфигураций и бинарников."""
        backups = list_backups()
        return json.dumps(backups, indent=2, ensure_ascii=False)


def main():
    if mcp:
        mcp.run()
    else:
        print("[!] Библиотека 'mcp' не установлена в текущем окружении. Статус системы:")
        print(json.dumps(get_system_status(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
