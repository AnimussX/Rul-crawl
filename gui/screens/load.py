import os
import shutil
import threading
from pathlib import Path
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Label, TextArea, Button, ProgressBar
from gui.database import get_novel
from gui.main_runner import run_main_with_log

class LoadScreen(Screen):
    def __init__(self, novel_id: int, chapters_spec: str, force: bool = False, ignore_image_errors: bool = False, ignore_errors: bool = False):
        super().__init__()
        self.novel_id = novel_id
        self.chapters_spec = chapters_spec
        self.force = force
        self.ignore_image_errors = ignore_image_errors
        self.ignore_errors = ignore_errors
        self.stop_flag = threading.Event()
        self.thread = None
        self.novel_data = None
        self.total_chapters = 0
        self.total_images = 0
        self.images_processed = 0

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
                yield Button("🏠 Главное меню", id="main_menu", variant="primary", disabled=True)
                yield Button("Закрыть", id="close", variant="primary", disabled=True)
        yield Footer()

    def on_mount(self):
        self.novel_data = get_novel(self.novel_id)
        if not self.novel_data:
            self._append_log("Ошибка: не найдены данные новеллы.")
            return
        self._append_log(f"URL: {self.novel_data['url']}")
        self._append_log(f"Диапазон глав: {self.chapters_spec}")
        if self.force:
            self._append_log("⚠️ Принудительная перезагрузка всех глав")
        if self.ignore_image_errors:
            self._append_log("⚠️ Ошибки изображений будут пропущены")
        if self.ignore_errors:
            self._append_log("⚠️ Ошибки загрузки глав будут пропущены (незагруженные главы не остановят создание EPUB)")

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

        os.makedirs(self.novel_data['target_dir'], exist_ok=True)

        self.thread = threading.Thread(target=self._run_main, daemon=True)
        self.thread.start()

    def _run_main(self):
        success = run_main_with_log(
            url=self.novel_data['url'],
            chapters_spec=self.chapters_spec,
            login=self.app.LOGIN,
            password=self.app.PASSWORD,
            total_chapters=self.total_chapters,
            workers=2,
            proxy_file=None,
            debug=False,
            target_dir=self.novel_data['target_dir'],
            force=self.force,
            ignore_image_errors=self.ignore_image_errors,
            ignore_errors=self.ignore_errors,  # новый параметр
            log_callback=self._append_log
        )
        self.app.call_from_thread(self._finish, success)

    def _finish(self, success: bool):
        if success:
            self._append_log("✅ Процесс завершён успешно.")
            target_dir = Path(self.novel_data['target_dir'])
            epubs = list(target_dir.glob("*.epub"))
            if epubs:
                epub_file = max(epubs, key=lambda p: p.stat().st_mtime)
                output_dir = Path(self.novel_data['output_books'])
                output_dir.mkdir(parents=True, exist_ok=True)
                dest = output_dir / epub_file.name
                if dest.exists():
                    dest.unlink()
                    self._append_log(f"♻️ Существующий файл {dest.name} удалён, будет заменён новым")
                shutil.move(str(epub_file), str(dest))
                self._append_log(f"📘 EPUB перемещён в {dest}")
            else:
                self._append_log("⚠️ Файл EPUB не найден в целевой папке.")
        else:
            self._append_log("❌ Процесс завершился с ошибкой.")
        self.query_one("#stop").disabled = True
        self.query_one("#close").disabled = False
        self.query_one("#main_menu").disabled = False
        self.query_one("#status_message").update("Готово")

    def _append_log(self, line: str):
        if line.startswith("PROGRESS: "):
            try:
                current, total = map(int, line[10:].split('/'))
                self.app.call_from_thread(self._update_chapters_progress, current)
            except:
                pass
        elif line.startswith("PROGRESS_IMG: "):
            try:
                current, total = map(int, line[14:].split('/'))
                self.app.call_from_thread(self._update_images_progress, current, total)
            except:
                pass
        else:
            if threading.current_thread() is threading.main_thread():
                self.__append_log_sync(line)
            else:
                self.app.call_from_thread(self.__append_log_sync, line)

    def _update_chapters_progress(self, current):
        progress_bar = self.query_one("#progress_chapters")
        progress_bar.progress = current
        self.query_one("#status_message").update(f"{current}/{self.total_chapters} глав, изображения: {self.images_processed}/{self.total_images if self.total_images else '?'}")

    def _update_images_progress(self, current, total):
        self.total_images = total
        self.images_processed = current
        progress_bar = self.query_one("#progress_images")
        progress_bar.total = total
        progress_bar.progress = current
        self.query_one("#status_message").update(f"{self.total_chapters}/{self.total_chapters} глав, изображения: {current}/{total}")

    def __append_log_sync(self, line: str):
        log = self.query_one("#log")
        log.text += line + "\n"
        log.scroll_end()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "stop":
            self.stop_flag.set()
            self._append_log("⚠️ Остановка запрошена (процесс может завершиться не сразу).")
        elif event.button.id == "close":
            self.app.pop_screen()
        elif event.button.id == "main_menu":
            from gui.screens.main_menu import MainMenuScreen
            self.app.pop_screen()
            while not isinstance(self.app.screen, MainMenuScreen):
                self.app.pop_screen()