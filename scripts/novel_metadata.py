# scripts/novel_metadata.py

import time
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any

from scripts.metadata import save_metadata, load_metadata


def get_novel_metadata(
    url: str,
    crawler,
    data_dir: Path,
    force: bool = False,
    callbacks=None,
) -> Tuple[str, str, str, Optional[str], List[Dict[str, Any]]]:
    """
    Возвращает (title, author, cover_url, synopsis, chapters).
    Если force=False и есть кэш – загружает из кэша.
    Если force=True – всегда загружает с сайта и перезаписывает кэш.
    """
    if not force:
        metadata = load_metadata(data_dir)
        if metadata:
            title = metadata["title"]
            author = metadata["author"]
            cover_url = metadata["cover_url"]
            synopsis = metadata.get("synopsis")
            chapters = metadata["chapters"]
            if callbacks:
                callbacks.on_log(f"✅ Метаданные загружены из кэша: {title}")
            return title, author, cover_url, synopsis, chapters

    if callbacks:
        callbacks.on_log(f"🌐 Загрузка метаданных с сайта (принудительно)...")
    crawler.novel_url = url
    for attempt in range(3):
        try:
            crawler.read_novel_info()
            break
        except Exception as e:
            if callbacks:
                callbacks.on_log(f"⚠️ Ошибка (попытка {attempt+1}): {e}")
            if attempt == 2:
                raise Exception(f"Не удалось загрузить информацию о книге: {e}")
            time.sleep(5)

    title = crawler.novel_title or "Без названия"
    author = crawler.novel_author or "Неизвестен"
    cover_url = crawler.novel_cover
    synopsis = crawler.novel_synopsis
    chapters = crawler.chapters
    save_metadata(data_dir, title, author, cover_url, synopsis, chapters)

    if callbacks:
        callbacks.on_log(f"✅ Метаданные сохранены: {title}")
    return title, author, cover_url, synopsis, chapters

def update_metadata_from_site(url, crawler, data_dir, callbacks=None):
    """Принудительно обновляет метаданные с сайта и сохраняет в кэш."""
    from scripts.metadata import save_metadata
    import time

    crawler.novel_url = url
    for attempt in range(3):
        try:
            crawler.read_novel_info()
            break
        except Exception as e:
            if callbacks:
                callbacks.on_log(f"⚠️ Ошибка обновления (попытка {attempt+1}): {e}")
            if attempt == 2:
                raise
            time.sleep(5)
    title = crawler.novel_title or "Без названия"
    author = crawler.novel_author or "Неизвестен"
    cover_url = crawler.novel_cover
    synopsis = crawler.novel_synopsis
    chapters = crawler.chapters
    save_metadata(data_dir, title, author, cover_url, synopsis, chapters)
    return title, author, cover_url, synopsis, chapters