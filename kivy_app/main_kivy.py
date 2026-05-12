# kivy_app/main_kivy.py
import sys
import os
import traceback
from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager

from gui.config import init_paths
from kivy_app.screens.login import LoginScreen
from kivy_app.screens.main_menu import MainMenuScreen
from kivy_app.screens.novel_list import NovelListScreen
from kivy_app.screens.novel_info import NovelInfoScreen
from kivy_app.screens.chapters import ChaptersScreen
from kivy_app.screens.load import LoadScreen
from kivy_app.screens.settings import SettingsScreen
from kivy_app.screens.new_novel import NewNovelScreen

try:
    from android.permissions import check_permission, Permission, request_permission
    from android.content import Intent
    from jnius import autoclass
    HAS_ANDROID = True
except ImportError:
    HAS_ANDROID = False


class RulateCrawlerApp(MDApp):
    def build(self):
        # Подключаем логгер ошибок
        sys.excepthook = self._log_uncaught_exception
        try:
            self._log_to_file("main_kivy: build() started")
            init_paths()
            self._log_to_file("main_kivy: paths initialized")

            import scripts.auth
            from kivy_app.utils.paths import get_auth_file
            scripts.auth.AUTH_FILE = get_auth_file()
            self._log_to_file("main_kivy: auth_file set")

            self._ensure_directories()
            if HAS_ANDROID:
                self._request_manage_storage()

        except Exception as e:
            self._log_to_file(f"main_kivy: build() error: {e}")
            raise

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

        from scripts.auth import load_auth
        self.LOGIN, self.PASSWORD = load_auth()

        if not self.LOGIN or not self.PASSWORD:
            self.sm.current = 'login'
        else:
            self.sm.current = 'main_menu'
        return self.sm

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
                    self._log_to_file(f"Failed to open storage settings: {e}")

    def _log_uncaught_exception(self, exc_type, exc_value, exc_tb):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        self._log_to_file(f"UNCAUGHT: {error_msg}")

    def _log_to_file(self, msg):
        try:
            log_path = "/sdcard/debug_log.txt"
            with open(log_path, "a") as f:
                f.write(f"{msg}\n")
        except:
            pass


if __name__ == '__main__':
    RulateCrawlerApp().run()