#!/data/data/com.termux/files/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from textual.app import App
from textual.binding import Binding

from scripts.auth import load_auth
from gui.database import init_db
from gui.screens.login import LoginScreen
from gui.screens.main_menu import MainMenuScreen

class RulateCrawlerTUI(App):
    TITLE = "Rulate Crawler"
    
    CSS = """
    Screen {
        align: center middle;
    }

    #main {
        width: 100%;
        height: 100%;
        layout: vertical;
        padding: 0;
    }

    /* ВЕРХНЯЯ ФИКСИРОВАННАЯ ЗОНА */
    #header_area {
        dock: top;
        width: 100%;
        height: auto;
        background: $surface;
        border-bottom: solid $primary;
    }

    #title {
        width: 100%;
        height: 3;
        content-align: center middle;
        background: $primary;
        color: white;
        text-style: bold;
    }

    /* Увеличиваем размер селекта для сенсорного экрана */
    #section_filter {
        width: 100%;
        height: 4;
        margin: 0;
        border: none;
        background: $surface;
        content-align: left middle;
        padding: 0 1;
    }

    /* Выпадающий список селекта – крупные элементы */
    Select > .select-options {
        background: $surface;
        border: solid $primary;
        max-height: 60vh;
    }

    Select > .select-options > .option {
        height: 4;
        padding: 0 2;
        border-bottom: solid $primary 20%;
        text-style: bold;
    }

    Select > .select-options > .option:hover {
        background: $accent;
    }

    Select > .select-options > .option.selected {
        background: $accent 50%;
    }

    #table_header_row {
        width: 100%;
        height: 3;
        background: $boost;
        align: left middle;
    }

    /* НИЖНЯЯ ФИКСИРОВАННАЯ ЗОНА */
    #buttons {
        dock: bottom;
        width: 100%;
        height: 7;
        layout: horizontal;
        background: $surface;
        border-top: solid $primary;
        align: center middle;
        padding: 0 1;
    }

    #buttons Button {
        width: 1fr;
        height: 4;
        margin: 0 1;
        text-style: bold;
        border: tall white;
    }

    /* СПИСОК: Занимает всё пространство посередине */
    #novel_list {
        height: 1fr;
        background: $surface;
        overflow-y: scroll;
        border: none;
    }

    /* Крупные строки списка */
    /* Стиль для Label внутри строки списка */
    #novel_list ListItem Label {
        width: 100%;
        height: 100%;
        content-align: left middle;
        padding: 0 1;
    }

    #novel_list ListItem {
        height: 4;
        border-bottom: solid $primary 20%;
    }

    .col_sec {
        width: 15;
        padding: 0 1;
        text-style: bold;
        color: $warning;
    }

    .col_title {
        width: 1fr;
        padding: 0 1;
    }

    #novel_list ListItem:focus {
        background: $accent 30%;
    }

    /* Стили для других экранов */
    #menu, #settings_container {
        width: 80;
        max-width: 100%;
        height: auto;
        border: solid $primary;
        padding: 1;
        align: center middle;
    }

    #menu Button {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    /* Chapters screen – на весь экран */
    .chapters-screen {
        width: 100%;
        height: 100%;
        padding: 0;
    }

    .chapters-screen #main {
        width: 100%;
        max-width: 100%;
        border: solid $primary;
        padding: 0 1;
        margin: 0;
    }

    .chapters-screen #chapters_list {
        height: 1fr;
        border: solid $secondary;
        margin: 0 0 1 0;
    }

    .chapters-screen #options {
        margin: 0 0 1 0;
        height: auto;
    }

    .chapters-screen #options Checkbox {
        padding: 0;
        margin: 0;
        height: auto;
    }

    .chapters-screen #action_buttons {
        margin: 0;
        height: auto;
    }

    .chapters-screen #action_buttons Horizontal {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        align: center middle;
    }

    .chapters-screen #action_buttons Button {
        width: 1fr;
        margin: 0 1;
        min-width: 10;
        padding: 0 1;
        height: 3;
    }

    /* Увеличиваем поля ввода и кнопку OK */
    .chapters-screen .range-input {
        width: 8;           /* шире */
        height: 3;          /* выше */
        margin: 0 1;
        padding: 0 1;
        background: $surface;
        border: solid $primary;
        color: $text;
    }

    .chapters-screen .range-input:focus {
        border: solid $accent;
        background: $boost;
    }

    .chapters-screen #select_range {
        width: 8;
        margin: 0;
        height: 3;
    }
    /* Кнопки навигации по списку глав */
    .chapters-screen #nav_buttons {
        margin: 0 0 1 0;
        height: auto;
    }
    .chapters-screen #nav_buttons Horizontal {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        align: center middle;
    }
    .chapters-screen #nav_buttons Button {
        width: 1fr;
        margin: 0 1;
        min-width: 10;
        padding: 0 1;
        height: 3;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Выход"),
    ]

    def __init__(self):
        super().__init__()
        self.LOGIN, self.PASSWORD = load_auth()

    def on_mount(self):
        init_db()
        if not self.LOGIN or not self.PASSWORD:
            self.push_screen(LoginScreen())
        else:
            self.push_screen(MainMenuScreen())

if __name__ == "__main__":
    app = RulateCrawlerTUI()
    app.run()