# kivy_app/screens/load.py
import os
import shutil
import glob
from threading import Thread

from kivymd.uix.screen import MDScreen
from kivy.clock import mainthread
from kivymd.app import MDApp

from gui.config import NOVELS_BASE
from gui.database import get_novel
from gui.main_runner import run_main_with_log
from scripts.transliterate import slugify

try:
    from android.permissions import check_permission, Permission
    HAS_ANDROID_PERMISSIONS = True
except ImportError:
    HAS_ANDROID_PERMISSIONS = False


class LoadScreen(MDScreen):
    novel_id = None
    chapters_spec = ''
    force = False
    ignore_images = False
    ignore_errors = False

    def on_enter(self):
        self.ids.progress_bar.value = 0
        self.ids.log_output.text = ""
        Thread(target=self.run_load).start()

    def run_load(self):
        app = MDApp.get_running_app()
        novel = get_novel(self.novel_id)
        if not novel:
            self.update_log("❌ Новелла не найдена в базе")
            return

        # Папка для временных файлов
        target_dir = novel['target_dir']
        os.makedirs(target_dir, exist_ok=True)

        # Общее количество глав (для прогресса)
        total_chapters = 0
        for part in self.chapters_spec.split(','):
            if '-' in part:
                s, e = map(int, part.split('-'))
                total_chapters += e - s + 1
            else:
                total_chapters += 1

        # Запуск основного скрипта
        success = run_main_with_log(
            url=novel['url'],
            chapters_spec=self.chapters_spec,
            login=app.LOGIN,
            password=app.PASSWORD,
            total_chapters=total_chapters,
            workers=2,
            proxy_file=None,
            debug=False,
            target_dir=target_dir,
            force=self.force,
            ignore_image_errors=self.ignore_images,
            ignore_errors=self.ignore_errors,
            log_callback=lambda line: mainthread(self.update_log)(line),
        )

        if success:
            # Ищем свежий EPUB в папке временных файлов
            epub_files = glob.glob(os.path.join(target_dir, '*.epub'))
            if epub_files:
                latest_epub = max(epub_files, key=os.path.getmtime)

                # Путь назначения из базы данных
                output_dir = novel['output_books']
                dest_epub = os.path.join(output_dir, os.path.basename(latest_epub))

                # Проверяем, можно ли писать в output_dir
                can_write = self._check_write_permission(output_dir)

                if can_write:
                    os.makedirs(output_dir, exist_ok=True)
                    try:
                        shutil.move(latest_epub, dest_epub)
                        self.update_log(f"📘 EPUB сохранён: {dest_epub}")
                    except Exception as e:
                        self.update_log(f"⚠️ Ошибка при перемещении EPUB: {e}")
                else:
                    self.update_log(
                        "⚠️ Нет разрешения на запись в " + output_dir +
                        "\nКнига осталась во временной папке: " + target_dir
                    )
            else:
                self.update_log("⚠️ EPUB не найден после загрузки")
        else:
            self.update_log("❌ Загрузка завершилась с ошибкой")

        mainthread(self.set_done)()

    def _check_write_permission(self, path):
        """Проверяет, нужны ли особые разрешения для записи в path."""
        # Если путь находится внутри песочницы приложения — разрешения не нужны
        app = MDApp.get_running_app()
        if path.startswith(app.user_data_dir):
            return True

        # Если путь снаружи (например, /storage/emulated/0/...) —
        # на Android 10+ нужно MANAGE_EXTERNAL_STORAGE
        if HAS_ANDROID_PERMISSIONS:
            try:
                return check_permission(Permission.MANAGE_EXTERNAL_STORAGE)
            except Exception:
                pass

        # На десктопе или при отсутствии модуля разрешений просто пробуем
        return True

    @mainthread
    def update_log(self, line: str):
        self.ids.log_output.text += line + "\n"

    def set_done(self):
        self.ids.progress_bar.value = 100