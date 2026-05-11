import json
import random
from pathlib import Path

ASSETS_DIR = Path(__file__).parent
BROWSERS_JSON = ASSETS_DIR / "browsers.json"

FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

def load_user_agents():
    if not BROWSERS_JSON.exists():
        print(f"⚠️ Файл {BROWSERS_JSON} не найден. Используется резервный список.")
        return FALLBACK_USER_AGENTS

    try:
        with open(BROWSERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        ua_list = []
        user_agents_section = data.get("user_agents", {})
        for platform, platform_data in user_agents_section.items():
            for device_type, device_data in platform_data.items():
                for browser, browser_list in device_data.items():
                    if isinstance(browser_list, list):
                        ua_list.extend(browser_list)

        if not ua_list:
            print("⚠️ В browsers.json не найдено ни одного User-Agent. Используется резервный список.")
            return FALLBACK_USER_AGENTS

        print(f"✅ Загружено {len(ua_list)} User-Agent'ов из browsers.json")
        return ua_list

    except Exception as e:
        print(f"⚠️ Ошибка загрузки User-Agent'ов: {e}. Используется резервный список.")
        return FALLBACK_USER_AGENTS

user_agents = load_user_agents()