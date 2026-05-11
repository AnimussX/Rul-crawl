import os
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, Input, Button, Select
from textual import on
from gui.database import add_novel
from gui.screens.novel_info import NovelInfoScreen
from gui.config import NOVELS_DIR

class ConfirmPathsScreen(Screen):
    SECTIONS = [
        ("Английские", "Английские"),
        ("Китайские", "Китайские"),
        ("Корейские", "Корейские"),
        ("Русские", "Русские"),
        ("Японские", "Японские"),
        ("(18+)", "(18+)"),
        ("Разные", "Разные"),
    ]

    def __init__(self, url: str, title: str, folder_name: str, target_dir: str, output_books: str, synopsis=None, total_chapters=0, section="Разные"):
        super().__init__()
        self.url = url
        self.title = title
        self.folder_name = folder_name
        self.target_dir = target_dir
        self.output_books = output_books
        self.synopsis = synopsis
        self.total_chapters = total_chapters
        self.section = section

    def compose(self):
        yield Header()
        yield Container(
            Label("Подтверждение путей", id="title"),
            Label(f"Название: {self.title}", id="title_display"),
            Select(options=self.SECTIONS, prompt="Раздел", id="section_select", value=self.section),
            Label("Папка для временных файлов (Novelsbase):"),
            Input(value=self.target_dir, id="target_dir"),
            Label("Папка для готовых EPUB (будет создана автоматически):"),
            Input(value=self.output_books, id="output_books"),
            Horizontal(
                Button("Далее", id="next", variant="success"),
                Button("Назад", id="back", variant="default"),
                id="buttons"
            ),
            id="main"
        )
        yield Footer()

    def on_mount(self):
        self.query_one("#section_select").value = self.section

    @on(Select.Changed, "#section_select")
    def on_section_changed(self, event: Select.Changed):
        """Автоматически обновляем путь при изменении раздела"""
        new_section = event.value
        current_output = self.query_one("#output_books").value
        
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
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "next":
            target_dir = self.query_one("#target_dir").value
            output_books = self.query_one("#output_books").value
            section = self.query_one("#section_select").value
            
            if not target_dir or not output_books:
                self.app.notify("Пути не могут быть пустыми", severity="warning")
                return
            if not section:
                section = "Разные"

            try:
                os.makedirs(target_dir, exist_ok=True)
                # Создаём родительскую папку для output_books
                os.makedirs(os.path.dirname(output_books), exist_ok=True)
                self.app.notify(f"✅ Папка создана: {target_dir}", severity="information")
            except Exception as e:
                self.app.notify(f"❌ Ошибка создания папки: {e}", severity="error")
                return

            novel_id = add_novel(
                title=self.title,
                url=self.url,
                target_dir=target_dir,
                output_books=output_books,
                synopsis=self.synopsis,
                total_chapters=self.total_chapters,
                section=section
            )
            self.app.push_screen(NovelInfoScreen(novel_id))