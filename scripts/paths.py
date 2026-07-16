# scripts/paths.py

import os
from pathlib import Path
from scripts.settings import load_settings

_settings = load_settings()

# Базовая папка для всех данных приложения (доступна в файловом менеджере)
# В Termux ~/storage/shared существует, только если выполнена команда termux-setup-storage.
# Иначе fallback на домашнюю папку Termux.
_STORAGE_BASE = os.path.expanduser("~/storage/shared")
if not os.path.isdir(_STORAGE_BASE):
    _STORAGE_BASE = os.path.expanduser("~")

STORAGE = _settings.get("data_root", os.path.join(_STORAGE_BASE, "lncrawl"))

# Папка для временных файлов и кэша (главы, БД, изображения)
NOVELS_BASE = _settings.get("cache_base_dir", os.path.join(STORAGE, "Novelsbase"))

# Папка для готовых EPUB
NOVELS_DIR = _settings.get("epub_output_dir", os.path.join(STORAGE, "Novels"))

# База данных
DB_PATH = os.path.join(NOVELS_BASE, "Novels.db")

# Cookies в приватной папке
COOKIES_DIR = Path.home() / ".local/share/rulate-crawler"
COOKIES_DIR.mkdir(parents=True, exist_ok=True)

# --- Rulate (tl.rulate.ru) ---
COOKIES_FILE = COOKIES_DIR / "cookies.pkl"
SELENIUM_COOKIES_FILE = COOKIES_DIR / "selenium_cookies.pkl"

# --- Ranobes (ranobes.com) ---
RANOBES_COOKIES_FILE = COOKIES_DIR / "ranobes_cookies.pkl"
RANOBES_SELENIUM_COOKIES_FILE = COOKIES_DIR / "ranobes_selenium_cookies.pkl"


def get_cookies_file(site: str) -> Path:
    """Универсальный доступ к cookie-файлу по короткому имени источника."""
    return COOKIES_DIR / f"{site}_cookies.pkl"


def get_selenium_cookies_file(site: str) -> Path:
    return COOKIES_DIR / f"{site}_selenium_cookies.pkl"


# При первом запуске создаём основные папки
for d in [NOVELS_BASE, NOVELS_DIR]:
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
