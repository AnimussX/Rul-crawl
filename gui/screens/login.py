from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer, Label, Input, Button
from scripts.auth import save_auth

class LoginScreen(Screen):
    def compose(self):
        yield Header()
        yield Container(
            Label("Введите логин и пароль от Rulate", id="title"),
            Input(placeholder="Логин", id="login"),
            Input(placeholder="Пароль", password=True, id="password"),
            Button("Сохранить", variant="primary", id="save"),
            id="dialog"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save":
            login = self.query_one("#login").value
            password = self.query_one("#password").value
            if login and password:
                save_auth(login, password)
                self.app.LOGIN, self.app.PASSWORD = login, password
                self.app.pop_screen()
            else:
                self.query_one("#title").update("Оба поля должны быть заполнены!")