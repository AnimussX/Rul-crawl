#!/data/data/com.termux/files/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import argparse
import time
import atexit
import shutil
import concurrent.futures
from functools import partial
from pathlib import Path

from ebooklib import epub
from bs4 import BeautifulSoup

try:
    from tqdm import tqdm
except ImportError:
    print("⚠️ Библиотека tqdm не установлена. Установите: pip install tqdm")
    sys.exit(1)

from scripts.auth import load_auth
from scripts.rulate import RulateCrawler
from scripts.download_cover import download_cover
from scripts.transliterate import slugify

from scripts.chapter_cache import get_chapter_file, save_chapter_json, load_chapter_json
from scripts.chapter_cleaner import clean_chapter_html
from scripts.image_downloader import download_all_images
from scripts.synopsis_handler import (
    process_synopsis_images,
    load_synopsis_cache,
    save_synopsis_cache,
    add_base_tag_to_html,
    ensure_image_in_synopsis
)
from scripts.epub_builder import build_epub
from scripts.metadata import save_metadata, load_metadata

from scripts.proxy import load_proxies, get_a_proxy, start_proxy_fetcher, stop_proxy_fetcher, remove_faulty_proxies

# Для обновления базы данных
from gui.config import DB_PATH
import sqlite3

STORAGE = os.path.expanduser("~/storage/shared/lncrawl")
NOVELS_BASE = os.path.join(STORAGE, "Novelsbase")
os.makedirs(NOVELS_BASE, exist_ok=True)


class Tee:
    def __init__(self, filename):
        self.file = open(filename, 'w', encoding='utf-8')
        self.stdout = sys.stdout

    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)
        self.file.flush()

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()


def debug_print(msg, debug):
    if debug:
        print(msg)


def parse_chapters_spec(chapters_spec, total_chapters):
    if not chapters_spec:
        return list(range(1, total_chapters + 1))

    selected = set()
    parts = chapters_spec.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-')
            try:
                s = int(start.strip())
                e = int(end.strip())
                if s < 1 or e > total_chapters or s > e:
                    raise ValueError
                selected.update(range(s, e + 1))
            except ValueError:
                print(f"❌ Неверный диапазон: {part}")
                sys.exit(1)
        else:
            try:
                ch = int(part)
                if ch < 1 or ch > total_chapters:
                    raise ValueError
                selected.add(ch)
            except ValueError:
                print(f"❌ Неверный номер главы: {part}")
                sys.exit(1)

    return sorted(selected)


def create_crawler(login, password, proxy_file=None, debug=False, use_selenium=False):
    if use_selenium:
        try:
            from scripts.selenium_crawler import SeleniumRulateCrawler
            crawler = SeleniumRulateCrawler(headless=not debug)
            crawler.initialize()
            if login and password:
                try:
                    crawler.login(login, password)
                    print("✅ Авторизация через Selenium выполнена успешно")
                except Exception as e:
                    print(f"⚠️ Ошибка авторизации через Selenium: {e}")
            return crawler
        except ImportError:
            print("❌ Модуль selenium_crawler не найден. Убедитесь, что файл scripts/selenium_crawler.py существует.")
            sys.exit(1)
    else:
        import cloudscraper
        crawler = RulateCrawler()
        crawler.initialize()

        scraper = cloudscraper.create_scraper(
            interpreter='nodejs',
            delay=15,
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
            }
        )
        scraper.headers.update(crawler.session.headers)
        crawler.session = scraper

        if login and password:
            try:
                crawler.login(login, password)
                print("✅ Авторизация выполнена успешно (без прокси)")
            except Exception as e:
                print(f"⚠️ Ошибка авторизации: {e}")

        if proxy_file and os.path.exists(proxy_file):
            load_proxies(proxy_file)
            start_proxy_fetcher()
            atexit.register(stop_proxy_fetcher)

            original_request = scraper.request
            def request_with_proxy(method, url, **kwargs):
                proxy_url = get_a_proxy('https')
                if proxy_url:
                    kwargs['proxies'] = {'http': proxy_url, 'https': proxy_url}
                try:
                    response = original_request(method, url, **kwargs)
                    if response.status_code == 403:
                        remove_faulty_proxies(proxy_url)
                        debug_print(f"   ⚠️ Прокси {proxy_url} получил 403, помечен как нерабочий", debug)
                    return response
                except Exception as e:
                    remove_faulty_proxies(proxy_url)
                    debug_print(f"   ⚠️ Ошибка при использовании прокси {proxy_url}: {e}", debug)
                    raise

            scraper.request = request_with_proxy
            debug_print(f"🔁 Ротация прокси включена. Файл: {proxy_file}", debug)

        return crawler


def download_one_chapter(main_crawler, login, password, debug, data_dir, chapters_json_dir, force, idx, ch,
                         pbar=None, use_selenium_fallback=False, selenium_crawler_ref=None):
    json_file = get_chapter_file(chapters_json_dir, idx)
    cached = load_chapter_json(json_file)

    if cached and not force:
        if pbar:
            pbar.set_postfix_str(f"Глава {idx} (кэш)")
            pbar.update(1)
        return (idx, ch['title'], cached['body'], cached.get('images', {}))

    current_crawler = main_crawler
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            start_time = time.time()
            raw_html = current_crawler.download_chapter_body({"url": ch['url']})
            elapsed = time.time() - start_time
            if not raw_html or len(raw_html) < 100:
                raise Exception("Слишком короткий ответ")
            if "Checking your browser" in raw_html:
                raise Exception("Обнаружена страница проверки браузера")

            from lncrawl.models import Chapter
            temp_chapter = Chapter(id=idx)
            temp_chapter.url = ch['url']
            temp_chapter.body = raw_html
            temp_chapter.images = {}
            temp_chapter.title = ch['title']

            current_crawler.output_path = str(data_dir)
            current_crawler.extract_chapter_images(temp_chapter)

            debug_print(f"   📸 Извлечено изображений: {len(temp_chapter.images)}", debug)
            if debug and temp_chapter.images:
                for name, url in list(temp_chapter.images.items())[:3]:
                    debug_print(f"      {name}: {url[:80]}", debug)

            if debug:
                soup_tmp = BeautifulSoup(raw_html, 'lxml')
                img_tags = soup_tmp.find_all('img')
                debug_print(f"   🔍 В raw_html найдено img: {len(img_tags)}", debug)
                for img in img_tags[:3]:
                    src = img.get('src', 'None')
                    debug_print(f"      src: {src[:80]}", debug)

            url_to_name = {url: name for name, url in temp_chapter.images.items()}
            cleaned_html = clean_chapter_html(temp_chapter.body, ch['title'], url_to_name, debug=debug)

            if '<img src="images/' in cleaned_html:
                debug_print(f"   ✅ Глава {idx}: изображения успешно вставлены", debug)
            else:
                debug_print(f"   ⚠️ Глава {idx}: изображения отсутствуют в финальном HTML", debug)

            chapter_data = {
                'id': idx,
                'title': ch['title'],
                'url': ch['url'],
                'body': cleaned_html,
                'images': temp_chapter.images
            }
            save_chapter_json(json_file, chapter_data)

            if pbar:
                pbar.set_postfix_str(f"Глава {idx} ({elapsed:.1f}с)")
                pbar.update(1)
            return (idx, ch['title'], cleaned_html, temp_chapter.images)

        except Exception as e:
            error_str = str(e)
            print(f"❌ Ошибка загрузки главы {idx} (попытка {attempt}): {error_str}")

            if (use_selenium_fallback and current_crawler is main_crawler and
                ("403" in error_str or "Forbidden" in error_str or "доступ запрещён" in error_str.lower())):
                if selenium_crawler_ref and selenium_crawler_ref[0] is None:
                    print(f"   ⚠️ Включаем Selenium fallback для главы {idx}")
                    try:
                        from scripts.selenium_crawler import SeleniumRulateCrawler
                        sel_crawler = SeleniumRulateCrawler(headless=not debug)
                        sel_crawler.initialize()
                        if login and password:
                            try:
                                sel_crawler.login(login, password)
                            except Exception as login_e:
                                print(f"   ⚠️ Ошибка авторизации Selenium: {login_e}")
                        selenium_crawler_ref[0] = sel_crawler
                        current_crawler = sel_crawler
                        continue
                    except ImportError:
                        print("   ❌ Модуль selenium_crawler не найден. Fallback невозможен.")
                elif selenium_crawler_ref and selenium_crawler_ref[0] is not None:
                    current_crawler = selenium_crawler_ref[0]
                    continue

            if attempt == max_attempts:
                if pbar:
                    pbar.set_postfix_str(f"Глава {idx} ошибка")
                    pbar.update(1)
                return None
            else:
                time.sleep(2)
                continue


def main():
    parser = argparse.ArgumentParser(description="Загрузчик книг с tl.rulate.ru")
    parser.add_argument("url")
    parser.add_argument("--chapters", "-c", help="Главы для загрузки. Формат: 1-5,7,10-12")
    parser.add_argument("--login")
    parser.add_argument("--password")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--proxy-file")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--log-file")
    parser.add_argument("--workers", type=int, default=2, help="Количество потоков для глав")
    parser.add_argument("--progress-total", type=int, help="Общее количество глав для прогресса")
    parser.add_argument("--selenium-fallback", action="store_true",
                        help="При ошибке 403 пробовать загрузить главу через Selenium")
    parser.add_argument("--target-dir", help="Явный путь для сохранения временных файлов (переопределяет автоматический)")
    parser.add_argument("--image-workers", type=int, default=2, help="Количество потоков для загрузки изображений")
    parser.add_argument("--image-retries", type=int, default=3, help="Количество попыток загрузки каждого изображения")
    parser.add_argument("--image-timeout", type=int, default=30, help="Таймаут для обычных изображений (сек)")
    parser.add_argument("--slow-image-timeout", type=int, default=120, help="Таймаут для фотохостингов (сек)")
    parser.add_argument("--ignore-errors", action="store_true",
                        help="Продолжить, даже если некоторые главы не загружены (по умолчанию – строго)")
    parser.add_argument("--ignore-image-errors", action="store_true",
                        help="Продолжить, даже если некоторые изображения не загружены")
    args = parser.parse_args()

    if args.log_file:
        tee = Tee(args.log_file)
        sys.stdout = tee
        def restore_stdout():
            sys.stdout = tee.stdout
            tee.close()
        atexit.register(restore_stdout)

    debug = args.debug

    login = args.login
    password = args.password
    if not login or not password:
        l, p = load_auth()
        login = login or l
        password = password or p

    # Создаём обычный краулер (без selenium, если не указан флаг)
    crawler = create_crawler(login, password, args.proxy_file, debug, use_selenium=False)

    metadata = None if args.force else load_metadata(Path(NOVELS_BASE) / slugify(args.url.rstrip('/').split('/')[-1]))

    if metadata:
        title = metadata['title']
        author = metadata['author']
        cover_url = metadata['cover_url']
        synopsis = metadata.get('synopsis')
        chapters = metadata['chapters']
    else:
        crawler.novel_url = args.url
        for attempt in range(3):
            try:
                crawler.read_novel_info()
                break
            except Exception as e:
                print(f"⚠️ Ошибка загрузки (попытка {attempt+1}): {e}")
                if attempt == 2:
                    sys.exit(1)
                time.sleep(5)
        title = crawler.novel_title or "Без названия"
        author = crawler.novel_author or "Неизвестен"
        cover_url = crawler.novel_cover
        synopsis = crawler.novel_synopsis
        chapters = crawler.chapters

    # Определяем целевую папку
    if args.target_dir:
        data_dir = Path(args.target_dir)
    else:
        folder_name = slugify(title)
        data_dir = Path(NOVELS_BASE) / folder_name

    data_dir.mkdir(parents=True, exist_ok=True)

    # Сохраняем метаданные (только если не было загружено из кэша)
    if not metadata:
        save_metadata(data_dir, title, author, cover_url, synopsis, chapters)

    if not chapters:
        print("❌ Нет глав")
        sys.exit(1)

    selected_numbers = parse_chapters_spec(args.chapters, len(chapters))
    selected = [chapters[i-1] for i in selected_numbers]
    total = len(selected)
    print(f"🎯 Выбрано глав: {total} ({min(selected_numbers)}-{max(selected_numbers)})")
    debug_print(f"   Полный список: {selected_numbers}", debug)

    chapters_json_dir = data_dir / "chapters_json"
    chapters_json_dir.mkdir(exist_ok=True)
    cover_path = data_dir / "cover.jpg"

    selenium_crawler_holder = [None]

    loaded = []
    start_time = time.time()

    with tqdm(total=total, desc="📥 Загрузка глав", unit="гл", disable=debug) as pbar:
        download_func = partial(
            download_one_chapter,
            crawler, login, password, debug, data_dir, chapters_json_dir, args.force,
            pbar=pbar,
            use_selenium_fallback=args.selenium_fallback,
            selenium_crawler_ref=selenium_crawler_holder
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_idx = {
                executor.submit(download_func, idx, ch): idx
                for idx, ch in zip(selected_numbers, selected)
            }
            completed = 0
            for future in concurrent.futures.as_completed(future_to_idx):
                result = future.result()
                if result:
                    loaded.append(result)
                completed += 1
                if args.progress_total and args.log_file:
                    with open(args.log_file, 'a') as f:
                        f.write(f"PROGRESS: {completed}/{args.progress_total}\n")

    if selenium_crawler_holder[0] is not None:
        selenium_crawler_holder[0].quit()

    elapsed = time.time() - start_time
    successful = len(loaded)
    failed = total - successful
    avg_speed = successful / elapsed if elapsed > 0 else 0

    print(f"\n📊 Статистика загрузки глав:")
    print(f"   ✅ Успешно: {successful}")
    if failed > 0:
        print(f"   ⚠️ Пропущено: {failed}")
    print(f"   ⏱️ Время: {elapsed:.1f} сек")
    print(f"   🚀 Средняя скорость: {avg_speed:.2f} гл/сек")

    # Проверка целостности – если есть ошибки и не указан флаг игнорирования, завершаемся
    if failed > 0 and not args.ignore_errors:
        print("\n❌ Обнаружены ошибки при загрузке глав. EPUB не будет создан.")
        print("   Используйте --ignore-errors, чтобы пропустить повреждённые главы и создать книгу из успешно загруженных.")
        sys.exit(1)

    if not loaded:
        print("❌ Нет загруженных глав")
        sys.exit(1)

    loaded.sort(key=lambda x: x[0])

    all_images = {}
    for _, _, _, images_dict in loaded:
        all_images.update(images_dict)

    images_from_synopsis = {}
    if synopsis:
        if not debug:
            print("\n📄 Обработка описания...")
        debug_print(f"\n📄 Синопсис до обработки (первые 200 символов):", debug)
        debug_print(synopsis[:200] + "..." if len(synopsis) > 200 else synopsis, debug)

        cached_synopsis, cached_images = load_synopsis_cache(data_dir)
        if cached_synopsis and not args.force:
            print(f"📂 Загружен обработанный синопсис из кэша")
            synopsis = cached_synopsis
            images_from_synopsis = cached_images
        else:
            print("🔄 Обработка изображений в синопсисе...")
            synopsis, images_from_synopsis = process_synopsis_images(crawler, synopsis, data_dir)
            save_synopsis_cache(data_dir, synopsis, images_from_synopsis)
            debug_print(f"📸 Изображений в синопсисе: {len(images_from_synopsis)}", debug)

        all_images.update(images_from_synopsis)

        if not synopsis.strip().startswith('<h1>'):
            title_tag = f'<h1>{title}</h1>\n'
            synopsis = title_tag + synopsis
            debug_print("   ✅ Заголовок книги добавлен в описание", debug)

        debug_print(f"\n📄 Синопсис после обработки (первые 200 символов):", debug)
        debug_print(synopsis[:200] + "..." if len(synopsis) > 200 else synopsis, debug)

    rename_map = {}
    if all_images:
        print("\n📸 Скачивание изображений...")
        image_progress_callback = None
        if args.progress_total and args.log_file:
            total_images = len(all_images)
            processed_images = 0
            def image_progress(old_fn, new_fn, error):
                nonlocal processed_images
                processed_images += 1
                with open(args.log_file, 'a') as f:
                    f.write(f"PROGRESS_IMG: {processed_images}/{total_images}\n")
            image_progress_callback = image_progress

        rename_map, failed = download_all_images(
            crawler, all_images, data_dir / "images",
            max_workers=args.image_workers,
            max_retries=args.image_retries,
            default_timeout=args.image_timeout,
            slow_timeout=args.slow_image_timeout,
            debug=debug,
            progress_callback=image_progress_callback
        )
        print(f"   Успешно: {len(rename_map)}, не удалось: {len(failed)}")
        if failed and not args.ignore_image_errors:
            print(f"\n❌ Не удалось загрузить {len(failed)} изображений. EPUB не будет создан.")
            print("   Используйте --ignore-image-errors, чтобы создать книгу без этих изображений.")
            sys.exit(1)
        if debug and failed:
            debug_print(f"   Неудавшиеся: {failed}", debug)
    else:
        if not debug:
            print("ℹ️ Нет изображений для скачивания")

    used_images = list(rename_map.values())

    if rename_map:
        debug_print("\n🔄 Обновление ссылок в HTML...", debug)
        for i, (idx, ch_title, content, _) in enumerate(loaded):
            new_content = content
            for old, new in rename_map.items():
                new_content = new_content.replace(f'src="images/{old}"', f'src="images/{new}"')
            if new_content != content:
                json_file = get_chapter_file(chapters_json_dir, idx)
                chapter_data = load_chapter_json(json_file)
                if chapter_data:
                    chapter_data['body'] = new_content
                    save_chapter_json(json_file, chapter_data)
                loaded[i] = (idx, ch_title, new_content, None)
                debug_print(f"   ✅ Глава {idx} обновлена", debug)

        if synopsis:
            new_synopsis = synopsis
            for old, new in rename_map.items():
                new_synopsis = new_synopsis.replace(f'src="images/{old}"', f'src="images/{new}"')
            if new_synopsis != synopsis:
                synopsis = new_synopsis
                save_synopsis_cache(data_dir, synopsis, images_from_synopsis)
                debug_print("   ✅ Синопсис обновлён", debug)

    if debug and rename_map:
        debug_print("\n📸 Карта переименования изображений:", debug)
        for old, new in rename_map.items():
            debug_print(f"   {old} -> {new}", debug)

        for idx, ch_title, content, _ in loaded:
            if f'src="images/' in content:
                debug_print(f"   ✅ Глава {idx}: изображения уже есть", debug)
            else:
                debug_print(f"   ⚠️ Глава {idx}: изображения отсутствуют", debug)

    debug_print("\n🔧 Добавление <base href=\"/\" />...", debug)
    for i, (idx, ch_title, content, _) in enumerate(loaded):
        new_content = add_base_tag_to_html(content)
        if new_content != content:
            json_file = get_chapter_file(chapters_json_dir, idx)
            chapter_data = load_chapter_json(json_file)
            if chapter_data:
                chapter_data['body'] = new_content
                save_chapter_json(json_file, chapter_data)
            loaded[i] = (idx, ch_title, new_content, None)
            debug_print(f"   ✅ Глава {idx} обновлена", debug)

    if synopsis:
        new_synopsis = add_base_tag_to_html(synopsis)
        if new_synopsis != synopsis:
            synopsis = new_synopsis
            save_synopsis_cache(data_dir, synopsis, images_from_synopsis)
            debug_print("   ✅ Синопсис обновлён", debug)

    synopsis, was_modified = ensure_image_in_synopsis(synopsis, images_from_synopsis, rename_map)
    if was_modified:
        save_synopsis_cache(data_dir, synopsis, images_from_synopsis)
        debug_print("   ✅ Изображение вставлено в описание", debug)

    # --- Обновление синопсиса в базе данных ---
    if synopsis:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id FROM novels WHERE target_dir = ?", (str(data_dir),))
            row = c.fetchone()
            if row:
                novel_id = row[0]
                c.execute("UPDATE novels SET synopsis = ? WHERE id = ?", (synopsis, novel_id))
                conn.commit()
                debug_print(f"   ✅ Синопсис обновлён в БД для книги ID={novel_id}", debug)
            else:
                debug_print("   ⚠️ Запись в БД не найдена для данной папки", debug)
            conn.close()
        except Exception as e:
            debug_print(f"   ⚠️ Не удалось обновить синопсис в БД: {e}", debug)

    min_chap = min(idx for idx, _, _, _ in loaded)
    max_chap = max(idx for idx, _, _, _ in loaded)
    range_suffix = f"_{min_chap:05d}-{max_chap:05d}"

    cover_data = None
    if cover_url:
        if cover_path.exists():
            debug_print(f"\n🖼️ Обложка уже есть: {cover_path}", debug)
            with open(cover_path, 'rb') as f:
                cover_data = f.read()
        else:
            print("🖼️ Скачивание обложки...")
            # Передаём сессию, если она есть у crawler
            session = getattr(crawler, 'session', None)
            if download_cover(cover_url, cover_path, session):
                with open(cover_path, 'rb') as f:
                    cover_data = f.read()
    else:
        debug_print("ℹ️ Обложка не найдена", debug)

    print(f"\n📚 Сборка EPUB: {title}")
    chapters_for_epub = [(idx, ch_title, content) for idx, ch_title, content, _ in loaded]

    book = build_epub(
        data_dir, title, author, synopsis,
        chapters_for_epub, cover_data, used_images
    )

    out_fname = f"{data_dir.name}{range_suffix}.epub"
    out_path = data_dir / out_fname
    epub.write_epub(str(out_path), book, {})
    print(f"\n✅ EPUB создан: {out_path}")


if __name__ == "__main__":
    main()