from kivymd.uix.screen import MDScreen
from kivy.clock import mainthread
from threading import Thread
from kivymd.uix.list import OneLineAvatarIconListItem, IconLeftWidget
from kivymd.app import MDApp
from gui.crawler_utils import get_novel_info
from gui.database import get_novel

class ChaptersScreen(MDScreen):
    chapters = []
    checked = []

    def on_enter(self):
        novel_id = MDApp.get_running_app().sm.get_screen('novel_info').novel_id
        novel = get_novel(novel_id)
        self.url = novel['url']
        self.ids.status_label.text = "Загрузка списка глав..."
        Thread(target=self.fetch_chapters).start()

    def fetch_chapters(self):
        try:
            app = MDApp.get_running_app()
            title, synopsis, chapters = get_novel_info(self.url, app.LOGIN, app.PASSWORD)
            self.chapters = chapters or []
            mainthread(self.update_ui)()
        except Exception as e:
            mainthread(lambda: setattr(self.ids.status_label, 'text', f"Ошибка: {e}"))()

    def update_ui(self):
        self.ids.status_label.text = f"Глав: {len(self.chapters)}"
        self.ids.chapters_list.clear_widgets()
        self.checked = [False] * len(self.chapters)
        for i, ch in enumerate(self.chapters):
            item = OneLineAvatarIconListItem(
                text=f"{i+1}. {ch.get('title', '?')}"
            )
            item.index = i
            item.bind(on_release=lambda inst, idx=i: self.toggle(idx))
            self.ids.chapters_list.add_widget(item)

    def toggle(self, idx):
        self.checked[idx] = not self.checked[idx]
        # можно визуально обновить чекбокс, но для простоты пропустим

    def select_all(self):
        for i in range(len(self.checked)):
            self.checked[i] = True
        self.ids.status_label.text = "Выбраны все главы"

    def deselect_all(self):
        for i in range(len(self.checked)):
            self.checked[i] = False
        self.ids.status_label.text = "Снято выделение"

    def start_download(self):
        selected = [i+1 for i, v in enumerate(self.checked) if v]
        if not selected:
            self.ids.status_label.text = "Не выбрано ни одной главы"
            return
        ranges = self.format_ranges(selected)
        app = MDApp.get_running_app()
        load_screen = app.sm.get_screen('load')
        load_screen.novel_id = app.sm.get_screen('novel_info').novel_id
        load_screen.chapters_spec = ranges
        load_screen.force = self.ids.force_check.active
        load_screen.ignore_images = self.ids.ignore_images.active
        load_screen.ignore_errors = self.ids.ignore_errors.active
        app.sm.current = 'load'

    @staticmethod
    def format_ranges(selected):
        selected.sort()
        ranges = []
        start = end = selected[0]
        for i in range(1, len(selected)):
            if selected[i] == end + 1:
                end = selected[i]
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = end = selected[i]
        ranges.append(f"{start}-{end}" if start != end else str(start))
        return ",".join(ranges)