from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer, Button, Label
from gui.screens.auth_settings import AuthSettingsScreen
from gui.screens.clean_dirs import CleanDirsScreen

class SettingsScreen(Screen):
    def compose(self):
        yield Header()
        yield Container(
            Label("⚙️ Настройки", id="title"),
            Button("🔐 Авторизация", id="auth", variant="primary"),
            Button("🧹 Очистить пустые папки", id="clean", variant="warning"),
            Button("◀️ Назад", id="back", variant="default"),
            id="settings_container"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "clean":
            self.app.push_screen(CleanDirsScreen())
        elif event.button.id == "auth":
            self.app.push_screen(AuthSettingsScreen())