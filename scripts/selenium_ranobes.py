# scripts/selenium_ranobes.py

import logging
import pickle
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

from .ranobes import RanobesCrawler
from scripts.paths import RANOBES_SELENIUM_COOKIES_FILE

logger = logging.getLogger(__name__)


class SeleniumRanobesCrawler(RanobesCrawler):
    """
    Краулер на основе Selenium для ranobes.com.
    Используется как запасной вариант при ошибках 403/Cloudflare
    (по аналогии с SeleniumRulateCrawler).
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
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        logger.info("Selenium Chrome driver initialized (ranobes)")

        if RANOBES_SELENIUM_COOKIES_FILE.exists():
            try:
                with open(RANOBES_SELENIUM_COOKIES_FILE, "rb") as f:
                    cookies = pickle.load(f)
                    for cookie in cookies:
                        if "domain" in cookie and "ranobes.com" in cookie["domain"]:
                            self.driver.add_cookie(cookie)
                logger.info("Selenium ranobes cookies loaded from file")
            except Exception as e:
                logger.warning(f"Failed to load selenium ranobes cookies: {e}")

    def get_soup(self, url, force_refresh=False, strainer=None):
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
        return BeautifulSoup(html, "lxml")

    def login(self, email: str, password: str):
        self.driver.get("https://ranobes.com/")
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "login_name"))
            )
        except TimeoutException:
            logger.error("Login form not found (ranobes, selenium)")
            raise

        login_input = self.driver.find_element(By.NAME, "login_name")
        login_input.send_keys(email)
        pass_input = self.driver.find_element(By.NAME, "login_password")
        pass_input.send_keys(password)
        pass_input.submit()

        time.sleep(3)
        try:
            error_element = self.driver.find_element(By.CSS_SELECTOR, ".error, .alert-danger")
            if error_element and error_element.text.strip():
                raise Exception(f"Login failed: {error_element.text}")
        except NoSuchElementException:
            pass

        with open(RANOBES_SELENIUM_COOKIES_FILE, "wb") as f:
            pickle.dump(self.driver.get_cookies(), f)
        logger.info(f"Selenium ranobes cookies saved to {RANOBES_SELENIUM_COOKIES_FILE}")

    def download_chapter_body(self, chapter):
        soup = self.get_soup(chapter["url"])
        container = soup.select_one("div.text#arrticle")
        if not container:
            raise Exception("Chapter content not found (Selenium, ranobes)")
        for junk in container.select("script, style"):
            junk.decompose()
        for ad_block in container.select('[id^="yandex_rtb_"]'):
            ad_block.decompose()
        self.cleaner.clean_contents(container)
        return str(container)

    def download_image(self, url):
        import requests
        cookies = {c["name"]: c["value"] for c in self.driver.get_cookies()}
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
