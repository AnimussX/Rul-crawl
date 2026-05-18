# kivy_app/main_kivy.py
import sys
import os
import traceback
from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.label import Label
from kivy.core.window import Window

from gui.config import init_paths

# Глобальная ссылка на метку для вывода (будет установлена из main.py)
try:
    from main import log_to_screen
except ImportError:
    def log_to_screen(msg):
        print(msg)

# Переменные экранов
LoginScreen = None
MainMenuScreen = None
NovelListScreen = None
NovelInfoScreen = None
ChaptersScreen = None
LoadScreen = None
SettingsScreen = None
NewNovelScreen = None

# Импорт экранов с логированием
try:
    log_to_screen("Importing screens...")
    from kivy_app.screens.login import LoginScreen
    from kivy_app.screens.main_menu import MainMenuScreen
    from kivy_app.screens.novel_list import NovelListScreen
    from kivy_app.screens.novel_info import NovelInfoScreen
    from kivy_app.screens.chapters import ChaptersScreen
    from kivy_app.screens.load import LoadScreen
    from kivy_app.screens.settings import SettingsScreen
    from kivy_app.screens.new_novel import NewNovelScreen
    log_to_screen("Screens imported")
except Exception as e:
    log_to_screen(f"Screens import error: {e}")
    class ErrorScreen(Label):
        def __init__(self, **kwargs):
            super().__init__(text=f"Import error: {e}", halign="center")
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
        self.loading_label = Label(text="Loading, please wait...", halign="center", valign="center")
        self.loading_label.text_size = (Window.width, None)

        try:
            self._init_internal()
            self._build_ui()
            return self.sm
        except Exception:
            error_msg = traceback.format_exc()
            log_to_screen(f"App crashed:\n{error_msg}")
            # Дополнительно пытаемся записать в файл, если есть разрешение
            try:
                with open("/sdcard/debug_log.txt", "a") as f:
                    f.write(error_msg + "\n")
            except:
                pass
            self.loading_label.text = f"Error:\n{error_msg}"
            return self.loading_label

    def _init_internal(self):
        log_to_screen("init_paths...")
        init_paths()
        log_to_screen("paths ok")

        import scripts.auth
        from kivy_app.utils.paths import get_auth_file
        scripts.auth.AUTH_FILE = get_auth_file()
        log_to_screen("auth set")

        self._ensure_directories()
        log_to_screen("directories ok")

        if HAS_ANDROID:
            self._request_manage_storage()
            log_to_screen("storage permission checked")

        from scripts.auth import load_auth
        self.LOGIN, self.PASSWORD = load_auth()
        log_to_screen(f"credentials: login={'yes' if self.LOGIN else 'no'}")

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
        log_to_screen(f"UI built, screen={self.sm.current}")

    def _ensure_directories(self):
        from kivy_app.utils.paths import get_novels_base, get_novels_output_dir
        dirs = [get_novels_base(), get_novels_output_dir()]
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)

    def _request_manage_storage(self):
        if not check_permission(Permission.MANAGE_EXTERNAL_STORAGE):
            log_to_screen("Requesting MANAGE_EXTERNAL_STORAGE...")
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
                    log_to_screen(f"Failed to open storage settings: {e}")


if __name__ == '__main__':
    RulateCrawlerApp().run()