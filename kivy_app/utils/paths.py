# kivy_app/utils/paths.py
import os
from kivy.app import App

def get_app_data_dir():
    """Корневая папка данных приложения (внутреннее хранилище)."""
    return App.get_running_app().user_data_dir

def get_novels_base():
    """Папка для временных файлов (аналог Novelsbase)."""
    return os.path.join(get_app_data_dir(), 'Novelsbase')

def get_novels_output_dir():
    """Папка для готовых EPUB (внутреннее хранение)."""
    return os.path.join(get_app_data_dir(), 'Novels')

def get_db_path():
    """Путь к базе данных."""
    return os.path.join(get_app_data_dir(), 'Novels.db')

def get_auth_file():
    """Путь к файлу авторизации."""
    return os.path.join(get_app_data_dir(), '.lncrawl.auth')