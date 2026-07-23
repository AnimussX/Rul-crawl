# gui/screens/new_novel.py

import os
import re
import threading

from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, Input, Button, Select, TextArea
from textual import on

from scripts.paths import NOVELS_BASE, NOVELS_DIR
from gui.database import STATUSES
from gui.constants import SECTIONS, SOURCE_LABELS, build_output_path
from scripts.transliterate import slugify
from gui.screens.confirm_paths import ConfirmPathsScreen


class CloudflarePauseScreen(ModalScreen):
    """Модальное окно для ручного обхода Cloudflare."""

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


class NewNovelScreen(Screen):
    SECTIONS = SECTIONS
    STATUS_OPTIONS = [(s, s) for s in STATUSES]

    def compose(self):
        yield Header()
        with Container(id="form"):
            yield Label("Создание новой записи", id="title")
            yield Input(placeholder="Ссылка на новеллу", id="url")
            yield Label("", id="source_label")
            yield Button("Получить информацию", id="fetch", variant="primary")
            yield Input(placeholder="Название", id="title_input")
            yield Select(options=self.SECTIONS, prompt="Выберите раздел", id="section_select")
            yield Select(options=self.STATUS_OPTIONS, prompt="Статус", id="status_select", value=STATUSES[0])
            with Horizontal(id="buttons"):
                yield Button("Далее", id="next", variant="success", disabled=True)
                yield Button("Отмена", id="cancel", variant="default")
            yield Label("📋 Лог выполнения:", id="log_label")
            yield TextArea(id="log_output", read_only=True, classes="log-area")
        yield Footer()

    def on_mount(self):
        self.query_one("#section_select").value = "Разные"
        self.query_one("#status_select").value = "в работе"
        self.source = None
        self.cloudflare_event = threading.Event()
        self._log("Готов к вводу URL")

    def _log(self, message: str):
        try:
            log_widget = self.query_one("#log_output", TextArea)
            log_widget.insert(message + "\n")
            log_widget.scroll_end(animate=False)
        except Exception:
            pass

    @on(Select.Changed, "#section_select")
    def on_section_changed(self, event: Select.Changed):
        self._update_path_preview()

    @on(Input.Changed, "#url")
    def on_url_changed(self, event: Input.Changed):
        url = event.value.strip()
        label = self.query_one("#source_label")
        if not url:
            label.update("")
            self.source = None
            return
        try:
            from scripts.crawler_factory import get_crawler_class, detect_source_name
            cls = get_crawler_class(url)
            self.source = detect_source_name(url)
            label.update(f"🔗 Источник: {SOURCE_LABELS.get(self.source, cls.__name__)}")
        except ValueError:
            self.source = None
            label.update("⚠️ Неизвестный сайт — ссылка не поддерживается")

    @on(Input.Changed, "#title_input")
    def on_title_changed(self, event: Input.Changed):
        if event.value.strip():
            self.query_one("#next").disabled = False
        else:
            self.query_one("#next").disabled = True

    def _update_path_preview(self):
        pass

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "fetch":
            url = self.query_one("#url").value.strip()
            if not url:
                self.app.notify("Введите ссылку", severity="warning")
                return
            try:
                from scripts.crawler_factory import get_crawler_class
                get_crawler_class(url)
            except ValueError:
                self.app.notify(
                    "Ссылка не относится ни к одному из поддерживаемых сайтов "
                    "(Rulate, Ranobes.com)",
                    severity="error",
                )
                return
            self._log(f"Запрос информации для {url}")
            self.query_one("#fetch").disabled = True
            self.query_one("#fetch").label = "⏳ Получение..."

            # SeleniumBase (ranobes.com) и обычный HTTP-краулер (Rulate)
            # теперь оба выполняются в фоновом потоке главного процесса —
            # без multiprocessing.Process. Это соответствует тому, как уже
            # работает сама загрузка глав (LoadScreen тоже использует
            # threading.Thread, а не отдельный процесс).
            threading.Thread(target=self._fetch_info_thread, args=(url,), daemon=True).start()

        elif event.button.id == "next":
            url = self.query_one("#url").value
            title = self.query_one("#title_input").value
            section = self.query_one("#section_select").value
            status = self.query_one("#status_select").value

            if not url or not title:
                self.app.notify("Заполните ссылку и название", severity="warning")
                return
            if not section:
                section = "Разные"
            if not status:
                status = "в работе"

            try:
                from scripts.crawler_factory import detect_source_name
                source = detect_source_name(url)
            except ValueError:
                self.app.notify("Неизвестный источник ссылки", severity="error")
                return

            folder_name = slugify(title)
            if not folder_name:
                folder_name = "unnamed"
            target_dir = os.path.join(NOVELS_BASE, folder_name)

            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title).strip() or "Новелла"
            output_books = build_output_path(NOVELS_DIR, section, safe_title)

            total = getattr(self, 'total_chapters', 0)

            self.app.push_screen(ConfirmPathsScreen(
                url, title, folder_name, target_dir, output_books,
                getattr(self, 'synopsis', None), total, section, status, source
            ))

    def _fetch_info_thread(self, url: str):
        """Получение информации о новелле в фоновом потоке (Rulate и ranobes.com)."""
        self._log("▶️ Запрос информации...")
        try:
            from gui.crawler_utils import get_novel_info
            title, synopsis, chapters = get_novel_info(url, self.app.LOGIN, self.app.PASSWORD)
            total = len(chapters) if chapters else 0
            self._log(f"✅ Итог: title='{title}', глав={total}")
            self.app.call_from_thread(self._on_info_fetched, title, synopsis, total)
        except Exception as e:
            error_str = str(e)
            self._log(f"❌ Ошибка получения информации: {error_str}")
            if 'ranobes.com' in url and ('Cloudflare' in error_str or '403' in error_str):
                self.app.call_from_thread(self._on_cloudflare_block)
            else:
                self.app.call_from_thread(self._on_fetch_error, error_str)

    def _on_cloudflare_block(self):
        self._log("🛑 Обнаружена блокировка Cloudflare, показываю инструкцию")
        self.cloudflare_event.clear()
        self.app.push_screen(CloudflarePauseScreen(self.cloudflare_event))
        self.query_one("#fetch").disabled = False
        self.query_one("#fetch").label = "Получить информацию"

    def _on_info_fetched(self, title, synopsis, total):
        fetch_btn = self.query_one("#fetch")
        fetch_btn.disabled = False
        fetch_btn.label = "Получить информацию"
        if title:
            self.query_one("#title_input").value = title
            self.query_one("#next").disabled = False
            self.synopsis = synopsis
            self.total_chapters = total
            self._log(f"Поля заполнены: название='{title}', синопсис={bool(synopsis)}, глав={total}")
        else:
            self.query_one("#title_input").placeholder = "Не удалось получить название, введите вручную"
            self.query_one("#title_input").value = ""
            self.app.notify("Не удалось получить информацию. Введите вручную.", severity="warning")

    def _on_fetch_error(self, error):
        fetch_btn = self.query_one("#fetch")
        fetch_btn.disabled = False
        fetch_btn.label = "Получить информацию"
        self.app.notify(f"Ошибка: {error}", severity="error")