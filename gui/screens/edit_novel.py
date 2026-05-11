import os
import re
from textual.screen import Screen
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Header, Footer, Label, Input, Button, Select
from textual import on
from gui.database import get_novel, update_novel
from gui.config import NOVELS_BASE, NOVELS_DIR
from scripts.transliterate import slugify

class EditNovelScreen(Screen):
    SECTIONS = [
        ("Английские", "Английские"),
        ("Китайские", "Китайские"),
        ("Корейские", "Корейские"),
        ("Русские", "Русские"),
        ("Японские", "Японские"),
        ("(18+)", "(18+)"),
        ("Разные", "Разные"),
    ]

    def __init__(self, novel_id: int):
        super().__init__()
        self.novel_id = novel_id
        self.novel_data = None

    def compose(self):
        yield Header()
        yield Container(
            Label("Редактирование новеллы", id="title"),
            ScrollableContainer(
                Label("Название:", id="title_label"),
                Input(value="", id="title_input"),
                Label("Раздел:", id="section_label"),
                Select(options=self.SECTIONS, prompt="Выберите раздел", id="section_select"),
                Label("Папка для временных файлов (Novelsbase):", id="target_label"),
                Input(value="", id="target_dir"),
                Label("Папка для готовых EPUB:", id="output_label"),
                Input(value="", id="output_books"),
                Label("Общее количество глав:", id="total_label"),
                Input(value="", id="total_chapters", type="integer"),
                Label("", id="status"),
                id="form_container"
            ),
            Horizontal(
                Button("Сохранить", id="save", variant="success"),
                Button("Отмена", id="cancel", variant="default"),
                id="buttons"
            ),
            id="main"
        )
        yield Footer()

    def on_mount(self):
        self.novel_data = get_novel(self.novel_id)
        if not self.novel_data:
            self.query_one("#status").update("❌ Не удалось загрузить информацию.")
            return
        self.query_one("#title_input").value = self.novel_data['title']
        # Устанавливаем выбранный раздел
        current_section = self.novel_data.get('section', 'Разные')
        self.query_one("#section_select").value = current_section
        self.query_one("#target_dir").value = self.novel_data['target_dir']
        self.query_one("#output_books").value = self.novel_data['output_books']
        self.query_one("#total_chapters").value = str(self.novel_data['total_chapters'])

    @on(Select.Changed, "#section_select")
    def on_section_changed(self, event: Select.Changed):
        """Автоматически обновляем путь при изменении раздела"""
        new_section = event.value
        
        # Если пользователь сбросил выбор (Select.BLANK), ничего не делаем
        if new_section == Select.BLANK:
            return

        current_output = self.query_one("#output_books").value
        if not current_output:
            return

        from pathlib import Path
        path = Path(current_output)
        folder_name = path.name  # оригинальное имя папки книги

        # Формируем новый путь с учётом нового раздела
        if new_section != "Разные":
            new_path = os.path.join(NOVELS_DIR, new_section, folder_name)
        else:
            new_path = os.path.join(NOVELS_DIR, folder_name)

        self.query_one("#output_books").value = new_path

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "save":
            title = self.query_one("#title_input").value.strip()
            section = self.query_one("#section_select").value
            target_dir = self.query_one("#target_dir").value.strip()
            output_books = self.query_one("#output_books").value.strip()
            total_str = self.query_one("#total_chapters").value.strip()

            # Если раздел не выбран (Select.BLANK), считаем как "Разные"
            if section == Select.BLANK:
                section = "Разные"

            if not title or not target_dir or not output_books:
                self.query_one("#status").update("⚠️ Все поля должны быть заполнены.")
                return

            try:
                total = int(total_str) if total_str else 0
            except ValueError:
                self.query_one("#status").update("⚠️ Общее количество глав должно быть числом.")
                return

            update_novel(self.novel_id, title=title, section=section, target_dir=target_dir, 
                        output_books=output_books, total_chapters=total)
            self.app.notify("✅ Данные сохранены")
            self.app.pop_screen()