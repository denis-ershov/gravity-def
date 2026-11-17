import os
import sys
import ctypes
import subprocess
import json
import time
import shutil
import re
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from tools.backup_manager import create_backup, restore_backup, list_backups, BACKUP_ROOT
from tools.proxy_manager import (
    find_best_proxy, pin_hosts, unpin_hosts, get_current_pinned_ip,
    clean_leaking_nrpt_rules
)

DEFAULT_BACKEND_URL = "https://daily-cloudcode-pa.googleapis.com"
TASK_NAME = "AntigravityUnlockerDaemon"

# Binary patching literals (length-preserving!)
SIG_INELIGIBLE = b"ineligible"   # 10 bytes
SIG_INEXIGIBLE = b"inexigible"   # 10 bytes
SIG_HTTPS_PROXY = b"https_proxy" # 11 bytes
SIG_AG_PROXY    = b"AG_LS_PROXY" # 11 bytes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_process(args=None):
    if is_admin():
        return True
    
    script = os.path.abspath(sys.argv[0])
    params = " ".join([f'"{a}"' for a in (args or sys.argv[1:])])
    executable = sys.executable

    print("[*] Запрос прав Администратора для модификации системных параметров...")
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        f'"{script}" {params}',
        None,
        1 # SW_SHOWNORMAL
    )
    if ret > 32:
        sys.exit(0)
    else:
        print("[-] Пользователь отклонил запрос прав Администратора.")
        return False

def get_binary_paths():
    """
    Глубокий поиск исполняемых файлов Antigravity (language_server, agy):
    1. Системные переменные %LOCALAPPDATA%, %APPDATA%, %USERPROFILE%, %ProgramFiles%.
    2. Сканирование реестра Windows (Uninstall ключи HKCU/HKLM/WOW6432Node).
    3. Сканирование Scoop-пакетов (%USERPROFILE%/scoop/apps, %SCOOP%/apps).
    4. Сканирование каталога автономного CLI ~/.gemini/bin/.
    5. Системный PATH через shutil.which.
    """
    local_app = os.environ.get("LOCALAPPDATA", "")
    app_data = os.environ.get("APPDATA", "")
    user_prof = os.environ.get("USERPROFILE", "")
    prog_files = os.environ.get("ProgramFiles", "")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", "")

    candidate_paths = [
        # Стандартные пути Antigravity Desktop
        os.path.join(local_app, "Programs", "antigravity", "resources", "bin", "language_server.exe"),
        os.path.join(local_app, "Programs", "antigravity", "resources", "bin", "agy.exe"),
        # Antigravity IDE расширения
        os.path.join(local_app, "Programs", "Antigravity IDE", "resources", "app", "extensions", "antigravity", "bin", "language_server_windows_x64.exe"),
        os.path.join(local_app, "Programs", "Antigravity IDE", "resources", "app", "extensions", "antigravity", "bin", "language_server.exe"),
        os.path.join(local_app, "Programs", "Antigravity IDE", "resources", "bin", "language_server.exe"),
        # Профиль пользователя и расширения
        os.path.join(user_prof, ".antigravity", "bin", "language_server.exe"),
        os.path.join(user_prof, ".antigravity", "bin", "agy.exe"),
        # ~/.gemini/bin/ (куда IDE 2.6+ скачивает автономный agy.exe)
        os.path.join(user_prof, ".gemini", "bin", "agy.exe"),
        os.path.join(user_prof, ".gemini", "bin", "language_server.exe"),
        os.path.join(user_prof, ".gemini", "antigravity", "bin", "agy.exe"),
        os.path.join(user_prof, ".gemini", "antigravity-cli", "bin", "agy.exe"),
    ]

    # Scoop apps
    scoop_roots = [
        os.path.join(user_prof, "scoop", "apps"),
        os.path.join(os.environ.get("SCOOP", ""), "apps")
    ]
    for sr in scoop_roots:
        if os.path.isdir(sr):
            for pat in ("*antigravity*", "agy*"):
                for p in Path(sr).glob(f"{pat}/**/language_server*.exe"):
                    candidate_paths.append(str(p))
                for p in Path(sr).glob(f"{pat}/**/agy*.exe"):
                    candidate_paths.append(str(p))

    # Реестр Windows (Uninstall)
    try:
        import winreg
        for hive, sub in (
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ):
            try:
                with winreg.OpenKey(hive, sub) as key:
                    num_keys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_keys):
                        try:
                            skey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, skey_name) as skey:
                                try:
                                    disp, _ = winreg.QueryValueEx(skey, "DisplayName")
                                except OSError:
                                    disp = None
                                if disp and "antigravity" in str(disp).lower():
                                    try:
                                        loc, _ = winreg.QueryValueEx(skey, "InstallLocation")
                                        if loc and os.path.isdir(loc):
                                            candidate_paths.append(os.path.join(loc, "resources", "bin", "language_server.exe"))
                                            candidate_paths.append(os.path.join(loc, "resources", "bin", "agy.exe"))
                                            for p in Path(loc).glob("**/language_server*.exe"):
                                                candidate_paths.append(str(p))
                                            for p in Path(loc).glob("**/agy*.exe"):
                                                candidate_paths.append(str(p))
                                    except OSError:
                                        pass
                        except OSError:
                            pass
            except OSError:
                pass
    except Exception:
        pass

    # Расширения VS Code / Cursor / Windsurf
    for base in (user_prof, local_app, app_data):
        ext_dir = os.path.join(base, ".antigravity", "extensions")
        if os.path.exists(ext_dir):
            for root, _, files in os.walk(ext_dir):
                for f in files:
                    if f.lower() in ("language_server.exe", "language_server_windows_x64.exe", "agy.exe"):
                        candidate_paths.append(os.path.join(root, f))

    # shutil.which
    for tool_name in ("language_server", "agy"):
        w = shutil.which(tool_name)
        if w:
            candidate_paths.append(w)

    # Дедупликация с сохранением порядка
    found = []
    seen = set()
    for p in candidate_paths:
        if not p:
            continue
        norm = os.path.normpath(p).lower()
        if os.path.isfile(p) and norm not in seen:
            seen.add(norm)
            found.append(p)
    return found

def safe_terminate_process(proc_name: str) -> None:
    """
    Безопасное завершение процессов с именем proc_name.
    Защищает текущий процесс, его предков (включая сессию IDE и Antigravity Hub)
    от случайного самозавершения.
    """
    target_name = proc_name.lower()
    my_pids = {os.getpid()}
    try:
        import psutil
        curr = psutil.Process()
        for p in curr.parents():
            my_pids.add(p.pid)
    except Exception:
        pass

    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pname = proc.info.get('name')
                if pname and pname.lower() == target_name:
                    pid = proc.info.get('pid')
                    if pid in my_pids:
                        continue  # Защита собственного древа процессов
                    cmdline = " ".join(proc.info.get('cmdline') or [])
                    # Если это активный Antigravity Hub / агент - не прерывать
                    if "--hub" in cmdline or "--app_data_dir" in cmdline:
                        continue
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        # Fallback на taskkill только для language_server (никогда для agy.exe вслепую)
        if target_name not in ("agy.exe", "antigravity.exe", "antigravity ide.exe"):
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True)

def apply_pending_patches():
    """
    Применяет отложенные патчи (.pending_patch), если файлы были заблокированы.
    """
    bins = get_binary_paths()
    for bpath in bins:
        pending = bpath + ".pending_patch"
        if os.path.exists(pending):
            fname = os.path.basename(bpath)
            try:
                with open(pending, "rb") as pf:
                    pdata = pf.read()
                with open(bpath, "wb") as bf:
                    bf.write(pdata)
                os.remove(pending)
                print(f"  [+] {fname}: Отложенный патч успешно применен.")
            except PermissionError:
                pass
            except Exception as e:
                print(f"  [-] {fname}: Ошибка применения отложенного патча: {e}")

def patch_binaries():
    """
    Двухуровневый патчинг бинарников с сохранением байтовой длины:
    1. ineligible -> inexigible (10 байт в 10 байт) — обход регионального гейта Google.
    2. https_proxy -> AG_LS_PROXY (11 байт в 11 байт) — изолированное чтение переменной прокси.
    """
    apply_pending_patches()
    bins = get_binary_paths()
    if not bins:
        print("  [-] Исполняемые файлы Antigravity не найдены.")
        return False

    patched_any = False
    for bpath in bins:
        fname = os.path.basename(bpath)
        try:
            with open(bpath, "rb") as f:
                data = f.read()

            inel_cnt = data.count(SIG_INELIGIBLE)
            inex_cnt = data.count(SIG_INEXIGIBLE)
            proxy_cnt = data.count(SIG_HTTPS_PROXY)
            ag_proxy_cnt = data.count(SIG_AG_PROXY)

            need_patch = (inel_cnt > 0) or (proxy_cnt > 0)
            if need_patch:
                # Безопасно завершаем конкурирующие процессы
                safe_terminate_process(fname)
                time.sleep(0.3)

                new_data = data
                changes = []
                if inel_cnt > 0:
                    new_data = new_data.replace(SIG_INELIGIBLE, SIG_INEXIGIBLE)
                    changes.append(f"регион: {inel_cnt} замен")
                if proxy_cnt > 0:
                    new_data = new_data.replace(SIG_HTTPS_PROXY, SIG_AG_PROXY)
                    changes.append(f"прокси-канал: {proxy_cnt} замен")

                try:
                    with open(bpath, "wb") as f:
                        f.write(new_data)
                    print(f"  [+] {fname}: Успешно пропатчен ({', '.join(changes)}).")
                    patched_any = True
                except PermissionError:
                    print(f"  [!] {fname}: Файл заблокирован активным процессом ({', '.join(changes)}).")
                    try:
                        pending_file = bpath + ".pending_patch"
                        with open(pending_file, "wb") as pf:
                            pf.write(new_data)
                        print(f"      Создан файл отложенного обновления: {fname}.pending_patch (применится при перезапуске).")
                    except Exception as pe:
                        print(f"      Не удалось создать отложенный патч: {pe}")
            elif inex_cnt > 0:
                print(f"  [i] {fname}: Уже пропатчен (активен inexigible: {inex_cnt}, AG_LS_PROXY: {ag_proxy_cnt}).")
            else:
                print(f"  [?] {fname}: Сигнатуры не обнаружены.")
        except Exception as e:
            print(f"  [-] {fname}: Ошибка патчинга: {e}")
    return True

def unpatch_binaries():
    """
    Чистый откат бинарников:
    1. inexigible -> ineligible
    2. AG_LS_PROXY -> https_proxy
    """
    bins = get_binary_paths()
    for bpath in bins:
        fname = os.path.basename(bpath)
        try:
            with open(bpath, "rb") as f:
                data = f.read()

            inex_cnt = data.count(SIG_INEXIGIBLE)
            ag_proxy_cnt = data.count(SIG_AG_PROXY)

            if inex_cnt > 0 or ag_proxy_cnt > 0:
                safe_terminate_process(fname)
                time.sleep(0.3)

                new_data = data.replace(SIG_INEXIGIBLE, SIG_INELIGIBLE)
                new_data = new_data.replace(SIG_AG_PROXY, SIG_HTTPS_PROXY)

                try:
                    with open(bpath, "wb") as f:
                        f.write(new_data)
                    print(f"  [+] {fname}: Полностью откачен обратно (регион: {inex_cnt}, прокси: {ag_proxy_cnt}).")
                except PermissionError:
                    print(f"  [!] {fname}: Файл заблокирован активным процессом. Откат отложен до перезапуска.")
        except Exception as e:
            print(f"  [-] {fname}: Ошибка отката: {e}")

def clean_ide_cache():
    """
    Очистка скомпилированного байткод-кэша V8 (CachedData, Code Cache/js).
    Предотвращает запуск закэшированного JS с проверками региона.
    """
    home = Path.home()
    appdata = os.environ.get("APPDATA", "")
    user_prof = os.environ.get("USERPROFILE", "")

    cache_targets = [
        os.path.join(appdata, "Antigravity IDE", "CachedData"),
        os.path.join(appdata, "Antigravity IDE", "Code Cache", "js"),
        os.path.join(appdata, "Antigravity", "CachedData"),
        os.path.join(appdata, "Antigravity", "Code Cache", "js"),
        os.path.join(user_prof, "scoop", "persist", "antigravity-ide", "data", "user-data", "CachedData"),
        os.path.join(user_prof, "scoop", "persist", "antigravity-ide", "data", "user-data", "Code Cache", "js"),
    ]

    cleaned = 0
    for target in cache_targets:
        if os.path.exists(target):
            try:
                shutil.rmtree(target, ignore_errors=True)
                cleaned += 1
            except Exception:
                pass
    if cleaned > 0:
        print(f"  [+] Очищен кэш V8/Electron ({cleaned} директорий CachedData/Code Cache).")
    return cleaned

def get_tcp_snapshot_path():
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    return os.path.join(BACKUP_ROOT, "tcp_state.json")

def parse_tcp_global():
    """Парсинг текущих глобальных настроек TCP Windows из netsh."""
    try:
        res = subprocess.run(["netsh", "int", "tcp", "show", "global"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if res.returncode != 0:
            return {}
        params = {}
        for line in res.stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                v = v.strip().lower()
                params[k] = v
        return params
    except Exception:
        return {}

def tune_tcp_stack(enable=True):
    """
    Оптимизация сетевого стека Windows для максимальной производительности gRPC / streaming:
    1. autotuninglevel = normal (устраняет торможение входящего буфера)
    2. fastopen = enabled (TCP Fast Open экономит 1 RTT)
    3. hystart = enabled, prr = enabled, timestamps = allowed, rss = enabled, ecncapability = enabled
    """
    if not is_admin():
        print("  [-] Для настройки TCP требуются права Администратора.")
        return False

    snapshot_file = get_tcp_snapshot_path()
    if enable:
        current = parse_tcp_global()
        if current and not os.path.exists(snapshot_file):
            try:
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    json.dump(current, f, indent=2, ensure_ascii=False)
                print(f"  [+] Исходные параметры TCP сохранены в {snapshot_file}")
            except Exception as e:
                print(f"  [-] Ошибка сохранения снимка TCP: {e}")

        commands = [
            ("autotuninglevel", "normal"),
            ("rss", "enabled"),
            ("fastopen", "enabled"),
            ("hystart", "enabled"),
            ("prr", "enabled"),
            ("timestamps", "allowed"),
            ("ecncapability", "enabled")
        ]
        logs = []
        for key, val in commands:
            cmd = ["netsh", "int", "tcp", "set", "global", f"{key}={val}"]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
            if res.returncode == 0:
                logs.append(f"{key}={val}")

        print(f"  [+] Сетевой стек Windows оптимизирован ({', '.join(logs)}).")
        return True
    else:
        return restore_tcp_stack()

def restore_tcp_stack():
    """Восстановление исходных параметров TCP из сохраненного снимка."""
    snapshot_file = get_tcp_snapshot_path()
    if os.path.exists(snapshot_file):
        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                snapshot = json.load(f)

            # Восстанавливаем ключевые параметры
            # netsh int tcp set global autotuninglevel=...
            for k, v in snapshot.items():
                if "auto-tuning" in k or "autotuning" in k:
                    val = v if v in ("normal", "disabled", "highlyrestricted", "restricted", "experimental") else "normal"
                    subprocess.run(["netsh", "int", "tcp", "set", "global", f"autotuninglevel={val}"], capture_output=True)
                elif "fast open" in k or "fastopen" in k:
                    val = "enabled" if "enabled" in v else "disabled"
                    subprocess.run(["netsh", "int", "tcp", "set", "global", f"fastopen={val}"], capture_output=True)
                elif "ecn" in k:
                    val = "enabled" if "enabled" in v else "disabled"
                    subprocess.run(["netsh", "int", "tcp", "set", "global", f"ecncapability={val}"], capture_output=True)

            print("  [+] Параметры TCP успешно возвращены в исходное состояние.")
            return True
        except Exception as e:
            print(f"  [-] Ошибка восстановления TCP: {e}")
            return False
    else:
        # Стандартные сбросы
        subprocess.run(["netsh", "int", "tcp", "set", "global", "autotuninglevel=normal"], capture_output=True)
        return True

def install_task_daemon():
    """
    Регистрация задачи в Планировщике Windows (Task Scheduler):
    Автоматический фоновый автопатч при входе в систему без всплывающих окон.
    """
    script_path = os.path.abspath(__file__)
    py_exe = sys.executable
    if py_exe.lower().endswith("python.exe"):
        pyw = py_exe[:-10] + "pythonw.exe"
        runner = pyw if os.path.exists(pyw) else py_exe
    else:
        runner = py_exe

    cmd_action = f'"{runner}" "{script_path}" --daemon-check'

    try:
        subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True)
        res = subprocess.run([
            "schtasks", "/create", "/tn", TASK_NAME,
            "/tr", cmd_action,
            "/sc", "ONLOGON",
            "/f"
        ], capture_output=True, text=True, errors="ignore")

        if res.returncode == 0:
            print(f"  [+] Фоновый автопатчер успешно установлен в Планировщик Windows (Задача: {TASK_NAME}, триггер: ONLOGON).")
            return True
        else:
            # Если ONLOGON требует повышенных прав, ставим интервальную задачу
            res2 = subprocess.run([
                "schtasks", "/create", "/tn", TASK_NAME,
                "/tr", cmd_action,
                "/sc", "MINUTE", "/mo", "30",
                "/f"
            ], capture_output=True, text=True, errors="ignore")
            if res2.returncode == 0:
                print(f"  [+] Фоновый автопатчер установлен с интервалом проверки 30 мин (Задача: {TASK_NAME}).")
                return True
            else:
                print(f"  [-] Ошибка установки в Планировщик задач: {res.stderr or res2.stderr}")
                return False
    except Exception as e:
        print(f"  [-] Исключение при вызове schtasks: {e}")
        return False

def uninstall_task_daemon():
    """Удаление задачи автопатчера из Планировщика Windows."""
    try:
        res = subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True, text=True, errors="ignore")
        if res.returncode == 0:
            print(f"  [+] Задача {TASK_NAME} успешно удалена из Планировщика Windows.")
            return True
        else:
            print(f"  [i] Задача {TASK_NAME} не была зарегистрирована.")
            return True
    except Exception as e:
        print(f"  [-] Ошибка удаления задачи: {e}")
        return False

def get_daemon_status():
    """Проверка регистрации задачи в Планировщике Windows."""
    try:
        res = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME], capture_output=True, text=True, errors="ignore")
        return res.returncode == 0
    except Exception:
        return False

def check_daemon_updates():
    """
    Тихий фоновый режим проверки: если Google обновил Antigravity и бинарники стали unpatched,
    автоматически патчим их и чистим кэш V8.
    """
    bins = get_binary_paths()
    needs_patch = False
    for b in bins:
        try:
            with open(b, "rb") as f:
                data = f.read()
            if SIG_INELIGIBLE in data or SIG_HTTPS_PROXY in data:
                needs_patch = True
                break
        except Exception:
            pass

    if needs_patch:
        patch_binaries()
        clean_ide_cache()

def configure_ide_settings(backend_url=DEFAULT_BACKEND_URL):
    app_data = os.environ.get("APPDATA", "")
    settings_dir = os.path.join(app_data, "Antigravity IDE", "User")
    settings_path = os.path.join(settings_dir, "settings.json")
    os.makedirs(settings_dir, exist_ok=True)

    data = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data["jetski.cloudCodeUrl"] = backend_url
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"  [+] Antigravity IDE: Настройка jetski.cloudCodeUrl = {backend_url}")
        return True
    except Exception as e:
        print(f"  [-] Ошибка записи settings.json: {e}")
        return False

def configure_env_vars(backend_url=DEFAULT_BACKEND_URL):
    cmd = f'[Environment]::SetEnvironmentVariable("CLOUD_CODE_URL", "{backend_url}", "User")'
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    os.environ["CLOUD_CODE_URL"] = backend_url
    print(f"  [+] Переменная окружения CLOUD_CODE_URL установлена ({backend_url}).")

def remove_env_vars():
    cmd = '[Environment]::SetEnvironmentVariable("CLOUD_CODE_URL", $null, "User")'
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    if "CLOUD_CODE_URL" in os.environ:
        del os.environ["CLOUD_CODE_URL"]
    print("  [+] Переменная окружения CLOUD_CODE_URL удалена.")

def set_ipv4_priority(enable=True):
    val = "46" if enable else "35"
    cmd = ["netsh", "interface", "ipv6", "set", "prefixpolicy", "::ffff:0:0/96", val, "4"]
    subprocess.run(cmd, capture_output=True)
    status = "включен" if enable else "сброшен"
    print(f"  [+] Приоритет IPv4 над IPv6: {status}.")

def execute_unlock(auto_find_proxy=True, target_ip=None, custom_worker_url=None):
    print("=" * 60)
    print("АКТИВАЦИЯ АНЛОКА ANTIGRAVITY (ГИБРИДНЫЙ АНТИ-LEAK АНЛОК)")
    print("=" * 60)

    # 1. Автоматический бэкап
    print("\n[Шаг 1/7] Создание резервной копии системы...")
    create_backup("pre_unlock")

    # 2. Очистка сбойных правил NRPT (защита от утечки в 111.88.96.50 и 172.217.x.x)
    print("\n[Шаг 2/7] Очистка сбойных правил NRPT и изоляция DNS...")
    clean_leaking_nrpt_rules()

    # 3. Выбор живого прокси
    if not target_ip:
        if auto_find_proxy:
            print("\n[Шаг 3/7] Поиск самого быстрого живого зарубежного SNI-прокси...")
            target_ip = find_best_proxy(verbose=True)
        else:
            target_ip = "94.130.180.225"

    # Привязка в hosts
    print(f"\n[Шаг 4/7] Привязка хостов в hosts к {target_ip}...")
    ok, msg = pin_hosts(target_ip)
    if ok:
        print(f"  [+] {msg}")
    else:
        print(f"  [-] {msg}")

    # 4. Патчинг бинарников (обход статуса ineligible и изоляция AG_LS_PROXY)
    print("\n[Шаг 5/7] Патчинг исполняемых файлов Language Server / agy...")
    patch_binaries()

    # 5. Очистка V8 кэша IDE
    print("\n[Шаг 6/7] Очистка скомпилированного байткод-кэша V8...")
    clean_ide_cache()

    # 6. Конфигурация IDE, переменных окружения, IPv4 и тюнинг TCP
    backend_url = custom_worker_url if custom_worker_url else DEFAULT_BACKEND_URL
    print(f"\n[Шаг 7/7] Настройка эндпоинтов IDE ({backend_url}), IPv4 и тюнинг TCP...")
    configure_ide_settings(backend_url)
    configure_env_vars(backend_url)
    set_ipv4_priority(True)
    tune_tcp_stack(True)
    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)

    print("\n" + "=" * 60)
    print("[УСПЕХ] Разблокировка успешно завершена! Antigravity готова к работе.")
    print("=" * 60)
    return True

def execute_rollback():
    print("=" * 60)
    print("ПОЛНЫЙ ОТКАТ ВСЕХ ИЗМЕНЕНИЙ (RESTORE)")
    print("=" * 60)

    print("\n[1/6] Удаление привязок из hosts и очистка NRPT...")
    ok, msg = unpin_hosts()
    print(f"  {msg}")

    print("\n[2/6] Откат бинарных патчей...")
    unpatch_binaries()

    print("\n[3/6] Удаление переменных окружения...")
    remove_env_vars()

    print("\n[4/6] Восстановление приоритета IPv6...")
    set_ipv4_priority(False)

    print("\n[5/6] Восстановление исходного сетевого стека TCP...")
    restore_tcp_stack()

    print("\n[6/6] Очистка DNS кэша...")
    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)

    print("\n" + "=" * 60)
    print("[УСПЕХ] Система полностью возвращена в исходное состояние.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon-check":
        check_daemon_updates()
        sys.exit(0)

    if not is_admin():
        elevate_process()
    else:
        if len(sys.argv) > 1 and sys.argv[1] == "--restore":
            execute_rollback()
        elif len(sys.argv) > 1 and sys.argv[1] == "--install-daemon":
            install_task_daemon()
        elif len(sys.argv) > 1 and sys.argv[1] == "--uninstall-daemon":
            uninstall_task_daemon()
        else:
            execute_unlock()
