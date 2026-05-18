import os, sys, traceback
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.core.window import Window

# Попытка импорта базы данных
try:
    from gui.database import get_all_novels
except Exception as e:
    def get_all_novels():
        return []
    try:
        with open("/sdcard/debug_log.txt", "a") as f:
            f.write(f"Database import error: {e}\n{traceback.format_exc()}\n")
    except:
        pass

class MainScreen(Screen):
    def on_enter(self):
        layout = self.ids.layout
        layout.clear_widgets()
        try:
            novels = get_all_novels()
        except Exception as e:
            novels = []
            try:
                with open("/sdcard/debug_log.txt", "a") as f:
                    f.write(f"get_all_novels error: {e}\n")
            except:
                pass
        if not novels:
            layout.add_widget(Label(text="No novels found. Add one to begin."))
            return
        for nid, title, section, total in novels:
            btn = Button(text=f"[{section}] {title}", size_hint_y=None, height=50)
            btn.bind(on_release=lambda inst, nid=nid: self.open_novel(nid))
            layout.add_widget(btn)

    def open_novel(self, novel_id):
        self.manager.current = 'novel_info'
        self.manager.get_screen('novel_info').novel_id = novel_id

class NovelInfoScreen(Screen):
    novel_id = None
    def on_enter(self):
        self.ids.label.text = f"Novel ID: {self.novel_id}\n(Full info will be here)"

class RulateCrawlerApp(App):
    def build(self):
        # Пытаемся писать лог
        self.can_log = False
        try:
            with open("/sdcard/debug_log.txt", "a") as f:
                f.write("App started\n")
            self.can_log = True
        except:
            pass
        self._log("App build() called")
        Window.bind(on_request_close=self.on_request_close)

        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(NovelInfoScreen(name='novel_info'))
        return sm

    def on_start(self):
        self._log("App on_start()")
        try:
            from android.permissions import check_permission, Permission, request_permission
            if not check_permission(Permission.MANAGE_EXTERNAL_STORAGE):
                request_permission(Permission.MANAGE_EXTERNAL_STORAGE)
                self._log("MANAGE_EXTERNAL_STORAGE requested")
        except Exception as e:
            self._log(f"Permission error: {e}")

    def on_request_close(self, *args):
        self._log("App closing")
        return False

    def _log(self, msg):
        try:
            with open("/sdcard/debug_log.txt", "a") as f:
                f.write(msg + "\n")
        except:
            pass

if __name__ == '__main__':
    RulateCrawlerApp().run()