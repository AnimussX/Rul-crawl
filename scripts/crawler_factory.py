# scripts/crawler_factory.py

import cloudscraper
from pathlib import Path
from scripts.rulate import RulateCrawler
from scripts.proxy import load_proxies, start_proxy_fetcher, get_a_proxy, remove_faulty_proxies

def create_crawler(login=None, password=None, proxy_file=None, debug=False, timeout=30):
    """Создаёт нового краулера с авторизацией."""
    crawler = RulateCrawler()
    crawler.initialize()
    scraper = cloudscraper.create_scraper(
        interpreter='nodejs',
        delay=15,
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update(crawler.session.headers)
    scraper.timeout = timeout
    crawler.session = scraper

    if login and password:
        try:
            crawler.login(login, password)
            if debug:
                print("✅ Авторизация выполнена")
        except Exception as e:
            print(f"⚠️ Ошибка авторизации: {e}")

    if proxy_file and Path(proxy_file).exists():
        load_proxies(proxy_file)
        start_proxy_fetcher()
        original_request = scraper.request
        def request_with_proxy(method, url, **kwargs):
            if 'timeout' not in kwargs:
                kwargs['timeout'] = timeout
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
        print(f"🔁 Ротация прокси включена. Файл: {proxy_file}")

    return crawler

def clone_crawler(original_crawler, debug=False):
    """Создаёт нового краулера с теми же cookies и заголовками, что и оригинальный."""
    crawler = RulateCrawler()
    crawler.initialize()
    # Создаём новый cloudscraper с такими же настройками
    scraper = cloudscraper.create_scraper(
        interpreter='nodejs',
        delay=15,
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    # Копируем заголовки из оригинальной сессии
    scraper.headers.update(original_crawler.session.headers)
    # Копируем cookies (если есть)
    if original_crawler.session.cookies:
        scraper.cookies.update(original_crawler.session.cookies)
    scraper.timeout = original_crawler.session.timeout
    crawler.session = scraper
    # Можно также скопировать настройки прокси, но они будут применяться при запросах
    return crawler