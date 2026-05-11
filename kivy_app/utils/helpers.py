from kivy.app import App
import os

def get_data_dir():
    # Внутреннее хранилище приложения (не требует разрешений)
    return App.get_running_app().user_data_dir

def get_novels_base():
    # По умолчанию используем внутреннее хранилище
    return os.path.join(get_data_dir(), 'Novelsbase')