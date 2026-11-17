import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Ensure tools directory in path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from tools.unlocker_core import (
    is_admin, elevate_process, execute_unlock, execute_rollback,
    patch_binaries, unpatch_binaries, set_ipv4_priority,
    configure_ide_settings, configure_env_vars, get_binary_paths,
    clean_ide_cache, tune_tcp_stack, restore_tcp_stack, parse_tcp_global,
    install_task_daemon, uninstall_task_daemon, get_daemon_status,
    SIG_INELIGIBLE, SIG_INEXIGIBLE, SIG_HTTPS_PROXY, SIG_AG_PROXY
)
from tools.proxy_manager import (
    find_best_proxy, pin_hosts, unpin_hosts, get_current_pinned_ip,
    probe_single_host, PROXIES_POOL, watchdog_instance
)
from tools.backup_manager import create_backup, restore_backup, list_backups
from tools.diagnostics import detect_model_activity

# Colors - Catppuccin Mocha inspired Dark Theme
BG_MAIN = "#1E1E2E"
BG_CARD = "#252538"
BG_CARD_BORDER = "#313244"
BG_CONSOLE = "#181825"
TEXT_MAIN = "#CDD6F4"
TEXT_MUTED = "#A6ADC8"
ACCENT_BLUE = "#89B4FA"
ACCENT_GREEN = "#A6E3A1"
ACCENT_RED = "#F38BA8"
ACCENT_YELLOW = "#F9E2AF"
ACCENT_PURPLE = "#CBA6F7"

class AntigravityUnlockerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Antigravity Unlocker 2.1 — Полный обход ограничений Google AI")
        self.geometry("940x740")
        self.minsize(850, 640)
        self.configure(bg=BG_MAIN)

        # Style configuration
        self.setup_styles()
        
        # UI Elements
        self.create_header()
        self.create_dashboard()
        self.create_action_buttons()
        self.create_console()

        # Start initial status check
        self.log("[*] Запуск интерфейса Antigravity Unlocker 2.1...")
        self.check_admin_status()
        self.refresh_dashboard_async()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure("TFrame", background=BG_MAIN)
        self.style.configure("Card.TFrame", background=BG_CARD, relief="solid", borderwidth=1)
        self.style.configure("TLabel", background=BG_MAIN, foreground=TEXT_MAIN, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=ACCENT_BLUE)
        self.style.configure("CardTitle.TLabel", font=("Segoe UI", 10, "bold"), background=BG_CARD, foreground=TEXT_MUTED)
        self.style.configure("CardValue.TLabel", font=("Segoe UI", 11, "bold"), background=BG_CARD, foreground=TEXT_MAIN)

    def log(self, text, color=None):
        self.console.config(state="normal")
        ts = time.strftime("[%H:%M:%S] ")
        self.console.insert(tk.END, ts + text + "\n")
        self.console.see(tk.END)
        self.console.config(state="disabled")

    def check_admin_status(self):
        if is_admin():
            self.admin_badge.config(text="● Права Администратора: ДА", foreground=ACCENT_GREEN)
            self.btn_elevate.pack_forget()
            self.log("[+] Приложение запущено с правами Администратора.")
        else:
            self.admin_badge.config(text="● Права Администратора: НЕТ", foreground=ACCENT_RED)
            self.btn_elevate.pack(side="right", padx=(0, 10))
            self.log("[!] Внимание: Для изменения hosts, сетевых политик и TCP требуются права Администратора.")

    def request_elevation(self):
        self.log("[*] Запрос повышения привилегий через UAC...")
        elevate_process()

    def create_header(self):
        header_frame = tk.Frame(self, bg=BG_MAIN, pady=8, padx=20)
        header_frame.pack(fill="x")

        title_label = tk.Label(
            header_frame, 
            text="🚀 Antigravity Unlocker 2.1", 
            font=("Segoe UI", 17, "bold"),
            bg=BG_MAIN, 
            fg=ACCENT_BLUE
        )
        title_label.pack(side="left")

        self.admin_badge = tk.Label(
            header_frame,
            text="● Проверка прав...",
            font=("Segoe UI", 10, "bold"),
            bg=BG_MAIN,
            fg=ACCENT_YELLOW
        )
        self.admin_badge.pack(side="right")

        self.btn_elevate = tk.Button(
            header_frame,
            text="🛡️ Перезапуск от Администратора",
            command=self.request_elevation,
            bg=ACCENT_RED,
            fg="#11111B",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2"
        )

    def create_dashboard(self):
        dash_frame = tk.Frame(self, bg=BG_MAIN, padx=20, pady=4)
        dash_frame.pack(fill="x")

        for col in range(4):
            dash_frame.columnconfigure(col, weight=1)

        # --- ROW 1 ---
        # Card 1: Binary Patch
        c1 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c1.grid(row=0, column=0, padx=4, pady=3, sticky="nsew")
        tk.Label(c1, text="Бинарный патч", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_patch_status = tk.Label(c1, text="Проверка...", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.lbl_patch_status.pack(anchor="w", pady=(2, 0))

        # Card 2: Hosts Pin
        c2 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c2.grid(row=0, column=1, padx=4, pady=3, sticky="nsew")
        tk.Label(c2, text="Привязка Hosts", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_hosts_status = tk.Label(c2, text="Проверка...", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.lbl_hosts_status.pack(anchor="w", pady=(2, 0))

        # Card 3: Ping Gemini API
        c3 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c3.grid(row=0, column=2, padx=4, pady=3, sticky="nsew")
        tk.Label(c3, text="Gemini API TLS", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_ping_status = tk.Label(c3, text="Тестирование...", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.lbl_ping_status.pack(anchor="w", pady=(2, 0))

        # Card 4: IPv4 Priority
        c4 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c4.grid(row=0, column=3, padx=4, pady=3, sticky="nsew")
        tk.Label(c4, text="Приоритет IPv4", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_ipv4_status = tk.Label(c4, text="Активен", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_GREEN)
        self.lbl_ipv4_status.pack(anchor="w", pady=(2, 0))

        # --- ROW 2 ---
        # Card 5: Model Activity (Log-based)
        c5 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c5.grid(row=1, column=0, padx=4, pady=3, sticky="nsew")
        tk.Label(c5, text="Статус модели (Логи)", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_model_status = tk.Label(c5, text="Анализ логов...", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.lbl_model_status.pack(anchor="w", pady=(2, 0))

        # Card 6: TCP Optimization
        c6 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c6.grid(row=1, column=1, padx=4, pady=3, sticky="nsew")
        tk.Label(c6, text="Сетевой стек TCP", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_tcp_status = tk.Label(c6, text="Проверка...", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.lbl_tcp_status.pack(anchor="w", pady=(2, 0))

        # Card 7: Background Daemon (Task Scheduler)
        c7 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c7.grid(row=1, column=2, padx=4, pady=3, sticky="nsew")
        tk.Label(c7, text="Автопатч (Daemon)", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_daemon_status = tk.Label(c7, text="Проверка...", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_YELLOW)
        self.lbl_daemon_status.pack(anchor="w", pady=(2, 0))

        # Card 8: V8 Bytecode Cache
        c8 = tk.Frame(dash_frame, bg=BG_CARD, padx=10, pady=8, highlightbackground=BG_CARD_BORDER, highlightthickness=1)
        c8.grid(row=1, column=3, padx=4, pady=3, sticky="nsew")
        tk.Label(c8, text="Кэш V8 / Electron", font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")
        self.lbl_cache_status = tk.Label(c8, text="Готов к очистке", font=("Segoe UI", 10, "bold"), bg=BG_CARD, fg=ACCENT_PURPLE)
        self.lbl_cache_status.pack(anchor="w", pady=(2, 0))

    def create_action_buttons(self):
        btn_frame = tk.Frame(self, bg=BG_MAIN, padx=20, pady=8)
        btn_frame.pack(fill="x")

        # Row 1: Главные кнопки действий
        r1 = tk.Frame(btn_frame, bg=BG_MAIN)
        r1.pack(fill="x", pady=2)

        btn_unlock = tk.Button(
            r1,
            text="⚡ АКТИВИРОВАТЬ АНЛОК (Smart Hosts + AG_LS_PROXY + TCP + Кэш)",
            font=("Segoe UI", 11, "bold"),
            bg="#2E7D32",
            fg="white",
            activebackground="#388E3C",
            activeforeground="white",
            relief="flat",
            padx=15,
            pady=8,
            cursor="hand2",
            command=self.run_unlock_thread
        )
        btn_unlock.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_rollback = tk.Button(
            r1,
            text="🔄 ПОЛНЫЙ ОТКАТ (Rollback)",
            font=("Segoe UI", 10, "bold"),
            bg="#C62828",
            fg="white",
            activebackground="#D32F2F",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            command=self.run_rollback_thread
        )
        btn_rollback.pack(side="right", padx=(5, 0))

        # Row 2: Быстрые инструменты из аудита
        r2 = tk.Frame(btn_frame, bg=BG_MAIN)
        r2.pack(fill="x", pady=4)

        self.btn_tcp = tk.Button(
            r2,
            text="⚡ Тюнинг TCP стека",
            font=("Segoe UI", 9, "bold"),
            bg="#1565C0",
            fg="white",
            activebackground="#1976D2",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=5,
            command=self.run_tcp_tune_thread
        )
        self.btn_tcp.pack(side="left", padx=(0, 4))

        self.btn_daemon_toggle = tk.Button(
            r2,
            text="⏰ Автопатч при входе",
            font=("Segoe UI", 9, "bold"),
            bg="#00695C",
            fg="white",
            activebackground="#00897B",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=5,
            command=self.run_daemon_toggle_thread
        )
        self.btn_daemon_toggle.pack(side="left", padx=4)

        btn_clean_cache = tk.Button(
            r2,
            text="🧹 Очистить кэш V8",
            font=("Segoe UI", 9),
            bg="#4527A0",
            fg="white",
            activebackground="#5E35B1",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=5,
            command=self.run_clean_cache_thread
        )
        btn_clean_cache.pack(side="left", padx=4)

        btn_diag = tk.Button(
            r2,
            text="🔍 Полная диагностика",
            font=("Segoe UI", 9),
            bg="#37474F",
            fg=TEXT_MAIN,
            activebackground="#455A64",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=5,
            command=self.run_diagnostics_thread
        )
        btn_diag.pack(side="left", padx=4)

        btn_elevate = tk.Button(
            r2,
            text="🔑 Запуск от Администратора",
            font=("Segoe UI", 9),
            bg="#4A148C",
            fg="white",
            activebackground="#6A1B9A",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=5,
            command=lambda: elevate_process([])
        )
        btn_elevate.pack(side="right", padx=(4, 0))

        # Row 3: Системные и сетевые утилиты
        r3 = tk.Frame(btn_frame, bg=BG_MAIN)
        r3.pack(fill="x", pady=2)

        self.btn_watchdog = tk.Button(
            r3,
            text="🐕 Watchdog: ВКЛЮЧЕН",
            font=("Segoe UI", 9, "bold"),
            bg="#1B5E20",
            fg="white",
            activebackground="#2E7D32",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=4,
            command=self.toggle_watchdog
        )
        self.btn_watchdog.pack(side="left", padx=(0, 4))

        btn_backup = tk.Button(
            r3,
            text="🛡️ Бэкап",
            font=("Segoe UI", 9),
            bg="#37474F",
            fg=TEXT_MAIN,
            activebackground="#455A64",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=4,
            command=self.run_backup_thread
        )
        btn_backup.pack(side="left", padx=4)

        btn_backups_list = tk.Button(
            r3,
            text="📁 История бэкапов",
            font=("Segoe UI", 9),
            bg="#37474F",
            fg=TEXT_MAIN,
            activebackground="#455A64",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=4,
            command=self.show_backups_dialog
        )
        btn_backups_list.pack(side="left", padx=4)

        btn_find_proxy = tk.Button(
            r3,
            text="⚡ Тест прокси",
            font=("Segoe UI", 9),
            bg="#37474F",
            fg=TEXT_MAIN,
            activebackground="#455A64",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=4,
            command=self.run_find_proxy_thread
        )
        btn_find_proxy.pack(side="left", padx=4)

        btn_worker = tk.Button(
            r3,
            text="☁️ Cloudflare L7 Relay",
            font=("Segoe UI", 9),
            bg="#BF360C",
            fg="white",
            activebackground="#D84315",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=4,
            command=self.show_worker_dialog
        )
        btn_worker.pack(side="left", padx=4)

        btn_github = tk.Button(
            r3,
            text="🚀 GitHub",
            font=("Segoe UI", 9, "bold"),
            bg="#24292E",
            fg="white",
            activebackground="#3F4448",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=4,
            command=self.show_github_dialog
        )
        btn_github.pack(side="right", padx=(4, 0))

    def create_console(self):
        console_frame = tk.Frame(self, bg=BG_MAIN, padx=20, pady=4)
        console_frame.pack(fill="both", expand=True)

        tk.Label(
            console_frame,
            text="Лог операций и системных событий:",
            font=("Segoe UI", 9, "bold"),
            bg=BG_MAIN,
            fg=TEXT_MUTED
        ).pack(anchor="w", pady=(0, 2))

        self.console = scrolledtext.ScrolledText(
            console_frame,
            bg=BG_CONSOLE,
            fg=TEXT_MAIN,
            font=("Consolas", 10),
            relief="flat",
            padx=10,
            pady=8,
            state="disabled",
            highlightbackground=BG_CARD_BORDER,
            highlightthickness=1
        )
        self.console.pack(fill="both", expand=True)

    def toggle_watchdog(self):
        if watchdog_instance.running:
            watchdog_instance.stop()
            self.btn_watchdog.config(text="🐕 Watchdog: ВЫКЛ", bg="#37474F")
        else:
            watchdog_instance.log_callback = lambda msg: self.log(msg)
            watchdog_instance.failover_callback = lambda new_ip: self.after(100, self._refresh_dashboard)
            watchdog_instance.start()
            self.btn_watchdog.config(text="🐕 Watchdog: ВКЛЮЧЕН", bg="#1B5E20")

    def show_worker_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Настройка Cloudflare Worker L7 Relay")
        dialog.geometry("680x420")
        dialog.configure(bg=BG_MAIN)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="☁️ Cloudflare Worker L7 Relay (Для 100% защиты русских аккаунтов)",
            font=("Segoe UI", 12, "bold"),
            bg=BG_MAIN,
            fg=ACCENT_BLUE
        ).pack(anchor="w", padx=15, pady=(15, 5))

        desc = (
            "Cloudflare Worker перехватывает эндпоинт :loadCodeAssist и подменяет ответ\n"
            "со статуса 'ineligible' на 'eligible' на лету, убирая геолокационные заголовки.\n\n"
            "Готовый скрипт воркера находится в файле: tools/cloudflare_worker.js"
        )
        tk.Label(dialog, text=desc, font=("Segoe UI", 9), bg=BG_MAIN, fg=TEXT_MUTED, justify="left").pack(anchor="w", padx=15, pady=5)

        f_url = tk.Frame(dialog, bg=BG_MAIN)
        f_url.pack(fill="x", padx=15, pady=10)

        tk.Label(f_url, text="URL вашего Worker:", font=("Segoe UI", 10, "bold"), bg=BG_MAIN, fg=TEXT_MAIN).pack(anchor="w")
        ent_url = tk.Entry(f_url, font=("Consolas", 10), bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN)
        ent_url.pack(fill="x", pady=5)
        
        cur_url = os.environ.get("CLOUD_CODE_URL", "https://daily-cloudcode-pa.googleapis.com")
        ent_url.insert(0, cur_url)

        def apply_worker_url():
            url = ent_url.get().strip()
            if not url.startswith("http"):
                messagebox.showerror("Ошибка", "URL должен начинаться с https:// или http://")
                return
            configure_ide_settings(url)
            configure_env_vars(url)
            self.log(f"[+] Установлен кастомный CloudCode URL: {url}")
            messagebox.showinfo("Успех", f"URL бэкенда успешно обновлен на:\n{url}")
            dialog.destroy()

        def reset_worker_url():
            default_url = "https://daily-cloudcode-pa.googleapis.com"
            configure_ide_settings(default_url)
            configure_env_vars(default_url)
            self.log("[+] Сброшен CloudCode URL на дефолтный.")
            messagebox.showinfo("Сброс", "URL сброшен на стандартный (daily-cloudcode-pa.googleapis.com)")
            dialog.destroy()

        btn_f = tk.Frame(dialog, bg=BG_MAIN)
        btn_f.pack(fill="x", padx=15, pady=15)

        tk.Button(btn_f, text="💾 Применить Worker URL", bg="#2E7D32", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=5, command=apply_worker_url).pack(side="left")
        tk.Button(btn_f, text="🔄 Сброс на дефолт", bg="#C62828", fg="white", font=("Segoe UI", 9), relief="flat", padx=10, pady=5, command=reset_worker_url).pack(side="left", padx=10)
        tk.Button(btn_f, text="Закрыть", bg="#37474F", fg="white", font=("Segoe UI", 9), relief="flat", padx=10, pady=5, command=dialog.destroy).pack(side="right")

    def show_github_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Публикация на GitHub (Open Source)")
        dialog.geometry("680x420")
        dialog.configure(bg=BG_MAIN)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="🚀 Публикация Antigravity Unlocker на ваш GitHub",
            font=("Segoe UI", 12, "bold"),
            bg=BG_MAIN,
            fg=ACCENT_BLUE
        ).pack(anchor="w", padx=15, pady=(15, 5))

        desc = (
            "1. Создайте пустой публичный репозиторий на github.com/new (без README/.gitignore)\n"
            "2. Вставьте ссылку на ваш репозиторий ниже\n"
            "3. Нажмите кнопку «Опубликовать на GitHub» — программа сама отправит все файлы!"
        )
        tk.Label(dialog, text=desc, font=("Segoe UI", 9), bg=BG_MAIN, fg=TEXT_MUTED, justify="left").pack(anchor="w", padx=15, pady=5)

        f_url = tk.Frame(dialog, bg=BG_MAIN)
        f_url.pack(fill="x", padx=15, pady=10)

        tk.Label(f_url, text="Ссылка на ваш GitHub репозиторий (.git):", font=("Segoe UI", 10, "bold"), bg=BG_MAIN, fg=TEXT_MAIN).pack(anchor="w")
        ent_url = tk.Entry(f_url, font=("Consolas", 10), bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN)
        ent_url.pack(fill="x", pady=5)
        ent_url.insert(0, "https://github.com/ВАШ_ЛОГИН/antigravity-unlocker.git")

        def do_publish():
            url = ent_url.get().strip()
            if not url.startswith("http") and not url.startswith("git@"):
                messagebox.showerror("Ошибка", "Ссылка должна начинаться с https:// или git@")
                return
            dialog.destroy()
            
            def _push_worker():
                self.log("\n" + "=" * 50)
                self.log(f"🚀 Публикация проекта на GitHub ({url})...")
                import subprocess
                subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
                subprocess.run(["git", "remote", "add", "origin", url], capture_output=True)
                res = subprocess.run(["git", "push", "-u", "origin", "main"], capture_output=True, text=True)
                if res.returncode == 0:
                    self.log("🎉 [УСПЕХ] Проект успешно опубликован на GitHub!")
                    self.log(f"  Ссылка: {url.replace('.git', '')}")
                    self.after(100, lambda: messagebox.showinfo("Успех", f"Репозиторий успешно опубликован на GitHub!\n\n{url.replace('.git', '')}"))
                else:
                    self.log(f"[-] Ошибка отправки:\n{res.stderr}")
                    self.after(100, lambda: messagebox.showerror("Ошибка публикации", f"Не удалось отправить репозиторий:\n{res.stderr}"))
                self.log("=" * 50)

            threading.Thread(target=_push_worker, daemon=True).start()

        btn_f = tk.Frame(dialog, bg=BG_MAIN)
        btn_f.pack(fill="x", padx=15, pady=15)

        tk.Button(btn_f, text="🚀 Опубликовать на GitHub", bg="#2E7D32", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=5, command=do_publish).pack(side="left")
        tk.Button(btn_f, text="Закрыть", bg="#37474F", fg="white", font=("Segoe UI", 9), relief="flat", padx=10, pady=5, command=dialog.destroy).pack(side="right")

    def refresh_dashboard_async(self):
        threading.Thread(target=self._refresh_dashboard, daemon=True).start()

    def _refresh_dashboard(self):
        # 1. Check Binary Patches
        bins = get_binary_paths()
        all_patched = True
        has_bins = bool(bins)
        for b in bins:
            try:
                with open(b, "rb") as f:
                    data = f.read()
                if data.count(SIG_INEXIGIBLE) == 0:
                    all_patched = False
                    break
            except Exception:
                all_patched = False

        if all_patched and has_bins:
            self.lbl_patch_status.config(text="ПРОПАТЧЕН [OK]", fg=ACCENT_GREEN)
        else:
            self.lbl_patch_status.config(text="ТРЕБУЕТСЯ ПАТЧ", fg=ACCENT_RED)

        # 2. Check Hosts Pin
        pinned_ip = get_current_pinned_ip()
        if pinned_ip:
            self.lbl_hosts_status.config(text=f"АКТИВЕН ({pinned_ip})", fg=ACCENT_GREEN)
        else:
            self.lbl_hosts_status.config(text="НЕ ПРИВЯЗАН", fg=TEXT_MUTED)

        # 3. Check Gemini API Ping
        target_host = "cloudcode-pa.googleapis.com"
        probe_target_ip = pinned_ip or "94.130.180.225"
        ok, lat, err = probe_single_host(probe_target_ip, target_host, timeout=2.0)
        if ok:
            self.lbl_ping_status.config(text=f"OK ({lat:.0f} ms)", fg=ACCENT_GREEN)
        else:
            self.lbl_ping_status.config(text="ТАЙМАУТ / ОШИБКА", fg=ACCENT_RED)

        # 4. Check Model Activity (Логи)
        model_res = detect_model_activity()
        m_status = model_res["status"]
        if m_status == "WORKING":
            self.lbl_model_status.config(text="ОТВЕЧАЕТ [OK]", fg=ACCENT_GREEN)
        elif m_status == "BLOCKED":
            self.lbl_model_status.config(text="ОТКАЗ СЕРВЕРА [400]", fg=ACCENT_RED)
        elif m_status == "NO_LOGS":
            self.lbl_model_status.config(text="НЕТ ЛОГОВ", fg=TEXT_MUTED)
        else:
            self.lbl_model_status.config(text="ОЖИДАНИЕ [IDLE]", fg=ACCENT_YELLOW)

        # 5. Check TCP stack
        tcp = parse_tcp_global()
        autotuning = tcp.get("receive window auto-tuning level", "unknown")
        if autotuning == "normal":
            self.lbl_tcp_status.config(text="NORMAL (TFO/RSS) [OK]", fg=ACCENT_GREEN)
        else:
            self.lbl_tcp_status.config(text=f"{autotuning.upper()}", fg=ACCENT_YELLOW)

        # 6. Check Daemon (Task Scheduler)
        d_active = get_daemon_status()
        if d_active:
            self.lbl_daemon_status.config(text="АКТИВЕН [ONLOGON]", fg=ACCENT_GREEN)
            self.btn_daemon_toggle.config(text="⏰ Автопатч: ВКЛ", bg="#00695C")
        else:
            self.lbl_daemon_status.config(text="НЕ УСТАНОВЛЕН", fg=TEXT_MUTED)
            self.btn_daemon_toggle.config(text="⏰ Автопатч: ВЫКЛ", bg="#37474F")

    def run_unlock_thread(self):
        if not is_admin():
            if messagebox.askyesno("Требуются права Администратора", "Для применения анлока требуются права Администратора.\n\nПерезапустить приложение с правами Администратора?"):
                elevate_process([])
            return
        threading.Thread(target=self._do_unlock, daemon=True).start()

    def _do_unlock(self):
        self.log("\n" + "="*50)
        self.log("🚀 ЗАПУСК ПОЛНОЙ АКТИВАЦИИ АНЛОКА 2.1...")
        try:
            execute_unlock()
            self.after(100, lambda: messagebox.showinfo("Успех", "Разблокировка успешно применена!\n\nВсе компоненты пропатчены, V8 кэш очищен, TCP оптимизирован."))
        except Exception as e:
            self.log(f"[-] Ошибка во время выполнения: {e}")
            self.after(100, lambda: messagebox.showerror("Ошибка", f"Произошла ошибка: {e}"))
        finally:
            self._refresh_dashboard()

    def run_rollback_thread(self):
        if not is_admin():
            if messagebox.askyesno("Требуются права Администратора", "Для отката требуются права Администратора.\n\nПерезапустить с правами Администратора?"):
                elevate_process([])
            return

        if not messagebox.askyesno("Подтверждение отката", "Вы уверены, что хотите отменить все изменения и вернуть систему в исходное состояние?"):
            return

        threading.Thread(target=self._do_rollback, daemon=True).start()

    def _do_rollback(self):
        self.log("\n" + "="*50)
        self.log("🔄 ЗАПУСК ПОЛНОГО ОТКАТА...")
        try:
            watchdog_instance.stop()
            self.btn_watchdog.config(text="🐕 Watchdog: ВЫКЛ", bg="#37474F")
            execute_rollback()
            self.after(100, lambda: messagebox.showinfo("Откат завершен", "Система успешно возвращена в исходное состояние."))
        except Exception as e:
            self.log(f"[-] Ошибка отката: {e}")
            self.after(100, lambda: messagebox.showerror("Ошибка", f"Ошибка отката: {e}"))
        finally:
            self._refresh_dashboard()

    def run_tcp_tune_thread(self):
        if not is_admin():
            if messagebox.askyesno("Права Администратора", "Для настройки TCP требуются права Администратора.\nПерезапустить?"):
                elevate_process([])
            return

        def _worker():
            self.log("\n[*] Применение оптимизации сетевого стека Windows (TCP Window Auto-Tuning, Fast Open, RSS)...")
            tune_tcp_stack(True)
            self.log("[+] Сетевой стек TCP успешно оптимизирован.")
            self._refresh_dashboard()

        threading.Thread(target=_worker, daemon=True).start()

    def run_daemon_toggle_thread(self):
        if not is_admin():
            if messagebox.askyesno("Права Администратора", "Для управления Планировщиком задач требуются права Администратора.\nПерезапустить?"):
                elevate_process([])
            return

        def _worker():
            active = get_daemon_status()
            if active:
                self.log("\n[*] Удаление задачи автопатчера из Планировщика Windows...")
                uninstall_task_daemon()
            else:
                self.log("\n[*] Регистрация фонового автопатчера в Планировщике Windows (ONLOGON)...")
                install_task_daemon()
            self._refresh_dashboard()

        threading.Thread(target=_worker, daemon=True).start()

    def run_clean_cache_thread(self):
        def _worker():
            self.log("\n[*] Очистка скомпилированного байткод-кэша V8 / Electron...")
            cnt = clean_ide_cache()
            self.log(f"[+] Очистка завершена ({cnt} каталогов).")
            self.lbl_cache_status.config(text="ОЧИЩЕН [OK]", fg=ACCENT_GREEN)

        threading.Thread(target=_worker, daemon=True).start()

    def run_backup_thread(self):
        threading.Thread(target=self._do_backup, daemon=True).start()

    def _do_backup(self):
        self.log("\n[+] Создание резервной копии...")
        bdir, _ = create_backup("manual")
        self.log(f"[+] Бэкап создан: {bdir}")
        self.after(100, lambda: messagebox.showinfo("Бэкап создан", f"Резервная копия успешно создана в:\n{bdir}"))

    def run_find_proxy_thread(self):
        threading.Thread(target=self._do_find_proxy, daemon=True).start()

    def _do_find_proxy(self):
        self.log("\n[+] Тестирование всех прокси серверов...")
        best_ip = find_best_proxy(verbose=True)
        self.log(f"[+] Самый быстрый прокси: {best_ip}")
        self._refresh_dashboard()

    def run_diagnostics_thread(self):
        threading.Thread(target=self._do_diagnostics, daemon=True).start()

    def _do_diagnostics(self):
        self.log("\n" + "="*50)
        self.log("🔍 ДИАГНОСТИКА СЕТИ, БИНАРНИКОВ И ЛОГОВ...")
        from tools.diagnostics import (
            check_hosts_pinning, check_nrpt_rules, check_dns_resolving,
            check_tls_connectivity, check_binary_patches,
            check_model_activity_report, check_system_services
        )
        
        old_stdout = sys.stdout
        class StdoutRedirector:
            def __init__(self, app):
                self.app = app
            def write(self, s):
                if s.strip():
                    self.app.log(s.strip())
            def flush(self):
                pass
        
        sys.stdout = StdoutRedirector(self)
        try:
            check_hosts_pinning()
            check_nrpt_rules()
            check_dns_resolving()
            check_tls_connectivity()
            check_binary_patches()
            check_model_activity_report()
            check_system_services()
        finally:
            sys.stdout = old_stdout
            self.log("="*50)

    def show_backups_dialog(self):
        backups = list_backups()
        dialog = tk.Toplevel(self)
        dialog.title("Управление резервными копиями (Бэкапы)")
        dialog.geometry("650x400")
        dialog.configure(bg=BG_MAIN)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="Список доступных резервных копий:", font=("Segoe UI", 11, "bold"), bg=BG_MAIN, fg=TEXT_MAIN).pack(anchor="w", padx=15, pady=10)

        tree_frame = tk.Frame(dialog, bg=BG_MAIN)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=5)

        cols = ("name", "created", "files")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=8)
        tree.heading("name", text="Имя бэкапа")
        tree.heading("created", text="Дата создания")
        tree.heading("files", text="Файлов")
        tree.column("name", width=220)
        tree.column("created", width=180)
        tree.column("files", width=80)

        for name, bpath, manifest in backups:
            tree.insert("", "end", values=(name, manifest.get("created_at", "N/A"), len(manifest.get("files", {}))), tags=(bpath,))

        tree.pack(side="left", fill="both", expand=True)

        btn_box = tk.Frame(dialog, bg=BG_MAIN, pady=10)
        btn_box.pack(fill="x", padx=15)

        def restore_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Внимание", "Выберите бэкап из списка!")
                return
            item = tree.item(sel[0])
            bpath = tree.item(sel[0], "tags")[0]
            if messagebox.askyesno("Восстановление", f"Восстановить файлы из бэкапа {item['values'][0]}?"):
                dialog.destroy()
                threading.Thread(target=lambda: (restore_backup(bpath), self._refresh_dashboard()), daemon=True).start()

        btn_restore = tk.Button(btn_box, text="🔄 Восстановить выбранный бэкап", bg="#2E7D32", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=5, command=restore_selected)
        btn_restore.pack(side="left")

        btn_close = tk.Button(btn_box, text="Закрыть", bg="#37474F", fg="white", font=("Segoe UI", 9), relief="flat", padx=10, pady=5, command=dialog.destroy)
        btn_close.pack(side="right")

if __name__ == "__main__":
    app = AntigravityUnlockerApp()
    app.mainloop()
