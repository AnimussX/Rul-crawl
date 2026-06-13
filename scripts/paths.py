# scripts/paths.py

import os
from pathlib import Path
from scripts.settings import load_settings

_settings = load_settings()
STORAGE = os.path.expanduser("~/storage/shared/lncrawl")
NOVELS_BASE = _settings.get("cache_base_dir", os.path.join(STORAGE, "Novelsbase"))
DB_PATH = os.path.join(NOVELS_BASE, "Novels.db")

# NOVELS_DIR теперь тоже из настроек
NOVELS_DIR = _settings.get("epub_output_dir", "/storage/emulated/0/Novels")