from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer, Label, Input, Button
from scripts.auth import save_auth, save_ranobes_auth

class AuthSettingsScreen(Screen):
    def compose(self):
        yield Header()
        with Container(id="main"):
            yield Label("🔐 Настройки авторизации", id="title")
            yield Label("Общие (Rulate):")                     # без id
            yield Input(placeholder="Логин (Rulate)", id="login", value=self.app.LOGIN or "")
            yield Input(placeholder="Пароль (Rulate)", password=True, id="password", value="")
            yield Label("🔹 Для Ranobes.com:")                # без id
            yield Input(placeholder="Логин (Ranobes)", id="ranobes_login",
                        value=self.app.RANOBES_LOGIN or "")
            yield Input(placeholder="Пароль (Ranobes)", password=True, id="ranobes_password",
                        value="")
            yield Button("💾 Сохранить всё", id="save", variant="primary")
            yield Label("", id="status")
            yield Button("◀️ Назад", id="back", variant="default")
        yield Footer()

    def on_mount(self):
        if self.app.LOGIN and self.app.PASSWORD:
            self.query_one("#status").update("✅ Общая авторизация выполнена")
        if self.app.RANOBES_LOGIN and self.app.RANOBES_PASSWORD:
            current = self.query_one("#status").render()
            self.query_one("#status").update(current + " | ✅ Ranobes авторизация выполнена")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "save":
            login = self.query_one("#login").value
            password = self.query_one("#password").value
            ranobes_login = self.query_one("#ranobes_login").value
            ranobes_password = self.query_one("#ranobes_password").value

            if login and password:
                save_auth(login, password)
                self.app.LOGIN, self.app.PASSWORD = login, password
            if ranobes_login and ranobes_password:
                save_ranobes_auth(ranobes_login, ranobes_password)
                self.app.RANOBES_LOGIN, self.app.RANOBES_PASSWORD = ranobes_login, ranobes_password

            status = []
            if self.app.LOGIN:
                status.append("✅ Общая авторизация сохранена")
            if self.app.RANOBES_LOGIN:
                status.append("✅ Ranobes авторизация сохранена")
            self.query_one("#status").update(" | ".join(status) if status else "❌ Введите данные")