# main.py
import traceback
from kivy.app import App
from kivy.uix.label import Label
from kivy.core.window import Window

def show_error(error_text):
    """Показывает ошибку на весь экран."""
    class ErrorApp(App):
        def build(self):
            return Label(text=error_text, font_size='14sp',
                         text_size=(Window.width, None))
    ErrorApp().run()

try:
    # Подключаем перехват необработанных исключений
    import sys
    def global_exception_handler(exc_type, exc_value, exc_tb):
        error = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(error)  # всё равно выведем в logcat при случае
        show_error(error)
        sys.__excepthook__(exc_type, exc_value, exc_tb)  # на всякий случай
    sys.excepthook = global_exception_handler

    # Пробуем запустить основное приложение
    from kivy_app.main_kivy import RulateCrawlerApp
    RulateCrawlerApp().run()
except Exception:
    # Если импорт или build сломались — показываем ошибку
    error = traceback.format_exc()
    show_error(error)