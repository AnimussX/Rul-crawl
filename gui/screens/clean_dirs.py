import os
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, Button, ListView, ListItem
from gui.config import NOVELS_BASE

class CleanDirsScreen(Screen):
    def compose(self):
        yield Header()
        yield Container(
            Label("Поиск пустых папок...", id="status"),
            ListView(id="list"),
            Horizontal(
                Button("Удалить всё", id="delete", variant="error", disabled=True),
                Button("Назад", id="back", variant="default"),
                id="buttons"
            ),
            id="main"
        )
        yield Footer()

    def on_mount(self):
        empty = []
        for base in [NOVELS_BASE]:
            if os.path.isdir(base):
                for root, dirs, files in os.walk(base):
                    if not files and not dirs:
                        empty.append(root)
        self.empty_dirs = empty
        list_view = self.query_one("#list")
        if not empty:
            list_view.append(ListItem(Label("Пустых папок не найдено.")))
        else:
            for d in empty:
                list_view.append(ListItem(Label(d)))
            self.query_one("#delete").disabled = False
        self.query_one("#status").update(f"Найдено пустых папок: {len(empty)}")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "delete":
            for d in self.empty_dirs:
                try:
                    os.rmdir(d)
                except:
                    pass
            self.query_one("#status").update(f"Удалено папок: {len(self.empty_dirs)}")
            self.query_one("#delete").disabled = True
            list_view = self.query_one("#list")
            list_view.clear()
            list_view.append(ListItem(Label("Готово.")))