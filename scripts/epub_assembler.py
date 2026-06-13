# scripts/epub_assembler.py

import re
import sqlite3
from pathlib import Path
from ebooklib import epub

from scripts.epub_builder import build_epub
from scripts.image_downloader import download_all_images
from scripts.synopsis_handler import (
    process_synopsis_images,
    load_synopsis_cache,
    save_synopsis_cache,
    ensure_image_in_synopsis,
)
from scripts.chapter_cache import ChapterCache
from scripts.paths import DB_PATH


def process_synopsis(crawler, data_dir, title, synopsis, force, callbacks, debug=False):
    if not synopsis:
        return synopsis, {}
    if callbacks:
        callbacks.on_log("📄 Обработка синопсиса...")
    if debug:
        callbacks.on_log(f"DEBUG: исходный синопсис (первые 200 символов): {synopsis[:200]}...")
    cached_synopsis, cached_images = load_synopsis_cache(data_dir)
    if cached_synopsis and not force:
        synopsis = cached_synopsis
        images_from_synopsis = cached_images
        if callbacks:
            callbacks.on_log("✅ Синопсис загружен из кэша")
        if debug:
            callbacks.on_log(f"DEBUG: синопсис из кэша: {len(synopsis)} символов, изображений: {len(images_from_synopsis)}")
    else:
        if debug:
            callbacks.on_log("DEBUG: обрабатываю синопсис с сайта...")
        synopsis, images_from_synopsis = process_synopsis_images(crawler, synopsis, data_dir)
        save_synopsis_cache(data_dir, synopsis, images_from_synopsis)
        if callbacks:
            callbacks.on_log("✅ Синопсис обработан")
        if debug:
            callbacks.on_log(f"DEBUG: синопсис после обработки: {len(synopsis)} символов, изображений: {len(images_from_synopsis)}")
    if not synopsis.strip().startswith("<h1>"):
        synopsis = f"<h1>{title}</h1>\n" + synopsis
    return synopsis, images_from_synopsis


def download_and_rename_images(crawler, all_images, data_dir, callbacks,
                               image_workers, image_retries, image_timeout,
                               slow_image_timeout, debug, ignore_image_errors):
    """
    Скачивает изображения, возвращает:
    rename_map: {хеш: новое_имя_файла}
    used_images: список новых имён
    url_to_new_name: {оригинальный_URL: новое_имя}
    """
    # Всегда возвращаем три значения, даже если all_images пуст
    if not all_images:
        return {}, [], {}

    if callbacks:
        callbacks.on_log(f"📸 Скачивание изображений (всего: {len(all_images)})")

    total_images = len(all_images)
    processed = 0

    def image_progress(old_fn, new_fn, error):
        nonlocal processed
        processed += 1
        if callbacks:
            callbacks.on_image_progress(processed, total_images)

    rename_map, failed_images = download_all_images(
        crawler,
        all_images,
        data_dir / "images",
        max_workers=image_workers,
        max_retries=image_retries,
        default_timeout=image_timeout,
        slow_timeout=slow_image_timeout,
        debug=debug,
        progress_callback=image_progress,
    )

    if callbacks:
        callbacks.on_log(f"   Успешно: {len(rename_map)}, не удалось: {len(failed_images)}")

    if failed_images and not ignore_image_errors:
        raise Exception(f"Не удалось загрузить {len(failed_images)} изображений")

    # Строим url_to_new_name: ключ – оригинальный URL, значение – новое имя файла
    url_to_new_name = {}
    for hash_val, url in all_images.items():  # all_images = {хеш: URL}
        new_name = rename_map.get(hash_val)
        if new_name:
            url_to_new_name[url] = new_name
        elif debug:
            callbacks.on_log(f"DEBUG: не найдено новое имя для хеша {hash_val} (URL: {url})")

    if debug:
        callbacks.on_log(f"DEBUG: url_to_new_name содержит {len(url_to_new_name)} записей")

    return rename_map, list(rename_map.values()), url_to_new_name

def replace_image_markers(data_dir, loaded, rename_map, callbacks, debug=False):
    """Заменяет текстовые метки [[IMG:хеш]] на теги <img>, сохраняя изменения через ChapterCache."""
    if not rename_map:
        return loaded

    if callbacks:
        callbacks.on_log("🔄 Замена меток на изображения в главах...")
    if debug:
        callbacks.on_log(f"DEBUG: rename_map размером {len(rename_map)}")

    from scripts.chapter_cache import ChapterCache
    cache = ChapterCache(data_dir)

    new_loaded = []
    for idx, ch_title, content, images in loaded:
        new_content = content
        replaced = 0
        for hash_val, new_name in rename_map.items():
            marker = f"[[IMG:{hash_val}]]"
            if marker in new_content:
                img_tag = f'<img src="images/{new_name}" style="max-width:100%; display:block; margin:1em auto;" alt="иллюстрация" />'
                new_content = new_content.replace(marker, img_tag)
                replaced += 1
                if debug:
                    callbacks.on_log(f"      DEBUG: глава {idx}: заменена метка {hash_val} -> {new_name}")
        if replaced and debug:
            callbacks.on_log(f"      DEBUG: в главе {idx} заменено {replaced} меток")
        if new_content != content:
            # Сохраняем изменения в кэше
            cached = cache.load_chapter(idx)
            if cached:
                cached["body"] = new_content
                cache.save_chapter(idx, cached["title"], cached["url"], new_content, cached["images"])
            else:
                # Запасной вариант – сохраняем напрямую
                cache.save_chapter(idx, ch_title, "", new_content, images)
        new_loaded.append((idx, ch_title, new_content, images))
    return new_loaded


def update_db_synopsis(data_dir, synopsis, callbacks):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM novels WHERE target_dir = ?", (str(data_dir),))
        row = c.fetchone()
        if row:
            c.execute("UPDATE novels SET synopsis = ? WHERE id = ?", (synopsis, row[0]))
            conn.commit()
            if callbacks:
                callbacks.on_log(f"✅ Синопсис обновлён в БД для книги ID={row[0]}")
        conn.close()
    except Exception as e:
        if callbacks:
            callbacks.on_log(f"⚠️ Не удалось обновить синопсис в БД: {e}")


def build_epub_file(data_dir, title, author, synopsis, loaded, cover_data, used_images, callbacks, debug=False):
    if callbacks:
        callbacks.on_log("📚 Сборка EPUB...")
    if debug:
        callbacks.on_log(f"DEBUG: used_images = {used_images[:5] if used_images else []}...")
    if loaded:
        first_idx = loaded[0][0]
        last_title = loaded[-1][1]
        safe_title = re.sub(r'[\\/*?:"<>|]', '', last_title).strip()
        if len(safe_title) > 100:
            safe_title = safe_title[:100]
        if not safe_title:
            safe_title = "last_chapter"
        out_fname = f"{first_idx} - {safe_title}.epub"
    else:
        out_fname = f"{title}.epub"
    out_path = data_dir / out_fname
    original_path = out_path
    counter = 1
    while out_path.exists():
        stem = original_path.stem
        out_fname = f"{stem}_{counter}.epub"
        out_path = data_dir / out_fname
        counter += 1
    chapters_for_epub = [(idx, ch_title, content) for idx, ch_title, content, _ in loaded]
    book = build_epub(data_dir, title, author, synopsis, chapters_for_epub, cover_data, used_images)
    epub.write_epub(str(out_path), book, {})
    if callbacks:
        callbacks.on_log(f"✅ EPUB создан: {out_path}")
    return out_path