#!/data/data/com.termux/files/usr/bin/env python3
# -*- coding: utf-8 -*-
#main.py 

import sys
import os
import os
# Имитируем наличие os.link для обхода ошибки в filelock на Android
if not hasattr(os, 'link'):
    def dummy_link(src, dst, *args, **kwargs):
        raise OSError("Hard links are not supported on Android")
    os.link = dummy_link
    # Также добавляем в supports_dir_fd, чтобы проверка os.link in os.supports_dir_fd не падала
    os.supports_dir_fd.add(dummy_link)

# ДАЛЬШЕ ИДЕТ ВАШ СТАРАЙ КОД:
# from gui.screens.login import LoginScreen...

from pathlib import Path


# Добавляем корень проекта в sys.path, чтобы работали импорты
sys.path.insert(0, str(Path(__file__).parent))

from textual.app import App
from textual.binding import Binding

from scripts.auth import load_auth, load_ranobes_auth
from scripts.paths import STORAGE
from gui.database import init_db
from gui.screens.login import LoginScreen
from gui.screens.main_menu import MainMenuScreen


# Проверка доступа к хранилищу Termux
if not os.path.isdir(STORAGE):
    print("⚠️  Хранилище не настроено. Выполните 'termux-setup-storage' и перезапустите.")
    print("Данные будут сохранены в домашнюю папку Termux.")

from scripts.chapter_cache import ChapterCache
from scripts.paths import NOVELS_BASE

# Миграция старых chapters_cache.json во всех папках книг
if Path(NOVELS_BASE).exists():
    for novel_dir in Path(NOVELS_BASE).iterdir():
        if novel_dir.is_dir():
            ChapterCache.migrate_old_chapters_cache(novel_dir)

class RulateCrawlerTUI(App):
    TITLE = "Rulate Crawler"

    CSS_PATH = "gui/styles/app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Выход"),
    ]

    def __init__(self):
            super().__init__()
            self.LOGIN, self.PASSWORD = load_auth()
            self.RANOBES_LOGIN, self.RANOBES_PASSWORD = load_ranobes_auth()

    def on_mount(self):
        init_db()
        if not self.LOGIN or not self.PASSWORD:
            self.push_screen(LoginScreen())
        else:
            self.push_screen(MainMenuScreen())


if __name__ == "__main__":
    app = RulateCrawlerTUI()
    app.run()