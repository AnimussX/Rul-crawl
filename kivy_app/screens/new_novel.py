import os
from kivymd.uix.screen import MDScreen
from kivymd.app import MDApp
from kivy.clock import mainthread
from threading import Thread

from gui.crawler_utils import get_novel_info
from gui.config import NOVELS_BASE, NOVELS_DIR
from gui.database import add_novel
from scripts.transliterate import slugify

class NewNovelScreen(MDScreen):
    def fetch_info(self):
        url = self.ids.url_field.text.strip()
        if not url:
            self.ids.status_label.text = "Введите ссылку"
            return
        self.ids.status_label.text = "Получение информации..."
        Thread(target=self._fetch, args=(url,)).start()

    def _fetch(self, url):
        app = MDApp.get_running_app()
        try:
            title, synopsis, chapters = get_novel_info(url, app.LOGIN, app.PASSWORD)
            mainthread(self._on_info)(title, synopsis, chapters)
        except Exception as e:
            mainthread(lambda: setattr(self.ids.status_label, 'text', f"Ошибка: {e}"))

    def _on_info(self, title, synopsis, chapters):
        if title:
            self.ids.title_field.text = title
            self.ids.status_label.text = f"Глав: {len(chapters) if chapters else 0}"
        else:
            self.ids.status_label.text = "Не удалось получить информацию"

    def confirm_add(self):
        url = self.ids.url_field.text.strip()
        title = self.ids.title_field.text.strip()
        if not url or not title:
            self.ids.status_label.text = "Заполните URL и название"
            return

        folder_name = slugify(title)
        target_dir = os.path.join(NOVELS_BASE, folder_name)
        # выходная папка внутри песочницы (потом можно перенести на SD)
        output_dir = os.path.join(NOVELS_DIR, title)

        novel_id = add_novel(
            title=title,
            url=url,
            target_dir=target_dir,
            output_books=output_dir,
            synopsis=getattr(self, 'synopsis', None),
            total_chapters=getattr(self, 'total_chapters', 0),
            section="Разные"
        )

        app = MDApp.get_running_app()
        app.sm.get_screen('novel_info').novel_id = novel_id
        app.sm.current = 'novel_info'
        self.ids.status_label.text = "✅ Добавлено"