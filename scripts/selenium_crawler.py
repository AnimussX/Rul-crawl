# -*- coding: utf-8 -*-
import os
import logging
import time
import pickle
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from bs4 import BeautifulSoup

from lncrawl.core.crawler import Crawler
from .rulate import RulateCrawler
from kivy_app.utils.paths import get_app_data_dir



logger = logging.getLogger(__name__)


COOKIES_FILE = Path(os.path.join(get_app_data_dir(), 'selenium_cookies.pkl'))

class SeleniumRulateCrawler(RulateCrawler):
    """
    Краулер на основе Selenium для обхода сложных защит.
    Используется как запасной вариант при ошибках 403.
    """
    def __init__(self, headless=True):
        super().__init__()
        self.headless = headless
        self.driver = None

    def initialize(self):
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self.driver = uc.Chrome(options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("Selenium Chrome driver initialized")

        if COOKIES_FILE.exists():
            try:
                with open(COOKIES_FILE, 'rb') as f:
                    cookies = pickle.load(f)
                    for cookie in cookies:
                        if 'domain' in cookie and cookie['domain'] in ['.tl.rulate.ru', 'tl.rulate.ru']:
                            self.driver.add_cookie(cookie)
                logger.info("Selenium cookies loaded from file")
            except Exception as e:
                logger.warning(f"Failed to load selenium cookies: {e}")

    def get_soup(self, url):
        logger.debug(f"Selenium visiting: {url}")
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            time.sleep(2)
        except TimeoutException:
            logger.warning(f"Selenium timeout on {url}")
        html = self.driver.page_source
        return BeautifulSoup(html, 'lxml')

    def login(self, email: str, password: str):
        login_url = "https://tl.rulate.ru/"
        self.driver.get(login_url)

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "login[login]"))
            )
            csrf_input = self.driver.find_elements(By.NAME, "_csrf")
            csrf_token = csrf_input[0].get_attribute('value') if csrf_input else None
        except TimeoutException:
            logger.error("Login page elements not found")
            raise

        login_input = self.driver.find_element(By.NAME, "login[login]")
        login_input.send_keys(email)
        pass_input = self.driver.find_element(By.NAME, "login[pass]")
        pass_input.send_keys(password)
        pass_input.submit()

        time.sleep(3)
        try:
            error_element = self.driver.find_element(By.CSS_SELECTOR, ".alert.alert-danger")
            if error_element and "Неверный" in error_element.text:
                raise Exception("Invalid login or password")
        except NoSuchElementException:
            pass

        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/user/']"))
            )
            logger.info("Selenium login successful")
        except TimeoutException:
            current_url = self.driver.current_url
            if "login" in current_url or "auth" in current_url:
                raise Exception("Login failed: still on login page")
            else:
                logger.warning("Selenium login might be successful but no profile link found")

        with open(COOKIES_FILE, 'wb') as f:
            pickle.dump(self.driver.get_cookies(), f)
        logger.info(f"Selenium cookies saved to {COOKIES_FILE}")

    def download_chapter_body(self, chapter):
        soup = self.get_soup(chapter['url'])
        contents = soup.select_one(".content-text")
        if not contents:
            raise Exception("Chapter content not found (Selenium)")
        self.cleaner.clean_contents(contents)
        return str(contents)

    def download_image(self, url):
        import requests
        cookies = {c['name']: c['value'] for c in self.driver.get_cookies()}
        response = requests.get(url, cookies=cookies, timeout=15)
        response.raise_for_status()
        from PIL import Image
        import io
        return Image.open(io.BytesIO(response.content))

    def quit(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __del__(self):
        self.quit()