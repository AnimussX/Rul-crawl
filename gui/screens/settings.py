# gui/screens/settings.py

import os
import json
from pathlib import Path
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.widgets import (
    Header, Footer, Label, Button, Checkbox,
    RadioSet, RadioButton, Input, TabbedContent, TabPane
)
from scripts.auth import load_auth
from scripts.settings import load_settings, save_settings
from gui.screens.confirm_dialog import ConfirmDialog


class SettingsScreen(Screen):
    """Настройки с вкладками для удобства."""

    CSS_PATH = "../styles/settings.tcss"

    def compose(self):
        self.settings = load_settings()
        login, _ = load_auth()
        debug_mode = self.settings.get("debug_mode", False)
        yield Header()
        with Container(id="main"):
            yield Label("⚙️ Настройки", id="title")
            with TabbedContent(initial="tab_general", id="tab_container"):
                # --- Вкладка "Общие" ---
                with TabPane("Общие", id="tab_general"):
                    with Vertical():
                        yield Label("🔐 Авторизация:")
                        with Horizontal():
                            self.auth_status = Label(
                                f"✅ Логин: {login[:5]}..." if login and len(login) > 5 else "❌ Не задан",
                                id="auth_status"
                            )
                            yield self.auth_status
                            yield Button("Изменить", id="edit_auth", variant="primary")
                        yield Label("")
                        self.debug_checkbox = Checkbox(
                            "Режим отладки (подробные логи)",
                            value=debug_mode
                        )
                        yield self.debug_checkbox
                        yield Label("")
                        yield Button("🗑️ Очистить кэш завершённых", id="clear_completed_cache", variant="warning")

                # --- Вкладка "Параметры загрузки" ---
                with TabPane("Загрузка", id="tab_download"):
                    with Grid():
                        workers_current = self.settings.get("workers", 2)
                        yield Label(f"Потоков для глав (1-5) [текущее: {workers_current}]:")
                        self.workers_input = Input("", type="integer", id="workers")
                        yield self.workers_input

                        image_workers_current = self.settings.get("image_workers", 2)
                        yield Label(f"Потоков для изображений (1-5) [текущее: {image_workers_current}]:")
                        self.image_workers_input = Input("", type="integer", id="image_workers")
                        yield self.image_workers_input

                        image_retries_current = self.settings.get("image_retries", 3)
                        yield Label(f"Попыток загрузки изображений (1-5) [текущее: {image_retries_current}]:")
                        self.image_retries_input = Input("", type="integer", id="image_retries")
                        yield self.image_retries_input

                        image_timeout_current = self.settings.get("image_timeout", 30)
                        yield Label(f"Таймаут обычных изображений (сек, 10-120) [текущее: {image_timeout_current}]:")
                        self.image_timeout_input = Input("", type="integer", id="image_timeout")
                        yield self.image_timeout_input

                        slow_timeout_current = self.settings.get("slow_image_timeout", 120)
                        yield Label(f"Таймаут медленных хостингов (сек, 30-300) [текущее: {slow_timeout_current}]:")
                        self.slow_image_timeout_input = Input("", type="integer", id="slow_image_timeout")
                        yield self.slow_image_timeout_input

                        progress_step_current = self.settings.get("progress_step", 1)
                        yield Label(f"Шаг обновления прогресса глав (1-100) [текущее: {progress_step_current}]:")
                        self.progress_step_input = Input("", type="integer", id="progress_step")
                        yield self.progress_step_input

                # --- Вкладка "Пути" ---
                # --- Вкладка "Пути" ---
                with TabPane("Пути", id="tab_paths"):
                    with Grid():
                        cache_dir_current = self.settings.get("cache_base_dir", "")
                        yield Label(f"Базовая папка для кэша [текущее: {cache_dir_current}]:")
                        self.cache_dir_input = Input("", id="cache_dir")
                        yield self.cache_dir_input

                        epub_dir_current = self.settings.get("epub_output_dir", "")
                        yield Label(f"Папка для готовых EPUB [текущее: {epub_dir_current}]:")
                        self.epub_dir_input = Input("", id="epub_dir")
                        yield self.epub_dir_input

                        chromium_current = self.settings.get("chromium_binary_path", "") or "(автоопределение)"
                        yield Label(f"Путь к Chromium (для ranobes.com) [текущее: {chromium_current}]:")
                        self.chromium_path_input = Input("", id="chromium_path")
                        yield self.chromium_path_input

                        chromedriver_current = self.settings.get("chromedriver_path", "") or "(автоопределение)"
                        yield Label(f"Путь к Chromedriver [текущее: {chromedriver_current}]:")
                        self.chromedriver_path_input = Input("", id="chromedriver_path")
                        yield self.chromedriver_path_input

                # --- Вкладка "Отладка" (только если debug_mode включён) ---
                if debug_mode:
                    with TabPane("Отладка", id="tab_debug"):
                        with Vertical():
                            self.auto_log_checkbox = Checkbox(
                                "Автоматически сохранять лог после загрузки",
                                value=self.settings.get("auto_save_log", True)
                            )
                            yield self.auto_log_checkbox
                            yield Label("🗄️ Тип кэша глав:")
                            self.cache_type_radio = RadioSet(
                                RadioButton("JSON (файлы)", value=self.settings.get("cache_type") == "json"),
                                RadioButton("SQLite (база данных)", value=self.settings.get("cache_type") == "sqlite")
                            )
                            yield self.cache_type_radio
                            self.selenium_fallback_checkbox = Checkbox(
                                "Использовать Selenium при ошибках Cloudflare",
                                value=self.settings.get("use_selenium_fallback", True)
                            )
                            yield self.selenium_fallback_checkbox
                
                # --- Вкладка "Экспорт" (всегда видна) ---
                with TabPane("Экспорт", id="tab_export"):
                    with Vertical():
                        yield Label("🔄 Экспорт/импорт настроек:")
                        with Horizontal():
                            yield Button("📤 Экспорт настроек", id="export_settings", variant="default")
                            yield Button("📥 Импорт настроек", id="import_settings", variant="default")
                        self.export_path_input = Input(
                            placeholder="Путь для экспорта/импорта (оставьте пустым для домашней папки)",
                            id="export_path"
                        )
                        yield self.export_path_input

            # --- Нижняя панель с кнопками ---
            yield Label("", id="status")
            with Horizontal(id="bottom_buttons"):
                yield Button("💾 Сохранить", id="save", variant="success")
                yield Button("◀️ Назад", id="back", variant="default")
        yield Footer()

    def on_mount(self):
        pass

    def _get_export_path(self):
        path = self.export_path_input.value.strip()
        if not path:
            return Path.home() / "lncrawl_settings_export.json"
        return Path(path)

    def _export_settings(self):
        export_path = self._get_export_path()
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            self.query_one("#status").update(f"✅ Настройки экспортированы в {export_path}")
        except Exception as e:
            self.query_one("#status").update(f"❌ Ошибка экспорта: {e}")

    def _import_settings(self):
        import_path = self._get_export_path()
        if not import_path.exists():
            self.query_one("#status").update(f"❌ Файл {import_path} не найден")
            return
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                new_settings = json.load(f)
            self.settings.update(new_settings)
            save_settings(self.settings)
            self.query_one("#status").update("✅ Настройки импортированы. Перезапустите приложение для применения.")
            self.workers_input.value = ""
            self.image_workers_input.value = ""
            self.image_retries_input.value = ""
            self.image_timeout_input.value = ""
            self.slow_image_timeout_input.value = ""
            self.progress_step_input.value = ""
            self.cache_dir_input.value = ""
            self.epub_dir_input.value = ""
        except Exception as e:
            self.query_one("#status").update(f"❌ Ошибка импорта: {e}")

    def _clear_completed_cache(self):
        from gui.database import get_completed_novels
        completed = get_completed_novels()
        if not completed:
            self.app.notify("Нет завершённых книг для очистки", severity="information")
            return
        count = len(completed)
        self.app.push_screen(ConfirmDialog(
            f"Удалить кэш ({count} завершённых книг)?\nЭто действие необратимо.",
            self._do_clear_completed_cache
        ))

    def _do_clear_completed_cache(self):
        import shutil
        from gui.database import get_completed_novels
        completed = get_completed_novels()
        deleted = 0
        for novel_id, target_dir in completed:
            try:
                p = Path(target_dir)
                if p.exists():
                    shutil.rmtree(p)
                    deleted += 1
            except Exception as e:
                self.app.notify(f"Ошибка удаления {target_dir}: {e}", severity="error")
        self.app.notify(f"Удалено папок кэша: {deleted} из {len(completed)}", severity="information")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "edit_auth":
            from gui.screens.auth_settings import AuthSettingsScreen
            self.app.push_screen(AuthSettingsScreen())
        elif event.button.id == "export_settings":
            self._export_settings()
        elif event.button.id == "import_settings":
            self._import_settings()
        elif event.button.id == "clear_completed_cache":
            self._clear_completed_cache()
        elif event.button.id == "save":
            self.settings["debug_mode"] = self.debug_checkbox.value

            numeric_fields = [
                (self.workers_input, "workers", 1, 5, 2, "число потоков для глав"),
                (self.image_workers_input, "image_workers", 1, 5, 2, "число потоков для изображений"),
                (self.image_retries_input, "image_retries", 1, 5, 3, "число попыток загрузки изображений"),
                (self.image_timeout_input, "image_timeout", 10, 120, 30, "таймаут обычных изображений"),
                (self.slow_image_timeout_input, "slow_image_timeout", 30, 300, 120, "таймаут медленных хостингов"),
                (self.progress_step_input, "progress_step", 1, 100, 1, "шаг прогресса"),
            ]
            
            for input_widget, key, min_val, max_val, default_val, label in numeric_fields:
                try:
                    value = int(input_widget.value) if input_widget.value else self.settings.get(key, default_val)
                    if value < min_val or value > max_val:
                        raise ValueError
                    self.settings[key] = value
                except ValueError:
                    self.query_one("#status").update(
                        f"⚠️ Ошибка: {label} должен быть от {min_val} до {max_val}"
                    )
                    return

            new_cache_dir = self.cache_dir_input.value.strip()
            if new_cache_dir:
                try:
                    os.makedirs(new_cache_dir, exist_ok=True)
                    self.settings["cache_base_dir"] = new_cache_dir
                except Exception as e:
                    self.query_one("#status").update(f"❌ Ошибка создания папки кэша: {e}")
                    return

            new_epub_dir = self.epub_dir_input.value.strip()
            if new_epub_dir:
                try:
                    os.makedirs(new_epub_dir, exist_ok=True)
                    self.settings["epub_output_dir"] = new_epub_dir
                except Exception as e:
                    self.query_one("#status").update(f"❌ Ошибка создания папки EPUB: {e}")
                    return
            new_chromium_path = self.chromium_path_input.value.strip()
            if new_chromium_path:
                if not os.path.isfile(new_chromium_path):
                    self.query_one("#status").update(f"❌ Файл не найден: {new_chromium_path}")
                    return
                self.settings["chromium_binary_path"] = new_chromium_path

            new_chromedriver_path = self.chromedriver_path_input.value.strip()
            if new_chromedriver_path:
                if not os.path.isfile(new_chromedriver_path):
                    self.query_one("#status").update(f"❌ Файл не найден: {new_chromedriver_path}")
                    return
                self.settings["chromedriver_path"] = new_chromedriver_path
            if self.settings["debug_mode"]:
                if hasattr(self, 'auto_log_checkbox'):
                    self.settings["auto_save_log"] = self.auto_log_checkbox.value
                if hasattr(self, 'cache_type_radio'):
                    selected = self.cache_type_radio.pressed_button
                    if selected and selected.label == "SQLite (база данных)":
                        self.settings["cache_type"] = "sqlite"
                    else:
                        self.settings["cache_type"] = "json"
                if hasattr(self, 'selenium_fallback_checkbox'):
                    self.settings["use_selenium_fallback"] = self.selenium_fallback_checkbox.value

            save_settings(self.settings)

            self.workers_input.value = ""
            self.image_workers_input.value = ""
            self.image_retries_input.value = ""
            self.image_timeout_input.value = ""
            self.slow_image_timeout_input.value = ""
            self.progress_step_input.value = ""
            self.cache_dir_input.value = ""
            self.epub_dir_input.value = ""
            self.export_path_input.value = ""
            self.chromium_path_input.value = ""
            self.chromedriver_path_input.value = ""
            self.query_one("#status").update("✅ Настройки сохранены. Перезапустите приложение для применения новых путей.")
            login, _ = load_auth()
            status_text = f"✅ Логин: {login[:5]}..." if login and len(login) > 5 else "❌ Не задан"
            self.query_one("#auth_status").update(status_text)