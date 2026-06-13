from textual.screen import Screen
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Header, Footer, Label, TextArea, Button
from gui.database import get_novel
from gui.screens.chapters import ChaptersScreen
from gui.screens.edit_novel import EditNovelScreen
from gui.screens.confirm_delete import ConfirmDeleteScreen
from gui.utils import html_to_text


class NovelInfoScreen(Screen):
    def __init__(self, novel_id: int):
        super().__init__()
        self.novel_id = novel_id
        self.novel_data = None

    def compose(self):
        yield Header()
        yield Container(
            Label("Загрузка информации...", id="status"),
            ScrollableContainer(
                Label("", id="title_display"),
                TextArea("", id="synopsis_display", read_only=True),
                id="info_container"
            ),
            Horizontal(
                Button("Загрузить", id="load", variant="success"),
                Button("Редактировать", id="edit", variant="primary"),
                Button("Удалить", id="delete", variant="error"),
                Button("Назад", id="back", variant="default"),
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
        self.query_one("#status").update("")
        self.query_one("#title_display").update(self.novel_data['title'])

        # Преобразуем HTML описание в читаемый текст
        raw_synopsis = self.novel_data['synopsis'] or "Описание отсутствует."
        plain_text = html_to_text(raw_synopsis)
        self.query_one("#synopsis_display").text = plain_text

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "load":
            self.app.push_screen(ChaptersScreen(self.novel_data['url'], self.novel_id))
        elif event.button.id == "edit":
            self.app.push_screen(EditNovelScreen(self.novel_id))
        elif event.button.id == "delete":
            self.app.push_screen(ConfirmDeleteScreen(self.novel_id, self.novel_data['title']))