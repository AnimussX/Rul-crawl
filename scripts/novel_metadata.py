# scripts/novel_metadata.py

import time
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
from requests.exceptions import Timeout, ConnectionError

from scripts.metadata import save_metadata, load_metadata
from scripts.crawler_factory import create_crawler
from scripts.auth import load_auth


def get_novel_metadata(
    url: str,
    crawler,
    data_dir: Path,
    force: bool = False,
    callbacks=None,
) -> Tuple[str, str, str, Optional[str], List[Dict[str, Any]]]:
    """
    Возвращает (title, author, cover_url, synopsis, chapters).
    Если force=False – сначала кэш.
    Если force=True – попытка загрузить с сайта, при ошибке сети – fallback на кэш (если есть).
    """
    # Всегда пробуем загрузить из кэша, если не force (или если force, но сайт недоступен)
    metadata = load_metadata(data_dir)
    if metadata and not force:
        title = metadata["title"]
        author = metadata["author"]
        cover_url = metadata["cover_url"]
        synopsis = metadata.get("synopsis")
        chapters = metadata["chapters"]
        if callbacks:
            callbacks.on_log(f"✅ Метаданные загружены из кэша: {title}")
        return title, author, cover_url, synopsis, chapters

    if callbacks and force:
        callbacks.on_log(f"🌐 Загрузка метаданных с сайта (принудительно)...")

    # Если краулер не передан, создаём новый (тип определяется по домену url)
    if crawler is None:
        login, password = load_auth()
        crawler = create_crawler(url=url, login=login, password=password, debug=bool(callbacks))

    crawler.novel_url = url
    success = False
    for attempt in range(3):
        try:
            crawler.read_novel_info()
            success = True
            break
        except (Timeout, ConnectionError) as e:
            if callbacks:
                callbacks.on_log(f"⚠️ Ошибка соединения (попытка {attempt+1}): {e}")
            if attempt == 2 and metadata:
                # fallback на кэш
                if callbacks:
                    callbacks.on_log(f"⚠️ Использую кэшированные метаданные (сеть недоступна)")
                title = metadata["title"]
                author = metadata["author"]
                cover_url = metadata["cover_url"]
                synopsis = metadata.get("synopsis")
                chapters = metadata["chapters"]
                return title, author, cover_url, synopsis, chapters
            time.sleep(5)
        except Exception as e:
            if callbacks:
                callbacks.on_log(f"⚠️ Ошибка (попытка {attempt+1}): {e}")
            if attempt == 2:
                raise Exception(f"Не удалось загрузить информацию о книге: {e}")
            time.sleep(5)

    if not success:
        # Если после трёх попыток не удалось, но есть кэш – используем его
        if metadata:
            if callbacks:
                callbacks.on_log(f"⚠️ Использую кэшированные метаданные после ошибок")
            title = metadata["title"]
            author = metadata["author"]
            cover_url = metadata["cover_url"]
            synopsis = metadata.get("synopsis")
            chapters = metadata["chapters"]
            return title, author, cover_url, synopsis, chapters
        raise Exception("Не удалось загрузить информацию о книге и нет кэша")

    title = crawler.novel_title or "Без названия"
    author = crawler.novel_author or "Неизвестен"
    cover_url = crawler.novel_cover
    synopsis = crawler.novel_synopsis
    chapters = crawler.chapters
    save_metadata(data_dir, title, author, cover_url, synopsis, chapters)

    if callbacks:
        callbacks.on_log(f"✅ Метаданные сохранены: {title}")
    return title, author, cover_url, synopsis, chapters
