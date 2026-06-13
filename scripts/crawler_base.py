# crawler_base.py

import hashlib
import math
import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from bs4 import BeautifulSoup, Comment
import requests

logger = logging.getLogger(__name__)


def format_title(title: str) -> str:
    return title.strip()


def normalize(text: str) -> str:
    return text.strip().lower()


def extract_base(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def atomic_write(file_path: Path):
    from contextlib import contextmanager
    @contextmanager
    def _write(path):
        tmp = path.with_suffix('.tmp')
        try:
            yield tmp
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
    return _write(file_path)


def generate_cover_image():
    from PIL import Image
    img = Image.new('RGB', (400, 600), color='gray')
    return img


class Cleaner:
    def __init__(self):
        self.bad_css = set()

    def clean_contents(self, soup):
        for tag in soup.find_all(['script', 'style', 'link', 'iframe', 'noscript', 'meta']):
            tag.decompose()
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        for selector in self.bad_css:
            for el in soup.select(selector):
                el.decompose()


# --------------------------------------------------------------------------
# Базовые модели (из lncrawl_stubs)
# --------------------------------------------------------------------------
class Box(dict):
    """Простой dict с доступом к ключам через атрибуты."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


class Chapter(Box):
    def __init__(self, id=None, url="", title="", volume=None, body="",
                 images=None, success=False, crawler_version=None, **kwargs):
        super().__init__()
        self.id = id
        self.url = url
        self.title = title
        self.volume = volume
        self.body = body
        self.images = images or {}
        self.success = success
        self.crawler_version = crawler_version
        self.update(kwargs)


class Volume(Box):
    def __init__(self, id, title="", chapters=0, crawler_version=None, **kwargs):
        super().__init__()
        self.id = id
        self.title = title
        self.chapters = chapters
        self.crawler_version = crawler_version
        self.update(kwargs)


class Novel(Box):
    def __init__(self, url, title="", cover_url="", volumes=None, chapters=None,
                 author="", synopsis="", tags=None, language=None,
                 is_manga=None, is_mtl=None, is_rtl=None, crawler_version=None, **kwargs):
        super().__init__()
        self.url = url
        self.title = title
        self.cover_url = cover_url
        self.volumes = volumes or []
        self.chapters = chapters or []
        self.author = author
        self.synopsis = synopsis
        self.tags = tags or []
        self.language = language
        self.is_manga = is_manga
        self.is_mtl = is_mtl
        self.is_rtl = is_rtl
        self.crawler_version = crawler_version
        self.update(kwargs)


class SearchResult(Box):
    def __init__(self, title, url, info="", **kwargs):
        super().__init__()
        self.title = str(title)
        self.url = str(url)
        self.info = str(info)
        self.update(kwargs)


# --------------------------------------------------------------------------
# Базовый краулер (заменяет lncrawl.core.crawler.Crawler)
# --------------------------------------------------------------------------
class BaseCrawler(ABC):
    base_url: Union[str, List[str]] = ""
    language = ""
    has_mtl = False
    has_manga = False
    can_login = False
    can_search = False
    chapters_per_volume = 100
    auto_generate_cover = True

    def __init__(self):
        self.session: Optional[requests.Session] = None
        self.novel_url: Optional[str] = None
        self.novel_title = ""
        self.novel_author = ""
        self.novel_cover = ""
        self.novel_synopsis = ""
        self.chapters: List[Dict[str, Any]] = []
        self.volumes: List[Dict[str, Any]] = []
        self.output_path = ""
        self.cleaner = Cleaner()
        self.novel_tags: List[str] = []
        self.scraper_last_soup_url = ""

    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def login(self, email: str, password: str) -> None:
        pass

    @abstractmethod
    def read_novel_info(self) -> None:
        pass

    @abstractmethod
    def download_chapter_body(self, chapter: Dict[str, Any]) -> str:
        pass

    def absolute_url(self, any_url: Any, page_url: Optional[str] = None) -> str:
        url = str(any_url or "").strip().rstrip("/")
        if not url:
            return url
        if url.startswith("http"):
            return url
        base_url = self.scraper_last_soup_url or self.novel_url or ""
        base_url = extract_base(base_url).strip("/")
        if url.startswith("//"):
            scheme = base_url.split(":")[0]
            return f"{scheme}:{url}"
        if url.startswith("/"):
            return base_url + url
        if not page_url:
            page_url = self.scraper_last_soup_url or self.novel_url or ""
        page_url = page_url.rstrip("/")
        if url.startswith("."):
            paths = page_url.split("/")
            parts = url.split("/")
            while parts and (parts[0] == ".." or parts[0] == "."):
                parts = parts[1:]
                if parts[0] == "..":
                    paths = paths[:-1]
            return "/".join(paths + parts)
        return f"{page_url}/{url}"

    def submit_form(self, url: str, data: dict) -> requests.Response:
        return self.session.post(url, data=data)

    def extract_chapter_images(self, chapter):
        if not chapter.body:
            return
        soup = BeautifulSoup(chapter.body, "lxml")
        imgs = soup.find_all("img")
        # Отладочный вывод в лог (через print, но его не видно, поэтому используем другой способ)
        # Но можно сохранить в атрибуте, а потом вывести в главе
        chapter._debug_img_count = len(imgs)  # временный костыль
        for img in imgs:
            src = img.get("src")
            if src:
                full_url = self.absolute_url(src)
                if full_url.startswith("http"):
                    image_id = hashlib.md5(full_url.encode()).hexdigest()
                    chapter.images[image_id] = full_url

    def download_image(self, url: str, output_file: Path) -> None:
        if not url:
            return
        if output_file.is_file():
            os.utime(output_file)
            return
        resp = self.session.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with atomic_write(output_file) as tmp:
            for chunk in resp.iter_content(8192):
                tmp.write(chunk)

    def download_cover(self, cover_url: str, cover_file: Path) -> None:
        try:
            self.download_image(cover_url, cover_file)
        except Exception:
            logger.warning(f"Cover download failed: {cover_url}")
            if not cover_file.is_file():
                img = generate_cover_image()
                with atomic_write(cover_file) as tmp:
                    img.save(tmp, "JPEG")

    def get_soup(self, url: str) -> BeautifulSoup:
        raise NotImplementedError


# Алиас для обратной совместимости с rulate.py
Crawler = BaseCrawler