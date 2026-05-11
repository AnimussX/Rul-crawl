from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Select, ListView, ListItem, Label
from textual import on
from gui.database import get_all_novels
from gui.screens.novel_info import NovelInfoScreen
from rich.text import Text

class NovelListScreen(Screen):
    SECTIONS = [
        ("Все", "Все"), ("Английские", "Английские"), ("Китайские", "Китайские"),
        ("Корейские", "Корейские"), ("Русские", "Русские"), ("Японские", "Японские"),
        ("(18+)", "(18+)"), ("Разные", "Разные"),
    ]

    def compose(self):
        yield Header()
        with Container(id="main"):
            # Группируем верхнюю панель, чтобы она не перекрывалась
            with Vertical(id="header_area"):
                yield Label("📚 Список новелл", id="title")
                yield Select(options=self.SECTIONS, prompt="Фильтр по разделу", id="section_filter", value="Все")
                with Horizontal(id="table_header_row"):
                    yield Label("Раздел", classes="col_sec")
                    yield Label("Название", classes="col_title")
            
            # Список новелл посередине
            yield ListView(id="novel_list")

            # Кнопки внизу
            with Horizontal(id="buttons"):
                yield Button("Загрузить", id="load", variant="success")
                yield Button("Назад", id="back", variant="default")
        yield Footer()

    def on_mount(self):
        self._refresh_list()

    def _refresh_list(self, section="Все"):
        list_view = self.query_one("#novel_list")
        
        # Получаем ширину экрана, чтобы знать, где резать текст
        # Вычитаем 20 (ширина колонки раздела + отступы), чтобы название влезло
        max_width = self.app.size.width - 20 

        with self.app.batch_update():
            list_view.clear()
            self.novel_ids = []
            novels = get_all_novels(section)

            if not novels:
                list_view.mount(ListItem(Label("Нет новелл")))
                return

            items = []
            for nid, title, sec, total in novels:
                display_sec = (sec if sec and sec != "Разные" else "-")[:12]
                
                # РУЧНАЯ ОБРЕЗКА: если название длиннее свободной ширины, 
                # режем его и добавляем троеточие. Это 100% защита от переноса.
                if len(title) > max_width:
                    display_title = title[:max_width-3] + "..."
                else:
                    display_title = title

                # Формируем одну строку. Теперь она гарантированно влезет в экран.
                row_text = f"[b cyan]{display_sec:<13}[/] {display_title}"
                
                items.append(ListItem(Label(row_text)))
                self.novel_ids.append(nid)
            
            list_view.mount(*items)

    @on(Select.Changed, "#section_filter")
    def on_section_changed(self, event: Select.Changed):
        selected = event.value if event.value != Select.BLANK else "Все"
        self._refresh_list(selected)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "load":
            list_view = self.query_one("#novel_list")
            idx = list_view.index
            if idx is not None and idx < len(self.novel_ids):
                self.app.push_screen(NovelInfoScreen(self.novel_ids[idx]))
            else:
                self.app.notify("Выберите новеллу из списка", severity="warning")
