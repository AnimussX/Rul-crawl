# gui/screens/chapters.py

import threading
from pathlib import Path
import requests
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Label, Input, Button, Checkbox
from gui.database import get_novel, update_novel
from gui.screens.load import LoadScreen
from gui.widgets.virtual_chapter_list import VirtualChapterList
from scripts.novel_metadata import get_novel_metadata
from scripts.crawler_factory import create_crawler
from scripts.metadata import load_metadata


class ChaptersScreen(Screen):
    CSS_PATH = "../styles/chapters.tcss"

    def __init__(self, url: str, novel_id: int):
        super().__init__()
        self.url = url
        self.novel_id = novel_id
        self.novel_data = None
        self.chapters = []
        self.virtual_list = None
        self.updating = False

    def compose(self):
        yield Header()
        with Container(id="main", classes="chapters-screen"):
            yield Label("Загрузка списка глав...", id="status")
            yield VirtualChapterList(
                on_selection_changed=self._update_load_button_status,
                id="virtual_list"
            )

            with Horizontal(id="bookmark_row"):
                yield Label("📌 Закладка (глава):", id="bookmark_label")
                self.bookmark_input = Input(
                    value="0",
                    id="bookmark_input",
                    type="integer",
                    classes="bookmark-input"
                    )
                yield self.bookmark_input
                yield Button("Сохранить", id="save_bookmark", variant="primary")

            # Внутри вашего метода compose():
            with Horizontal(id="options_row"):  # Корневой контейнер
                
                # Левая колонка: чекбоксы
                with Vertical(id="options"):  # Убрали некорректный аргумент expand=True
                    yield Checkbox("Принудительно перезагрузить все главы", id="force_check", value=False)
                    yield Checkbox("Пропускать ошибки изображений", id="ignore_images_check", value=False)
                    yield Checkbox("Игнорировать ошибки загрузки глав", id="ignore_errors_check", value=False)
                    yield Checkbox("Только собрать EPUB (без загрузки)", id="rebuild_check", value=False)
            
                # Правая колонка: диапазон и кнопка
                with Vertical(id="range_selector"):
                    with Horizontal(id="inputs_row"):  # Добавили ID для точечной настройки ширины
                        yield Input(placeholder="С", id="range_from", type="integer", classes="range-input")
                        yield Input(placeholder="По", id="range_to", type="integer", classes="range-input")
                    yield Button("OK", id="select_range", variant="primary", classes="small-button")




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
        self.virtual_list = self.query_one("#virtual_list")
        self.novel_data = get_novel(self.novel_id)
        if not self.novel_data:
            self.query_one("#status").update("❌ Ошибка загрузки данных новеллы")
            return

        last_read = self.novel_data.get('last_read_chapter', 0)
        self.bookmark_input.value = str(last_read)

        # Пробуем загрузить список глав из единого кэша (metadata.json)
        data_dir = Path(self.novel_data["target_dir"])
        meta = load_metadata(data_dir)
        if meta and "chapters" in meta:
            self.chapters = meta["chapters"]
            self._display_chapters(self.chapters, cached_mode=True)
            self.query_one("#status").update(
                f"📚 Показаны главы из кэша ({len(self.chapters)}). "
                f"Нажмите «Обновить» для проверки новых."
            )
        else:
            self.query_one("#status").update("Нет кэша, загрузка с сайта...")
            threading.Thread(target=self._fetch_chapters_background, args=(True,), daemon=True).start()

    def _fetch_chapters_background(self, force=False):
        if self.updating:
            return
        self.updating = True
        try:
            data_dir = Path(self.novel_data["target_dir"])
            # Тип краулера определяется по домену self.url (Rulate/Ranobes/...)
            crawler = create_crawler(url=self.url, login=self.app.LOGIN, password=self.app.PASSWORD)
            _, _, _, _, chapters = get_novel_metadata(
                url=self.url,
                crawler=crawler,
                data_dir=data_dir,
                force=force,            # если force=True, лезем на сайт и обновляем metadata.json
                callbacks=None
            )
            self.app.call_from_thread(self._on_fresh_chapters, chapters)
        except requests.exceptions.ConnectionError:
            self.app.call_from_thread(self._on_network_error)
        except Exception as e:
            self.app.call_from_thread(self._on_chapters_error, str(e))
        finally:
            self.updating = False

    def _on_fresh_chapters(self, chapters):
        current_total = self.novel_data.get('total_chapters', 0)
        if len(chapters) != current_total:
            update_novel(self.novel_id, total_chapters=len(chapters))
            self.novel_data['total_chapters'] = len(chapters)
            self.app.notify(f"📚 Обновлено количество глав: {len(chapters)}", severity="information")

        self.chapters = chapters
        self._display_chapters(chapters, cached_mode=False)
        self.query_one("#status").update(f"📚 Найдено глав: {len(chapters)} (обновлено)")

    def _on_network_error(self):
        self.query_one("#status").update("⚠️ Нет подключения к интернету, показан кэшированный список")
        self.app.notify("Нет доступа к сети", severity="warning")

    def _on_chapters_error(self, error_msg: str):
        self.query_one("#status").update(f"❌ Ошибка: {error_msg[:100]}")
        self.app.notify(f"Ошибка загрузки: {error_msg[:100]}", severity="error")

    def _display_chapters(self, chapters, cached_mode=False):
        self.virtual_list.update_data(chapters)
        if cached_mode:
            self.query_one("#status").update(
                f"📚 Показаны главы из кэша ({len(chapters)}). "
                f"Нажмите «Обновить» для проверки новых."
            )
        else:
            self.query_one("#status").update(f"✅ Список глав обновлен ({len(chapters)}).")
        self._update_load_button_status()

    def _update_load_button_status(self):
        selected = self.virtual_list.get_selected_indices()
        load_btn = self.query_one("#load", Button)
        load_btn.disabled = len(selected) == 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "save_bookmark":
            try:
                val = int(self.bookmark_input.value)
                if val < 0:
                    raise ValueError
                update_novel(self.novel_id, last_read_chapter=val)
                self.novel_data['last_read_chapter'] = val
                self.app.notify(f"✅ Закладка сохранена: глава {val}", severity="information")
            except ValueError:
                self.app.notify("⚠️ Введите корректный номер главы (целое число >= 0)", severity="warning")

        elif button_id == "select_all":
            self.virtual_list.select_all()
        elif button_id == "deselect_all":
            self.virtual_list.deselect_all()
        elif button_id == "scroll_start":
            self.virtual_list.scroll_to_top()
        elif button_id == "scroll_end":
            self.virtual_list.scroll_to_bottom()
        elif button_id == "refresh_chapters":
            self.query_one("#status").update("🔄 Принудительное обновление списка...")
            threading.Thread(target=self._fetch_chapters_background, args=(True,), daemon=True).start()
        elif button_id == "select_range":
            try:
                from_val = int(self.query_one("#range_from", Input).value)
                to_val = int(self.query_one("#range_to", Input).value)
                self.virtual_list.set_range(from_val, to_val)
            except ValueError:
                self.query_one("#status").update("⚠️ Введите корректные числа в диапазон!")
        elif button_id == "back":
            self.app.pop_screen()
        elif button_id == "load":
            selected_indices = self.virtual_list.get_selected_indices()
            if not selected_indices:
                self.app.notify("Не выбрано ни одной главы", severity="warning")
                return
            selected_indices.sort()
            ranges = []
            start = selected_indices[0]
            end = start
            for i in range(1, len(selected_indices)):
                if selected_indices[i] == end + 1:
                    end = selected_indices[i]
                else:
                    if start == end:
                        ranges.append(str(start))
                    else:
                        ranges.append(f"{start}-{end}")
                    start = selected_indices[i]
                    end = start
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            chapters_spec = ",".join(ranges)

            force = self.query_one("#force_check", Checkbox).value
            ignore_img = self.query_one("#ignore_images_check", Checkbox).value
            ignore_err = self.query_one("#ignore_errors_check", Checkbox).value
            rebuild = self.query_one("#rebuild_check", Checkbox).value

            self.app.push_screen(
                LoadScreen(
                    novel_id=self.novel_id,
                    chapters_spec=chapters_spec,
                    force=force,
                    ignore_image_errors=ignore_img,
                    ignore_errors=ignore_err,
                    rebuild_only=rebuild
                )
            )
