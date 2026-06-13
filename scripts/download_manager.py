# scripts/download_manager.py

import time
import threading
import concurrent.futures
from pathlib import Path
from typing import Optional, Tuple

from tqdm import tqdm

from scripts.auth import load_auth
from scripts.crawler_factory import create_crawler, clone_crawler
from scripts.chapter_parser import parse_chapters_spec
from scripts.chapter_loader import download_one_chapter
from scripts.novel_metadata import get_novel_metadata
from scripts.epub_assembler import (
    process_synopsis,
    download_and_rename_images,
    replace_image_markers,
    update_db_synopsis,
    build_epub_file,
)
from scripts.paths import NOVELS_BASE
from scripts.transliterate import slugify
from scripts.metadata import save_metadata
from scripts.synopsis_handler import save_synopsis_cache
from scripts.settings import load_settings
from scripts.chapter_cache import ChapterCache


class DownloadCallbacks:
    def __init__(self, log_callback=None, progress_chapter_callback=None, progress_image_callback=None):
        self.log = log_callback or print
        self.progress_chapter = progress_chapter_callback
        self.progress_image = progress_image_callback

    def on_log(self, msg: str):
        self.log(msg)

    def on_chapter_progress(self, current: int, total: int):
        if self.progress_chapter:
            self.progress_chapter(current, total)

    def on_image_progress(self, current: int, total: int):
        if self.progress_image:
            self.progress_image(current, total)


def get_requested_max(chapters_spec: str) -> int:
    requested_max = 0
    for part in chapters_spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                s, e = map(int, part.split('-'))
                requested_max = max(requested_max, e)
            except:
                pass
        else:
            try:
                ch = int(part)
                requested_max = max(requested_max, ch)
            except:
                pass
    return requested_max


def download_book(
    url: str,
    chapters_spec: str,
    login: Optional[str] = None,
    password: Optional[str] = None,
    target_dir: Optional[str] = None,
    force: bool = False,
    ignore_image_errors: bool = False,
    ignore_errors: bool = False,
    workers: int = 2,
    image_workers: int = 2,
    image_retries: int = 3,
    image_timeout: int = 30,
    slow_image_timeout: int = 120,
    proxy_file: Optional[str] = None,
    debug: bool = False,
    stop_event: Optional[threading.Event] = None,
    callbacks: Optional[DownloadCallbacks] = None,
    rebuild_only: bool = False,
) -> Tuple[bool, str]:
    if callbacks is None:
        callbacks = DownloadCallbacks()

    settings = load_settings()
    debug = settings.get("debug_mode", False)
    progress_step = settings.get("progress_step", 1)

    if debug:
        callbacks.on_log("🔍 Включён режим отладки (подробные сообщения)")

    try:
        callbacks.on_log("🚀 Начало загрузки книги")

        # Авторизация
        if not login or not password:
            l, p = load_auth()
            login = login or l
            password = password or p
        if debug:
            callbacks.on_log(f"DEBUG: логин установлен: {login[:3]}...")

        # Целевая папка
        if target_dir:
            data_dir = Path(target_dir)
        else:
            folder_name = slugify(url.rstrip("/").split("/")[-1])
            data_dir = Path(NOVELS_BASE) / folder_name
        data_dir.mkdir(parents=True, exist_ok=True)
        if debug:
            callbacks.on_log(f"DEBUG: целевая папка = {data_dir}")

        # Инициализация кэша
        cache = ChapterCache(data_dir)
        if cache.cache_type == "sqlite" and not (data_dir / "cache.db").exists():
            callbacks.on_log("🔄 Перенос существующих JSON-глав в SQLite...")
            cache.migrate_from_json()
            callbacks.on_log("✅ Миграция завершена")

        # Метаданные
        title, author, cover_url, synopsis, chapters = get_novel_metadata(
            url, None, data_dir, force, callbacks
        )
        if debug:
            callbacks.on_log(f"DEBUG: метаданные получены, глав в кэше: {len(chapters)}")

        if not chapters:
            return False, "Нет глав"

        # Парсинг спецификации глав
        try:
            selected_numbers = parse_chapters_spec(chapters_spec, len(chapters), log_func=callbacks.on_log)
        except Exception as e:
            callbacks.on_log(f"❌ Ошибка парсинга: {e}")
            return False, str(e)

        if not selected_numbers:
            return False, "Не выбрано ни одной главы"

        callbacks.on_log(f"🔢 Выбрано глав для загрузки: {len(selected_numbers)}")

        # ========== REBUILD ONLY ==========
        if rebuild_only:
            callbacks.on_log("🔧 Режим пересборки EPUB из кэша (без загрузки)")
            loaded = []
            for idx in selected_numbers:
                cached = cache.load_chapter(idx)
                if cached:
                    loaded.append((idx, cached["title"], cached["body"], cached.get("images", {})))
                else:
                    callbacks.on_log(f"⚠️ Глава {idx} отсутствует в кэше, пропускаем")
            if not loaded:
                return False, "Нет загруженных глав в кэше"
            loaded.sort(key=lambda x: x[0])
            # Пропускаем всё, что ниже (создание краулеров, загрузку глав), сразу идём к сборке EPUB
        else:
            # ========== ОБЫЧНЫЙ РЕЖИМ (с загрузкой) ==========
            # Автообновление метаданных, если запрошено больше глав
            requested_max = get_requested_max(chapters_spec)
            if requested_max > len(chapters) and not force:
                callbacks.on_log(f"⚠️ Обнаружены новые главы...")
                # Для обновления нужен краулер, создадим временный
                temp_crawler = create_crawler(login, password, proxy_file, debug, timeout=image_timeout)
                try:
                    temp_crawler.novel_url = url
                    for attempt in range(3):
                        try:
                            temp_crawler.read_novel_info()
                            break
                        except Exception as e:
                            callbacks.on_log(f"⚠️ Ошибка обновления (попытка {attempt+1}): {e}")
                            if attempt == 2:
                                raise
                            time.sleep(5)
                    title = temp_crawler.novel_title or title
                    author = temp_crawler.novel_author or "Неизвестен"
                    cover_url = temp_crawler.novel_cover
                    synopsis = temp_crawler.novel_synopsis or synopsis
                    chapters = temp_crawler.chapters
                    save_metadata(data_dir, title, author, cover_url, synopsis, chapters)
                    callbacks.on_log(f"✅ Метаданные обновлены. Теперь глав: {len(chapters)}")
                except Exception as e:
                    callbacks.on_log(f"❌ Не удалось обновить метаданные: {e}")

            # Создаём пул краулеров
            callbacks.on_log(f"🔧 Создание пула из {workers} краулеров...")
            master_crawler = create_crawler(login, password, proxy_file, debug, timeout=image_timeout)
            crawler_pool = [master_crawler]
            for _ in range(workers - 1):
                try:
                    clone = clone_crawler(master_crawler, debug)
                    crawler_pool.append(clone)
                except Exception as e:
                    if debug:
                        callbacks.on_log(f"DEBUG: клонирование не удалось ({e}), создаём нового")
                    crawler_pool.append(create_crawler(login, password, proxy_file, debug, timeout=image_timeout))
            callbacks.on_log("✅ Пул краулеров готов")

            selected_chapters = [chapters[i-1] for i in selected_numbers]
            total = len(selected_numbers)
            loaded = []
            completed = 0
            start_time = time.time()

            pool_lock = threading.Lock()
            pool_index = 0
            def get_next_crawler():
                nonlocal pool_index
                with pool_lock:
                    c = crawler_pool[pool_index]
                    pool_index = (pool_index + 1) % len(crawler_pool)
                return c

            with tqdm(total=total, desc="📥 Загрузка глав", unit="гл", disable=not debug) as pbar:
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = []
                    for idx, ch in zip(selected_numbers, selected_chapters):
                        if stop_event and stop_event.is_set():
                            callbacks.on_log("⚠️ Остановка по требованию пользователя")
                            break
                        crawler = get_next_crawler()
                        fut = executor.submit(
                            download_one_chapter,
                            crawler, data_dir, force,
                            idx, ch, callbacks, pbar,
                            debug_flag=debug,
                            use_selenium_fallback=settings.get("use_selenium_fallback", True),
                            login=login, password=password,
                            stop_event=stop_event
                        )
                        futures.append((idx, fut))

                    for idx, fut in futures:
                        if stop_event and stop_event.is_set():
                            for _, f in futures:
                                f.cancel()
                            break
                        result = fut.result()
                        if result:
                            loaded.append(result)
                        completed += 1
                        if completed % progress_step == 0 or completed == total:
                            callbacks.on_chapter_progress(completed, total)

            elapsed = time.time() - start_time
            successful = len(loaded)
            failed = total - successful
            callbacks.on_log(f"📊 Статистика загрузки глав: ✅ {successful}, ⚠️ {failed}, ⏱️ {elapsed:.1f} сек")

            if failed > 0 and not ignore_errors:
                return False, "Некоторые главы не загружены, создание EPUB отменено"
            if not loaded:
                return False, "Нет загруженных глав"

            loaded.sort(key=lambda x: x[0])
            if debug:
                callbacks.on_log(f"DEBUG: отсортировано {len(loaded)} глав")

        # ========== ОБЩАЯ ЧАСТЬ (сборка EPUB) ==========
        # Сбор всех изображений из глав
        all_images = {}
        for _, _, _, images in loaded:
            all_images.update(images)
        if debug:
            callbacks.on_log(f"DEBUG: собрано {len(all_images)} уникальных изображений")

        # Обработка синопсиса (для rebuild_only нужно иметь краулер? но синопсис уже в кэше)
        # Если rebuild_only, то используем `None` как краулер, но process_synopsis может его не требовать, если синопсис уже закэширован.
        # Упростим: передадим None и надеемся, что process_synopsis не будет вызывать сайт.
        crawler_for_synopsis = None if rebuild_only else master_crawler
        synopsis, images_from_synopsis = process_synopsis(crawler_for_synopsis, data_dir, title, synopsis, force, callbacks, debug=debug)
        all_images.update(images_from_synopsis)
        if debug:
            callbacks.on_log(f"DEBUG: после добавления синопсиса всего изображений: {len(all_images)}")

        # Скачивание изображений (если есть)
        rename_map, used_images, url_to_new_name = {}, [], {}
        if all_images:
            if rebuild_only:
                # В режиме пересборки не скачиваем, а строим rename_map из существующих файлов
                images_dir = data_dir / "images"
                if images_dir.exists():
                    for img_hash, url in all_images.items():
                        # Ищем файл с таким же хешем (любое расширение)
                        matched = list(images_dir.glob(f"{img_hash}.*"))
                        if matched:
                            new_name = matched[0].name
                            rename_map[img_hash] = new_name
                            url_to_new_name[url] = new_name
                    used_images = list(rename_map.values())
                    if debug:
                        callbacks.on_log(f"DEBUG: из существующих файлов получено rename_map: {len(rename_map)}")
                else:
                    callbacks.on_log("⚠️ Папка images не найдена, изображения не будут добавлены")
            else:
                # Обычный режим – скачиваем
                rename_map, used_images, url_to_new_name = download_and_rename_images(
                    master_crawler, all_images, data_dir, callbacks,
                    image_workers, image_retries, image_timeout,
                    slow_image_timeout, debug, ignore_image_errors
                )
                if debug:
                    callbacks.on_log(f"DEBUG: rename_map = {rename_map}")
                    callbacks.on_log(f"DEBUG: url_to_new_name = {url_to_new_name}")

        # Замена меток в главах
        loaded = replace_image_markers(data_dir, loaded, rename_map, callbacks, debug=debug)

        # Обновление синопсиса
        if synopsis and url_to_new_name:
            new_synopsis = synopsis
            for url, new_name in url_to_new_name.items():
                new_synopsis = new_synopsis.replace(f'src="{url}"', f'src="images/{new_name}"')
                new_synopsis = new_synopsis.replace(f"src='{url}'", f'src="images/{new_name}"')
                new_synopsis = new_synopsis.replace(url, f'images/{new_name}')
            if new_synopsis != synopsis:
                synopsis = new_synopsis
                save_synopsis_cache(data_dir, synopsis, images_from_synopsis)
                callbacks.on_log("✅ Ссылки на изображения в синопсисе заменены")
            else:
                callbacks.on_log("⚠️ В синопсисе не найдено ни одного URL для замены")
        else:
            if not synopsis:
                callbacks.on_log("ℹ️ Синопсис пуст")
            elif not url_to_new_name:
                callbacks.on_log("ℹ️ Нет соответствий URL для замены в синопсисе")

        if synopsis:
            update_db_synopsis(data_dir, synopsis, callbacks)

        # Загрузка обложки
        cover_data = None
        cover_path = data_dir / "cover.jpg"
        if cover_url:
            if cover_path.exists():
                with open(cover_path, "rb") as f:
                    cover_data = f.read()
                callbacks.on_log("🖼️ Обложка уже есть")
            else:
                if not rebuild_only:
                    callbacks.on_log("🖼️ Скачивание обложки...")
                    from scripts.download_cover import download_cover
                    # Для скачивания нужна сессия. Если нет краулера, создадим временный
                    session = getattr(master_crawler, 'session', None) if not rebuild_only else None
                    if session is None and rebuild_only:
                        # Пытаемся взять сессию из первого краулера, если он есть
                        if 'master_crawler' in locals():
                            session = getattr(master_crawler, 'session', None)
                    if session is None:
                        import requests
                        session = requests.Session()
                    if download_cover(cover_url, cover_path, session):
                        with open(cover_path, "rb") as f:
                            cover_data = f.read()
                        callbacks.on_log("✅ Обложка загружена")
                    else:
                        callbacks.on_log("⚠️ Не удалось скачать обложку")
                else:
                    callbacks.on_log("⚠️ Обложка не найдена в кэше и пропущена в режиме пересборки")
        else:
            callbacks.on_log("ℹ️ Обложка не найдена")

        # Сборка EPUB
        out_path = build_epub_file(data_dir, title, author, synopsis, loaded, cover_data, used_images, callbacks, debug=debug)

        cache.close()
        if proxy_file and not rebuild_only:
            from scripts.proxy import stop_proxy_fetcher
            stop_proxy_fetcher()

        return True, str(out_path)

    except Exception as e:
        import traceback
        error_msg = f"КРИТИЧЕСКАЯ ОШИБКА: {e}\n{traceback.format_exc()}"
        callbacks.on_log(error_msg)
        return False, error_msg