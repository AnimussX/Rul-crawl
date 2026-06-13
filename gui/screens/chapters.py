# gui/screens/chapters.py

import threading
from pathlib import Path
import requests
from textual.screen import Screen
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.widgets import Header, Footer, Label, Input, Button, Checkbox
from gui.crawler_utils import get_novel_info
from gui.database import get_novel, update_novel
from gui.screens.load import LoadScreen
from scripts.chapter_cache import ChapterCache


class ChaptersScreen(Screen):
    def __init__(self, url: str, novel_id: int):
        super().__init__()
        self.url = url
        self.novel_id = novel_id
        self.novel_data = None
        self.chapters = []
        self.checkboxes = []
        self.cached_mode = False

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
                yield Checkbox("Только собрать EPUB (без загрузки)", id="rebuild_check", value=False)
            with Vertical(id="nav_buttons"):
                with Horizontal():
                    yield Button("▲ В начало", id="scroll_start", variant="default")
                    yield Button("▼ В конец", id="scroll_end", variant="default")
            with Vertical(id="action_buttons"):
                with Horizontal():
                    yield Button("Выбрать все", id="select_all", variant="primary")
                    yield Button("Снять все", id="deselect_all", variant="primary")
                with Horizontal():
                    yield Button("🔄 Обновить список", id="refresh_chapters", variant="default")
                    yield Button("Загрузить выбранные", id="load", variant="success", disabled=True)
                    yield Button("Назад", id="back", variant="default")
        yield Footer()

    def on_mount(self):
        self.novel_data = get_novel(self.novel_id)
        if not self.novel_data:
            self.query_one("#status").update("❌ Ошибка загрузки данных новеллы")
            return

        cache = ChapterCache(Path(self.novel_data["target_dir"]))
        cached = cache.load_chapters_list()
        if cached:
            self._display_chapters(cached, cached_mode=True)
            self.query_one("#status").update(f"📚 Показаны кэшированные главы ({len(cached)}). Проверка обновлений...")
        else:
            self.query_one("#status").update("Загрузка списка глав...")

        threading.Thread(target=self._fetch_chapters_background, daemon=True).start()

    def _fetch_chapters_background(self):
        try:
            _, _, chapters = get_novel_info(self.url, self.app.LOGIN, self.app.PASSWORD)
            self.app.call_from_thread(self._on_fresh_chapters, chapters)
        except requests.exceptions.ConnectionError:
            self.app.call_from_thread(self._on_network_error)
        except Exception as e:
            self.app.call_from_thread(self._on_chapters_error, str(e))

    def _on_fresh_chapters(self, chapters):
        cache = ChapterCache(Path(self.novel_data["target_dir"]))
        cache.save_chapters_list(chapters)

        current_total = self.novel_data.get('total_chapters', 0)
        if len(chapters) != current_total:
            update_novel(self.novel_id, total_chapters=len(chapters))
            self.novel_data['total_chapters'] = len(chapters)
            self.app.notify(f"📚 Обновлено количество глав: {len(chapters)}", severity="information")

        if self.cached_mode or len(self.chapters) != len(chapters):
            self._display_chapters(chapters, cached_mode=False)
            self.query_one("#status").update(f"📚 Найдено глав: {len(chapters)} (обновлено)")
        else:
            self.query_one("#status").update(f"📚 Найдено глав: {len(chapters)} (актуально)")

    def _on_network_error(self):
        self.query_one("#status").update("⚠️ Нет подключения к интернету, показан кэшированный список")
        self.app.notify("Нет доступа к сети", severity="warning")

    def _on_chapters_error(self, error_msg: str):
        if self.cached_mode:
            self.query_one("#status").update(f"⚠️ Не удалось обновить список: {error_msg[:100]}. Показан кэш.")
        else:
            self.query_one("#status").update(f"❌ Ошибка: {error_msg[:100]}")

    def _display_chapters(self, chapters, cached_mode=False):
        self.chapters = chapters
        self.cached_mode = cached_mode
        container = self.query_one("#chapters_list")
        # Удаляем все существующие виджеты, чтобы избежать конфликта ID
        for child in list(container.children):
            child.remove()

        self.checkboxes = []
        for i, ch in enumerate(chapters):
            title = ch.get('title', f'Глава {i+1}')
            # Не задаём ID явно, Textual сгенерирует уникальный
            cb = Checkbox(label=f"{i+1}. {title}")
            container.mount(cb)
            self.checkboxes.append(cb)

        self.query_one("#load").disabled = False
        if cached_mode:
            self.query_one("#status").update(f"📚 Показаны кэшированные главы ({len(chapters)}).")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "refresh_chapters":
            self.query_one("#status").update("Обновление списка глав...")
            threading.Thread(target=self._fetch_chapters_background, daemon=True).start()
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
            rebuild_only = self.query_one("#rebuild_check").value

            self.app.push_screen(LoadScreen(
                self.novel_id,
                chapters_spec,
                force=force,
                ignore_image_errors=ignore_images,
                ignore_errors=ignore_errors,
                rebuild_only=rebuild_only
            ))
        elif event.button.id == "scroll_start":
            scrollable = self.query_one("#chapters_list")
            scrollable.scroll_to(0, animate=False)
        elif event.button.id == "scroll_end":
            scrollable = self.query_one("#chapters_list")
            scrollable.scroll_to(0, scrollable.max_scroll_y, animate=False)