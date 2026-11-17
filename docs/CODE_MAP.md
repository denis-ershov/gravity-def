# 🗺️ Open Source Карта Кода и Архитектурный Аудит (Code Map)

Проект **Antigravity Unlocker** является на 100% прозрачным Open Source программным обеспечением. В проекте **отсутствуют скомпилированные бинарные блобы, скрытая телеметрия или обфусцированный код**.

> ⚡ **Zero Dependencies (Чистый стандартный стек):**  
> Приложение написано исключительно с использованием стандартной библиотеки Python (Standard Library). Для запуска **не требуется установка сторонних пакетов через `pip`**, что полностью исключает риски атак на цепочку поставок (Supply Chain Attacks).

---

## 📁 Назначение и аудит каждого файла

```
├── gui.py                         # Точка входа в графический интерфейс
├── Запустить_Анлокер.bat          # Безопасный лаунчер Windows (запрос UAC)
├── Опубликовать_на_GitHub.bat    # Скрипт публикации репозитория
├── LICENSE                        # Официальная лицензия MIT
├── PROJECT_RULES.md               # База знаний и спецификация доменов
├── README.md                      # Главное руководство пользователя
├── .gitignore                     # Правила исключения временных файлов
├── docs/
│   ├── ARCHITECTURE.md            # Техническая спецификация сетевых уровней
│   ├── CODE_MAP.md                # Данная карта кода и аудит
│   ├── FAQ.md                     # Часто задаваемые вопросы
│   ├── CONTRIBUTING.md             # Руководство для контрибьюторов
│   └── SECURITY.md                # Политика безопасности и приватности
├── mcp/
│   └── win_unlocker_mcp.py        # FastMCP-сервер для управления AI-агентами
└── tools/
    ├── unlocker_core.py           # Оркестратор системных модификаций и отката
    ├── proxy_manager.py           # Пул прокси, бенчмарк и фоновый Watchdog
    ├── cloudflare_worker.js       # Исходный код Cloudflare Worker L7
    ├── backup_manager.py          # Модуль бэкапов с SHA-256 хешированием
    ├── diagnostics.py             # Комплексный сканер сетевых маршрутов
    ├── pin_hosts.py               # Низкоуровневый модуль работы с hosts
    ├── unlocker.py                # Консольная утилита анлока
    ├── test_proxies.py            # Быстрый тест доступности узлов
    └── test_http_proxy.py         # Утилита тестирования HTTP-прокси
```

---

## 🔍 Детальный аудит компонентов

### 1. `tools/proxy_manager.py` (Сетевой менеджер и Watchdog)
* **Используемые модули:** `socket`, `ssl`, `time`, `subprocess`, `threading`, `concurrent.futures`.
* **Что делает:**
  - `probe_single_host()`: Открывает стандартный TCP-сокет на порт 443 и инициирует безопасный TLS Client Hello с указанием SNI хоста. Замеряет задержку в миллисекундах.
  - `find_best_proxy()`: Многопоточно опрашивает открытый пул европейских узлов и выбирает быстрейший.
  - `clean_leaking_nrpt_rules()`: Вызывает системную команду PowerShell `Remove-DnsClientNrptRule` для очистки сбойных резолверов (защита от утечки в `172.217.x.x`).
  - `ProxyWatchdog`: Фоновый поток демона (Daemon Thread), который раз в 20 секунд проверяет соединение и при ошибке 10054 переключает `hosts` на резервный узел.

### 2. `tools/unlocker_core.py` (Ядро системы)
* **Используемые модули:** `os`, `sys`, `ctypes`, `subprocess`, `json`, `time`, `shutil`, `re`, `pathlib`, `winreg`.
* **Что делает:**
  - `is_admin()` / `elevate_process()`: Проверяет наличие прав Администратора через Windows API `ctypes.windll.shell32.IsUserAnAdmin()` и при необходимости запрашивает повышение через стандартный системный диалог UAC (`runas`).
  - `get_binary_paths()`: Глубокий поиск исполняемых файлов через реестр Windows (`HKCU`/`HKLM`/`WOW6432Node Uninstall`), Scoop (`scoop/apps`), `~/.gemini/bin/` (для Antigravity 2.6+), стандартные каталоги и `shutil.which`.
  - `patch_binaries()`: Двухуровневый байтовый патч с сохранением длины:
    - `ineligible` -> `inexigible` (10 байт в 10 байт) — обход региональной проверки;
    - `https_proxy` -> `AG_LS_PROXY` (11 байт в 11 байт) — изолированный канал проксирования без влияния на системный `HTTPS_PROXY`.
  - `clean_ide_cache()`: Очистка скомпилированного байткод-кэша V8 (`CachedData`, `Code Cache/js`), предотвращающая запуск старых JS-проверок.
  - `tune_tcp_stack()` / `restore_tcp_stack()`: Автонастройка TCP стека Windows (`autotuninglevel=normal`, `fastopen=enabled`, `rss=enabled`, `hystart=enabled`, `prr=enabled`, `ecncapability=enabled`) с сохранением снимка в `backups/tcp_state.json`.
  - `install_task_daemon()` / `uninstall_task_daemon()`: Управление фоновой задачей автопатчинга в Планировщике Windows (`schtasks`) для выживания при обновлениях Antigravity.
  - `configure_ide_settings()`: Записывает `"jetski.cloudCodeUrl"` в `%APPDATA%\Antigravity IDE\User\settings.json`.
  - `set_ipv4_priority()`: Выполняет системную команду `netsh interface ipv6 set prefixpolicy ::ffff:0:0/96 46 4` для приоритета IPv4.

### 2.1. `tools/diagnostics.py` (Сетевая диагностика и мониторинг)
* **Используемые модули:** `socket`, `ssl`, `subprocess`, `json`, `re`.
* **Что делает:**
  - `detect_model_activity()`: Непрерывный анализ живых логов Language Server (`%APPDATA%\Antigravity\logs\language_server.log` и `ls-main.log`). Детектирует реальный ответ модели (`streamGenerateContent?alt=sse ... ResponseID: ...`) либо отказ сервера по геолокации (`400 FAILED_PRECONDITION: User location is not supported` / `403 PERMISSION_DENIED: UNSUPPORTED_LOCATION`).
  - `check_hosts_pinning()` / `check_nrpt_rules()` / `check_dns_resolving()`: Комплексная валидация DNS и предотвращение утечек прямых IP Google.
  - `check_system_services()`: Контроль параметров TCP стека и статуса задачи Планировщика Windows.

### 3. `tools/backup_manager.py` (Безопасность и бэкапы)
* **Используемые модули:** `os`, `shutil`, `hashlib`, `json`, `time`.
* **Что делает:**
  - Копирует системный файл `hosts`, оригинальные бинарники и `settings.json` в локальную директорию `backups/`.
  - Вычисляет SHA-256 хеши каждого сохраненного файла и создает `manifest.json`.
  - Позволяет в любой момент восстановить файлы байт-в-байт.

### 4. `tools/cloudflare_worker.js` (L7 Cloudflare Relay)
* **Используемый стек:** Стандартный JavaScript (Fetch API, Web Standards).
* **Что делает:**
  - Удаляет заголовки `CF-Connecting-IP`, `X-Forwarded-For`.
  - Перенаправляет запрос на `cloudcode-pa.googleapis.com` из европейских/американских датацентров Cloudflare.
  - Перехватывает эндпоинт `:loadCodeAssist` и подменяет ответ со статуса `INELIGIBLE` на `ALLOWED`.

---

## 🛡️ Гарантии безопасности данных

1. **Никакой телеметрии:** Приложение не содержит аналитики, трекеров или внешних счетчиков.
2. **Прямой сквозной TLS:** Домены авторизации (`accounts.google.com`) идут напрямую через стандартный интернет. Ни логины, ни пароли, ни токены не могут быть перехвачены.
3. **100% локальное исполнение:** Все скрипты выполняются только на вашем локальном компьютере.
