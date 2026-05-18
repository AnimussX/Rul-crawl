# main.py
import sys
import traceback
from kivy.app import App
from kivy.uix.label import Label
from kivy.core.window import Window

# Глобальный экран для вывода сообщений
output_label = None

def log_to_screen(text):
    global output_label
    if output_label:
        output_label.text += text + "\n"
        # Прокрутка не нужна, т.к. текст может быть длинным, но для экрана телефона просто показываем как есть
    else:
        # Если экран ещё не создан, просто печатаем (может попасть в logcat)
        print(text)

def show_error(error_text):
    log_to_screen(f"FATAL ERROR:\n{error_text}")

class MinimalApp(App):
    def build(self):
        global output_label
        # Создаём метку на весь экран, в которую будем выводить логи
        output_label = Label(
            text="Starting...",
            font_size='12sp',
            text_size=(Window.width - 20, None),
            halign='left',
            valign='top'
        )
        return output_label

    def on_start(self):
        # Запрашиваем разрешение на запись в хранилище (Android)
        try:
            from android.permissions import check_permission, Permission, request_permission
            if not check_permission(Permission.MANAGE_EXTERNAL_STORAGE):
                request_permission(Permission.MANAGE_EXTERNAL_STORAGE)
        except ImportError:
            pass  # не на Android

        # Теперь запускаем инициализацию
        try:
            self._init_main_app()
        except Exception:
            error = traceback.format_exc()
            log_to_screen(f"Initialization failed:\n{error}")
            return

    def _init_main_app(self):
        log_to_screen("Importing main kivy app...")
        from kivy_app.main_kivy import RulateCrawlerApp
        log_to_screen("Creating app...")
        # Закрываем наше минимальное приложение и запускаем основное
        self.stop()
        RulateCrawlerApp().run()

if __name__ == '__main__':
    MinimalApp().run()