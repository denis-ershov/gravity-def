"""
Antigravity Unlocker 2.1 CLI
Единая консольная точка входа для применения анлока, отката и сервисных операций.
"""
import sys
import os
import argparse

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from tools.unlocker_core import (
    execute_unlock, execute_rollback, patch_binaries, unpatch_binaries,
    tune_tcp_stack, clean_ide_cache, install_task_daemon, uninstall_task_daemon,
    is_admin, elevate_process
)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Antigravity Unlocker 2.1 CLI")
    parser.add_argument("--apply", action="store_true", help="Применить полный комплексный анлок")
    parser.add_argument("--restore", action="store_true", help="Полный откат системы к исходному состоянию")
    parser.add_argument("--patch-only", action="store_true", help="Только патчинг бинарников")
    parser.add_argument("--unpatch-only", action="store_true", help="Откат бинарных патчей")
    parser.add_argument("--clean-cache", action="store_true", help="Очистка кэша V8")
    parser.add_argument("--tune-tcp", action="store_true", help="Оптимизация сетевого стека TCP")
    parser.add_argument("--daemon-install", action="store_true", help="Установка автопатчера в Планировщик Windows")
    parser.add_argument("--daemon-remove", action="store_true", help="Удаление автопатчера из Планировщика")
    args = parser.parse_args()

    if args.restore:
        execute_rollback()
    elif args.patch_only:
        patch_binaries()
    elif args.unpatch_only:
        unpatch_binaries()
    elif args.clean_cache:
        clean_ide_cache()
    elif args.tune_tcp:
        tune_tcp_stack(True)
    elif args.daemon_install:
        install_task_daemon()
    elif args.daemon_remove:
        uninstall_task_daemon()
    else:
        execute_unlock()
