# kivy_app/main_kivy.py
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

# Импорт только для Android (на десктопе упадёт, поэтому обернём в try)
try:
    from android.permissions import check_permission, Permission, request_permission
    from android.content import Intent
    from jnius import autoclass
    HAS_ANDROID = True
except ImportError:
    HAS_ANDROID = False


class RulateCrawlerApp(MDApp):
    def build(self):
        init_paths()   # внутренние пути приложения

        # Устанавливаем AUTH_FILE
        import scripts.auth
        from kivy_app.utils.paths import get_auth_file
        scripts.auth.AUTH_FILE = get_auth_file()

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

        # Загружаем логин/пароль
        from scripts.auth import load_auth
        self.LOGIN, self.PASSWORD = load_auth()

        if not self.LOGIN or not self.PASSWORD:
            self.sm.current = 'login'
        else:
            self.sm.current = 'main_menu'
        return self.sm

    def on_start(self):
        # Запрос разрешений для Android 12+
        if HAS_ANDROID:
            self._request_manage_storage()

    def _request_manage_storage(self):
        if not check_permission(Permission.MANAGE_EXTERNAL_STORAGE):
            request_permission(Permission.MANAGE_EXTERNAL_STORAGE)
            # Если сразу не дали – открываем настройки приложения
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
                except Exception:
                    pass


if __name__ == '__main__':
    RulateCrawlerApp().run()