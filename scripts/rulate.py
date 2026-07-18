# scripts/rulate.py

import logging
import pickle
import cloudscraper
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup, SoupStrainer

from .crawler_base import Crawler
from scripts.paths import COOKIES_FILE       # <-- импорт вместо жёсткого пути

logger = logging.getLogger(__name__)

# Старая строка удалена:
# COOKIES_FILE = Path("/sdcard/cookies.pkl")

class RulateCrawler(Crawler):
    base_url = ["https://tl.rulate.ru/"]

    def __init__(self):
        super().__init__()
        self._soup_cache = {}          # кэш страниц
        self._novel_info_cache = {}    # кэш метаданных новелл

    def initialize(self):
        super().initialize()
        self.session = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
                "mobile": False,
            },
            interpreter="native"
        )
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        # Не удаляем thumbnail, чтобы не потерять иллюстрации в синопсисе
        # self.cleaner.bad_css.update([".thumbnail"])

        if COOKIES_FILE.exists():
            try:
                with open(COOKIES_FILE, "rb") as f:
                    self.session.cookies.update(pickle.load(f))
                logger.info("Cookies loaded from file")
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}")

    def get_soup(self, url, force_refresh=False, strainer=None):
        """Кэширующая версия get_soup с поддержкой SoupStrainer."""
        cache_key = (url, str(strainer) if strainer else "__FULL__")

        if force_refresh or cache_key not in self._soup_cache:
            logger.debug(f"Fetching (new): {url}")
            response = self.session.get(url, timeout=60)
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
        login_url = "https://tl.rulate.ru/"
        soup = self.get_soup(login_url, force_refresh=True)
        csrf_input = soup.find("input", {"name": "_csrf"})
        csrf_token = csrf_input["value"] if csrf_input else None

        login_data = {
            "login[login]": email,
            "login[pass]": password,
        }
        if csrf_token:
            login_data["_csrf"] = csrf_token

        for attempt in range(3):
            try:
                response = self.session.post(login_url, data=login_data)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "lxml")
                error_div = soup.find("div", class_="alert alert-danger")
                if error_div and "Неверный" in error_div.text:
                    raise Exception("Invalid login or password")

                with open(COOKIES_FILE, "wb") as f:
                    pickle.dump(self.session.cookies, f)

                logger.info(f"Login successful, cookies saved to {COOKIES_FILE}")
                self._soup_cache.clear()
                return True
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"Login attempt {attempt + 1} failed: {e}. Retrying...")
                time.sleep(5)

    def _trim_synopsis(self, html: str) -> str:
        """
        Обрезает синопсис, оставляя только содержимое блока .book-description
        и удаляя всё, что идёт после <h3>Рецензии</h3>.
        """
        if not html:
            return html

        # Ищем блок <div class="book-description"...>...</div>
        match = re.search(r'<div\s+class="book-description"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if match:
            trimmed = match.group(1).strip()
            # Дополнительно обрезаем по <h3>Рецензии</h3> (на случай, если внутри окажется)
            trimmed = re.split(r'<h3>Рецензии</h3>', trimmed, flags=re.IGNORECASE)[0]
            return trimmed

        # Если блок .book-description не найден, возвращаем исходный HTML
        return html

    def _extract_synopsis(self, soup):
        """
        Извлечение описания книги с сохранением HTML-разметки и изображений.
        """
        candidate_selectors = [
            "div#Info",
            "#Info",
            ".book-description",
            ".description",
            ".text-content",
            ".content-text",
            ".book-info",
            ".book-content",
        ]

        junk_selectors = [
            ".slick",
            ".rating-block",
            ".btn-toolbar",
            ".btn-group",
            ".reviews",
            "#comments",
            ".social-likes",
            ".share-buttons",
            ".advert",
            ".ads",
            "script",
            "style",
            "iframe",
        ]

        def normalize_images(container):
            for img in container.find_all("img"):
                src = (
                    img.get("src")
                    or img.get("data-src")
                    or img.get("data-original")
                    or img.get("data-lazy")
                )
                if not src:
                    img.decompose()
                    continue
                src = src.strip()
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = self.absolute_url(src)
                img["src"] = src
                for attr in ("srcset", "data-src", "data-original", "data-lazy", "loading", "decoding"):
                    img.attrs.pop(attr, None)

        def cleanup_container(container):
            for selector in junk_selectors:
                for tag in container.select(selector):
                    tag.decompose()
            normalize_images(container)
            for p in container.find_all("p"):
                if not p.get_text(" ", strip=True) and not p.find("img"):
                    p.decompose()
            html = str(container).strip()
            text_len = len(BeautifulSoup(html, "lxml").get_text(" ", strip=True))
            if text_len < 20:
                return None
            return html

        # 1) Пробуем явные контейнеры
        for selector in candidate_selectors:
            block = soup.select_one(selector)
            if block:
                html = cleanup_container(block)
                if html:
                    return html

        # 2) Fallback по маркерам страницы
        start_marker = soup.find(string=lambda s: s and "Начать чтение" in s)
        if not start_marker or not getattr(start_marker, "parent", None):
            return None

        start_tag = start_marker.parent
        end_markers = {
            "Рецензии",
            "Оглавление",
            "Обсуждение",
            "Другие работы автора",
            "Другие переводы команды",
        }
        fragments = []

        for node in start_tag.next_siblings:
            if getattr(node, "name", None) in {"h2", "h3"}:
                title = node.get_text(" ", strip=True)
                if title in end_markers:
                    break
            if not getattr(node, "name", None):
                continue
            normalize_images(node)
            for selector in junk_selectors:
                for tag in node.select(selector):
                    tag.decompose()
            if node.name == "p":
                if len(node.get_text(" ", strip=True)) < 3 and not node.find("img"):
                    continue
            fragments.append(str(node))

        synopsis = "\n".join(fragments).strip()
        if synopsis:
            text_len = len(BeautifulSoup(synopsis, "lxml").get_text(" ", strip=True))
            if text_len >= 20:
                synopsis = re.sub(r"\n{3,}", "\n\n", synopsis).strip()
                return synopsis
        return None

    def _extract_cover(self, soup):
        meta = soup.select_one('meta[property="og:image"]')
        if meta and meta.get("content"):
            return meta["content"]

        img = soup.select_one("div.span2 img, div.cover img")
        if img and img.get("src"):
            return self.absolute_url(img["src"])

        for candidate in soup.find_all("img"):
            try:
                width = int(candidate.get("width", 0))
                if width >= 200 and candidate.get("src"):
                    return self.absolute_url(candidate["src"])
            except Exception:
                pass
        return None

    def read_novel_info(self, force_refresh=False):
        # Кэш по URL новеллы
        if not force_refresh and self.novel_url in self._novel_info_cache:
            cached = self._novel_info_cache[self.novel_url]
            self.novel_title = cached["title"]
            self.novel_author = cached["author"]
            self.novel_cover = cached["cover"]
            self.novel_synopsis = cached["synopsis"]
            self.chapters = cached["chapters"]
            self.volumes = cached["volumes"]
            self.novel_tags = cached.get("tags", [])
            logger.info("Novel info loaded from cache")
            return

        soup = self.get_soup(self.novel_url, force_refresh=True)
        chapters_el = soup.select_one("#Chapters")

        # Подтверждение возраста
        if not chapters_el:
            input_path = soup.find("input", {"name": "book_id", "type": "hidden"})
            if input_path:
                for attempt in range(3):
                    try:
                        self.submit_form(
                            url="https://tl.rulate.ru/mature",
                            data={"path": input_path["value"], "ok": "Да"},
                        )
                        soup = self.get_soup(self.novel_url, force_refresh=True)
                        chapters_el = soup.select_one("#Chapters")
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise
                        logger.warning(f"Mature retry {attempt + 1}: {e}")
                        time.sleep(2)

        # Название
        title = None
        h1 = soup.select_one("h1")
        if h1:
            title = h1.text.split("/")[-1].strip()
        if not title:
            meta_title = soup.select_one('meta[property="og:title"]')
            if meta_title:
                title = meta_title.get("content", "").strip()
        if not title:
            title_tag = soup.select_one("title")
            if title_tag:
                title = title_tag.text.strip()
        self.novel_title = title or "Без названия"

        # Автор
        author = None
        meta_author = soup.select_one('meta[property="book:author"], meta[name="author"]')
        if meta_author:
            author = meta_author.get("content", "").strip()
        if not author:
            author_block = soup.find("strong", string="Автор:")
            if author_block and author_block.parent:
                link = author_block.parent.find("a")
                if link:
                    author = link.text.strip()
                else:
                    author = author_block.parent.get_text(separator=" ", strip=True).replace("Автор:", "").strip()
        self.novel_author = author or "Неизвестен"

        self.novel_cover = self._extract_cover(soup)
        raw_synopsis = self._extract_synopsis(soup)
        self.novel_synopsis = self._trim_synopsis(raw_synopsis)   # обрезка до .book-description

        # Теги
        self.novel_tags = [tag.text for tag in soup.select("a.badge")]

        # Главы
        self.chapters = []
        self.volumes = [{"id": 1}]
        chap_id = 0
        if chapters_el:
            rows = chapters_el.select("tr:not(.volume_helper)")
            for row in rows:
                if row.find("span", class_="disabled"):
                    continue
                link = row.select_one('a[href*="/book/"]')
                if link:
                    chap_id += 1
                    self.chapters.append({
                        "id": chap_id,
                        "volume": 1,
                        "url": self.absolute_url(link["href"]),
                        "title": link.text.strip(),
                    })
        logger.info(f"Total chapters found: {len(self.chapters)}")

        # Сохраняем в кэш
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
        strainer = SoupStrainer(class_="content-text")
        soup = self.get_soup(chapter["url"], force_refresh=True, strainer=strainer)
        contents = (
            soup
            if getattr(soup, "name", None) == "div" and "content-text" in soup.get("class", [])
            else soup.select_one(".content-text")
        )
        if not contents:
            soup_full = self.get_soup(chapter["url"], force_refresh=True)
            contents = soup_full.select_one(".content-text")
        if not contents:
            raise Exception("Chapter content not found")
        self.cleaner.clean_contents(contents)
        return str(contents)