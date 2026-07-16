# scripts/ranobes.py

import asyncio
import logging
import pickle
import re
import time
import atexit
import random

import cloudscraper
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from .crawler_base import Crawler
from scripts.paths import RANOBES_COOKIES_FILE, RANOBES_SELENIUM_COOKIES_FILE

logger = logging.getLogger(__name__)

CHROMIUM_BINARY_PATH = '/data/data/com.termux/files/usr/bin/chromium-browser'
CHROMEDRIVER_PATH = '/data/data/com.termux/files/usr/lib/chromium/chromedriver'


class RanobesCrawler(Crawler):
    base_url = ["https://ranobes.com/"]

    def __init__(self):
        super().__init__()
        self._soup_cache = {}
        self._novel_info_cache = {}
        self._driver = None
        self._display = None
        self._use_selenium = False
        self._selenium_requests = 0
        self._restart_every = 5

    def initialize(self):
        super().initialize()
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True, "mobile": False},
            interpreter="native",
        )
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
            "Accept": "text/html,...",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        if RANOBES_COOKIES_FILE.exists():
            with open(RANOBES_COOKIES_FILE, "rb") as f:
                self.session.cookies.update(pickle.load(f))

        if self.novel_url and 'ranobes.com' in self.novel_url:
            self._use_selenium = True
            asyncio.create_task(self._async_init_driver())

    # Асинхронная инициализация драйвера
    async def _async_init_driver(self):
        if self._driver is not None:
            return
        logger.info("Starting virtual display and Chrome driver (async thread)")
        def _sync():
            display = Display(visible=0, size=(1920, 1080))
            display.start()
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.binary_location = CHROMIUM_BINARY_PATH
            service = Service(executable_path=CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=options)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.navigator.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU','ru'] });
                '''
            })
            driver.get("https://ranobes.com/")
            time.sleep(2)
            for cookie in self.session.cookies:
                try:
                    driver.add_cookie({"name": cookie.name, "value": cookie.value,
                                       "domain": cookie.domain or "ranobes.com", "path": cookie.path or "/"})
                except: pass
            return driver, display
        self._driver, self._display = await asyncio.to_thread(_sync)
        atexit.register(self._quit_driver)

    def _quit_driver(self):
        if self._driver:
            try: self._driver.quit()
            except: pass
            self._driver = None
        if self._display:
            try: self._display.stop()
            except: pass
            self._display = None
        self._selenium_requests = 0

    # Асинхронное получение страницы
    async def _async_get_selenium_soup(self, url):
        await self._async_init_driver()
        if self._selenium_requests > 0 and self._selenium_requests % self._restart_every == 0:
            self._quit_driver()
            await self._async_init_driver()
        def _sync():
            self._driver.get(url)
            max_wait = 30
            start = time.time()
            while time.time() - start < max_wait:
                html = self._driver.page_source
                if 'Checking your browser' not in html and \
                   ('div.text#arrticle' in html or 'div.cat_block' in html or 'div#dle-content' in html):
                    break
                if 'turns' in html and 'cloudflare' in html.lower():
                    try:
                        iframes = self._driver.find_elements('css selector', 'iframe[src*="turns"]')
                        for iframe in iframes:
                            try:
                                self._driver.switch_to.frame(iframe)
                                checkbox = self._driver.find_element('css selector', 'input[type="checkbox"], .checkmark')
                                if checkbox:
                                    checkbox.click()
                                    time.sleep(3)
                                    self._driver.switch_to.default_content()
                            except: self._driver.switch_to.default_content()
                    except: pass
                time.sleep(1)
            return self._driver.page_source
        page_source = await asyncio.to_thread(_sync)
        self._selenium_requests += 1
        return BeautifulSoup(page_source, "lxml")

    # Синхронные обёртки (для вызовов из download_manager)
    def _init_driver(self):
        if self._driver is not None: return
        self._display = Display(visible=0, size=(1920, 1080))
        self._display.start()
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.binary_location = CHROMIUM_BINARY_PATH
        service = Service(executable_path=CHROMEDRIVER_PATH)
        self._driver = webdriver.Chrome(service=service, options=options)
        self._driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''Object.defineProperty(navigator, 'webdriver', {get: () => undefined});...'''})
        self._driver.get("https://ranobes.com/")
        time.sleep(2)
        for cookie in self.session.cookies:
            try: self._driver.add_cookie({"name": cookie.name, "value": cookie.value,
                                          "domain": cookie.domain or "ranobes.com", "path": cookie.path or "/"})
            except: pass
        atexit.register(self._quit_driver)

    def _get_selenium_soup(self, url):
        self._init_driver()
        if self._selenium_requests > 0 and self._selenium_requests % self._restart_every == 0:
            self._quit_driver()
            self._init_driver()
        self._driver.get(url)
        max_wait = 30
        start = time.time()
        while time.time() - start < max_wait:
            html = self._driver.page_source
            if 'Checking your browser' not in html and \
               ('div.text#arrticle' in html or 'div.cat_block' in html or 'div#dle-content' in html):
                break
            if 'turns' in html and 'cloudflare' in html.lower():
                try:
                    iframes = self._driver.find_elements('css selector', 'iframe[src*="turns"]')
                    for iframe in iframes:
                        try:
                            self._driver.switch_to.frame(iframe)
                            checkbox = self._driver.find_element('css selector', 'input[type="checkbox"], .checkmark')
                            if checkbox:
                                checkbox.click()
                                time.sleep(3)
                                self._driver.switch_to.default_content()
                        except: self._driver.switch_to.default_content()
                except: pass
            time.sleep(1)
        self._selenium_requests += 1
        return BeautifulSoup(self._driver.page_source, "lxml")

    def get_soup(self, url, force_refresh=False, strainer=None):
        if self._use_selenium:
            return self._get_selenium_soup(url)
        cache_key = (url, str(strainer) if strainer else "__FULL__")
        if force_refresh or cache_key not in self._soup_cache:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml", parse_only=strainer) if strainer else BeautifulSoup(response.text, "lxml")
            self._soup_cache[cache_key] = soup
        return self._soup_cache[cache_key]

    # ... все остальные методы (login, extract_*, read_novel_info, download_chapter_body) без изменений ...
    # В download_chapter_body используйте self._get_selenium_soupreturn

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
        meta = soup.select_one('meta[property="og:image"]')
        if meta and meta.get("content"):
            return meta["content"]
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
            logger.error("No chapter blocks found even with Selenium.")
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
                if not re.search(r'/chapters/[^/]+/\d+-\d+\.html', href):
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
                time.sleep(random.uniform(0.5, 1.5))
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
            if not re.search(r'/chapters/[^/]+/\d+-\d+\.html', href):
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
            raise Exception("Chapter content not found (Selenium)")
        time.sleep(random.uniform(1, 3))
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

    def __del__(self):
        self._quit_driver()