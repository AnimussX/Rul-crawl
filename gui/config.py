# gui/config.py
import os

STORAGE = None
NOVELS_BASE = None
NOVELS_DIR = None
DB_PATH = None
AUTH_FILE = None

def init_paths():
    """Вызывается один раз при старте Kivy‑приложения."""
    from kivy_app.utils.paths import (
        get_novels_base, get_novels_output_dir, get_db_path, get_auth_file
    )
    global STORAGE, NOVELS_BASE, NOVELS_DIR, DB_PATH, AUTH_FILE
    NOVELS_BASE = get_novels_base()
    NOVELS_DIR = get_novels_output_dir()
    DB_PATH = get_db_path()
    AUTH_FILE = get_auth_file()
    STORAGE = NOVELS_BASE