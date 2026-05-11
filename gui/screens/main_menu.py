from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer, Button
from gui.screens.novel_list import NovelListScreen
from gui.screens.new_novel import NewNovelScreen
from gui.screens.settings import SettingsScreen

class MainMenuScreen(Screen):
    def compose(self):
        yield Header()
        yield Container(
            Button("📚 Список новелл", id="list", variant="primary"),
            Button("➕ Создать новую запись", id="new", variant="success"),
            Button("⚙️ Настройки", id="settings", variant="default"),
            Button("🚪 Выход", id="exit", variant="error"),
            id="menu"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "list":
            self.app.push_screen(NovelListScreen())
        elif event.button.id == "new":
            self.app.push_screen(NewNovelScreen())
        elif event.button.id == "settings":
            self.app.push_screen(SettingsScreen())
        elif event.button.id == "exit":
            self.app.exit()