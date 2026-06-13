# main.py
import os
import threading
from pathlib import Path
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivymd.app import MDApp
from kivymd.uix.list import OneLineListItem, TwoLineListItem
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.clock import Clock

# Импорты бизнес-логики
from scripts.auth import load_auth, save_auth
from scripts.settings import load_settings, save_settings
from gui.database import init_db, get_all_novels, add_novel, delete_novel, get_novel, update_novel
from gui.crawler_utils import get_novel_info
from scripts.download_manager import download_book, DownloadCallbacks
from scripts.transliterate import slugify
from scripts.paths import NOVELS_BASE, NOVELS_DIR
import sqlite3

# KV разметка (встроенная для компактности, но можно вынести в отдельный файл)
KV = '''
ScreenManager:
    LoginScreen:
    MainScreen:
    AddScreen:
    ChaptersScreen:
    LoadScreen:
    SettingsScreen:

<LoginScreen>:
    name: 'login'
    MDBoxLayout:
        orientation: 'vertical'
        spacing: dp(20)
        padding: dp(40)
        MDLabel:
            text: 'Rulate Crawler'
            font_style: 'H4'
            halign: 'center'
            size_hint_y: 0.3
        MDTextField:
            id: login_input
            hint_text: 'Логин'
            icon_left: 'account'
            size_hint_x: 0.9
            pos_hint: {'center_x': 0.5}
        MDTextField:
            id: password_input
            hint_text: 'Пароль'
            icon_left: 'lock'
            password: True
            size_hint_x: 0.9
            pos_hint: {'center_x': 0.5}
        MDRaisedButton:
            text: 'Войти'
            size_hint_x: 0.6
            pos_hint: {'center_x': 0.5}
            on_release: app.do_login()
        MDLabel:
            size_hint_y: 0.2

<MainScreen>:
    name: 'main'
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: 'Мои книги'
            left_action_items: [['menu', lambda x: app.toggle_menu()]]
            right_action_items: [['plus', lambda x: app.go_to_add()]]
        MDList:
            id: novel_list
        MDRaisedButton:
            text: 'Настройки'
            size_hint_x: 0.5
            pos_hint: {'center_x': 0.5}
            on_release: app.open_settings()

<AddScreen>:
    name: 'add'
    MDBoxLayout:
        orientation: 'vertical'
        spacing: dp(20)
        padding: dp(20)
        MDTopAppBar:
            title: 'Добавить книгу'
            left_action_items: [['arrow-left', lambda x: app.go_back()]]
        MDTextField:
            id: url_input
            hint_text: 'URL новеллы'
            helper_text: 'Введите ссылку на tl.rulate.ru'
            helper_text_mode: 'on_focus'
        MDRaisedButton:
            text: 'Получить информацию'
            on_release: app.fetch_novel_info()
        MDLabel:
            id: info_label
            text: ''
            markup: True
        MDRaisedButton:
            text: 'Далее'
            disabled: True
            id: next_btn
            on_release: app.confirm_paths()

<ChaptersScreen>:
    name: 'chapters'
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: 'Выбор глав'
            left_action_items: [['arrow-left', lambda x: app.go_back()]]
        MDBoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.1
            MDTextField:
                id: range_from
                hint_text: 'С'
                input_filter: 'int'
                size_hint_x: 0.3
            MDTextField:
                id: range_to
                hint_text: 'По'
                input_filter: 'int'
                size_hint_x: 0.3
            MDRaisedButton:
                text: 'OK'
                size_hint_x: 0.3
                on_release: app.select_range()
        MDBoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.1
            MDCheckbox:
                id: force_check
                size_hint_x: 0.1
            MDLabel:
                text: 'Принудительно перезагрузить все главы'
                size_hint_x: 0.9
        MDBoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.1
            MDCheckbox:
                id: rebuild_check
                size_hint_x: 0.1
            MDLabel:
                text: 'Только собрать EPUB (без загрузки)'
                size_hint_x: 0.9
        ScrollView:
            MDList:
                id: chapters_list
        MDBoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.1
            MDRaisedButton:
                text: 'Выбрать все'
                on_release: app.select_all()
            MDRaisedButton:
                text: 'Снять все'
                on_release: app.deselect_all()
            MDRaisedButton:
                text: 'Загрузить'
                on_release: app.start_download()

<LoadScreen>:
    name: 'load'
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: 'Загрузка'
            left_action_items: [['arrow-left', lambda x: app.stop_download()]]
        MDLabel:
            text: 'Главы:'
        MDProgressBar:
            id: chapter_progress
            max: 100
            value: 0
        MDLabel:
            text: 'Изображения:'
        MDProgressBar:
            id: image_progress
            max: 100
            value: 0
        MDLabel:
            id: status_label
            text: ''
        ScrollView:
            MDLabel:
                id: log_label
                text: ''
                markup: True
                size_hint_y: None
                height: self.texture_size[1]

<SettingsScreen>:
    name: 'settings'
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: 'Настройки'
            left_action_items: [['arrow-left', lambda x: app.go_back()]]
        ScrollView:
            MDList:
                id: settings_list
'''

class LoginScreen(Screen):
    pass

class MainScreen(Screen):
    pass

class AddScreen(Screen):
    pass

class ChaptersScreen(Screen):
    pass

class LoadScreen(Screen):
    pass

class SettingsScreen(Screen):
    pass

class RulateApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_novel_id = None
        self.current_url = None
        self.current_title = None
        self.current_synopsis = None
        self.current_chapters = None
        self.settings = None

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.sm = ScreenManager()
        self.sm.add_widget(LoginScreen(name='login'))
        self.sm.add_widget(MainScreen(name='main'))
        self.sm.add_widget(AddScreen(name='add'))
        self.sm.add_widget(ChaptersScreen(name='chapters'))
        self.sm.add_widget(LoadScreen(name='load'))
        self.sm.add_widget(SettingsScreen(name='settings'))
        init_db()
        self.settings = load_settings()
        # Если есть сохранённые логин/пароль, пробуем войти
        login, pwd = load_auth()
        if login and pwd:
            Clock.schedule_once(lambda dt: self.switch_to_main(), 0.5)
        return self.sm

    def switch_to_main(self):
        self.sm.current = 'main'
        self.load_novels()

    def do_login(self):
        login = self.root.get_screen('login').ids.login_input.text
        password = self.root.get_screen('login').ids.password_input.text
        if login and password:
            save_auth(login, password)
            self.sm.current = 'main'
            self.load_novels()
        else:
            Snackbar(text='Введите логин и пароль').open()

    def load_novels(self):
        list_widget = self.root.get_screen('main').ids.novel_list
        list_widget.clear_widgets()
        novels = get_all_novels()
        for n in novels:
            item = TwoLineListItem(text=n[1], secondary_text=n[2])
            item.bind(on_release=lambda x, nid=n[0]: self.open_novel(nid))
            list_widget.add_widget(item)

    def open_novel(self, novel_id):
        self.current_novel_id = novel_id
        self.sm.current = 'chapters'
        self.load_chapters()

    def load_chapters(self):
        novel = get_novel(self.current_novel_id)
        if not novel:
            Snackbar(text='Ошибка загрузки данных').open()
            return
        # Загружаем список глав с сайта или из кэша
        url = novel['url']
        login, pwd = load_auth()
        threading.Thread(target=self._fetch_chapters, args=(url, login, pwd), daemon=True).start()

    def _fetch_chapters(self, url, login, pwd):
        try:
            title, synopsis, chapters = get_novel_info(url, login, pwd)
            self.current_title = title
            self.current_synopsis = synopsis
            self.current_chapters = chapters
            Clock.schedule_once(lambda dt: self.display_chapters(), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: Snackbar(text=f'Ошибка: {e}').open(), 0)

    def display_chapters(self):
        screen = self.root.get_screen('chapters')
        list_widget = screen.ids.chapters_list
        list_widget.clear_widgets()
        for i, ch in enumerate(self.current_chapters):
            cb = MDCheckbox(size_hint_x=0.1)
            label = MDLabel(text=f"{i+1}. {ch['title']}", size_hint_x=0.9)
            box = MDBoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
            box.add_widget(cb)
            box.add_widget(label)
            list_widget.add_widget(box)
            # Храним чекбоксы в списке
            if not hasattr(self, 'checkboxes'):
                self.checkboxes = []
            self.checkboxes.append(cb)

    def select_all(self):
        for cb in self.checkboxes:
            cb.active = True

    def deselect_all(self):
        for cb in self.checkboxes:
            cb.active = False

    def select_range(self):
        screen = self.root.get_screen('chapters')
        from_ = screen.ids.range_from.text
        to_ = screen.ids.range_to.text
        if from_.isdigit() and to_.isdigit():
            f = int(from_)
            t = int(to_)
            for i, cb in enumerate(self.checkboxes):
                idx = i+1
                cb.active = (f <= idx <= t)
        else:
            Snackbar(text='Введите числа').open()

    def start_download(self):
        selected = [i+1 for i, cb in enumerate(self.checkboxes) if cb.active]
        if not selected:
            Snackbar(text='Выберите главы').open()
            return
        selected.sort()
        ranges = []
        start = selected[0]
        end = start
        for i in range(1, len(selected)):
            if selected[i] == end+1:
                end = selected[i]
            else:
                ranges.append(f"{start}-{end}" if start!=end else str(start))
                start = end = selected[i]
        ranges.append(f"{start}-{end}" if start!=end else str(start))
        spec = ",".join(ranges)
        screen = self.root.get_screen('chapters')
        force = screen.ids.force_check.active
        rebuild_only = screen.ids.rebuild_check.active
        # Передаём параметры в LoadScreen
        load_screen = self.root.get_screen('load')
        load_screen.chapters_spec = spec
        load_screen.force = force
        load_screen.rebuild_only = rebuild_only
        self.sm.current = 'load'
        self.start_load()

    def start_load(self):
        novel = get_novel(self.current_novel_id)
        login, pwd = load_auth()
        settings = load_settings()
        self.stop_flag = threading.Event()
        self.load_thread = threading.Thread(target=self._run_download, args=(novel, login, pwd, settings), daemon=True)
        self.load_thread.start()

    def _run_download(self, novel, login, pwd, settings):
        callbacks = DownloadCallbacks(
            log_callback=self._append_log,
            progress_chapter_callback=self._update_chapter_progress,
            progress_image_callback=self._update_image_progress
        )
        success, result = download_book(
            url=novel['url'],
            chapters_spec=self.root.get_screen('load').chapters_spec,
            login=login, password=pwd,
            target_dir=novel['target_dir'],
            force=self.root.get_screen('load').force,
            ignore_image_errors=False,
            ignore_errors=False,
            workers=settings.get('workers', 2),
            image_workers=settings.get('image_workers', 2),
            image_retries=settings.get('image_retries', 3),
            image_timeout=settings.get('image_timeout', 30),
            slow_image_timeout=settings.get('slow_image_timeout', 120),
            proxy_file=None,
            debug=settings.get('debug_mode', False),
            stop_event=self.stop_flag,
            callbacks=callbacks,
            rebuild_only=self.root.get_screen('load').rebuild_only
        )
        Clock.schedule_once(lambda dt: self.finish_download(success, result), 0)

    def _append_log(self, line):
        Clock.schedule_once(lambda dt: self._add_log_line(line), 0)

    def _add_log_line(self, line):
        log_label = self.root.get_screen('load').ids.log_label
        log_label.text += line + "\n"
        log_label.height = log_label.texture_size[1]

    def _update_chapter_progress(self, current, total):
        Clock.schedule_once(lambda dt: self._set_chapter_progress(current, total), 0)

    def _set_chapter_progress(self, current, total):
        progress = self.root.get_screen('load').ids.chapter_progress
        progress.max = total
        progress.value = current
        self.root.get_screen('load').ids.status_label.text = f"Главы: {current}/{total}"

    def _update_image_progress(self, current, total):
        Clock.schedule_once(lambda dt: self._set_image_progress(current, total), 0)

    def _set_image_progress(self, current, total):
        progress = self.root.get_screen('load').ids.image_progress
        progress.max = total
        progress.value = current

    def finish_download(self, success, result):
        if success:
            Snackbar(text=f"Готово! EPUB: {result}").open()
        else:
            Snackbar(text=f"Ошибка: {result}").open()
        self.sm.current = 'main'
        self.load_novels()

    def stop_download(self):
        if hasattr(self, 'stop_flag'):
            self.stop_flag.set()
            self._append_log("Остановка запрошена...")
        else:
            self.sm.current = 'main'

    def open_settings(self):
        self.sm.current = 'settings'
        # Загружаем настройки в интерфейс (можно сделать отдельно)

    def go_to_add(self):
        self.sm.current = 'add'
        screen = self.root.get_screen('add')
        screen.ids.url_input.text = ''
        screen.ids.info_label.text = ''
        screen.ids.next_btn.disabled = True

    def fetch_novel_info(self):
        url = self.root.get_screen('add').ids.url_input.text.strip()
        if not url:
            Snackbar(text='Введите URL').open()
            return
        login, pwd = load_auth()
        threading.Thread(target=self._fetch_info, args=(url, login, pwd), daemon=True).start()

    def _fetch_info(self, url, login, pwd):
        try:
            title, synopsis, chapters = get_novel_info(url, login, pwd)
            self.current_url = url
            self.current_title = title
            self.current_synopsis = synopsis
            self.current_chapters_count = len(chapters)
            Clock.schedule_once(lambda dt: self._show_info(title, synopsis), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: Snackbar(text=f'Ошибка: {e}').open(), 0)

    def _show_info(self, title, synopsis):
        screen = self.root.get_screen('add')
        screen.ids.info_label.text = f"[b]{title}[/b]\n\n{synopsis[:200]}..."
        screen.ids.next_btn.disabled = False

    def confirm_paths(self):
        # Переход к экрану подтверждения путей (можно реализовать отдельно)
        # Здесь для простоты создадим книгу с автоматическими путями
        folder_name = slugify(self.current_title)
        target_dir = str(Path(NOVELS_BASE) / folder_name)
        section = "Разные"  # позже можно выбрать
        output_books = str(Path(NOVELS_DIR) / folder_name)
        novel_id = add_novel(
            title=self.current_title,
            url=self.current_url,
            target_dir=target_dir,
            output_books=output_books,
            synopsis=self.current_synopsis,
            total_chapters=self.current_chapters_count,
            section=section
        )
        self.current_novel_id = novel_id
        self.sm.current = 'chapters'
        self.load_chapters()

    def toggle_menu(self):
        # Можно добавить боковое меню, пока заглушка
        pass

    def go_back(self):
        if self.sm.current == 'chapters':
            self.sm.current = 'main'
        elif self.sm.current == 'add':
            self.sm.current = 'main'
        elif self.sm.current == 'settings':
            self.sm.current = 'main'

if __name__ == '__main__':
    RulateApp().run()