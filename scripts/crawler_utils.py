# gui/crawler_utils.py

import os
import time
import types
import cloudscraper
import logging
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup

from scripts.rulate import RulateCrawler
from scripts.proxy import load_proxies, get_a_proxy, start_proxy_fetcher, stop_proxy_fetcher, remove_faulty_proxies

logger = logging.getLogger(__name__)


def create_crawler(
    login: Optional[str] = None,
    password: Optional[str] = None,
    proxy_file: Optional[str] = None,
    debug: bool = False,
    use_nodejs: bool = True,
    timeout: int = 30,
):
    """
    Создаёт RulateCrawler с усиленной защитой (cloudscraper) и увеличенным таймаутом.
    """
    crawler = RulateCrawler()
    crawler.initialize()

    # Создаём cloudscraper (пробуем nodejs, иначе native)
    interpreter = 'nodejs' if use_nodejs else 'native'
    try:
        scraper = cloudscraper.create_scraper(
            interpreter=interpreter,
            delay=15,
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
            }
        )
    except Exception:
        if debug:
            print(f"⚠️ Не удалось создать cloudscraper с interpreter={interpreter}, пробуем native")
        scraper = cloudscraper.create_scraper(
            interpreter='native',
            delay=15,
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
            }
        )
    scraper.headers.update(crawler.session.headers)
    crawler.session = scraper

    # Авторизация
    if login and password:
        try:
            crawler.login(login, password)
            if debug:
                print("✅ Авторизация выполнена успешно")
        except Exception as e:
            if debug:
                print(f"⚠️ Ошибка авторизации: {e}")

    # Подключение ротации прокси (если указан файл)
    if proxy_file and os.path.exists(proxy_file):
        load_proxies(proxy_file)
        start_proxy_fetcher()
        original_request = scraper.request

        def request_with_proxy(method, url, **kwargs):
            proxy_url = get_a_proxy('https')
            if proxy_url:
                kwargs['proxies'] = {'http': proxy_url, 'https': proxy_url}
            try:
                response = original_request(method, url, **kwargs)
                if response.status_code == 403:
                    remove_faulty_proxies(proxy_url)
                return response
            except Exception:
                remove_faulty_proxies(proxy_url)
                raise

        scraper.request = request_with_proxy
        if debug:
            print(f"🔁 Ротация прокси включена. Файл: {proxy_file}")

    # Переопределяем get_soup с увеличенным таймаутом (по умолчанию 30 секунд)
    def patched_get_soup(self, url, timeout=timeout):
        logger.debug(f"Visiting: {url}")
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')

    crawler.get_soup = types.MethodType(patched_get_soup, crawler)
    return crawler


def get_novel_info(
    url: str,
    login: Optional[str],
    password: Optional[str],
    proxy_file: Optional[str] = None,
    debug: bool = False,
    max_attempts: int = 3,
) -> Tuple[Optional[str], Optional[str], Optional[List[dict]]]:
    """
    Получает информацию о новелле с повторными попытками.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            crawler = create_crawler(login, password, proxy_file, debug)
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
                raise e  # Пробрасываем исключение после всех попыток