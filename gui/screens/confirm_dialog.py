# gui/screens/confirm_dialog.py

from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Label, Button


class ConfirmDialog(ModalScreen):
    """Модальное окно подтверждения действия."""

    CSS_PATH = "../styles/confirm_dialog.tcss"

    def __init__(self, message: str, on_confirm):
        super().__init__()
        self.message = message
        self.on_confirm = on_confirm

    def compose(self):
        with Container(id="dialog"):
            yield Label(self.message, id="dialog_message")
            with Horizontal(id="dialog_buttons"):
                yield Button("Да", id="dialog_yes", variant="error")
                yield Button("Нет", id="dialog_no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "dialog_yes":
            self.on_confirm()
        self.dismiss()