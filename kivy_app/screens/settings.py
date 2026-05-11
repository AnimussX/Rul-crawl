# kivy_app/screens/settings.py
import os
from threading import Thread

from kivymd.uix.screen import MDScreen
from kivymd.uix.filemanager import MDFileManager
from kivymd.app import MDApp
from kivy.clock import mainthread

from scripts.auth import save_auth
from kivy_app.utils.import_data import import_termux_data

class SettingsScreen(MDScreen):
    file_manager = None

    def on_enter(self):
        app = MDApp.get_running_app()
        self.ids.login_field.text = app.LOGIN or ''
        self.ids.pass_field.text = ''

    def save_settings(self):
        login = self.ids.login_field.text
        password = self.ids.pass_field.text
        if login and password:
            save_auth(login, password)
            app = MDApp.get_running_app()
            app.LOGIN, app.PASSWORD = login, password
            self.ids.status_label.text = "✅ Настройки сохранены"
        else:
            self.ids.status_label.text = "⚠️ Введите логин и пароль"

    def open_file_manager(self):
        if not self.file_manager:
            self.file_manager = MDFileManager(
                select_path=self.import_from_path,
                exit_manager=self.close_file_manager,
                preview=False,
            )
        # Показываем файловый менеджер, начиная с корня SD-карты
        self.file_manager.show('/storage/emulated/0/')

    def close_file_manager(self, *args):
        self.file_manager.close()

    def import_from_path(self, path):
        """Вызывается после выбора папки в файловом менеджере."""
        self.close_file_manager()
        # Предполагаем, что выбрали корень lncrawl (где лежат Novelsbase и Novels.db)
        source_novelsbase = os.path.join(path, 'Novelsbase')
        source_db = os.path.join(path, 'Novelsbase', 'Novels.db')  # или просто os.path.join(path, 'Novels.db')
        self.ids.status_label.text = "Импорт запущен..."
        Thread(target=self._run_import, args=(source_novelsbase, source_db)).start()

    def _run_import(self, src_nb, src_db):
        import_termux_data(
            src_nb, src_db,
            progress_callback=lambda msg: mainthread(self._update_status)(msg)
        )
        mainthread(self._import_done)()

    def _update_status(self, msg):
        self.ids.status_label.text = msg

    def _import_done(self):
        self.ids.status_label.text = "Импорт завершён. Перезапустите приложение."