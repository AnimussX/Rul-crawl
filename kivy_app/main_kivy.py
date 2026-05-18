# kivy_app/main_kivy.py
import sys
import os
import traceback
from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.label import Label
from kivy.core.window import Window

from gui.config import init_paths

# Импортируем экраны (если какой-то не найдётся, увидим ошибку на экране)
try:
    from kivy_app.screens.login import LoginScreen
    from kivy_app.screens.main_menu import MainMenuScreen
    from kivy_app.screens.novel_list import NovelListScreen
    from kivy_app.screens.novel_info import NovelInfoScreen
    from kivy_app.screens.chapters import ChaptersScreen
    from kivy_app.screens.load import LoadScreen
    from kivy_app.screens.settings import SettingsScreen
    from kivy_app.screens.new_novel import NewNovelScreen
except Exception as e:
    # На случай ошибки импорта — покажем сразу
    class ErrorScreen(Label):
        def __init__(self, **kwargs):
            super().__init__(text=f"Import error: {e}", **kwargs)
    # Заменим все экраны заглушкой, чтобы приложение не упало
    LoginScreen = MainMenuScreen = NovelListScreen = NovelInfoScreen = ChaptersScreen = LoadScreen = SettingsScreen = NewNovelScreen = ErrorScreen

try:
    from android.permissions import check_permission, Permission, request_permission
    from android.content import Intent
    from jnius import autoclass
    HAS_ANDROID = True
except ImportError:
    HAS_ANDROID = False


class RulateCrawlerApp(MDApp):
    def build(self):
        # Сразу показываем индикатор загрузки
        self.loading_label = Label(text="Loading, please wait...", halign="center", valign="center")
        self.loading_label.text_size = (Window.width, None)

        try:
            self._init_internal()
            # Если всё хорошо, строим нормальный интерфейс
            self._build_ui()
            return self.sm
        except Exception as e:
            # Любая ошибка — показываем на экране
            error_msg = f"App crashed:\n{traceback.format_exc()}"
            self.loading_label.text = error_msg
            return self.loading_label

    def _init_internal(self):
        # Логируем каждый шаг
        self._log("init_paths...")
        init_paths()
        self._log("paths done")

        import scripts.auth
        from kivy_app.utils.paths import get_auth_file
        scripts.auth.AUTH_FILE = get_auth_file()
        self._log("auth done")

        self._ensure_directories()
        self._log("dirs ok")

        if HAS_ANDROID:
            self._request_manage_storage()
            self._log("storage request done")

        # Загружаем логин/пароль
        from scripts.auth import load_auth
        self.LOGIN, self.PASSWORD = load_auth()
        self._log("credentials loaded")

    def _build_ui(self):
        self.theme_cls.primary_palette = "Teal"
        self.sm = ScreenManager()
        self.sm.add_widget(LoginScreen(name='login'))
        self.sm.add_widget(MainMenuScreen(name='main_menu'))
        self.sm.add_widget(NovelListScreen(name='novel_list'))
        self.sm.add_widget(NovelInfoScreen(name='novel_info'))
        self.sm.add_widget(ChaptersScreen(name='chapters'))
        self.sm.add_widget(LoadScreen(name='load'))
        self.sm.add_widget(SettingsScreen(name='settings'))
        self.sm.add_widget(NewNovelScreen(name='new_novel'))

        if not self.LOGIN or not self.PASSWORD:
            self.sm.current = 'login'
        else:
            self.sm.current = 'main_menu'

    def _ensure_directories(self):
        from kivy_app.utils.paths import get_novels_base, get_novels_output_dir
        dirs = [get_novels_base(), get_novels_output_dir()]
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)

    def _request_manage_storage(self):
        if not check_permission(Permission.MANAGE_EXTERNAL_STORAGE):
            request_permission(Permission.MANAGE_EXTERNAL_STORAGE)
            if not check_permission(Permission.MANAGE_EXTERNAL_STORAGE):
                try:
                    Intent = autoclass('android.content.Intent')
                    Settings = autoclass('android.provider.Settings')
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    context = PythonActivity.mActivity
                    intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                    uri = autoclass('android.net.Uri').parse("package:" + context.getPackageName())
                    intent.setData(uri)
                    context.startActivity(intent)
                except Exception as e:
                    self._log(f"storage permission error: {e}")

    def _log(self, msg):
        try:
            with open("/sdcard/debug_log.txt", "a") as f:
                f.write(msg + "\n")
        except:
            pass


if __name__ == '__main__':
    RulateCrawlerApp().run()