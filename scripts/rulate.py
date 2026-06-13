# -*- coding: utf-8 -*-
import logging
import pickle
import cloudscraper
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup

# Вместо from lncrawl.core.crawler import Crawler
from .crawler_base import Crawler   # <-- используем нашу заглушку
logger = logging.getLogger(__name__)

COOKIES_FILE = Path("/sdcard/cookies.pkl")


class RulateCrawler(Crawler):
    base_url = [
        "https://tl.rulate.ru/",
    ]

    def initialize(self):
        super().initialize()
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
                'mobile': False,
            },
            interpreter='native'
        )
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://tl.rulate.ru/',
        })
        self.cleaner.bad_css.update([".thumbnail"])

        if COOKIES_FILE.exists():
            try:
                with open(COOKIES_FILE, 'rb') as f:
                    self.session.cookies.update(pickle.load(f))
                logger.info("Cookies loaded from file")
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}")

    def get_soup(self, url):
        logger.debug(f"Visiting: {url}")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')

    def login(self, email: str, password: str):
        login_url = "https://tl.rulate.ru/"
        resp = self.session.get(login_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        csrf_input = soup.find('input', {'name': '_csrf'})
        csrf_token = csrf_input['value'] if csrf_input else None

        login_data = {
            "login[login]": email,
            "login[pass]": password,
        }
        if csrf_token:
            login_data['_csrf'] = csrf_token

        for attempt in range(3):
            try:
                response = self.session.post(login_url, data=login_data)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                error_div = soup.find('div', class_='alert alert-danger')
                if error_div and 'Неверный' in error_div.text:
                    raise Exception("Invalid login or password")

                with open(COOKIES_FILE, 'wb') as f:
                    pickle.dump(self.session.cookies, f)
                logger.info(f"Login successful, cookies saved to {COOKIES_FILE}")
                return True
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"Login attempt {attempt+1} failed: {e}. Retrying...")
                time.sleep(5)

    def _extract_synopsis(self, soup):
        """Извлекает описание как HTML, собирая только параграфы и удаляя мусор."""
        info_div = soup.find("div", id="Info")
        if not info_div:
            print("[DEBUG] Блок #Info не найден")
            return None
    
        # Удаляем явные мусорные блоки
        garbage_selectors = [
            '.span2', '.images', '.slick', 'a.badge', 'button', '.rating-block',
            '.cat', 'p.cat', 'div#comments', 'div.reviews', '.btn-toolbar',
            '.btn-group', '.row-fluid', '.span5', '.span7'
        ]
        for sel in garbage_selectors:
            for tag in info_div.select(sel):
                tag.decompose()
    
        # Собираем все оставшиеся параграфы
        paragraphs = info_div.find_all('p')
        if not paragraphs:
            print("[DEBUG] Параграфы не найдены")
            return None
    
        # Фильтруем короткие параграфы (менее 20 символов)
        good_paragraphs = []
        for p in paragraphs:
            text_len = len(p.get_text(strip=True))
            if text_len >= 20:
                good_paragraphs.append(p)
    
        if not good_paragraphs:
            print("[DEBUG] Нет параграфов достаточной длины")
            return None
    
        # Преобразуем в строку HTML
        html_parts = [str(p) for p in good_paragraphs]
        full_html = '\n'.join(html_parts)
        print(f"[DEBUG] Синопсис собран из {len(good_paragraphs)} параграфов, длина HTML: {len(full_html)}")
        return full_html
        
    def _extract_cover(self, soup):
        """Извлекает URL обложки различными способами."""
        # 1. Open Graph image
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            url = meta["content"]
            print(f"[DEBUG] Обложка найдена через og:image: {url}")
            return url

        # 2. div.span2 (старый способ)
        possible_images = soup.find("div", {"class": "span2"})
        if possible_images:
            img = possible_images.find("img")
            if img and img.get("src"):
                url = self.absolute_url(img["src"])
                print(f"[DEBUG] Обложка найдена через div.span2: {url}")
                return url

        # 3. div.cover
        cover_div = soup.find("div", class_=re.compile(r"cover", re.I))
        if cover_div:
            img = cover_div.find("img")
            if img and img.get("src"):
                url = self.absolute_url(img["src"])
                print(f"[DEBUG] Обложка найдена через div.cover: {url}")
                return url

        # 4. Любое изображение подходящего размера (например, width >= 200)
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue
            width = img.get("width")
            if width and width.isdigit() and int(width) >= 200:
                url = self.absolute_url(src)
                print(f"[DEBUG] Обложка найдена по ширине >=200: {url}")
                return url

        print("[DEBUG] Обложка не найдена ни одним способом")
        return None

    def read_novel_info(self):
        logger.debug("Visiting %s", self.novel_url)
        soup = self.get_soup(self.novel_url)

        chapters = soup.select_one("#Chapters")
        mature_confirmed = False

        if not chapters:
            input_path = soup.find("input", {"name": "book_id", "type": "hidden"})
            if input_path:
                for attempt in range(3):
                    try:
                        self.submit_form(
                            url="https://tl.rulate.ru/mature",
                            data={
                                "path": input_path["value"],
                                "ok": "Да",
                            },
                        )
                        soup = self.get_soup(self.novel_url)
                        chapters = soup.select_one("#Chapters")
                        mature_confirmed = True
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise
                        logger.warning(f"Mature confirmation attempt {attempt+1} failed: {e}. Retrying...")
                        time.sleep(2)

        # Извлекаем описание (после возможного подтверждения)
        synopsis = self._extract_synopsis(soup)
        self.novel_synopsis = synopsis

        # Поиск названия книги
        title = None
        
        # 1. Пробуем h1
        h1 = soup.find("h1")
        if h1 and h1.text.strip():
            title = h1.text.split("/")[-1].strip()
        
        # 2. Fallback: meta og:title
        if not title:
            meta_title = soup.find("meta", property="og:title")
            if meta_title and meta_title.get("content"):
                title = meta_title["content"].strip()
        
        # 3. Fallback: title в head
        if not title:
            head_title = soup.find("title")
            if head_title and head_title.text.strip():
                title = head_title.text.strip()
        
        # 4. Fallback: атрибут data-title или класс
        if not title:
            title_div = soup.find("div", class_="book-title")  # пример
            if title_div:
                title = title_div.text.strip()
        
        if not title:
            title = "Без названия"
        
        self.novel_title = title

        # Обложка
        self.novel_cover = self._extract_cover(soup)
        logger.info("Novel cover: %s", self.novel_cover)

        # --- Ищем автора ---
        author = None
        
        # Основной способ: meta-тег book:author
        meta_book_author = soup.find("meta", property="book:author")
        if meta_book_author and meta_book_author.get("content"):
            author = meta_book_author["content"].strip()
        
        # Запасной способ 1: meta-тег author (обычный)
        if not author:
            meta_author = soup.find("meta", {"name": "author"})
            if meta_author and meta_author.get("content"):
                author = meta_author["content"].strip()
        
        # Запасной способ 2: сильный тег "Автор:" с ссылкой
        if not author:
            author_block = soup.find("strong", string="Автор:")
            if author_block and author_block.parent:
                link = author_block.parent.find("a")
                if link:
                    author = link.text.strip()
        
        # Запасной способ 3: сильный тег "Автор:" без ссылки
        if not author and author_block:
            parent_text = author_block.parent.get_text(separator=" ", strip=True)
            author = parent_text.replace("Автор:", "").strip()
        
        self.novel_author = author or "Неизвестен"
        print(f"👤 Автор: {self.novel_author}")
        logger.info("Novel author: %s", self.novel_author)

        for tag in soup.find_all("a", {"class": "badge"}):
            self.novel_tags.append(tag.text)
        logger.info("Novel tags: %s", self.novel_tags)

        chap_id = 0
        vol_id = 1
        self.volumes.append({"id": vol_id})
        if chapters:
            for row in chapters.find_all("tr"):
                if not row.has_attr("class"):
                    continue
                if row["class"][0] == "volume_helper":
                    if chap_id:
                        vol_id = vol_id + 1
                    else:
                        self.volumes.pop()
                    self.volumes.append({"id": vol_id, "title": row.text})
                    continue
                if row.find("span", {"class": "disabled"}):
                    continue
                possible_chapter_ref = row.find("a", {"class": False, "href": True})
                if possible_chapter_ref:
                    chap_id = chap_id + 1
                    self.chapters.append(
                        {
                            "id": chap_id,
                            "volume": vol_id,
                            "url": self.absolute_url(possible_chapter_ref["href"]),
                            "title": possible_chapter_ref.text,
                        }
                    )
        logger.info(f"Total chapters found: {len(self.chapters)}")

    def download_chapter_body(self, chapter):
        soup = self.get_soup(chapter["url"])
        contents = soup.select_one(".content-text")
        self.cleaner.clean_contents(contents)
        return str(contents)