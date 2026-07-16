# gui/screens/new_novel.py

import os
import re
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, Input, Button, Select
from textual import work, on
from gui.crawler_utils import get_novel_info
from scripts.crawler_factory import get_crawler_class, detect_source_name
from scripts.paths import NOVELS_BASE, NOVELS_DIR
from gui.database import STATUSES
from scripts.transliterate import slugify
from gui.screens.confirm_paths import ConfirmPathsScreen

SOURCE_LABELS = {
    "rulate": "Rulate (tl.rulate.ru)",
    "ranobes": "Ranobes.com",
}


class NewNovelScreen(Screen):
    SECTIONS = [
        ("Английские", "Английские"),
        ("Китайские", "Китайские"),
        ("Корейские", "Корейские"),
        ("Русские", "Русские"),
        ("Японские", "Японские"),
        ("(18+)", "(18+)"),
        ("Разные", "Разные"),
    ]

    # Статусы для выбора
    STATUS_OPTIONS = [(s, s) for s in STATUSES]

    def compose(self):
        yield Header()
        yield Container(
            Label("Создание новой записи", id="title"),
            Input(placeholder="Ссылка на новеллу", id="url"),
            Label("", id="source_label"),
            Button("Получить информацию", id="fetch", variant="primary"),
            Input(placeholder="Название", id="title_input"),
            Select(options=self.SECTIONS, prompt="Выберите раздел", id="section_select"),
            Select(options=self.STATUS_OPTIONS, prompt="Статус", id="status_select", value=STATUSES[0]),
            Horizontal(
                Button("Далее", id="next", variant="success", disabled=True),
                Button("Отмена", id="cancel", variant="default"),
                id="buttons"
            ),
            id="form"
        )
        yield Footer()

    def on_mount(self):
        self.query_one("#section_select").value = "Разные"
        self.query_one("#status_select").value = "в работе"
        self.source = None

    @on(Select.Changed, "#section_select")
    def on_section_changed(self, event: Select.Changed):
        self._update_path_preview()

    @on(Input.Changed, "#url")
    def on_url_changed(self, event: Input.Changed):
        """Определяем источник по домену сразу при вводе ссылки."""
        url = event.value.strip()
        label = self.query_one("#source_label")
        if not url:
            label.update("")
            self.source = None
            return
        try:
            cls = get_crawler_class(url)
            self.source = detect_source_name(url)
            label.update(f"🔗 Источник: {SOURCE_LABELS.get(self.source, cls.__name__)}")
        except ValueError:
            self.source = None
            label.update("⚠️ Неизвестный сайт — ссылка не поддерживается")

    @on(Input.Changed, "#title_input")
    def on_title_changed(self, event: Input.Changed):
        if event.value.strip():
            self.query_one("#next").disabled = False
        else:
            self.query_one("#next").disabled = True

    def _update_path_preview(self):
        pass

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "fetch":
            url = self.query_one("#url").value.strip()
            if not url:
                self.app.notify("Введите ссылку", severity="warning")
                return
            try:
                get_crawler_class(url)
            except ValueError:
                self.app.notify(
                    "Ссылка не относится ни к одному из поддерживаемых сайтов "
                    "(Rulate, Ranobes.com)",
                    severity="error",
                )
                return
            self.query_one("#fetch").disabled = True
            self.query_one("#fetch").label = "⏳ Получение..."
            self._fetch_info(url)
        elif event.button.id == "next":
            url = self.query_one("#url").value
            title = self.query_one("#title_input").value
            section = self.query_one("#section_select").value
            status = self.query_one("#status_select").value

            if not url or not title:
                self.app.notify("Заполните ссылку и название", severity="warning")
                return
            if not section:
                section = "Разные"
            if not status:
                status = "в работе"

            try:
                source = detect_source_name(url)
            except ValueError:
                self.app.notify("Неизвестный источник ссылки", severity="error")
                return

            folder_name = slugify(title)
            if not folder_name:
                folder_name = "unnamed"
            target_dir = os.path.join(NOVELS_BASE, folder_name)

            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            safe_title = safe_title.strip()
            if not safe_title:
                safe_title = "Новелла"
            
            if section != "Разные":
                output_books = os.path.join(NOVELS_DIR, section, safe_title)
            else:
                output_books = os.path.join(NOVELS_DIR, safe_title)

            total = getattr(self, 'total_chapters', 0)

            self.app.push_screen(ConfirmPathsScreen(
                url, title, folder_name, target_dir, output_books,
                getattr(self, 'synopsis', None), total, section, status, source
            ))

    @work(thread=True)
    def _fetch_info(self, url: str):
        try:
            title, synopsis, chapters = get_novel_info(url, self.app.LOGIN, self.app.PASSWORD)
            total = len(chapters) if chapters else 0
            self.app.call_from_thread(self._on_info_fetched, title, synopsis, total)
        except Exception as e:
            self.app.call_from_thread(self._on_fetch_error, str(e))

    def _on_info_fetched(self, title, synopsis, total):
        fetch_btn = self.query_one("#fetch")
        fetch_btn.disabled = False
        fetch_btn.label = "Получить информацию"
        if title:
            self.query_one("#title_input").value = title
            self.query_one("#next").disabled = False
            self.synopsis = synopsis
            self.total_chapters = total
        else:
            self.query_one("#title_input").placeholder = "Не удалось получить название, введите вручную"
            self.query_one("#title_input").value = ""
            self.app.notify("Не удалось получить информацию. Введите вручную.", severity="warning")

    def _on_fetch_error(self, error):
        fetch_btn = self.query_one("#fetch")
        fetch_btn.disabled = False
        fetch_btn.label = "Получить информацию"
        self.app.notify(f"Ошибка: {error}", severity="error")
