from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer, Label, Input, Button
from scripts.auth import save_auth

class AuthSettingsScreen(Screen):
    def compose(self):
        yield Header()
        with Container(id="main"):
            yield Label("🔐 Настройки авторизации", id="title")
            yield Input(placeholder="Логин", id="login", value=self.app.LOGIN or "")
            yield Input(placeholder="Пароль", password=True, id="password", value="")
            yield Button("💾 Сохранить", id="save", variant="primary")
            yield Label("", id="status")
            yield Button("◀️ Назад", id="back", variant="default")
        yield Footer()

    def on_mount(self):
        if self.app.LOGIN and self.app.PASSWORD:
            self.query_one("#status").update("✅ Авторизация выполнена")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "save":
            login = self.query_one("#login").value
            password = self.query_one("#password").value
            if login and password:
                save_auth(login, password)
                self.app.LOGIN, self.app.PASSWORD = login, password
                self.query_one("#status").update("✅ Авторизация выполнена")
                self.query_one("#password").value = ""
            else:
                self.app.notify("Введите логин и пароль", severity="warning")