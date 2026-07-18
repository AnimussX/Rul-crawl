# scripts/crawler_factory.py

from pathlib import Path
from urllib.parse import urlparse

import cloudscraper

from scripts.rulate import RulateCrawler
from scripts.ranobes import RanobesCrawler
from scripts.auth import load_ranobes_auth
from scripts.proxy import load_proxies, start_proxy_fetcher, get_a_proxy, remove_faulty_proxies

CRAWLER_REGISTRY = {
    "tl.rulate.ru": RulateCrawler,
    "ranobes.com": RanobesCrawler,
}

SOURCE_NAMES = {
    RulateCrawler: "rulate",
    RanobesCrawler: "ranobes",
}


def get_crawler_class(url: str):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, cls in CRAWLER_REGISTRY.items():
        if domain in host:
            return cls
    raise ValueError(f"Неизвестный источник: {host or url}")


def detect_source_name(url: str) -> str:
    cls = get_crawler_class(url)
    return SOURCE_NAMES.get(cls, cls.__name__.lower())


def create_crawler(url, login=None, password=None, proxy_file=None, debug=False, timeout=60):
    crawler_cls = get_crawler_class(url)
    crawler = crawler_cls()
    crawler.initialize()
    scraper = cloudscraper.create_scraper(
        interpreter='nodejs',
        delay=15,
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update(crawler.session.headers)
    scraper.timeout = timeout
    crawler.session = scraper

    # Подбираем правильные учётные данные (код остаётся для будущего использования)
    if crawler_cls is RanobesCrawler:
        ran_login, ran_pass = load_ranobes_auth()
        effective_login = ran_login or login
        effective_password = ran_pass or password
    else:
        effective_login = login
        effective_password = password

    # Авторизация ВРЕМЕННО ОТКЛЮЧЕНА для RanobesCrawler (Cloudflare мешает)
    if effective_login and effective_password and crawler_cls is not RanobesCrawler:
        try:
            crawler.login(effective_login, effective_password)
            if debug:
                print(f"✅ Авторизация выполнена ({crawler_cls.__name__})")
        except Exception as e:
            print(f"⚠️ Ошибка авторизации ({crawler_cls.__name__}): {e}")

    if proxy_file and Path(proxy_file).exists():
        load_proxies(proxy_file)
        start_proxy_fetcher()
        original_request = scraper.request
        def request_with_proxy(method, req_url, **kwargs):
            if 'timeout' not in kwargs:
                kwargs['timeout'] = timeout
            proxy_url = get_a_proxy('https')
            if proxy_url:
                kwargs['proxies'] = {'http': proxy_url, 'https': proxy_url}
            try:
                response = original_request(method, req_url, **kwargs)
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
    crawler_cls = type(original_crawler)
    crawler = crawler_cls()
    crawler.initialize()
    scraper = cloudscraper.create_scraper(
        interpreter='nodejs',
        delay=15,
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update(original_crawler.session.headers)
    if original_crawler.session.cookies:
        scraper.cookies.update(original_crawler.session.cookies)
    scraper.timeout = original_crawler.session.timeout

    if hasattr(original_crawler.session, 'request'):
        original_request = original_crawler.session.request
        if original_request is not scraper.request:
            scraper.request = original_request

    crawler.session = scraper
    # Авторизацию при клонировании не повторяем, куки уже скопированы
    return crawler