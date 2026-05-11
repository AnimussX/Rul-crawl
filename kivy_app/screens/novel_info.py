from kivymd.uix.screen import MDScreen
from gui.database import get_novel
from gui.utils import html_to_text

class NovelInfoScreen(MDScreen):
    novel_id = None

    def on_enter(self):
        if not self.novel_id:
            return
        novel = get_novel(self.novel_id)
        self.ids.title_label.text = novel['title']
        self.ids.synopsis_label.text = html_to_text(novel['synopsis'] or "Нет описания")