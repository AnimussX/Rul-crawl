# gui/config.py

import os
from scripts.paths import STORAGE, NOVELS_BASE, DB_PATH

# Оставляем для обратной совместимости, но основные пути теперь в scripts.paths
NOVELS_DIR = "/storage/emulated/0/Novels"
AUTH_FILE = os.path.expanduser("~/.lncrawl.auth")

# Для удобства экспортируем также другие константы (можно удалить, если не используются)
__all__ = ['STORAGE', 'NOVELS_BASE', 'DB_PATH', 'NOVELS_DIR', 'AUTH_FILE']