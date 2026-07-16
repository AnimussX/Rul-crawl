# gui/screens/novel_list.py

from textual import on
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Button,
    Select,
    Label,
    DataTable,
    Input,
)
import threading

from gui.database import get_all_novels
from gui.screens.novel_info import NovelInfoScreen


class NovelListScreen(Screen):
    """Экран списка новелл на базе DataTable с поиском и асинхронной загрузкой."""

    CSS_PATH = "../styles/novel_list.tcss"

    SECTIONS = [
        ("Все", "Все"),
        ("Завершённые", "Завершённые"),
        ("Английские", "Английские"),
        ("Китайские", "Китайские"),
        ("Корейские", "Корейские"),
        ("Русские", "Русские"),
        ("Японские", "Японские"),
        ("(18+)", "(18+)"),
        ("Разные", "Разные"),
    ]

    BINDINGS = [
        ("enter", "open_selected", "Открыть"),
        ("/", "focus_search", "Поиск"),
    ]


    def __init__(self):
        super().__init__()
        self.novel_ids: list[int] = []
        self._search_timer = None

    def compose(self):
        yield Header()
        with Container(id="main"):
            with Vertical(id="header_area"):
                yield Label("📚 Список новелл", id="title")
                with Horizontal(id="filters"):
                    yield Select(
                        options=self.SECTIONS,
                        prompt="Раздел",
                        id="section_filter",
                        value="Все",
                    )
                    yield Input(
                        placeholder="🔍 Поиск по названию...",
                        id="search_input",
                    )
                yield Label("", id="status_bar")

            yield DataTable(
                id="novel_table",
                cursor_type="row",
                zebra_stripes=True,
            )

            with Horizontal(id="buttons"):
                yield Button("Загрузить", id="load", variant="success")
                yield Button("Назад", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#novel_table", DataTable)
        table.add_column("Раздел", width=15)
        table.add_column("Название")
        table.add_column("Глав", width=8)
        table.cursor_type = "row"
        self._refresh_table()

    def _refresh_table(self, section: str = "Все", search: str = "") -> None:
        """Запускает фоновую загрузку данных."""
        threading.Thread(
            target=self._load_data,
            args=(section, search),
            daemon=True
        ).start()

    def _load_data(self, section: str, search: str) -> None:
        """Загружает данные в фоне и обновляет таблицу."""
        try:
            # Определяем параметры для get_all_novels
            if section == "Завершённые":
                # Показываем только завершённые + заброшенные автором
                novels = get_all_novels(status="Завершённые")
            elif section == "Все":
                # Все, кроме завершённых и заброшенных автором
                novels = get_all_novels(exclude_completed=True)
            else:
                # Обычный раздел (без исключения завершённых)
                novels = get_all_novels(section=section)
            if search.strip():
                search_lower = search.strip().lower()
                novels = [n for n in novels if search_lower in n[1].lower()]
            self.app.call_from_thread(self._update_table, novels)
        except Exception as e:
            self.app.call_from_thread(self._on_load_error, str(e))

    def _update_table(self, novels: list[tuple]) -> None:
        """Обновляет таблицу в основном потоке."""
        table = self.query_one("#novel_table", DataTable)
        self.novel_ids.clear()
        with self.app.batch_update():
            table.clear()
            for novel_id, title, sec, total, status in novels:
                display_sec = sec if sec and sec != "Разные" else "-"
                # Для завершённых и заброшенных автором добавим пометку
                if status in ("завершено", "заброшено автором"):
                    title_display = f"{title} ✅"
                else:
                    title_display = title
                table.add_row(display_sec, title_display, str(total))
                self.novel_ids.append(novel_id)
        status_bar = self.query_one("#status_bar", Label)
        status_bar.update(f"📖 Найдено новелл: {len(novels)}")

    def _on_load_error(self, error: str) -> None:
        self.query_one("#status_bar", Label).update(f"❌ Ошибка: {error}")

    @on(Select.Changed, "#section_filter")
    def on_section_changed(self, event: Select.Changed) -> None:
        section = event.value if event.value != Select.BLANK else "Все"
        search = self.query_one("#search_input", Input).value
        self._refresh_table(section, search)

    @on(Input.Submitted, "#search_input")
    @on(Input.Changed, "#search_input")
    def on_search_changed(self, event: Input.Changed) -> None:
        if self._search_timer:
            self._search_timer.cancel()
        self._search_timer = self.set_timer(
            0.5,
            lambda: self._refresh_table(
                self.query_one("#section_filter", Select).value or "Все",
                event.value
            )
        )

    @on(DataTable.RowSelected, "#novel_table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        self._open_current()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "load":
            self._open_current()

    def action_open_selected(self) -> None:
        self._open_current()

    def action_focus_search(self) -> None:
        self.query_one("#search_input", Input).focus()

    def _open_current(self) -> None:
        table = self.query_one("#novel_table", DataTable)
        row_index = table.cursor_row
        if row_index is None or not (0 <= row_index < len(self.novel_ids)):
            self.app.notify("Выберите новеллу из списка", severity="warning")
            return
        self.app.push_screen(NovelInfoScreen(self.novel_ids[row_index]))