# scripts/chapter_loader.py

import time
import threading
from typing import Optional
from tqdm import tqdm

from scripts.chapter_cache import ChapterCache
from scripts.chapter_cleaner import clean_chapter_html
from .crawler_base import Chapter

try:
    from scripts.selenium_crawler import SeleniumRulateCrawler
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    SeleniumRulateCrawler = None


def download_one_chapter(
    crawler,
    data_dir,
    force,
    idx,
    ch,
    callbacks,
    pbar: Optional[tqdm] = None,
    debug_flag: bool = False,
    use_selenium_fallback: bool = True,
    login: Optional[str] = None,
    password: Optional[str] = None,
    stop_event: Optional[threading.Event] = None,
):
    cache = ChapterCache(data_dir)
    cached = cache.load_chapter(idx)

    if cached and not force:
        if pbar:
            pbar.update(1)
        callbacks.on_log(f"📦 Глава {idx} из кэша")
        if debug_flag:
            callbacks.on_log(f"DEBUG: глава {idx} из кэша, изображений: {len(cached.get('images', {}))}")
        return (idx, cached["title"], cached["body"], cached.get("images", {}))

    def create_fallback_crawler():
        if not SELENIUM_AVAILABLE:
            return None
        if debug_flag:
            callbacks.on_log(f"DEBUG: создаю Selenium-краулер для главы {idx}")
        sel_crawler = SeleniumRulateCrawler(headless=not debug_flag)
        sel_crawler.initialize()
        if login and password:
            try:
                sel_crawler.login(login, password)
            except Exception as e:
                callbacks.on_log(f"⚠️ Ошибка авторизации Selenium: {e}")
        return sel_crawler

    fallback_crawler = None
    for attempt in range(1, 4):
        if stop_event and stop_event.is_set():
            callbacks.on_log(f"⚠️ Загрузка главы {idx} прервана пользователем")
            return None

        current_crawler = fallback_crawler if fallback_crawler else crawler
        try:
            raw_html = current_crawler.download_chapter_body({"url": ch["url"]})
            if not raw_html or len(raw_html) < 100:
                raise Exception("Слишком короткий ответ")
            if "Checking your browser" in raw_html:
                raise Exception("Обнаружена страница проверки браузера")

            temp_chapter = Chapter(id=idx, url=ch["url"], body=raw_html, title=ch["title"])
            current_crawler.output_path = str(data_dir)
            current_crawler.extract_chapter_images(temp_chapter)

            if debug_flag:
                callbacks.on_log(f"DEBUG: глава {idx}, найдено изображений: {len(temp_chapter.images)}")

            cleaned_html = clean_chapter_html(raw_html, ch["title"], debug=debug_flag)

            cache.save_chapter(idx, ch["title"], ch["url"], cleaned_html, temp_chapter.images)
            if pbar:
                pbar.update(1)
            if debug_flag:
                callbacks.on_log(f"DEBUG: глава {idx} сохранена")
            return (idx, ch["title"], cleaned_html, temp_chapter.images)

        except Exception as e:
            status_code = None
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                error_msg = f"HTTP {status_code}: {e}"
            else:
                error_msg = str(e)
            callbacks.on_log(f"❌ Ошибка главы {idx} (попытка {attempt}): {error_msg}")

            if use_selenium_fallback and fallback_crawler is None:
                should_fallback = status_code in [403, 503] or any(keyword in error_msg for keyword in ["Cloudflare", "Checking your browser"])
                if should_fallback and SELENIUM_AVAILABLE:
                    callbacks.on_log(f"   🔄 Включаю Selenium fallback для главы {idx}")
                    fallback_crawler = create_fallback_crawler()
                    if fallback_crawler:
                        continue
                    else:
                        callbacks.on_log(f"   ⚠️ Selenium недоступен, продолжаю с обычным краулером")

            if attempt == 3:
                if pbar:
                    pbar.update(1)
                return None
            delay = 2 ** attempt
            callbacks.on_log(f"   ⏳ Повтор через {delay} сек...")
            # Прерываемый сон
            for _ in range(delay):
                if stop_event and stop_event.is_set():
                    callbacks.on_log(f"⚠️ Загрузка главы {idx} прервана пользователем")
                    return None
                time.sleep(1)
    return None