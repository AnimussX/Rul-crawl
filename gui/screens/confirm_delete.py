from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, Button

class ConfirmDeleteScreen(Screen):
    def __init__(self, novel_id: int, title: str):
        super().__init__()
        self.novel_id = novel_id
        self.title = title

    def compose(self):
        yield Header()
        yield Container(
            Label(f"Удалить новеллу «{self.title}»?", id="question"),
            Label("Выберите действие:", id="sub"),
            Horizontal(
                Button("Только запись", id="only_db", variant="warning"),
                Button("Запись и файлы", id="with_files", variant="error"),
                Button("Отмена", id="cancel", variant="primary"),
                id="buttons"
            ),
            id="dialog"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "only_db":
            from gui.database import delete_novel
            delete_novel(self.novel_id, delete_files=False)
            self.app.pop_screen()
            self._go_back_to_list()
        elif event.button.id == "with_files":
            from gui.database import delete_novel
            delete_novel(self.novel_id, delete_files=True)
            self.app.pop_screen()
            self._go_back_to_list()

    def _go_back_to_list(self):
        from gui.screens.novel_list import NovelListScreen
        while not isinstance(self.app.screen, NovelListScreen):
            self.app.pop_screen()