from textual.screen import Screen
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.widgets import Header, Footer, Label, Input, Button, Checkbox
from textual import work
from gui.crawler_utils import get_novel_info
from gui.screens.load import LoadScreen

class ChaptersScreen(Screen):
    def __init__(self, url: str, novel_id: int):
        super().__init__()
        self.url = url
        self.novel_id = novel_id
        self.chapters = []
        self.checkboxes = []

    def compose(self):
        yield Header()
        with Container(id="main", classes="chapters-screen"):
            yield Label("Загрузка списка глав...", id="status")
            with ScrollableContainer(id="chapters_list"):
                pass
            with Horizontal():
                yield Input(placeholder="С", id="range_from", type="integer", classes="range-input")
                yield Input(placeholder="По", id="range_to", type="integer", classes="range-input")
                yield Button("OK", id="select_range", variant="primary", classes="small-button")
            with Vertical(id="options"):
                yield Checkbox("Принудительно перезагрузить все главы", id="force_check", value=False)
                yield Checkbox("Пропускать ошибки изображений", id="ignore_images_check", value=False)
                yield Checkbox("Игнорировать ошибки загрузки глав", id="ignore_errors_check", value=False)
            # Новый блок с кнопками навигации
            with Vertical(id="nav_buttons"):
                with Horizontal():
                    yield Button("▲ В начало", id="scroll_start", variant="default")
                    yield Button("▼ В конец", id="scroll_end", variant="default")
            with Vertical(id="action_buttons"):
                with Horizontal():
                    yield Button("Выбрать все", id="select_all", variant="primary")
                    yield Button("Снять все", id="deselect_all", variant="primary")
                with Horizontal():
                    yield Button("Загрузить выбранные", id="load", variant="success", disabled=True)
                    yield Button("Назад", id="back", variant="default")
        yield Footer()

    def on_mount(self):
        self._fetch_chapters()

    @work(thread=True)
    def _fetch_chapters(self):
        try:
            title, synopsis, chapters = get_novel_info(self.url, self.app.LOGIN, self.app.PASSWORD)
            self.app.call_from_thread(self._on_chapters_fetched, chapters)
        except Exception as e:
            self.app.call_from_thread(self._on_chapters_error, str(e))

    def _on_chapters_error(self, error_msg: str):
        self.query_one("#status").update(f"❌ Ошибка: {error_msg[:100]}")

    def _on_chapters_fetched(self, chapters):
        self.chapters = chapters
        status = self.query_one("#status")
        if not chapters:
            status.update("❌ Список глав пуст")
            return
        status.update(f"📚 Найдено глав: {len(chapters)}")

        container = self.query_one("#chapters_list")
        for child in list(container.children):
            child.remove()

        self.checkboxes = []
        for i, ch in enumerate(chapters):
            if isinstance(ch, dict):
                title = ch.get('title', f'Глава {i+1}')
            else:
                title = getattr(ch, 'title', f'Глава {i+1}')
            cb = Checkbox(label=f"{i+1}. {title}", id=f"ch_{i}")
            container.mount(cb)
            self.checkboxes.append(cb)

        self.query_one("#load").disabled = False

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "select_all":
            for cb in self.checkboxes:
                cb.value = True
        elif event.button.id == "deselect_all":
            for cb in self.checkboxes:
                cb.value = False
        elif event.button.id == "select_range":
            from_ = self.query_one("#range_from").value
            to_ = self.query_one("#range_to").value
            if from_.isdigit() and to_.isdigit():
                from_ = int(from_)
                to_ = int(to_)
                for i, cb in enumerate(self.checkboxes):
                    idx = i + 1
                    if from_ <= idx <= to_:
                        cb.value = True
                    else:
                        cb.value = False
            else:
                self.app.notify("Введите корректные числа", severity="warning")
        elif event.button.id == "load":
            selected = [i+1 for i, cb in enumerate(self.checkboxes) if cb.value]
            if not selected:
                self.app.notify("Не выбрано ни одной главы", severity="warning")
                return
            selected.sort()
            ranges = []
            start = selected[0]
            end = start
            for i in range(1, len(selected)):
                if selected[i] == end + 1:
                    end = selected[i]
                else:
                    if start == end:
                        ranges.append(str(start))
                    else:
                        ranges.append(f"{start}-{end}")
                    start = selected[i]
                    end = start
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            chapters_spec = ",".join(ranges)

            force = self.query_one("#force_check").value
            ignore_images = self.query_one("#ignore_images_check").value
            ignore_errors = self.query_one("#ignore_errors_check").value

            self.app.push_screen(LoadScreen(
                self.novel_id,
                chapters_spec,
                force=force,
                ignore_image_errors=ignore_images,
                ignore_errors=ignore_errors
            ))
        elif event.button.id == "scroll_start":
            scrollable = self.query_one("#chapters_list")
            scrollable.scroll_to(0, animate=False)
        elif event.button.id == "scroll_end":
            scrollable = self.query_one("#chapters_list")
            scrollable.scroll_to(0, scrollable.max_scroll_y, animate=False)