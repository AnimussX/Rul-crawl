# scripts/selenium_termux_config.py

import os
import shutil
import logging

logger = logging.getLogger(__name__)

_TERMUX_PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")

# Порядок важен: сначала официальная команда пакета chromium в Termux,
# затем «сырой» бинарник напрямую из lib/chromium как запасной вариант.
_CHROMIUM_CANDIDATES = [
    ("bin", "chromium-browser"),
    ("bin", "chromium"),
    ("bin", "google-chrome"),
    ("lib/chromium", "chrome"),
]

_CHROMEDRIVER_CANDIDATES = [
    ("bin", "chromedriver"),
    ("bin", "chromium-driver"),
    ("lib/chromium", "chromedriver"),
]


def _find_binary(candidates):
    for subdir, name in candidates:
        direct = os.path.join(_TERMUX_PREFIX, subdir, name)
        if os.path.isfile(direct) and os.access(direct, os.X_OK):
            return direct
    for _, name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


def resolve_chromium_paths(settings: dict | None = None) -> tuple[str, str]:
    """
    Определяет пути к Chromium и chromedriver.

    Приоритет:
    1) явные пути из settings (chromium_binary_path / chromedriver_path),
       заданные пользователем в настройках приложения;
    2) переменные окружения CHROMIUM_BINARY_PATH / CHROMEDRIVER_PATH;
    3) автопоиск в $PREFIX/bin, $PREFIX/lib/chromium и через PATH.
    """
    settings = settings or {}

    chromium_path = (
        settings.get("chromium_binary_path")
        or os.environ.get("CHROMIUM_BINARY_PATH")
        or _find_binary(_CHROMIUM_CANDIDATES)
    )
    chromedriver_path = (
        settings.get("chromedriver_path")
        or os.environ.get("CHROMEDRIVER_PATH")
        or _find_binary(_CHROMEDRIVER_CANDIDATES)
    )

    missing = []
    if not chromium_path:
        missing.append(
            "Chromium не найден (искали chromium-browser / chromium / chrome). "
            "Установите: pkg install chromium"
        )
    if not chromedriver_path:
        missing.append("Chromedriver не найден. Обычно ставится вместе с chromium.")
    if missing:
        raise RuntimeError(
            "Не удалось настроить SeleniumBase для ranobes.com:\n" + "\n".join(missing) +
            "\nЕсли бинарники установлены, но лежат в нестандартном месте, "
            "укажите путь вручную в настройках приложения (вкладка «Пути»)."
        )

    logger.info(f"Chromium: {chromium_path}")
    logger.info(f"Chromedriver: {chromedriver_path}")
    return chromium_path, chromedriver_path


def ensure_chromedriver_on_path(chromedriver_path: str) -> None:
    """Гарантирует, что каталог с chromedriver есть в PATH процесса —
    иначе Selenium может попытаться скачать драйвер через Selenium Manager,
    который не поддерживает linux/aarch64 (Termux)."""
    driver_dir = os.path.dirname(chromedriver_path)
    current_path = os.environ.get("PATH", "")
    path_entries = current_path.split(os.pathsep) if current_path else []
    if driver_dir not in path_entries:
        os.environ["PATH"] = driver_dir + os.pathsep + current_path
        logger.info(f"Добавлен в PATH каталог с chromedriver: {driver_dir}")


def ensure_seleniumbase_local_driver(chromedriver_path: str) -> None:
    """
    SeleniumBase хранит свою копию chromedriver в seleniumbase/drivers/.
    Если она невалидна для текущей архитектуры (например, случайно оказался
    x86_64-бинарник на aarch64 Termux), запуск падает, а попытка чинить
    через Selenium Manager тоже не работает на этой архитектуре.
    Подменяем локальный файл симлинком на рабочий Termux-chromedriver.
    """
    import seleniumbase
    sb_drivers_dir = os.path.join(os.path.dirname(seleniumbase.__file__), "drivers")
    local_driver = os.path.join(sb_drivers_dir, "chromedriver")

    if os.path.islink(local_driver) and os.readlink(local_driver) == chromedriver_path:
        return

    try:
        if os.path.exists(local_driver) or os.path.islink(local_driver):
            os.remove(local_driver)
        os.symlink(chromedriver_path, local_driver)
        os.chmod(chromedriver_path, 0o755)
        logger.info(f"seleniumbase/drivers/chromedriver → симлинк на {chromedriver_path}")
    except OSError as e:
        logger.warning(
            f"Не удалось создать симлинк в {sb_drivers_dir}: {e}. "
            f"Если ranobes.com не заработает, выполните вручную:\n"
            f"  rm -f {local_driver}\n"
            f"  ln -s {chromedriver_path} {local_driver}"
        )


def check_version_compatibility(chromium_path: str, chromedriver_path: str) -> str | None:
    """Возвращает предупреждение, если версии Chromium и chromedriver разошлись."""
    import subprocess
    import re

    def get_major_version(binary: str) -> str | None:
        try:
            out = subprocess.run(
                [binary, "--version"], capture_output=True, text=True, timeout=15
            ).stdout
            m = re.search(r"(\d+)\.", out)
            return m.group(1) if m else None
        except Exception:
            return None

    chromium_major = get_major_version(chromium_path)
    driver_major = get_major_version(chromedriver_path)

    if chromium_major and driver_major and chromium_major != driver_major:
        return (
            f"⚠️ Версии не совпадают: Chromium {chromium_major}.x, "
            f"chromedriver {driver_major}.x. Переустановите: pkg reinstall chromium"
        )
    return None