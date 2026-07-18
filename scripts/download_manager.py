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
from gui.database import get_novel_by_target_dir, STATUS_COMPLETED, STATUS_DROPPED_BY_AUTHOR, STATUS_DROPPED_BY_TRANSLATOR, STATUS_IN_PROGRESS
import re

class DownloadCallbacks:
    def __init__(self, log_callback=None, progress_chapter_callback=None,
                 progress_image_callback=None, cloudflare_callback=None,
                 cloudflare_event=None):
        self.log = log_callback or print
        self.progress_chapter = progress_chapter_callback
        self.progress_image = progress_image_callback
        self.cloudflare_callback = cloudflare_callback
        self.cloudflare_event = cloudflare_event

    def on_log(self, msg: str):
        self.log(msg)

    def on_chapter_progress(self, current: int, total: int):
        if self.progress_chapter:
            self.progress_chapter(current, total)

    def on_image_progress(self, current: int, total: int):
        if self.progress_image:
            self.progress_image(current, total)

    def on_cloudflare_block(self):
        if self.cloudflare_callback:
            self.cloudflare_callback()


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

def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()


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

    effective_workers = workers
    effective_image_workers = image_workers
    is_ranobes = 'ranobes.com' in url
    if is_ranobes:
        effective_workers = 1
        effective_image_workers = 1
        callbacks.on_log("🔒 Обнаружен ranobes.com – принудительный однопоточный режим для глав и изображений")

    if debug:
        callbacks.on_log("🔍 Включён режим отладки (подробные сообщения)")

    master_crawler = None
    cache = None
    try:
        callbacks.on_log("🚀 Начало загрузки книги")

        if not login or not password:
            l, p = load_auth()
            login = login or l
            password = password or p

        if target_dir:
            data_dir = Path(target_dir)
        else:
            folder_name = slugify(url.rstrip("/").split("/")[-1])
            data_dir = Path(NOVELS_BASE) / folder_name
        data_dir.mkdir(parents=True, exist_ok=True)

        novel_info = get_novel_by_target_dir(str(data_dir))
        status = novel_info.get("status", STATUS_IN_PROGRESS) if novel_info else STATUS_IN_PROGRESS
        last_read_chapter = novel_info.get("last_read_chapter", 0) if novel_info else 0

        cache = ChapterCache(data_dir)
        if cache.cache_type == "sqlite" and not (data_dir / "cache.db").exists():
            callbacks.on_log("🔄 Перенос существующих JSON-глав в SQLite...")
            cache.migrate_from_json()
            callbacks.on_log("✅ Миграция завершена")

        if cache.cache_type == "sqlite":
            cache.clear_drafts()

        title, author, cover_url, synopsis, chapters = get_novel_metadata(
            url, None, data_dir, force, callbacks
        )
        original_title = title

        if not chapters:
            return False, "Нет глав"

        selected_numbers = parse_chapters_spec(chapters_spec, len(chapters), log_func=callbacks.on_log)
        if not selected_numbers:
            return False, "Не выбрано ни одной главы"

        callbacks.on_log(f"🔢 Выбрано глав для загрузки: {len(selected_numbers)}")

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
        else:
            requested_max = get_requested_max(chapters_spec)
            if requested_max > len(chapters) and not force:
                callbacks.on_log(f"⚠️ Обнаружены новые главы (запрошено до {requested_max}, в кэше {len(chapters)})...")
                temp_crawler = create_crawler(url, login, password, proxy_file, debug, timeout=image_timeout)
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
                    save_metadata(data_dir, original_title, author, cover_url, synopsis, chapters)
                    callbacks.on_log(f"✅ Метаданные обновлены. Теперь глав: {len(chapters)}")
                    selected_numbers = parse_chapters_spec(chapters_spec, len(chapters), log_func=callbacks.on_log)
                    if not selected_numbers:
                        return False, "После обновления не выбрано ни одной главы"
                    callbacks.on_log(f"🔢 После обновления выбрано глав: {len(selected_numbers)}")
                except Exception as e:
                    callbacks.on_log(f"❌ Не удалось обновить метаданные: {e}")

            callbacks.on_log(f"🔧 Создание пула из {effective_workers} краулеров...")
            master_crawler = create_crawler(url, login, password, proxy_file, debug, timeout=image_timeout)
            if hasattr(master_crawler, '_use_selenium'):
                master_crawler._use_selenium = True
                master_crawler._ensure_driver()   # инициализация драйвера для ранобеса

            crawler_pool = [master_crawler]
            for _ in range(effective_workers - 1):
                try:
                    clone = clone_crawler(master_crawler, debug)
                    if hasattr(clone, '_use_selenium'):
                        clone._use_selenium = True
                        clone._ensure_driver()
                    crawler_pool.append(clone)
                except Exception as e:
                    if debug:
                        callbacks.on_log(f"DEBUG: клонирование не удалось ({e}), создаём нового")
                    new_crawler = create_crawler(url, login, password, proxy_file, debug, timeout=image_timeout)
                    if hasattr(new_crawler, '_use_selenium'):
                        new_crawler._use_selenium = True
                        new_crawler._ensure_driver()
                    crawler_pool.append(new_crawler)
            callbacks.on_log("✅ Пул краулеров готов")

            selected_chapters = [chapters[i-1] for i in selected_numbers]
            total = len(selected_numbers)
            loaded = []
            chapters_to_save = []
            completed = 0
            start_time = time.time()
            batch_size = settings.get("cache_batch_size", 100)
            saved_indices = []

            pool_lock = threading.Lock()
            pool_index = 0

            def make_get_next(pool):
                idx = 0
                def get_next():
                    nonlocal idx
                    with pool_lock:
                        c = pool[idx]
                        idx = (idx + 1) % len(pool)
                    return c
                return get_next

            get_next_crawler = make_get_next(crawler_pool)

            with tqdm(total=total, desc="📥 Загрузка глав", unit="гл", disable=not debug) as pbar:
                with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
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
                            stop_event=stop_event,
                            cache=cache,   # теперь безопасно благодаря check_same_thread=False + lock
                        )
                        futures.append((idx, ch, fut))

                    for idx, ch, fut in futures:
                        if stop_event and stop_event.is_set():
                            break
                        try:
                            result = fut.result()
                        except Exception as e:
                            callbacks.on_log(f"❌ Глава {idx}: необработанное исключение при загрузке: {e}")
                            if debug:
                                import traceback
                                callbacks.on_log(traceback.format_exc())
                            result = None

                        if result:
                            loaded.append(result)
                            chapters_to_save.append((idx, result[1], ch["url"], result[2], result[3]))
                            if len(chapters_to_save) >= batch_size:
                                for sidx, title, url, body, images in chapters_to_save:
                                    cache.save_chapter(sidx, title, url, body, images, status=0)
                                cache.commit()
                                indices = [item[0] for item in chapters_to_save]
                                cache.commit_chapters(indices)
                                saved_indices.extend(indices)
                                if debug:
                                    callbacks.on_log(f"DEBUG: сохранено и подтверждено {len(indices)} глав (пакет {batch_size})")
                                chapters_to_save = []
                            completed += 1
                            if completed % progress_step == 0 or completed == total:
                                callbacks.on_chapter_progress(completed, total)
                        else:
                            # Глава не загрузилась
                            if is_ranobes and callbacks.cloudflare_event:
                                # Сохраняем накопленные главы перед паузой
                                if chapters_to_save:
                                    for sidx, title, url, body, images in chapters_to_save:
                                        cache.save_chapter(sidx, title, url, body, images, status=0)
                                    cache.commit()
                                    indices = [item[0] for item in chapters_to_save]
                                    cache.commit_chapters(indices)
                                    saved_indices.extend(indices)
                                    callbacks.on_log(f"💾 Сохранено {len(indices)} глав перед ожиданием Cloudflare")
                                    chapters_to_save = []

                                callbacks.on_log(f"🛑 Cloudflare заблокировал главу {idx}. Ожидание ручной проверки...")
                                callbacks.cloudflare_event.clear()
                                callbacks.on_cloudflare_block()
                                callbacks.on_log("⏳ Ожидание нажатия «Продолжить»...")
                                callbacks.cloudflare_event.wait()
                                callbacks.cloudflare_event.clear()

                                callbacks.on_log("🔄 Пересоздание сессии (cookies сохранены)...")
                                master_crawler = create_crawler(url, login, password, proxy_file, debug, timeout=image_timeout)
                                if hasattr(master_crawler, '_use_selenium'):
                                    master_crawler._use_selenium = True
                                    master_crawler._ensure_driver()

                                crawler_pool = [master_crawler]
                                for _ in range(effective_workers - 1):
                                    clone = clone_crawler(master_crawler, debug)
                                    if hasattr(clone, '_use_selenium'):
                                        clone._use_selenium = True
                                        clone._ensure_driver()
                                    crawler_pool.append(clone)

                                get_next_crawler = make_get_next(crawler_pool)

                                callbacks.on_log(f"🔄 Повторная загрузка главы {idx}...")
                                retry_crawler = get_next_crawler()
                                retry_result = download_one_chapter(
                                    retry_crawler, data_dir, force,
                                    idx, ch, callbacks, pbar,
                                    debug_flag=debug,
                                    use_selenium_fallback=False,
                                    login=login, password=password,
                                    stop_event=stop_event
                                )
                                if retry_result:
                                    loaded.append(retry_result)
                                    chapters_to_save.append((idx, retry_result[1], ch["url"], retry_result[2], retry_result[3]))
                                    if len(chapters_to_save) >= batch_size:
                                        for sidx, title, url, body, images in chapters_to_save:
                                            cache.save_chapter(sidx, title, url, body, images, status=0)
                                        cache.commit()
                                        indices = [item[0] for item in chapters_to_save]
                                        cache.commit_chapters(indices)
                                        saved_indices.extend(indices)
                                        if debug:
                                            callbacks.on_log(f"DEBUG: сохранено и подтверждено {len(indices)} глав (пакет {batch_size})")
                                        chapters_to_save = []
                                    completed += 1
                                    if completed % progress_step == 0 or completed == total:
                                        callbacks.on_chapter_progress(completed, total)
                                else:
                                    callbacks.on_log(f"❌ Глава {idx} не загружена даже после пересоздания сессии")
                                    completed += 1
                            else:
                                callbacks.on_log(f"⚠️ Глава {idx} не загружена")
                                completed += 1

            if chapters_to_save:
                for sidx, title, url, body, images in chapters_to_save:
                    cache.save_chapter(sidx, title, url, body, images, status=0)
                cache.commit()
                indices = [item[0] for item in chapters_to_save]
                cache.commit_chapters(indices)
                saved_indices.extend(indices)

            elapsed = time.time() - start_time
            successful = len(loaded)
            failed = total - successful
            callbacks.on_log(f"📊 Статистика загрузки глав: ✅ {successful}, ⚠️ {failed}, ⏱️ {elapsed:.1f} сек")

            if failed > 0 and not ignore_errors:
                return False, "Некоторые главы не загружены, создание EPUB отменено"
            if not loaded:
                return False, "Нет загруженных глав"

            loaded.sort(key=lambda x: x[0])

        # === Сборка EPUB (без изменений) ===
        all_images = {}
        for _, _, _, images in loaded:
            all_images.update(images)

        crawler_for_synopsis = None if rebuild_only else master_crawler
        synopsis, images_from_synopsis = process_synopsis(crawler_for_synopsis, data_dir, original_title, synopsis, force, callbacks, debug=debug)
        if not images_from_synopsis and synopsis:
            from scripts.synopsis_handler import load_synopsis_cache
            _, images_from_synopsis = load_synopsis_cache(data_dir)
        all_images.update(images_from_synopsis)

        rename_map, used_images, url_to_new_name = {}, [], {}
        if all_images:
            if rebuild_only:
                images_dir = data_dir / "images"
                if images_dir.exists():
                    for img_hash, url in all_images.items():
                        matched = list(images_dir.glob(f"{img_hash}.*"))
                        if matched:
                            new_name = matched[0].name
                            rename_map[img_hash] = new_name
                            url_to_new_name[url] = new_name
                    used_images = list(rename_map.values())
            else:
                rename_map, used_images, url_to_new_name = download_and_rename_images(
                    master_crawler, all_images, data_dir, callbacks,
                    effective_image_workers, image_retries, image_timeout,
                    slow_image_timeout, debug, ignore_image_errors
                )

        if synopsis and url_to_new_name:
            new_synopsis = synopsis
            for url, new_name in url_to_new_name.items():
                new_synopsis = new_synopsis.replace(f'src="{url}"', f'src="images/{new_name}"')
                new_synopsis = new_synopsis.replace(f"src='{url}'", f'src="images/{new_name}"')
                new_synopsis = new_synopsis.replace(url, f'images/{new_name}')
            if new_synopsis != synopsis:
                synopsis = new_synopsis
                save_synopsis_cache(data_dir, synopsis, images_from_synopsis)
        if synopsis:
            update_db_synopsis(data_dir, synopsis, callbacks)

        cover_data = None
        cover_path = data_dir / "cover.jpg"
        if cover_url:
            if cover_path.exists():
                with open(cover_path, "rb") as f:
                    cover_data = f.read()
            elif not rebuild_only:
                from scripts.download_cover import download_cover
                session = getattr(master_crawler, 'session', None) or requests.Session()
                if download_cover(cover_url, cover_path, session):
                    with open(cover_path, "rb") as f:
                        cover_data = f.read()

        if rename_map:
            for i, (idx, ch_title, content, images) in enumerate(loaded):
                new_content = content
                for hash_val, new_name in rename_map.items():
                    marker = f"[[IMG:{hash_val}]]"
                    if marker in new_content:
                        img_tag = f'<img src="images/{new_name}" style="max-width:100%; display:block; margin:1em auto;" alt="иллюстрация" />'
                        new_content = new_content.replace(marker, img_tag)
                loaded[i] = (idx, ch_title, new_content, images)

        leftover_pattern = re.compile(r'\[\[IMG:[0-9a-fA-F]+\]\]')
        for i, (idx, ch_title, content, images) in enumerate(loaded):
            new_content, count = leftover_pattern.subn('', content)
            if count:
                loaded[i] = (idx, ch_title, new_content, images)

        out_path = build_epub_file(data_dir, original_title, author, synopsis, loaded, cover_data, used_images, callbacks, debug=debug)

        if out_path and out_path.exists():
            name_for_file = original_title if original_title else title
            from scripts.epub_naming import build_final_epub_name
            new_name = build_final_epub_name(out_path, status, name_for_file, loaded, last_read_chapter)
            if new_name and new_name != out_path.name:
                new_path = out_path.parent / new_name
                counter = 1
                while new_path.exists():
                    stem = re.sub(r'(_\d+)$', '', new_path.stem)
                    new_path = new_path.with_name(f"{stem}_{counter}{out_path.suffix}")
                    counter += 1
                out_path.rename(new_path)
                out_path = new_path

        return True, str(out_path)

    except Exception as e:
        import traceback
        error_msg = f"КРИТИЧЕСКАЯ ОШИБКА: {e}\n{traceback.format_exc()}"
        callbacks.on_log(error_msg)
        return False, error_msg
    finally:
        if proxy_file and not rebuild_only:
            from scripts.proxy import stop_proxy_fetcher
            stop_proxy_fetcher()
        if cache is not None:
            cache.close()