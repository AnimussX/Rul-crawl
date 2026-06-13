# scripts/settings.py

import json
from pathlib import Path

SETTINGS_FILE = Path.home() / ".lncrawl_settings.json"

DEFAULT_SETTINGS = {
    "auto_save_log": True,
    "debug_mode": False,
    "cache_type": "json",           # "json" или "sqlite"
    "workers": 2,
    "image_workers": 2,
    "image_retries": 3,
    "image_timeout": 30,
    "slow_image_timeout": 120,
    "use_selenium_fallback": True,
    "progress_step": 1
}

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Объединяем с дефолтными, чтобы новые поля появились
                return {**DEFAULT_SETTINGS, **data}
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass