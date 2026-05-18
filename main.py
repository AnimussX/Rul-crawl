# main.py
import sys
import traceback
from kivymd.app import MDApp
from kivy.uix.label import Label
from kivy.core.window import Window

# Заставка на время загрузки
class LoadingScreen(Label):
    def __init__(self, **kwargs):
        super().__init__(text="Loading, please wait...", halign="center", valign="center")
        self.text_size = (Window.width, None)

def show_error(error_text):
    """Показывает ошибку на весь экран."""
    class ErrorApp(MDApp):
        def build(self):
            return Label(text=error_text, font_size='14sp',
                         text_size=(Window.width, None))
    ErrorApp().run()

try:
    # Импортируем основное приложение
    from kivy_app.main_kivy import RulateCrawlerApp
    # Запускаем его
    RulateCrawlerApp().run()
except Exception:
    # Если произошла ошибка, показываем её на экране
    error = traceback.format_exc()
    show_error(error)