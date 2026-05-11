import os
import re
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, Input, Button, Select
from textual import work, on
from gui.crawler_utils import get_novel_info
from gui.config import NOVELS_BASE, NOVELS_DIR
from scripts.transliterate import slugify
from gui.screens.confirm_paths import ConfirmPathsScreen

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

    def compose(self):
        yield Header()
        yield Container(
            Label("Создание новой записи", id="title"),
            Input(placeholder="Ссылка на новеллу", id="url"),
            Button("Получить информацию", id="fetch", variant="primary"),
            Input(placeholder="Название", id="title_input"),
            Select(options=self.SECTIONS, prompt="Выберите раздел", id="section_select"),
            Horizontal(
                Button("Далее", id="next", variant="success", disabled=True),
                Button("Отмена", id="cancel", variant="default"),
                id="buttons"
            ),
            id="form"
        )
        yield Footer()

    def on_mount(self):
        # Устанавливаем значение по умолчанию
        self.query_one("#section_select").value = "Разные"

    @on(Select.Changed, "#section_select")
    def on_section_changed(self, event: Select.Changed):
        """Обновляем предварительный просмотр пути при изменении раздела"""
        self._update_path_preview()

    @on(Input.Changed, "#title_input")
    def on_title_changed(self, event: Input.Changed):
        """Активируем кнопку Далее, если название не пустое"""
        if event.value.strip():
            self.query_one("#next").disabled = False
        else:
            self.query_one("#next").disabled = True

    def _update_path_preview(self):
        """Показываем пользователю, какой путь сформируется (опционально)"""
        # Можно добавить Label с предпросмотром, если нужно
        pass

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "fetch":
            url = self.query_one("#url").value
            if not url:
                self.app.notify("Введите ссылку", severity="warning")
                return
            self.query_one("#fetch").disabled = True
            self.query_one("#fetch").label = "⏳ Получение..."
            self._fetch_info(url)
        elif event.button.id == "next":
            url = self.query_one("#url").value
            title = self.query_one("#title_input").value
            section = self.query_one("#section_select").value

            if not url or not title:
                self.app.notify("Заполните ссылку и название", severity="warning")
                return
            if not section:
                section = "Разные"

            folder_name = slugify(title)
            if not folder_name:
                folder_name = "unnamed"
            target_dir = os.path.join(NOVELS_BASE, folder_name)

            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            safe_title = safe_title.strip()
            if not safe_title:
                safe_title = "Новелла"
            
            # Формируем путь с учётом раздела
            if section != "Разные":
                output_books = os.path.join(NOVELS_DIR, section, safe_title)
            else:
                output_books = os.path.join(NOVELS_DIR, safe_title)

            # Получаем общее количество глав (если есть)
            total = getattr(self, 'total_chapters', 0)

            self.app.push_screen(ConfirmPathsScreen(
                url, title, folder_name, target_dir, output_books,
                getattr(self, 'synopsis', None), total, section
            ))

    @work(thread=True)
    def _fetch_info(self, url: str):
        title, synopsis, chapters = get_novel_info(url, self.app.LOGIN, self.app.PASSWORD)
        total = len(chapters) if chapters else 0
        self.app.call_from_thread(self._on_info_fetched, title, synopsis, total)

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