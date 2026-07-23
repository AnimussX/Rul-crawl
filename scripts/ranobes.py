# scripts/ranobes.py

import asyncio
import logging
import os
import pickle
import re
import sys
import time
import atexit
import random
# scripts/ranobes.py, в начало файла после импортов
import threading as _threading

_driver_launch_lock = _threading.Lock()

if sys.platform == 'android':
    sys.platform = 'linux'

os.environ['FILELOCK_USE_FLOCK'] = '0'
import filelock
filelock.FileLock = filelock.SoftFileLock

import cloudscraper
from bs4 import BeautifulSoup
from seleniumbase import Driver

from .crawler_base import Crawler
from scripts.paths import RANOBES_COOKIES_FILE, RANOBES_SELENIUM_COOKIES_FILE
from scripts.selenium_termux_config import (
    resolve_chromium_paths,
    check_version_compatibility,
    ensure_chromedriver_on_path,
    ensure_seleniumbase_local_driver,
)
from scripts.settings import load_settings

logger = logging.getLogger(__name__)

RANOBES_UC_PROFILE_DIR = "/data/data/com.termux/files/home/ranobes_uc_profile"


class RanobesCrawler(Crawler):
    base_url = ["https://ranobes.com/"]

    def __init__(self, ui_screen=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ui_screen = ui_screen  # Теперь краулер знает про экран TUI

        self._soup_cache = {}
        self._novel_info_cache = {}
        self._driver = None
        self._use_selenium = False
        self._selenium_requests = 0
        self._restart_every = 30
        self._chromium_path = None
        self._chromedriver_path = None

    def initialize(self):
        super().initialize()
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True, "mobile": False},
            interpreter="native",
        )
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                      "image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        if RANOBES_COOKIES_FILE.exists():
            try:
                with open(RANOBES_COOKIES_FILE, "rb") as f:
                    self.session.cookies.update(pickle.load(f))
                logger.info("Ranobes cookies loaded from file")
            except Exception as e:
                logger.warning(f"Failed to load ranobes cookies: {e}")

        if self.novel_url and 'ranobes.com' in self.novel_url:
            logger.info("ranobes.com detected, will use SeleniumBase")
            self._use_selenium = True

    def _clear_stale_profile_lock(self):
        """Удаляет lock-файлы Chrome, оставшиеся от аварийного завершения
        предыдущего запуска (SIGKILL/terminate) — иначе новый Chrome
        отказывается стартовать с той же user_data_dir."""
        for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            lock_path = os.path.join(RANOBES_UC_PROFILE_DIR, lock_name)
            if os.path.exists(lock_path) or os.path.islink(lock_path):
                try:
                    os.remove(lock_path)
                    logger.info(f"Удалён stale-лок профиля: {lock_path}")
                except OSError as e:
                    logger.warning(f"Не удалось удалить {lock_path}: {e}")

    def _ensure_driver(self):
        """Гарантирует, что headless CDP-драйвер запущен."""
        if self._driver is not None:
            return

        with _driver_launch_lock:
            if self._driver is not None:  # повторная проверка после получения лока
                return

            if self._chromium_path is None or self._chromedriver_path is None:
                settings = load_settings()
                self._chromium_path, self._chromedriver_path = resolve_chromium_paths(settings)
                ensure_chromedriver_on_path(self._chromedriver_path)
                ensure_seleniumbase_local_driver(self._chromedriver_path)
                warning = check_version_compatibility(self._chromium_path, self._chromedriver_path)
                if warning:
                    logger.warning(warning)

            os.makedirs(RANOBES_UC_PROFILE_DIR, exist_ok=True)
            self._clear_stale_profile_lock()

            logger.info("Starting SeleniumBase driver (headless, CDP mode)")

            self._driver = Driver(
                browser="chrome",
                headless=True,
                uc=True,
                binary_location=self._chromium_path,
                block_images=True,  # изображения не нужны для скрапинга текста —
                                     # реальные картинки качаются отдельно через requests
                user_data_dir=RANOBES_UC_PROFILE_DIR,
                chromium_arg=(
                    "--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--memory-pressure-off,--js-flags='--max-old-space-size=256'","--disable-blink-features=LayoutNG,--disable-threaded-scrolling"

                ),
                driver_version="keep",
            )

            self._driver.uc_open_with_reconnect("https://ranobes.com/", reconnect_time=6)
            time.sleep(5)
            # uc_gui_handle_captcha() требует реальный дисплей (X11/Xvfb) и
            # НЕ РАБОТАЕТ в headless-режиме — вызывать его здесь бессмысленно
            # и тратит ресурсы впустую. В headless единственный рабочий путь —
            # дать Cloudflare JS-челленджу пройти самому (обычно секунды) или
            # перезагрузить страницу, если элемент так и не появился.

            self._driver.activate_cdp_mode() # без url — не грузит страницу повторно
            
            # УСКОРЕНИЕ: Блокируем CSS, шрифты и рекламу на уровне движка Chrome
            try:
                self._driver.execute_cdp_cmd("Network.enable", {})
                self._driver.execute_cdp_cmd("Network.setBlockedURLs", {
                    "urls": [
                        "*.css",          # Стили не нужны для скрапинга текста
                        "*.woff*",        # Шрифты весят много и тормозят загрузку
                        "*.ttf",
                        "*yandex*",       # Блокируем метрику и рекламу Яндекса
                        "*google-analytics*", 
                        "*vk.com*",       # Виджеты соцсетей
                        "*/ads/*"
                    ]
                })
                logger. info("CDP сетевые фильтры успешно активированы")
            except Exception as e:
                logger. warning(f"Не удалось настроить сетевые фильтры CDP: {e}")


            logger.info("SeleniumBase driver initialized successfully (CDP active)")
            # atexit НЕ регистрируем: он держит вечную ссылку на self, из-за
            # чего краулер и его Chrome-процесс никогда не освобождаются до
            # конца жизни всего приложения. Закрытие — только через close(),
            # вызываемый явно кодом, который использовал краулер.

    def _check_memory_pressure(self) -> bool:
        """Возвращает True, если свободной памяти в системе критически мало —
        сигнал на принудительный рестарт драйвера до того, как ОС убьёт процесс."""
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            for line in meminfo.splitlines():
                if line.startswith("MemAvailable:"):
                    available_kb = int(line.split()[1])
                    return available_kb < 400_000  # меньше ~400MB свободно
        except Exception:
            pass
        return False

    def _quit_driver(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
        self._selenium_requests = 0


    def _get_selenium_soup(self, url):
        """Быстрая загрузка страниц через уже активный CDP-режим."""
        just_restarted = False

        if self._driver is None:
            self._ensure_driver()
            just_restarted = True

        if self._selenium_requests > 0 and (
            self._selenium_requests % self._restart_every == 0 or self._check_memory_pressure()
        ):
            logger.info("Driver restart (по счётчику или нехватке памяти)")
            self._quit_driver()
            self._ensure_driver()
            just_restarted = True

        time.sleep(random.uniform(0.7, 2.3))

        # uc_open_with_reconnect открывает НОВУЮ вкладку (см. документацию
        # SeleniumBase) — используем его только на прогреве/рестарте, чтобы
        # не копить лишние вкладки на каждый обычный запрос. Обычная
        # навигация — через uc_open (та же вкладка) или cdp.open (без
        # WebDriver-протокола вовсе).
        try:
            if just_restarted:
                self._driver.uc_open_with_reconnect(url, reconnect_time=5)
                self._driver.activate_cdp_mode()
            else:
                # Безопасный переход на той же вкладке БЕЗ создания новых тарджетов в CDP:
                self._driver.execute_cdp_cmd("Page.navigate", {"url": url})
        except Exception as e:
            logger.warning( f"Навигация не удалась ({ e }), пересоздаю драйвер")
            self._quit_driver()
            self._ensure_driver()
            self._driver.execute_cdp_cmd("Page.navigate", {"url": url})


        target_selectors = "div#dle-content, div.text#arrticle, div.cat_block"
        try:
            self._driver.cdp.wait_for_element(target_selectors, timeout=3)
        except Exception:
            # В headless нет смысла звать GUI-клик по капче — вместо этого
            # даём Cloudflare JS-челленджу время пройти и перезагружаем страницу.
            if self._ui_screen:
                self._ui_screen._log("⚠️ Cloudflare-челлендж, жду и перезагружаю страницу...")
            try:
                time.sleep(4)
                self._driver.cdp.reload()
                self._driver.cdp.wait_for_element(target_selectors, timeout=8)
            except Exception:
                pass

        self._selenium_requests += 1

        try:
            clean_html = self._driver.cdp.evaluate(
                "document.querySelector('div#dle-content, div.text#arrticle, body').outerHTML"
            )
        except Exception:
            clean_html = self._driver.cdp.get_page_source()

        return BeautifulSoup(clean_html, "lxml")


    def get_soup(self, url, force_refresh=False, strainer=None):
        if self._use_selenium:
            return self._get_selenium_soup(url)

        cache_key = (url, str(strainer) if strainer else "__FULL__")
        if force_refresh or cache_key not in self._soup_cache:
            logger.debug(f"Fetching (new): {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            if strainer:
                soup = BeautifulSoup(response.text, "lxml", parse_only=strainer)
            else:
                soup = BeautifulSoup(response.text, "lxml")
            self._soup_cache[cache_key] = soup
        else:
            logger.debug(f"Fetching (cached): {url}")
            soup = self._soup_cache[cache_key]
        return soup

    def login(self, email: str, password: str):
        login_url = "https://ranobes.com/"
        login_data = {
            "login_name": email,
            "login_password": password,
            "login": "submit",
        }
        for attempt in range(3):
            try:
                resp = self.session.post(login_url, data=login_data, allow_redirects=True, timeout=30)
                resp.raise_for_status()
                cookie_names = self.session.cookies.get_dict().keys()
                if not any(name.startswith("dle_") for name in cookie_names):
                    soup = BeautifulSoup(resp.text, "lxml")
                    error = soup.find(class_=re.compile("error", re.I))
                    msg = error.get_text(strip=True) if error else "неверный логин или пароль"
                    raise Exception(f"Не удалось авторизоваться на ranobes.com: {msg}")
                with open(RANOBES_COOKIES_FILE, "wb") as f:
                    pickle.dump(self.session.cookies, f)
                logger.info(f"Ranobes login successful, cookies saved to {RANOBES_COOKIES_FILE}")
                self._soup_cache.clear()
                return True
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"Ranobes login attempt {attempt + 1} failed: {e}. Retrying...")
                time.sleep(5)

    def _extract_title(self, soup):
        h1 = soup.select_one("h1.title")
        if h1 and h1.contents:
            first = h1.contents[0]
            title = str(first).strip() if isinstance(first, str) else first.get_text(strip=True)
            if title:
                return title
        meta_title = soup.select_one('meta[property="og:title"]')
        if meta_title and meta_title.get("content"):
            return meta_title["content"].strip()
        return "Без названия"

    def _extract_cover(self, soup):
        # Жесткая проверка: обрабатываем только если это ranobes
        if not self.novel_url or 'ranobes.com' not in self.novel_url:
            return None
    
        if self._ui_screen:
            self._ui_screen._log("🔍 [Ranobes] Поиск обложки новеллы...")
    
        # Способ 1: Пытаемся вытащить из мета-тегов OpenGraph
        meta = soup.select_one('meta[property="og:image"]')
        if meta and meta.get("content"):
            url = meta["content"].strip()
            if url.startswith("http") and "nocover" not in url:
                return url
    
        # Способ 2: Запасные селекторы для адаптивной/мобильной верстки Ranobes в Termux
        img_selectors = [
            "div.poster img", 
            "div.r-fullstory-poster img", 
            "span.story_post img",
            ".rd-card-img img",
            "div.flex-img img" # Часто встречается в мобильных шаблонах
        ]
        
        for selector in img_selectors:
            img = soup.select_one(selector)
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    abs_url = self.absolute_url(src.strip())
                    if "nocover" not in abs_url:
                        return abs_url
                        
        return None


    def _extract_synopsis(self, soup):
        desc = soup.select_one("div.r-desription .cont-text")
        if not desc:
            return None
        desc = BeautifulSoup(str(desc), "lxml")
        for style in desc.find_all("style"):
            style.decompose()
        for junk in desc.select(".showcont-btn, .showcont-hh"):
            junk.decompose()
        html = str(desc).strip()
        text_len = len(BeautifulSoup(html, "lxml").get_text(" ", strip=True))
        if text_len < 20:
            return None
        return html

    def _extract_author(self, soup):
        for li in soup.select(".r-fullstory-spec li"):
            label = li.get_text(" ", strip=True)
            if label.startswith("Авторы:") or label.startswith("Автор:"):
                links = li.select("a")
                if links:
                    return ", ".join(a.get_text(strip=True) for a in links)
                return label.split(":", 1)[-1].strip() or "Неизвестен"
        return "Неизвестен"

    def _extract_toc_url(self, soup):
        link = soup.select_one('a.read-continue, a[title="Перейти в оглавление"]')
        if link and link.get("href"):
            return self.absolute_url(link["href"])
        m = re.search(r"/ranobe/\d+-([^/.]+)", self.novel_url or "")
        if m:
            return f"https://ranobes.com/chapters/{m.group(1)}/"
        return None

    def _collect_full_toc(self, toc_url):
        if not toc_url:
            return []

        soup = self._get_selenium_soup(toc_url)
        content_area = soup.select_one('#dle-content') or soup
        test_blocks = content_area.select('div.cat_block.cat_line')

        if not test_blocks:
            logger.error("No chapter blocks found even with SeleniumBase.")
            return []

        last_page = 1
        pages_block = content_area.select_one('div.pages')
        if pages_block:
            page_links = pages_block.find_all('a', href=True)
            numbers = []
            for a in page_links:
                m = re.search(r'/page/(\d+)/', a['href'])
                if m:
                    numbers.append(int(m.group(1)))
            if numbers:
                last_page = max(numbers)
        logger.info(f"Total pages detected: {last_page}")
        if last_page > 10:
            logger.info(
                f"⏳ Оглавление состоит из {last_page} страниц — сбор может занять несколько минут, "
                f"пожалуйста, подождите"
            )

        seen_urls = set()
        raw_items = []

        def parse_page(page_soup, page_num):
            count = 0
            area = page_soup.select_one('#dle-content') or page_soup
            for block in area.select('div.cat_block.cat_line'):
                a_tag = block.find('a', href=True)
                if not a_tag:
                    continue
                href = a_tag['href']
                if '/chapters/' not in href:
                    continue
                if not re.search(r'/chapters/[^/]+/\d+-[^/]+\.html$', href):
                    continue
                url = self.absolute_url(href)
                if url in seen_urls:
                    continue
                title_el = a_tag.find('h6', class_='title') or a_tag
                title = title_el.get_text(strip=True)
                if not title:
                    continue
                seen_urls.add(url)
                raw_items.append((url, title))
                count += 1
            logger.info(f"Page {page_num}/{last_page}: found {count} chapters (total so far: {len(raw_items)})")

        parse_page(content_area, 1)

        for page in range(2, last_page + 1):
            page_url = f"{toc_url.rstrip('/')}/page/{page}/"
            try:
                page_soup = self._get_selenium_soup(page_url)
                parse_page(page_soup, page)
            except Exception as e:
                logger.warning(f"Failed to load page {page}: {e}")

        raw_items.reverse()
        logger.info(f"Total chapters collected: {len(raw_items)}")
        return raw_items

    def _collect_chapters_from_page(self, soup, base_url=""):
        chapters = []
        seen_urls = set()
        main_content = soup.select_one('#mainside') or soup
        for block in main_content.select('div.cat_block.cat_line'):
            a_tag = block.find('a', href=True)
            if not a_tag:
                continue
            href = a_tag['href']
            if '/chapters/' not in href:
                continue
            if not re.search(r'/chapters/[^/]+/\d+-[^/]+\.html$', href):
                continue
            url = self.absolute_url(href, base_url)
            if url in seen_urls:
                continue
            title_el = a_tag.find('h6', class_='title') or a_tag
            title = title_el.get_text(strip=True)
            if not title:
                continue
            seen_urls.add(url)
            chapters.append((url, title))
        chapters.reverse()
        return chapters

    def read_novel_info(self, force_refresh=False):
        if not force_refresh and self.novel_url in self._novel_info_cache:
            cached = self._novel_info_cache[self.novel_url]
            self.novel_title = cached["title"]
            self.novel_author = cached["author"]
            self.novel_cover = cached["cover"]
            self.novel_synopsis = cached["synopsis"]
            self.chapters = cached["chapters"]
            self.volumes = cached["volumes"]
            self.novel_tags = cached.get("tags", [])
            logger.info("Ranobes novel info loaded from cache")
            return

        soup = self._get_selenium_soup(self.novel_url)

        self.novel_title = self._extract_title(soup)
        self.novel_cover = self._extract_cover(soup)
        self.novel_synopsis = self._extract_synopsis(soup)
        self.novel_author = self._extract_author(soup)
        self.novel_tags = [a.get_text(strip=True) for a in soup.select("#mc-fs-genre a")]

        toc_url = self._extract_toc_url(soup)
        raw_items = []

        if toc_url:
            logger.info(f"Trying to fetch TOC from: {toc_url}")
            raw_items = self._collect_full_toc(toc_url)

        if not raw_items:
            logger.info("TOC empty or not found, falling back to chapters on main page")
            raw_items = self._collect_chapters_from_page(soup, self.novel_url)

        if not raw_items:
            raise Exception("Не удалось найти ни одной главы")

        self.chapters = []
        self.volumes = [{"id": 1}]
        for idx, (url, raw_title) in enumerate(raw_items, start=1):
            self.chapters.append({
                "id": idx,
                "volume": 1,
                "url": url,
                "title": raw_title,
            })
        logger.info(f"Total chapters found: {len(self.chapters)}")

        self._novel_info_cache[self.novel_url] = {
            "title": self.novel_title,
            "author": self.novel_author,
            "cover": self.novel_cover,
            "synopsis": self.novel_synopsis,
            "chapters": self.chapters,
            "volumes": self.volumes,
            "tags": self.novel_tags,
        }

    def download_chapter_body(self, chapter):
        soup = self._get_selenium_soup(chapter["url"])
        container = soup.select_one("div.text#arrticle")
        if not container:
            raise Exception("Chapter content not found (SeleniumBase)")
        time.sleep(random.uniform(0.1, 0.3))
        return self._clean_chapter_body(container)

    def _clean_chapter_body(self, container):
        for junk in container.select("script, style"):
            junk.decompose()
        for ad_block in container.select('[id^="yandex_rtb_"]'):
            ad_block.decompose()
        for div in container.find_all("div", align="center"):
            if not div.get_text(strip=True) and not div.find("img"):
                div.decompose()
        self.cleaner.clean_contents(container)
        return str(container)

    def close(self):
        """Явно закрывает Selenium-драйвер. Обязательно вызывать после
        того, как краулер использован для однократной операции —
        полагаться на сборщик мусора нельзя (см. причину в _ensure_driver)."""
        self._quit_driver()

    def __del__(self):
        self._quit_driver()