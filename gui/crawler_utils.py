# gui/crawler_utils.py
import os
import time
from typing import Optional, List, Tuple

from scripts.crawler_factory import create_crawler   # единый источник
from scripts.proxy import load_proxies, start_proxy_fetcher, get_a_proxy, remove_faulty_proxies
import logging

logger = logging.getLogger(__name__)


def get_novel_info(
    url: str,
    login: Optional[str],
    password: Optional[str],
    proxy_file: Optional[str] = None,
    debug: bool = False,
    max_attempts: int = 1,
) -> Tuple[Optional[str], Optional[str], Optional[List[dict]]]:
    for attempt in range(1, max_attempts + 1):
        try:
            # Используем единую фабрику; тип краулера определяется по домену url
            crawler = create_crawler(url=url, login=login, password=password,
                                     proxy_file=proxy_file, debug=debug)
            crawler.novel_url = url
            crawler.read_novel_info()
            title = crawler.novel_title.strip()
            synopsis = crawler.novel_synopsis
            chapters = crawler.chapters
            return title, synopsis, chapters
        except Exception as e:
            if debug:
                print(f"Попытка {attempt}/{max_attempts} не удалась: {e}")
            if attempt < max_attempts:
                time.sleep(2 ** attempt)
            else:
                raise e
        finally:
            if crawler is not None:
                crawler.close()
