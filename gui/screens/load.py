# gui/screens/load.py

import threading
from pathlib import Path
from datetime import datetime
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, TextArea, Button, ProgressBar, Checkbox
from gui.database import get_novel
from scripts.download_manager import download_book, DownloadCallbacks
from scripts.settings import load_settings


class LoadScreen(Screen):
    def __init__(
        self,
        novel_id: int,
        chapters_spec: str,
        force: bool = False,
        ignore_image_errors: bool = False,
        ignore_errors: bool = False,
        rebuild_only: bool = False,
    ):
        super().__init__()
        self.novel_id = novel_id
        self.chapters_spec = chapters_spec
        self.force = force
        self.ignore_image_errors = ignore_image_errors
        self.ignore_errors = ignore_errors
        self.rebuild_only = rebuild_only
        self.stop_flag = threading.Event()
        self.thread = None
        self.novel_data = None
        self.total_chapters = 0
        self.total_images = 0
        self.images_processed = 0
        self.settings = load_settings()
        self.debug_mode = self.settings.get("debug_mode", False)

    def compose(self):
        yield Header()
        with Container(id="main"):
            yield Label("Загрузка...", id="title")
            yield Label("Главы:", id="chapters_label")
            yield ProgressBar(total=100, show_eta=False, id="progress_chapters")
            yield Label("Изображения:", id="images_label")
            yield ProgressBar(total=100, show_eta=False, id="progress_images")
            yield Label("", id="status_message")
            yield TextArea(id="log", read_only=True)
            with Horizontal(id="buttons"):
                yield Button("Стоп", id="stop", variant="error")
                if self.debug_mode:
                    yield Button("💾 Сохранить лог", id="save_log", variant="primary")
                yield Button("🏠 Главное меню", id="main_menu", variant="primary", disabled=True)
                yield Button("Закрыть", id="close", variant="primary", disabled=True)
        yield Footer()

    def on_mount(self):
        self.novel_data = get_novel(self.novel_id)
        if not self.novel_data:
            self._append_log("Ошибка: не найдены данные новеллы.")
            return

        total = 0
        for part in self.chapters_spec.split(','):
            if '-' in part:
                s, e = map(int, part.split('-'))
                total += e - s + 1
            else:
                total += 1
        self.total_chapters = total
        progress_bar = self.query_one("#progress_chapters")
        progress_bar.total = total
        progress_bar.progress = 0
        self.query_one("#status_message").update(f"0/{total} глав, изображения: ожидание")

        self.thread = threading.Thread(target=self._run_download, daemon=True)
        self.thread.start()

    def _run_download(self):
        try:
            callbacks = DownloadCallbacks(
                log_callback=self._append_log,
                progress_chapter_callback=self._update_chapters_progress,
                progress_image_callback=self._update_images_progress,
            )
            settings = load_settings()
            success, result = download_book(
                url=self.novel_data["url"],
                chapters_spec=self.chapters_spec,
                login=self.app.LOGIN,
                password=self.app.PASSWORD,
                target_dir=self.novel_data["target_dir"],
                force=self.force,
                ignore_image_errors=self.ignore_image_errors,
                ignore_errors=self.ignore_errors,
                workers=settings.get("workers", 2),
                image_workers=settings.get("image_workers", 2),
                image_retries=settings.get("image_retries", 3),
                image_timeout=settings.get("image_timeout", 30),
                slow_image_timeout=settings.get("slow_image_timeout", 120),
                proxy_file=None,
                debug=self.debug_mode,
                stop_event=self.stop_flag,
                callbacks=callbacks,
                rebuild_only=self.rebuild_only,
            )
            self.app.call_from_thread(self._finish, success, result)
        except Exception as e:
            self.app.call_from_thread(self._finish, False, f"Критическая ошибка: {e}")

    def _finish(self, success: bool, result: str):
        if success:
            self._append_log("✅ Процесс завершён успешно.")
            epub_path = Path(result)
            output_dir = Path(self.novel_data["output_books"])
            output_dir.mkdir(parents=True, exist_ok=True)
            dest = output_dir / epub_path.name
            if dest.exists():
                dest.unlink()
            epub_path.rename(dest)
            self._append_log(f"📘 EPUB перемещён в {dest}")
        else:
            self._append_log(f"❌ Процесс завершился с ошибкой: {result}")

        if self.debug_mode and self.settings.get("auto_save_log", True):
            self._save_log(auto=True)

        self.query_one("#stop").disabled = True
        self.query_one("#close").disabled = False
        self.query_one("#main_menu").disabled = False
        self.query_one("#status_message").update("Готово")

    def _save_log(self, auto=False):
        if not self.novel_data:
            return
        log_widget = self.query_one("#log")
        log_text = log_widget.text
        if not log_text.strip():
            if not auto:
                self.__append_log_sync("Лог пуст, нечего сохранять.")
            return
        target_dir = Path(self.novel_data["target_dir"])
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = target_dir / f"download_log_{timestamp}.txt"
        try:
            with open(log_filename, "w", encoding="utf-8") as f:
                f.write(log_text)
            if not auto:
                self.__append_log_sync(f"✅ Лог сохранён: {log_filename}")
        except Exception as e:
            if not auto:
                self.__append_log_sync(f"❌ Ошибка сохранения лога: {e}")

    def _append_log(self, line: str):
        if threading.current_thread() is threading.main_thread():
            self.__append_log_sync(line)
        else:
            self.app.call_from_thread(self.__append_log_sync, line)

    def __append_log_sync(self, line: str):
        if not self.is_mounted:
            return
        log = self.query_one("#log")
        log.text += line + "\n"
        log.scroll_end(animate=False)

    def _update_chapters_progress(self, current: int, total: int):
        self.app.call_from_thread(self.__update_chapters_progress, current, total)

    def __update_chapters_progress(self, current: int, total: int):
        if not self.is_mounted:
            return
        self.total_chapters = total
        progress_bar = self.query_one("#progress_chapters")
        progress_bar.total = total
        progress_bar.progress = current
        self.query_one("#status_message").update(
            f"{current}/{total} глав, изображения: {self.images_processed}/{self.total_images if self.total_images else '?'}"
        )

    def _update_images_progress(self, current: int, total: int):
        self.total_images = total
        self.images_processed = current
        self.app.call_from_thread(self.__update_images_progress, current, total)

    def __update_images_progress(self, current: int, total: int):
        if not self.is_mounted:
            return
        progress_bar = self.query_one("#progress_images")
        progress_bar.total = total
        progress_bar.progress = current
        self.query_one("#status_message").update(
            f"{self.total_chapters}/{self.total_chapters} глав, изображения: {current}/{total}"
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "stop":
            self.stop_flag.set()
            self._append_log("⚠️ Остановка запрошена. Загрузка будет прервана после текущей главы или в ближайшей паузе.")
        elif event.button.id == "save_log" and self.debug_mode:
            self._save_log()
        elif event.button.id == "close":
            self.app.pop_screen()
        elif event.button.id == "main_menu":
            from gui.screens.main_menu import MainMenuScreen
            self.app.pop_screen()
            while not isinstance(self.app.screen, MainMenuScreen):
                self.app.pop_screen()