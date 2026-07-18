# gui/screens/cloudflare_pause.py

import threading
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Label, Button


class CloudflarePauseScreen(ModalScreen):
    """Модальное окно, информирующее о блокировке Cloudflare (используется во всех экранах)."""

    def __init__(self, cloudflare_event: threading.Event):
        super().__init__()
        self.cloudflare_event = cloudflare_event

    def compose(self):
        with Container(id="dialog"):
            yield Label("⚠️ Сработала защита Cloudflare", id="dialog_title")
            yield Label(
                "Откройте в обычном браузере сайт ranobes.com,\n"
                "пройдите проверку (капчу), затем нажмите «Продолжить».",
                id="dialog_message"
            )
            with Horizontal(id="dialog_buttons"):
                yield Button("Продолжить", id="cloudflare_continue", variant="success")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cloudflare_continue":
            self.cloudflare_event.set()
            self.dismiss()