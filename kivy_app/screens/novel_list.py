from kivymd.uix.screen import MDScreen
from kivymd.uix.list import OneLineListItem
from gui.database import get_all_novels
from kivymd.app import MDApp

class NovelListScreen(MDScreen):
    def on_enter(self):
        self.ids.container.clear_widgets()
        novels = get_all_novels()
        for nid, title, section, total in novels:
            item = OneLineListItem(
                text=f"[{section}] {title}",
                on_release=lambda x, nid=nid: self.open_novel(nid)
            )
            self.ids.container.add_widget(item)

    def open_novel(self, novel_id):
        app = MDApp.get_running_app()
        app.sm.get_screen('novel_info').novel_id = novel_id
        app.sm.current = 'novel_info'